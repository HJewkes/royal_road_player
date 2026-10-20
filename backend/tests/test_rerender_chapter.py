"""Tests for the pooled render path in scripts/rerender_chapter.py (fake pool, no models)."""
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from src.tts.engines import chunk_seed

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rerender_chapter.py"
_spec = importlib.util.spec_from_file_location("rerender_chapter", _SCRIPT)
rerender_chapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rerender_chapter)


@dataclass
class FakeChunk:
    index: int
    text: str


class FakePool:
    built: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.renders = []
        self.closed = False
        FakePool.built.append(self)

    def render(self, text, output_path, seed=None):
        self.renders.append((text, output_path.name, seed))
        return output_path, 0.0

    def shutdown(self):
        self.closed = True


def test_pooled_render_sends_every_chunk_with_its_seed_on_the_chosen_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(rerender_chapter, "RenderPool", FakePool)
    chunks = [FakeChunk(1, "first line"), FakeChunk(2, "second line")]

    rerender_chapter._synthesize_pooled(chunks, tmp_path, "chatterbox", 2, True, 0.0)

    pool = FakePool.built[-1]
    assert sorted(pool.renders) == [
        ("first line", "001.wav", chunk_seed(1)),
        ("second line", "002.wav", chunk_seed(2)),
    ]
    assert pool.kwargs["engine"] == "chatterbox"
    assert pool.kwargs["workers"] == 2
    assert pool.closed
