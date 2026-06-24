"""Tests for the pipeline event store."""

import json
import threading
from pathlib import Path

import pytest

from src.events import EventStore


@pytest.fixture
def store(tmp_path) -> EventStore:
    """An event store backed by a fresh temp file."""
    return EventStore(path=tmp_path / "events.jsonl")


class TestEmitAndRead:
    def test_emit_assigns_monotonic_ids(self, store):
        first = store.emit("chapter.completed", fiction_id="1", book=7, chapter=1)
        second = store.emit("run.error", severity="error")
        assert first["id"] == 1
        assert second["id"] == 2

    def test_emitted_event_has_timestamp_and_fields(self, store):
        event = store.emit(
            "chapter.completed", fiction_id="124774", book=7, chapter=10,
            detail={"export_path": "/x.mp3"},
        )
        assert event["type"] == "chapter.completed"
        assert event["fiction_id"] == "124774"
        assert event["book"] == 7
        assert event["chapter"] == 10
        assert event["detail"] == {"export_path": "/x.mp3"}
        assert event["ts"].endswith("+00:00")

    def test_read_since_returns_only_newer_events(self, store):
        store.emit("a")
        store.emit("b")
        store.emit("c")
        newer = store.read(since=1)
        assert [e["type"] for e in newer] == ["b", "c"]

    def test_read_filters_by_type(self, store):
        store.emit("chapter.completed", chapter=1)
        store.emit("run.error", severity="error")
        store.emit("chapter.completed", chapter=2)
        errors = store.read(type="run.error")
        assert len(errors) == 1
        assert errors[0]["type"] == "run.error"

    def test_read_respects_limit(self, store):
        for _ in range(5):
            store.emit("a")
        assert len(store.read(limit=2)) == 2

    def test_read_empty_when_no_file(self, tmp_path):
        assert EventStore(path=tmp_path / "missing.jsonl").read() == []


class TestPersistence:
    def test_ids_stay_monotonic_across_restart(self, tmp_path):
        path = tmp_path / "events.jsonl"
        EventStore(path=path).emit("a")
        EventStore(path=path).emit("b")  # fresh instance recovers last id
        reopened = EventStore(path=path)
        third = reopened.emit("c")
        assert third["id"] == 3
        assert [e["id"] for e in reopened.read()] == [1, 2, 3]


class TestConcurrency:
    def test_concurrent_emits_are_unique_and_uncorrupted(self, store):
        def emit_many():
            for _ in range(50):
                store.emit("chapter.completed")

        threads = [threading.Thread(target=emit_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Every line must be valid JSON (no interleaved/corrupted writes)...
        lines = [l for l in store._path.read_text().splitlines() if l.strip()]
        ids = [json.loads(l)["id"] for l in lines]
        # ...and ids must be exactly 1..200 with no duplicates or gaps.
        assert sorted(ids) == list(range(1, 201))
