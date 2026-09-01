"""tests/test_unready.py

Unit tests for commands/unready.py (SPUR.MAIN.S:84-85 / skip :90-91).

Run with:
    python -m pytest tests/test_unready.py -v
"""
from __future__ import annotations

import unittest

from commands.unready import UnreadyCommand


class _FakeWeapon:
    def __init__(self, name):
        self.name = name


class _FakePlayer:
    def __init__(self, readied_weapon=None):
        self.readied_weapon = readied_weapon
        self.storm_servant_bonus = (2, 2) if readied_weapon else None
        self.unsaved_changes = False


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    def sent(self) -> str:
        return '\n'.join(self._sent)


class TestUnreadyCommand(unittest.IsolatedAsyncioTestCase):

    async def test_no_weapon_readied(self):
        player = _FakePlayer(readied_weapon=None)
        ctx = _FakeCtx(player)
        result = await UnreadyCommand().execute(ctx)
        self.assertTrue(result.success)
        self.assertIn('No weapon readied!', ctx.sent())

    async def test_unreadies_current_weapon(self):
        sword = _FakeWeapon('LONG SWORD')
        player = _FakePlayer(readied_weapon=sword)
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx)
        self.assertIsNone(player.readied_weapon)
        self.assertIn('You repack the LONG SWORD.', ctx.sent())
        self.assertTrue(player.unsaved_changes)

    async def test_clears_storm_servant_bonus(self):
        storm = _FakeWeapon('STORM STAFF')
        player = _FakePlayer(readied_weapon=storm)
        self.assertIsNotNone(player.storm_servant_bonus)
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx)
        self.assertIsNone(player.storm_servant_bonus)


class TestUnreadyAllyWeapon(unittest.IsolatedAsyncioTestCase):
    """"unready <ally>" -- mirror of READY's ally-weapon toggle."""

    def _player_with_ally(self, readied=None):
        from bar.ally_data import Ally, AllyStatus
        from party import Party
        player = _FakePlayer(readied_weapon=None)
        player.name = 'Rulan'
        ally = Ally('ALAN OF YOR', 'm', 12, 5)
        ally.status = AllyStatus.SERVANT
        ally.readied_weapon = readied
        player.party = Party()
        player.party.add_member(player, ally)
        return player, ally

    async def test_unready_named_ally_repacks_their_weapon(self):
        player, ally = self._player_with_ally(readied=_FakeWeapon('SHORT SWORD'))
        ally.ammo_rounds = 5
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx, 'alan')
        self.assertIsNone(ally.readied_weapon)
        self.assertEqual(ally.ammo_rounds, 0)
        self.assertIn('ALAN OF YOR repacks the SHORT SWORD.', ctx.sent())
        self.assertTrue(player.unsaved_changes)

    async def test_unready_ally_with_nothing_readied(self):
        player, ally = self._player_with_ally(readied=None)
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx, 'alan')
        self.assertIn('ALAN OF YOR has no weapon readied.', ctx.sent())

    async def test_unready_unknown_ally_name(self):
        player, ally = self._player_with_ally(readied=_FakeWeapon('SHORT SWORD'))
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx, 'nobody')
        self.assertIn('No party ally matching "nobody".', ctx.sent())
        self.assertIsNotNone(ally.readied_weapon)


if __name__ == '__main__':
    unittest.main(verbosity=2)
