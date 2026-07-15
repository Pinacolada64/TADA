"""tests/test_dbg_command.py

Unit tests for commands/dbg.py: a fast shortcut for toggling
PlayerFlags.DEBUG_MODE without going through EditPlayer's flags menu.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.dbg import DbgCommand


def make_ctx(*, toggled_state=True):
    player = MagicMock()
    player.toggle_flag = MagicMock(return_value=(toggled_state, None))
    player.unsaved_changes = False

    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


class TestDbgCommand(unittest.IsolatedAsyncioTestCase):

    async def test_toggle_on_reports_on(self):
        cmd = DbgCommand()
        ctx = make_ctx(toggled_state=True)
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        ctx.send.assert_awaited_once_with('Debug mode: On.')

    async def test_toggle_off_reports_off(self):
        cmd = DbgCommand()
        ctx = make_ctx(toggled_state=False)
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        ctx.send.assert_awaited_once_with('Debug mode: Off.')

    async def test_marks_unsaved_changes(self):
        cmd = DbgCommand()
        ctx = make_ctx()
        await cmd.execute(ctx)
        self.assertTrue(ctx.player.unsaved_changes)

    async def test_calls_toggle_flag_on_player(self):
        cmd = DbgCommand()
        ctx = make_ctx()
        await cmd.execute(ctx)
        ctx.player.toggle_flag.assert_called_once()


if __name__ == '__main__':
    unittest.main()
