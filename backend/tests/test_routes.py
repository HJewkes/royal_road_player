"""Route checks that don't need a running backend or heavy models."""
import asyncio
import inspect
from types import SimpleNamespace

import pytest
from fastapi.params import Path as PathParam
from fastapi.routing import APIRoute


@pytest.fixture(scope="module")
def routes():
    from src.api.routes import app

    return [r for r in app.routes if isinstance(r, APIRoute)]


def _path_params_declared(route: APIRoute) -> set[str]:
    sig = inspect.signature(route.endpoint)
    return {
        name
        for name, p in sig.parameters.items()
        if isinstance(p.default, PathParam)
        or any(isinstance(m, PathParam) for m in getattr(p.annotation, "__metadata__", ()))
    }


def test_every_declared_path_param_appears_in_its_route_path(routes):
    # A Path param missing from the URL template is unsatisfiable: every call 422s.
    offenders = [
        f"{route.path} missing {{{name}}}"
        for route in routes
        for name in _path_params_declared(route)
        if f"{{{name}}}" not in route.path
    ]
    assert offenders == []


def test_scraper_preview_takes_fiction_id_in_the_path(routes):
    paths = {r.path for r in routes}
    assert "/api/scraper/preview/{fiction_id}" in paths


class _Chapters:
    def __init__(self, texts: dict[int, str]):
        self.texts = texts

    def list_chapters(self, fiction_id, book_number):
        return [SimpleNamespace(chapter_number=n) for n in self.texts]

    def get_normalized_text(self, fiction_id, book_number, chapter_number):
        return self.texts[chapter_number]


class _Queue:
    def __init__(self):
        self.chapters = []

    def add_chapter(self, fiction_id, book_number, chapter_number, chunks):
        self.chapters.append(chapter_number)
        return len(chunks)


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Route module wired to a tmp books dir, with a settable engine."""
    from src.api import routes
    from src.config import Settings
    from src.discovery import ChunkDiscovery

    state = SimpleNamespace(engine="xtts", texts={}, queue=_Queue(), routes=routes)
    monkeypatch.setattr(
        routes, "get_settings", lambda: Settings(_env_file=None, tts_engine=state.engine)
    )
    monkeypatch.setattr(routes, "get_chunk_discovery", lambda: ChunkDiscovery(books_dir=tmp_path))
    monkeypatch.setattr(routes, "get_chapter_discovery", lambda: _Chapters(state.texts))
    monkeypatch.setattr(routes, "get_job_queue", lambda: state.queue)
    return state


def _chunk(api, chapters=None):
    request = api.routes.ChunkRequest(fiction_id="1", book_number=1, chapter_numbers=chapters)
    return asyncio.run(api.routes.chunk_chapters(request))


def _generate(api):
    request = api.routes.GenerateRequest(fiction_id="1", book_number=1)
    return asyncio.run(api.routes.queue_generation(request))


def test_chunk_route_uses_engine_chunker(api):
    paragraph = " ".join(["The keeper walked the long road home at dusk."] * 7)
    assert 250 < len(paragraph) < 450
    api.texts = {1: paragraph}
    api.engine = "chatterbox"

    result = _chunk(api)

    assert result.data["count"] == 1


def test_chunk_route_stamps_chapter_with_active_engine(api):
    api.texts = {1: "A short line of synthetic text."}
    api.engine = "chatterbox"

    _chunk(api)

    stamp = api.routes.get_chunk_discovery().read_engine_stamp("1", 1, 1)
    assert stamp == {"engine": "chatterbox", "chunking": "chatterbox-450", "profile": "p4"}


def test_generate_skips_mismatched_chapter(api):
    api.texts = {1: "The first synthetic chapter.", 2: "The second synthetic chapter."}
    _chunk(api, chapters=[1])
    api.engine = "chatterbox"
    _chunk(api, chapters=[2])

    result = _generate(api)

    assert api.queue.chapters == [2]
    assert result.data["skipped_engine_mismatch"] == [1]
    assert "Re-chunk" in result.message


def test_generate_queues_legacy_chapters_under_xtts(api):
    api.texts = {1: "An unstamped synthetic chapter."}
    api.routes.get_chunk_discovery().save_chunks("1", 1, 1, [(1, api.texts[1])])

    result = _generate(api)

    assert api.queue.chapters == [1]
    assert result.data["skipped_engine_mismatch"] == []
