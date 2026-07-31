"""tests/social/test_follow_command.py

Unit tests for commands/follow.py: FOLLOW (alias FL), a shortcut for
toggling PlayerFlags.GUILD_FOLLOW_MODE, gated on real guild membership
(SPUR.MISC5.S's `follow` label: `if vv<3 print "For guild members
only"`). Mirrors tests/social/test_prompt_mode_command.py's structure.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Guild
from commands.follow import FollowCommand


def make_ctx(*, guild=Guild.CLAW, toggled_state=True):
    player = MagicMock()
    player.guild = guild
    player.toggle_flag = MagicMock(return_value=(toggled_state, None))
    player.unsaved_changes = False

    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


class TestFollowCommand(unittest.IsolatedAsyncioTestCase):

    async def test_toggle_on_reports_on(self):
        cmd = FollowCommand()
        ctx = make_ctx(toggled_state=True)
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        ctx.send.assert_awaited_once_with('Guild Follow: On')

    async def test_toggle_off_reports_off(self):
        cmd = FollowCommand()
        ctx = make_ctx(toggled_state=False)
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        ctx.send.assert_awaited_once_with('Guild Follow: Off')

    async def test_marks_unsaved_changes(self):
        cmd = FollowCommand()
        ctx = make_ctx()
        await cmd.execute(ctx)
        self.assertTrue(ctx.player.unsaved_changes)

    async def test_calls_toggle_flag_on_player(self):
        cmd = FollowCommand()
        ctx = make_ctx()
        await cmd.execute(ctx)
        ctx.player.toggle_flag.assert_called_once()

    async def test_civilian_is_rejected(self):
        cmd = FollowCommand()
        ctx = make_ctx(guild=Guild.CIVILIAN)
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        ctx.send.assert_awaited_once_with('For guild members only.')
        ctx.player.toggle_flag.assert_not_called()

    async def test_outlaw_is_rejected(self):
        cmd = FollowCommand()
        ctx = make_ctx(guild=Guild.OUTLAW)
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        ctx.player.toggle_flag.assert_not_called()

    async def test_fist_and_sword_guild_members_can_toggle(self):
        for guild in (Guild.FIST, Guild.SWORD):
            cmd = FollowCommand()
            ctx = make_ctx(guild=guild)
            res = await cmd.execute(ctx)
            self.assertTrue(res.success)
            ctx.player.toggle_flag.assert_called_once()


if __name__ == '__main__':
    unittest.main()
