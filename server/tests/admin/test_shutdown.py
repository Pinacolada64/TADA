"""tests/admin/test_shutdown.py — Unit tests for commands/shutdown.py.

os.kill() is always mocked -- letting the real one fire would send a
real SIGTERM to the pytest process itself.

Uses IsolatedAsyncioTestCase (one persistent event loop per test) rather
than separate asyncio.run() calls per interaction -- a background task
created by one asyncio.run() call is orphaned/force-cancelled the moment
that call returns (asyncio.run()'s own cleanup cancels anything still
pending), so a scheduled shutdown's countdown task has to be created and
awaited/inspected within the same running loop as everything else in a
given test.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from commands.shutdown import ShutdownCommand
from flags import PlayerFlags


def make_ctx(*, is_admin=True, clients=None):
    player = MagicMock()
    player.name = 'Admin'
    player.query_flag = MagicMock(side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin)

    server = MagicMock()
    server.clients = clients if clients is not None else {}
    # A fresh MagicMock's getattr(server, '_shutdown_task', None) would
    # return a truthy child Mock instead of the real "nothing scheduled"
    # default -- delattr so getattr(..., None) falls through correctly.
    del server._shutdown_task
    del server._shutdown_at

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.send = AsyncMock()
    return ctx


def _connected_client():
    client_ctx = MagicMock()
    client_ctx.send = AsyncMock()
    return SimpleNamespace(ctx=client_ctx), client_ctx


class TestPermission(unittest.IsolatedAsyncioTestCase):

    async def test_non_admin_refused(self):
        ctx = make_ctx(is_admin=False)
        result = await ShutdownCommand().execute(ctx, '#time', 'now')
        self.assertFalse(result.success)
        self.assertIn('lack the authority', str(ctx.send.call_args).lower())


class TestScheduling(unittest.IsolatedAsyncioTestCase):

    async def test_missing_time_value(self):
        ctx = make_ctx()
        result = await ShutdownCommand().execute(ctx, '#time')
        self.assertFalse(result.success)

    async def test_invalid_time_value(self):
        ctx = make_ctx()
        result = await ShutdownCommand().execute(ctx, '#time', 'banana')
        self.assertFalse(result.success)

    async def test_negative_time_rejected(self):
        ctx = make_ctx()
        result = await ShutdownCommand().execute(ctx, '#time', '-5')
        self.assertFalse(result.success)

    @patch('commands.shutdown.os.kill')
    async def test_schedule_sets_task_and_time(self, mock_kill):
        ctx = make_ctx()
        result = await ShutdownCommand().execute(ctx, '#time', '30')
        self.assertTrue(result.success)
        self.assertIsNotNone(ctx.server._shutdown_at)
        self.assertFalse(ctx.server._shutdown_task.done())
        ctx.server._shutdown_task.cancel()

    @patch('commands.shutdown.os.kill')
    async def test_cannot_double_schedule(self, mock_kill):
        ctx = make_ctx()
        await ShutdownCommand().execute(ctx, '#time', '30')
        result = await ShutdownCommand().execute(ctx, '#time', '10')
        self.assertFalse(result.success)
        ctx.server._shutdown_task.cancel()


class TestStatus(unittest.IsolatedAsyncioTestCase):

    async def test_no_shutdown_scheduled(self):
        ctx = make_ctx()
        await ShutdownCommand().execute(ctx)
        self.assertIn('No shutdown', str(ctx.send.call_args))

    @patch('commands.shutdown.os.kill')
    async def test_status_shows_scheduled_time(self, mock_kill):
        ctx = make_ctx()
        await ShutdownCommand().execute(ctx, '#time', '30')
        ctx.send.reset_mock()
        await ShutdownCommand().execute(ctx)
        sent = str(ctx.send.call_args)
        self.assertIn('Shutdown scheduled', sent)
        ctx.server._shutdown_task.cancel()


class TestCancel(unittest.IsolatedAsyncioTestCase):

    async def test_cancel_with_nothing_scheduled(self):
        ctx = make_ctx()
        result = await ShutdownCommand().execute(ctx, '#cancel')
        self.assertTrue(result.success)
        self.assertIn('No shutdown', str(ctx.send.call_args))

    @patch('commands.shutdown.os.kill')
    async def test_cancel_stops_pending_task(self, mock_kill):
        ctx = make_ctx()
        await ShutdownCommand().execute(ctx, '#time', '30')
        task = ctx.server._shutdown_task
        await ShutdownCommand().execute(ctx, '#cancel')
        self.assertIsNone(ctx.server._shutdown_task)
        self.assertIsNone(ctx.server._shutdown_at)
        # task.cancel() only *requests* cancellation -- give the loop a
        # turn to actually process it before checking task state.
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled() or task.done())

    @patch('commands.shutdown.os.kill')
    async def test_cancel_broadcasts_to_connected_clients(self, mock_kill):
        client, client_ctx = _connected_client()
        ctx = make_ctx(clients={('1.2.3.4', 1): client})
        await ShutdownCommand().execute(ctx, '#time', '30')
        client_ctx.send.reset_mock()
        await ShutdownCommand().execute(ctx, '#cancel')
        self.assertIn('cancelled', str(client_ctx.send.call_args).lower())


class TestImmediateShutdown(unittest.IsolatedAsyncioTestCase):

    @patch('commands.shutdown.os.kill')
    async def test_now_broadcasts_and_signals_immediately(self, mock_kill):
        client, client_ctx = _connected_client()
        ctx = make_ctx(clients={('1.2.3.4', 1): client})
        await ShutdownCommand().execute(ctx, '#time', 'now')
        # Let the scheduled countdown task actually run to completion.
        await ctx.server._shutdown_task
        self.assertIn('NOW', str(client_ctx.send.call_args))
        mock_kill.assert_called_once()

    @patch('commands.shutdown.os.kill')
    async def test_a_broadcast_failure_does_not_prevent_shutdown(self, mock_kill):
        client, client_ctx = _connected_client()
        client_ctx.send = AsyncMock(side_effect=RuntimeError('boom'))
        ctx = make_ctx(clients={('1.2.3.4', 1): client})
        await ShutdownCommand().execute(ctx, '#time', 'now')
        await ctx.server._shutdown_task
        mock_kill.assert_called_once()


class TestCountdownWarnings(unittest.IsolatedAsyncioTestCase):

    @patch('commands.shutdown.asyncio.sleep', new_callable=AsyncMock)
    @patch('commands.shutdown.os.kill')
    async def test_short_schedule_warns_and_signals(self, mock_kill, mock_sleep):
        """A 2-minute schedule should hit the 1-minute checkpoint then
        the final NOW broadcast, with asyncio.sleep mocked out so the
        test doesn't actually wait two minutes."""
        client, client_ctx = _connected_client()
        ctx = make_ctx(clients={('1.2.3.4', 1): client})
        await ShutdownCommand().execute(ctx, '#time', '2')
        await ctx.server._shutdown_task

        sent = [str(c) for c in client_ctx.send.call_args_list]
        joined = ' '.join(sent)
        self.assertIn('2 minutes', joined)
        self.assertIn('1 minute', joined)
        self.assertIn('NOW', joined)
        mock_kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
