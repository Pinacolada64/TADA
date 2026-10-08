"""tests/server/test_run_until_stopped.py

simple_server.run_until_stopped() -- the SIGINT/SIGTERM -> graceful_shutdown()
runner shared by simple_server.py's __main__ and run_server.py (the live
server's entry point, which used to skip graceful_shutdown() entirely).
"""
import asyncio
import os
import signal

import pytest

from simple_server import run_until_stopped


class _FakeServer:
    def __init__(self, finish_on_its_own=False):
        self.finish_on_its_own = finish_on_its_own
        self.graceful_called = False
        self.start_cancelled = False

    async def start(self):
        if self.finish_on_its_own:
            return
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.start_cancelled = True
            raise

    async def graceful_shutdown(self):
        self.graceful_called = True


@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
def test_signal_runs_graceful_shutdown_then_stops(sig):
    server = _FakeServer()

    async def scenario():
        asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), sig)
        await asyncio.wait_for(run_until_stopped(server), timeout=5)

    asyncio.run(scenario())
    assert server.graceful_called
    assert server.start_cancelled


def test_start_returning_on_its_own_skips_graceful_shutdown():
    server = _FakeServer(finish_on_its_own=True)
    asyncio.run(asyncio.wait_for(run_until_stopped(server), timeout=5))
    assert not server.graceful_called


def test_signal_handlers_removed_afterward():
    """A Ctrl-C after the runner returns must behave normally again
    (KeyboardInterrupt), not poke a dead loop's stop_event."""
    asyncio.run(run_until_stopped(_FakeServer(finish_on_its_own=True)))
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_test_time_exits_without_graceful_shutdown():
    server = _FakeServer()
    asyncio.run(asyncio.wait_for(run_until_stopped(server, test_time=0.05), timeout=5))
    assert server.start_cancelled
    assert not server.graceful_called
