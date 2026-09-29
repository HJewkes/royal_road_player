"""Tests for RenderPool recovering from a dead synthesis worker.

The process executor is replaced by a fake so no models load: a worker dying is
simulated by a future that raises BrokenProcessPool, as the real executor does.
"""

from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pytest

from src.tts.pool import RenderPool


class FakeExecutor:
    def __init__(self, broken=False):
        self.broken = broken
        self.shut_down = False

    def submit(self, fn, *args):
        future = Future()
        if self.broken:
            future.set_exception(BrokenProcessPool("worker died"))
        else:
            future.set_result((Path(args[1]), 1.0))
        return future

    def shutdown(self, wait=True, cancel_futures=False):
        self.shut_down = True


def _pool_with(executor):
    pool = RenderPool(workers=2, threads_per_worker=0, verify=False, retries=0)
    pool._executor = executor
    return pool


def test_render_returns_the_workers_result():
    pool = _pool_with(FakeExecutor())

    assert pool.render("hello", Path("001.wav")) == (Path("001.wav"), 1.0)


def test_dead_worker_fails_the_chunk_and_discards_the_broken_pool():
    broken = FakeExecutor(broken=True)
    pool = _pool_with(broken)

    with pytest.raises(BrokenProcessPool):
        pool.render("hello", Path("001.wav"))

    assert broken.shut_down
    assert pool._executor is None


def test_second_failure_on_a_stale_pool_keeps_the_replacement():
    broken, replacement = FakeExecutor(broken=True), FakeExecutor()
    pool = _pool_with(replacement)

    pool._discard(broken)

    assert pool._executor is replacement
    assert not replacement.shut_down
