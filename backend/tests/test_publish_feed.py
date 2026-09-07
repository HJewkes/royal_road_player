"""Tests for the R2 uploader (scripts/publish_feed.py).

The interesting behaviour is the skip rule: publishing runs after every export,
so it must skip mp3s the bucket already holds byte-for-byte while still pushing
a chapter that was re-exported under the same object key. No boto3 and no
network — a fake client stands in for R2.
"""
import hashlib
import importlib.util
from pathlib import Path

from src.config import Settings

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "publish_feed.py"
_spec = importlib.util.spec_from_file_location("publish_feed", _SCRIPT)
publish_feed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish_feed)


class FakeR2:
    """Minimal stand-in for the boto3 S3 client, paginating like R2 does."""

    def __init__(self, objects: dict[str, bytes], page_size: int = 1000):
        self.stored = dict(objects)
        self.page_size = page_size
        self.puts: list[str] = []

    def _entry(self, key: str) -> dict:
        body = self.stored[key]
        return {
            "Key": key,
            "Size": len(body),
            "ETag": f'"{hashlib.md5(body).hexdigest()}"',
        }

    def list_objects_v2(self, **kw):
        keys = sorted(self.stored)
        start = int(kw.get("ContinuationToken", 0))
        page = keys[start:start + self.page_size]
        truncated = start + self.page_size < len(keys)
        return {
            "Contents": [self._entry(k) for k in page],
            "IsTruncated": truncated,
            "NextContinuationToken": str(start + self.page_size),
        }

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803 — boto3 casing
        self.stored[Key] = Body.read() if hasattr(Body, "read") else Body
        self.puts.append(Key)


def _mp3(tmp_path: Path, body: bytes) -> Path:
    path = tmp_path / "episode.mp3"
    path.write_bytes(body)
    return path


def _remote(body: bytes) -> tuple[int, str]:
    return len(body), hashlib.md5(body).hexdigest()


def test_unchanged_file_is_not_uploaded(tmp_path):
    body = b"same bytes"
    assert publish_feed._needs_upload(_mp3(tmp_path, body), _remote(body)) is False


def test_changed_bytes_are_uploaded(tmp_path):
    body = b"corrected audio"
    stale = b"stale audio!!!!"  # same length, so only the hash can tell them apart
    assert len(stale) == len(body)
    assert publish_feed._needs_upload(_mp3(tmp_path, body), _remote(stale)) is True


def test_missing_key_is_uploaded(tmp_path):
    assert publish_feed._needs_upload(_mp3(tmp_path, b"new"), None) is True


def test_different_size_is_uploaded(tmp_path):
    assert publish_feed._needs_upload(_mp3(tmp_path, b"longer body"), _remote(b"short")) is True


def test_multipart_etag_falls_back_to_size(tmp_path):
    body = b"a multipart upload"
    remote = (len(body), "d41d8cd98f00b204e9800998ecf8427e-3")
    assert publish_feed._needs_upload(_mp3(tmp_path, body), remote) is False


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        exports_dir=tmp_path / "exports",
        delivery_base_url="https://pub-test.r2.dev",
        delivery_path_prefix="",
        delivery_collection_series=[],
        delivery_collection_aliases=[],
        r2_bucket="bucket",
        r2_endpoint_url="https://r2.example",
        r2_access_key_id="id",
        r2_secret_access_key="secret",
    )


def _export(tmp_path: Path, body: bytes) -> str:
    folder = tmp_path / "exports" / "Test Series - Book 1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Test Series - Book 1 - Chapter 1.mp3").write_bytes(body)
    return "test-series/book-01/chapter-001.mp3"


def _publish(monkeypatch, tmp_path: Path, client: FakeR2) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(publish_feed, "get_settings", lambda: settings)
    monkeypatch.setattr(publish_feed, "_r2_client", lambda _s: client)
    assert publish_feed.main() == 0


def test_publish_replaces_a_re_exported_chapter(monkeypatch, tmp_path):
    key = _export(tmp_path, b"corrected audio")
    client = FakeR2({key: b"stale audio!!!!"})

    _publish(monkeypatch, tmp_path, client)

    assert key in client.puts
    assert client.stored[key] == b"corrected audio"


def test_publish_skips_an_unchanged_chapter(monkeypatch, tmp_path):
    body = b"unchanged audio"
    key = _export(tmp_path, body)
    client = FakeR2({key: body}, page_size=1)

    _publish(monkeypatch, tmp_path, client)

    assert client.puts == ["test-series/feed.xml"]
