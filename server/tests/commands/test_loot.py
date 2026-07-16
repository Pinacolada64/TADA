"""tests/commands/test_loot.py

Covers commands/loot.py -- SPUR.MISC3.S's "loot" subroutine, PVP item
theft between live players sharing a room (not "search a dead monster's
corpse", despite the verb):

  - Target selection (list room-mates, pick by number).
  - Guardian block: a fellow guild member of the target's blocks the
    theft (New in TADA simplification -- see commands/loot.py's module
    docstring).
  - Successful steal moves the item, docks the THIEF's own honor (30,
    or 50 for a Knight), and marks loot used this session.
  - Once-per-session limit (twice for Outlaws).
  - Duplicate-ownership block (thief or their ally already carries one).
  - battle.log entries for both outcomes.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from base_classes import Guild, PlayerClass
from commands.loot import LootCommand
from inventory import Inventory
from items import Item, ItemCategory
from player import Player


def _player(name, guild=None, char_class=None) -> Player:
    p = Player(name=name)
    p.inventory = Inventory(capacity=10)
    p.map_level = 1
    if guild is not None:
        p.guild = guild
    if char_class is not None:
        p.char_class = char_class
    return p


def _client(player, room=1) -> MagicMock:
    client = MagicMock()
    client.room = room
    client.ctx = MagicMock()
    client.ctx.player = player
    return client


class _FakeCtx:
    def __init__(self, client, server, responses=None):
        self.client = client
        self.server = server
        self.player = client.ctx.player
        self._q = list(responses or [])
        self.sent: list = []
        self.room_sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        for a in args:
            if isinstance(a, list):
                self.room_sent.extend(a)
            else:
                self.room_sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _server(*clients) -> MagicMock:
    server = MagicMock()
    server.clients = {i: c for i, c in enumerate(clients)}
    return server


class _IsolatedBattleLog(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import net_common
        self._orig_dir = net_common.run_server_dir
        self._tmp = tempfile.TemporaryDirectory()
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_dir
        self._tmp.cleanup()

    def _log_text(self) -> str:
        path = Path(self._tmp.name) / 'battle.log'
        return path.read_text() if path.exists() else ''


class TestNoTargets(_IsolatedBattleLog):
    async def test_empty_room_says_no_adventurers(self):
        thief = _player('Rulan')
        client = _client(thief)
        ctx = _FakeCtx(client, _server(client))
        await LootCommand().execute(ctx)
        self.assertIn('No adventurers here!', ctx._flat())

    async def test_only_self_in_room_still_says_no_adventurers(self):
        thief = _player('Rulan')
        client = _client(thief, room=5)
        ctx = _FakeCtx(client, _server(client))
        await LootCommand().execute(ctx)
        self.assertIn('No adventurers here!', ctx._flat())

    async def test_other_level_same_room_number_not_counted(self):
        thief  = _player('Rulan')
        victim = _player('Gareth')
        victim.map_level = 2
        c1 = _client(thief, room=5)
        c2 = _client(victim, room=5)
        ctx = _FakeCtx(c1, _server(c1, c2))
        await LootCommand().execute(ctx)
        self.assertIn('No adventurers here!', ctx._flat())


class TestGates(_IsolatedBattleLog):
    async def test_loot_limit_reached_blocks_before_listing(self):
        thief = _player('Rulan')
        thief.loot_count = 1
        victim = _player('Gareth')
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2))
        await LootCommand().execute(ctx)
        self.assertIn('SPUR gestapo', ctx._flat())

    async def test_outlaw_gets_two_loots(self):
        thief = _player('Rulan', guild=Guild.OUTLAW)
        thief.loot_count = 1  # one used, one left
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertIn('You steal the dagger from Gareth!', ctx._flat())

    async def test_full_inventory_blocks_loot(self):
        thief = _player('Rulan')
        thief.inventory = Inventory(capacity=0)
        victim = _player('Gareth')
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2))
        await LootCommand().execute(ctx)
        self.assertIn('You can carry no more Items.', ctx._flat())


class TestTargetSelection(_IsolatedBattleLog):
    async def test_invalid_selection(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['99'])
        await LootCommand().execute(ctx)
        self.assertIn('Invalid selection.', ctx._flat())

    async def test_blank_at_target_prompt_aborts(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=[''])
        await LootCommand().execute(ctx)
        self.assertEqual(len(victim.inventory.entries()), 1)  # untouched

    async def test_target_carrying_nothing(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1'])
        await LootCommand().execute(ctx)
        self.assertIn("Gareth isn't carrying any items!", ctx._flat())

    async def test_blank_at_item_prompt_aborts(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', ''])
        await LootCommand().execute(ctx)
        self.assertEqual(len(victim.inventory.entries()), 1)  # untouched

    async def test_invalid_item_selection(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '99'])
        await LootCommand().execute(ctx)
        self.assertIn("Gareth doesn't carry that!", ctx._flat())


class TestSuccessfulSteal(_IsolatedBattleLog):
    async def test_item_moves_to_thief_inventory(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertEqual(len(victim.inventory.entries()), 0)
        self.assertEqual(len(thief.inventory.find(item_id=1)), 1)
        self.assertIn('You steal the dagger from Gareth!', ctx._flat())

    async def test_room_broadcast_sent(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertTrue(any('steals from' in l for l in ctx.room_sent))

    async def test_honor_docked_thirty_for_non_knight(self):
        thief = _player('Rulan', char_class=PlayerClass.FIGHTER)
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertEqual(thief.honor, 970)

    async def test_honor_docked_fifty_for_knight(self):
        thief = _player('Rulan', char_class=PlayerClass.KNIGHT)
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertEqual(thief.honor, 950)

    async def test_honor_never_goes_negative(self):
        thief = _player('Rulan')
        thief.honor = 10
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertEqual(thief.honor, 0)

    async def test_loot_count_incremented(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertEqual(thief.loot_count, 1)

    async def test_battle_log_pillage_entry(self):
        thief = _player('Rulan')
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        log_text = self._log_text()
        self.assertIn('Rulan STOLE dagger FROM Gareth', log_text)

    async def test_already_carrying_one_blocks_steal(self):
        thief = _player('Rulan')
        thief.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        victim = _player('Gareth')
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertIn('You already have one!', ctx._flat())
        self.assertEqual(len(victim.inventory.entries()), 1)  # not stolen


class TestGuardianBlock(_IsolatedBattleLog):
    async def test_fellow_guild_member_blocks_theft(self):
        thief    = _player('Rulan')
        victim   = _player('Gareth', guild=Guild.SWORD)
        guardian = _player('Aldric', guild=Guild.SWORD)
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2, c3 = _client(thief), _client(victim), _client(guardian)
        ctx = _FakeCtx(c1, _server(c1, c2, c3), responses=['1'])
        await LootCommand().execute(ctx)
        self.assertIn('blocks the path', ctx._flat())
        self.assertEqual(len(victim.inventory.entries()), 1)  # untouched
        self.assertEqual(thief.honor, 1000)  # no cost when blocked
        self.assertEqual(thief.loot_count, 0)

    async def test_battle_log_comrades_entry_on_block(self):
        thief    = _player('Rulan')
        victim   = _player('Gareth', guild=Guild.CLAW)
        guardian = _player('Aldric', guild=Guild.CLAW)
        c1, c2, c3 = _client(thief), _client(victim), _client(guardian)
        ctx = _FakeCtx(c1, _server(c1, c2, c3), responses=['1'])
        await LootCommand().execute(ctx)
        self.assertIn('COMRADES', self._log_text())

    async def test_no_guardian_without_a_fellow_member_present(self):
        """Only the target is Sword-guild -- nobody else shares that
        guild, so there's no guardian and the steal proceeds normally."""
        thief  = _player('Rulan')
        victim = _player('Gareth', guild=Guild.SWORD)
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2 = _client(thief), _client(victim)
        ctx = _FakeCtx(c1, _server(c1, c2), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertIn('You steal the dagger from Gareth!', ctx._flat())

    async def test_civilian_target_has_no_guardian_mechanic(self):
        """Civilian/Outlaw aren't in _GUARDIAN_GUILDS -- even with another
        civilian present, there's no guardian block."""
        thief  = _player('Rulan')
        victim = _player('Gareth', guild=Guild.CIVILIAN)
        bystander = _player('Aldric', guild=Guild.CIVILIAN)
        victim.inventory.add(Item(id_number=1, name='dagger', category=ItemCategory.ITEM))
        c1, c2, c3 = _client(thief), _client(victim), _client(bystander)
        ctx = _FakeCtx(c1, _server(c1, c2, c3), responses=['1', '1'])
        await LootCommand().execute(ctx)
        self.assertIn('You steal the dagger from Gareth!', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
