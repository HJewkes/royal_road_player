#!/usr/bin/env python3
"""Build the podcast feed(s) from exports and (when configured) push to R2.

Always writes each series' feed.xml to a local staging dir so it's inspectable
without any cloud setup. If AUDIOBOOK_DELIVERY_BASE_URL and the four R2_* settings
are present, it also uploads any new or changed chapter mp3s plus the freshly
built feeds to the R2 bucket — the always-on host the phone's podcast app pulls
from. Safe to run on every export: uploads are incremental (an mp3 whose bytes
already match the stored object is skipped) and feeds are small.

Usage:
  publish_feed.py            # build locally; upload if configured
  publish_feed.py --no-upload  # build locally only
  publish_feed.py --dry-run    # list what would upload against R2; upload nothing
"""
import hashlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.delivery.feed import (  # noqa: E402
    build_all_feeds,
    build_collection_feed,
    discover_episodes,
    feed_key_for,
    prefixed,
    slugify,
)


def _local_feed_dir(settings) -> Path:
    return settings.exports_dir.parent / "feeds"


def _build_feeds(settings, base_url: str, prefix: str) -> dict[str, str]:
    """Map every feed key to its XML.

    With a collection configured, its member series do not get standalone feeds
    — they ARE the collection. The collection feed is published at its own key
    and at each configured alias (an existing subscription URL), so the same XML
    can appear more than once by design.
    """
    members = settings.delivery_collection_series
    feeds = {
        slug: xml
        for slug, xml in build_all_feeds(
            settings.exports_dir, base_url, settings.delivery_author, prefix
        ).items()
        if slug not in members
    }

    if not members:
        return feeds

    collection_slug = slugify(settings.delivery_collection_title)
    xml = build_collection_feed(
        settings.exports_dir,
        settings.delivery_collection_title,
        members,
        base_url,
        settings.delivery_author,
        prefix,
        feed_slug=collection_slug,
    )
    if xml:
        for key in [collection_slug, *settings.delivery_collection_aliases]:
            feeds[key] = xml
    return feeds


def _upload_configured(settings) -> bool:
    return bool(
        settings.delivery_base_url
        and settings.r2_bucket
        and settings.r2_endpoint_url
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    )


def _r2_client(settings):
    import boto3  # lazy — only needed when uploading

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _remote_objects(client, bucket: str) -> dict[str, tuple[int, str]]:
    """Map every stored key to its (size, etag) so changed files can be spotted."""
    objects: dict[str, tuple[int, str]] = {}
    token = None
    while True:
        kw = {"Bucket": bucket}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for o in resp.get("Contents", []):
            objects[o["Key"]] = (o.get("Size", -1), str(o.get("ETag", "")).strip('"'))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return objects


def _file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _needs_upload(local_path: Path, remote: tuple[int, str] | None) -> bool:
    """True when the local mp3 differs from what the bucket already holds.

    A re-exported chapter keeps its object key, so key presence alone can't
    decide this — comparing content is what makes a corrected episode reach the
    phone. R2 sets the ETag of a single-part put to the body's MD5 hex, which is
    what we upload with; a multipart ETag carries a '-<parts>' suffix that is not
    an MD5 of the whole body, so there we fall back to comparing size only.
    """
    if remote is None:
        return True
    size, etag = remote
    if size != local_path.stat().st_size:
        return True
    if not etag or "-" in etag:
        return False
    return etag.lower() != _file_md5(local_path)


def find_key_collisions(episodes_by_slug: dict) -> dict[str, list[Path]]:
    """Object keys that more than one local file claims.

    Two exports of the same chapter under different book titles collide on one
    key. Because their bytes differ, whichever the walk reaches last wins and
    `_needs_upload` is true again on the next run, so the pair re-uploads forever.
    Seen live: a Book 5 chapter 1 left over from a malformed book title
    ("creating LitRPG and Progression Fantasy novels") shadowing the corrected
    export, re-uploading ~27 MB on every publish.
    """
    by_key: dict[str, list[Path]] = {}
    for episodes in episodes_by_slug.values():
        for ep in episodes:
            by_key.setdefault(ep.object_key, []).append(ep.path)
    return {k: v for k, v in by_key.items() if len(v) > 1}


