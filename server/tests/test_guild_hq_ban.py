"""tests/test_guild_hq_ban.py — guild_hq/main.py's [K]ick/ban management
option (ported from SPUR.GUILD.S's `bann` subroutine, gated there to
guild officers via flag(19); this port has no separate officer rank yet
so it's gated to Admin/Dungeon Master instead) and the entry-time ban
gate in main().
"""
from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

import net_common
from base_classes import Guild
from flags import PlayerFlags
from guild_hq.main import _ban_management, _can_manage_bans, main


class _FakePlayer:
    def __init__(self, name, guild=Guild.CLAW, flags=()):
        self.name = name
        self.guild = guild
        self._flags = set(flags)
        self.unsaved_changes = False
        self.is_expert = True  # skip menu rendering noise
        self.drink = 20
        self.saved = False

    def query_flag(self, flag) -> bool:
        return flag in self._flags

    def save(self, force=False):
        self.saved = True


class _FakeCtx:
    def __init__(self, player, prompts=()):
        self.player = player
        self.sent: list = []
        self._prompts = list(prompts)

    async def send(self, *lines):
        self.sent.extend(lines)

    async def prompt(self, *_a, **_kw):
        return self._prompts.pop(0) if self._prompts else None


def _flat(sent) -> list[str]:
    out = []
    for item in sent:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def _run(coro):
    return asyncio.run(coro)


class TestBanManagementGating(unittest.TestCase):
    def test_non_admin_is_refused(self):
        player = _FakePlayer('Rank', flags=())
        ctx = _FakeCtx(player)
        state = {'banned': [], 'log': []}
        _run(_ban_management(ctx, player, state, {'key': 'CLAW', 'name': 'Mark of the Claw'}))
        self.assertIn('Lurch snickers..', _flat(ctx.sent))
        self.assertEqual(state['banned'], [])

    def test_admin_can_manage_bans(self):
        admin = _FakePlayer('Boss', flags=(PlayerFlags.ADMIN,))
        self.assertTrue(_can_manage_bans(admin))
        dm = _FakePlayer('DM', flags=(PlayerFlags.DUNGEON_MASTER,))
        self.assertTrue(_can_manage_bans(dm))
        civilian = _FakePlayer('Civ', flags=())
        self.assertFalse(_can_manage_bans(civilian))


class TestBanToggle(unittest.TestCase):
    def _admin_ctx(self, prompts):
        admin = _FakePlayer('Boss', flags=(PlayerFlags.ADMIN,))
        return admin, _FakeCtx(admin, prompts=prompts)

    def test_banning_a_guildmate_adds_to_list_and_demotes(self):
        admin, ctx = self._admin_ctx(prompts=['Y'])
        target = _FakePlayer('Rulan', guild=Guild.CLAW)
        state = {'banned': [], 'log': []}
        info = {'key': 'CLAW', 'name': 'Mark of the Claw'}

        with patch('commands.messaging.prompt_player_choice', return_value='Rulan'), \
             patch('commands.editplayer._find_character', return_value=(target, True)):
            _run(_ban_management(ctx, admin, state, info))

        self.assertIn('Rulan', state['banned'])
        self.assertEqual(target.guild, Guild.OUTLAW)
        self.assertTrue(target.unsaved_changes)
        self.assertFalse(target.saved)  # online -- save() not called directly
        self.assertTrue(any('BANNED' in ln for ln in state['log']))

    def test_banning_offline_target_saves_immediately(self):
        admin, ctx = self._admin_ctx(prompts=['Y'])
        target = _FakePlayer('Offliner', guild=Guild.CLAW)
        state = {'banned': [], 'log': []}
        info = {'key': 'CLAW', 'name': 'Mark of the Claw'}

        with patch('commands.messaging.prompt_player_choice', return_value='Offliner'), \
             patch('commands.editplayer._find_character', return_value=(target, False)):
            _run(_ban_management(ctx, admin, state, info))

        self.assertIn('Offliner', state['banned'])
        self.assertTrue(target.saved)

    def test_banning_a_different_guild_member_does_not_demote(self):
        admin, ctx = self._admin_ctx(prompts=['Y'])
        target = _FakePlayer('Swordsman', guild=Guild.SWORD)
        state = {'banned': [], 'log': []}
        info = {'key': 'CLAW', 'name': 'Mark of the Claw'}

        with patch('commands.messaging.prompt_player_choice', return_value='Swordsman'), \
             patch('commands.editplayer._find_character', return_value=(target, True)):
            _run(_ban_management(ctx, admin, state, info))

        self.assertIn('Swordsman', state['banned'])
        self.assertEqual(target.guild, Guild.SWORD)

    def test_unbanning_removes_from_list(self):
        admin, ctx = self._admin_ctx(prompts=['Y'])
        target = _FakePlayer('Rulan', guild=Guild.CLAW)
        state = {'banned': ['Rulan'], 'log': []}
        info = {'key': 'CLAW', 'name': 'Mark of the Claw'}

        with patch('commands.messaging.prompt_player_choice', return_value='Rulan'), \
             patch('commands.editplayer._find_character', return_value=(target, True)):
            _run(_ban_management(ctx, admin, state, info))

        self.assertNotIn('Rulan', state['banned'])
        self.assertTrue(any('UNBANNED' in ln for ln in state['log']))

    def test_declining_the_confirm_leaves_state_untouched(self):
        admin, ctx = self._admin_ctx(prompts=['N'])
        target = _FakePlayer('Rulan', guild=Guild.CLAW)
        state = {'banned': [], 'log': []}
        info = {'key': 'CLAW', 'name': 'Mark of the Claw'}

        with patch('commands.messaging.prompt_player_choice', return_value='Rulan'), \
             patch('commands.editplayer._find_character', return_value=(target, True)):
            _run(_ban_management(ctx, admin, state, info))

        self.assertEqual(state['banned'], [])
        self.assertEqual(state['log'], [])


class TestEntryGate(unittest.TestCase):
    def setUp(self):
        self._orig_run_server_dir = getattr(net_common, 'run_server_dir', None)
        self.tmp = Path('run') / 'server' / 'test_guild_hq_ban'
        self.tmp.mkdir(parents=True, exist_ok=True)
        net_common.run_server_dir = self.tmp

    def tearDown(self):
        import shutil
        net_common.run_server_dir = self._orig_run_server_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_banned_player_is_turned_away(self):
        from guild_hq.state import load, save
        state = load('CLAW')
        state['banned'] = ['Rulan']
        save('CLAW', state)

        player = _FakePlayer('Rulan', guild=Guild.CLAW)
        ctx = _FakeCtx(player)
        _run(main(ctx, 'CLAW'))

        self.assertTrue(any("banned from the Mark of the Claw" in ln for ln in _flat(ctx.sent)))

    def test_admin_bypasses_own_ban_list(self):
        from guild_hq.state import load, save
        state = load('CLAW')
        state['banned'] = ['Boss']
        save('CLAW', state)

        player = _FakePlayer('Boss', guild=Guild.CLAW, flags=(PlayerFlags.ADMIN,))
        ctx = _FakeCtx(player)
        # Immediately quit once inside so we don't need to fake presence broadcasts further.
        ctx._prompts = ['Q']
        with patch('presence.broadcast_area'), patch('presence.broadcast_open_room'):
            ctx.client = type('C', (), {'virtual_location': None})()
            _run(main(ctx, 'CLAW'))

        self.assertFalse(any('banned from the' in ln for ln in _flat(ctx.sent)))


if __name__ == '__main__':
    unittest.main()