def _warn_on_key_collisions(episodes_by_slug: dict) -> None:
    for key, paths in sorted(find_key_collisions(episodes_by_slug).items()):
        print(f"WARNING: {len(paths)} local files map to {key} — they will "
              f"re-upload on every run until one is removed:", file=sys.stderr)
        for p in sorted(paths):
            print(f"    {p.name}", file=sys.stderr)


def _pending_mp3s(all_episodes: dict, existing: dict, prefix: str) -> list[tuple[str, Path, bool]]:
    """(key, local path, replaces an existing object) for every mp3 that differs from R2."""
    pending = []
    for episodes in all_episodes.values():
        for ep in episodes:
            key = prefixed(ep.object_key, prefix)
            remote = existing.get(key)
            if _needs_upload(ep.path, remote):
                pending.append((key, ep.path, remote is not None))
    return pending


def _print_dry_run(pending: list, feed_keys: list[str]) -> None:
    for key, _path, replaces in pending:
        print(f"would {'replace' if replaces else 'upload'} mp3: {key}")
    for key in feed_keys:
        print(f"would upload feed: {key}")
    replaced = sum(1 for *_, replaces in pending if replaces)
    print(f"Dry run — {len(pending) - replaced} new mp3(s), {replaced} to replace, "
          f"{len(feed_keys)} feed(s); nothing uploaded.")


def _write_local_feeds(settings, feeds: dict[str, str], base_url: str, prefix: str) -> None:
    feed_dir = _local_feed_dir(settings)
    for slug, xml in feeds.items():
        out = feed_dir / slug / "feed.xml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml)
        print(f"feed: {out}  ->  {base_url}/{prefixed(feed_key_for(slug), prefix)}")


def _upload(client, bucket: str, pending: list, feeds: dict[str, str], prefix: str) -> None:
    for key, path, replaces in pending:
        with open(path, "rb") as fh:
            client.put_object(Bucket=bucket, Key=key, Body=fh, ContentType="audio/mpeg")
        print(f"{'re-uploaded' if replaces else 'uploaded'} mp3: {key}")

    for slug, xml in feeds.items():
        key = prefixed(feed_key_for(slug), prefix)
        client.put_object(
            Bucket=bucket, Key=key,
            Body=xml.encode("utf-8"), ContentType="application/rss+xml",
        )
        print(f"uploaded feed: {key}")

    replaced = sum(1 for *_, replaces in pending if replaces)
    print(f"Done — {len(pending) - replaced} new mp3(s), {replaced} re-uploaded, "
          f"{len(feeds)} feed(s).")


def _skip_reason(settings) -> str:
    reasons = []
    if "--no-upload" in sys.argv:
        reasons.append("--no-upload was given")
    if not _upload_configured(settings):
        reasons.append("delivery is not configured")
    return " and ".join(reasons)


def main() -> int:
    settings = get_settings()
    dry_run = "--dry-run" in sys.argv
    do_upload = "--no-upload" not in sys.argv and _upload_configured(settings)

    base_url = settings.delivery_base_url or "https://REPLACE-ME.example"
    prefix = settings.delivery_path_prefix
    feeds = _build_feeds(settings, base_url, prefix)

    # Always write feeds locally for inspection.
    _write_local_feeds(settings, feeds, base_url, prefix)

    if not feeds:
        print("No exported chapters found — nothing to publish.")
        return 0

    if not do_upload:
        if dry_run:
            print(f"Dry run — {_skip_reason(settings)}, so nothing was compared "
                  "against R2 and nothing was uploaded.")
        if not _upload_configured(settings):
            print("Delivery not configured (set AUDIOBOOK_DELIVERY_BASE_URL + R2_*); "
                  "built feeds locally only.")
        return 0

    try:
        client = _r2_client(settings)
        existing = _remote_objects(client, settings.r2_bucket)
    except Exception as exc:  # missing boto3, bad creds, network
        print(f"Upload skipped — R2 client/list failed: {exc}", file=sys.stderr)
        return 0

    all_episodes = discover_episodes(settings.exports_dir)
    _warn_on_key_collisions(all_episodes)
    pending = _pending_mp3s(all_episodes, existing, prefix)
    if dry_run:
        _print_dry_run(pending, [prefixed(feed_key_for(slug), prefix) for slug in feeds])
        return 0

    _upload(client, settings.r2_bucket, pending, feeds, prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
