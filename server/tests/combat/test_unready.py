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
        self._answers = iter([])

    def set_answers(self, answers):
        self._answers = iter(answers)

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *a, **kw):
        return next(self._answers, None)

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


class TestBareUnreadyMenu(unittest.IsolatedAsyncioTestCase):
    """Bare UNREADY lists every readied weapon (player's + allies') when an
    ally is wielding something, mirroring bare READY's list."""

    def _party(self, own=None, ally_readied=None, second_ally_readied=None):
        from bar.ally_data import Ally, AllyStatus
        from party import Party
        player = _FakePlayer(readied_weapon=own)
        player.name = 'Rulan'
        player.return_key = 'RETURN'
        player.party = Party()
        allies = []
        alan = Ally('ALAN OF YOR', 'm', 12, 5)
        alan.status = AllyStatus.SERVANT
        alan.readied_weapon = ally_readied
        player.party.add_member(player, alan)
        allies.append(alan)
        if second_ally_readied is not None:
            bri = Ally('BRIANNA', 'f', 12, 5)
            bri.status = AllyStatus.SERVANT
            bri.readied_weapon = second_ally_readied
            player.party.add_member(player, bri)
            allies.append(bri)
        return player, allies

    async def test_solo_player_still_repacks_directly(self):
        # No ally wielding anything -> unchanged SPUR path, no menu.
        player, _ = self._party(own=_FakeWeapon('LONG SWORD'), ally_readied=None)
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx)
        self.assertIsNone(player.readied_weapon)
        self.assertIn('You repack the LONG SWORD.', ctx.sent())
        self.assertNotIn('Weapons readied:', ctx.sent())

    async def test_nobody_readied_reports_no_weapon(self):
        player, _ = self._party(own=None, ally_readied=None)
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx)
        self.assertIn('No weapon readied!', ctx.sent())

    async def test_only_ally_readied_repacks_without_menu(self):
        player, (alan,) = self._party(own=None, ally_readied=_FakeWeapon('SHORT SWORD'))
        alan.ammo_rounds = 4
        ctx = _FakeCtx(player)
        await UnreadyCommand().execute(ctx)
        self.assertIsNone(alan.readied_weapon)
        self.assertEqual(alan.ammo_rounds, 0)
        self.assertIn('ALAN OF YOR repacks the SHORT SWORD.', ctx.sent())
        self.assertNotIn('Weapons readied:', ctx.sent())

    async def test_menu_lists_player_and_ally_and_picks_player(self):
        player, (alan,) = self._party(own=_FakeWeapon('LONG SWORD'),
                                      ally_readied=_FakeWeapon('SHORT SWORD'))
        ctx = _FakeCtx(player)
        ctx.set_answers(['1'])   # 1 = You: LONG SWORD
        await UnreadyCommand().execute(ctx)
        self.assertIn('Weapons readied:', ctx.sent())
        self.assertIn('1. You: LONG SWORD', ctx.sent())
        self.assertIn('2. ALAN OF YOR: SHORT SWORD', ctx.sent())
        self.assertIsNone(player.readied_weapon)
        self.assertIsNotNone(alan.readied_weapon)
        self.assertIn('You repack the LONG SWORD.', ctx.sent())

    async def test_menu_pick_ally_repacks_that_ally(self):
        player, (alan,) = self._party(own=_FakeWeapon('LONG SWORD'),
                                      ally_readied=_FakeWeapon('SHORT SWORD'))
        ctx = _FakeCtx(player)
        ctx.set_answers(['2'])
        await UnreadyCommand().execute(ctx)
        self.assertIsNotNone(player.readied_weapon)
        self.assertIsNone(alan.readied_weapon)
        self.assertIn('ALAN OF YOR repacks the SHORT SWORD.', ctx.sent())

    async def test_menu_cancel_leaves_everything_readied(self):
        own = _FakeWeapon('LONG SWORD')
        player, (alan,) = self._party(own=own, ally_readied=_FakeWeapon('SHORT SWORD'))
        ctx = _FakeCtx(player)
        ctx.set_answers([''])
        await UnreadyCommand().execute(ctx)
        self.assertIs(player.readied_weapon, own)
        self.assertIsNotNone(alan.readied_weapon)

    async def test_menu_invalid_selection(self):
        player, (alan,) = self._party(own=_FakeWeapon('LONG SWORD'),
                                      ally_readied=_FakeWeapon('SHORT SWORD'))
        ctx = _FakeCtx(player)
        ctx.set_answers(['9'])
        await UnreadyCommand().execute(ctx)
        self.assertIn('Invalid selection.', ctx.sent())
        self.assertIsNotNone(player.readied_weapon)
        self.assertIsNotNone(alan.readied_weapon)

    async def test_menu_lists_two_allies(self):
        player, (alan, bri) = self._party(
            own=None,
            ally_readied=_FakeWeapon('SHORT SWORD'),
            second_ally_readied=_FakeWeapon('DAGGER'))
        ctx = _FakeCtx(player)
        ctx.set_answers(['2'])   # 1 = ALAN, 2 = BRIANNA
        await UnreadyCommand().execute(ctx)
        self.assertIn('1. ALAN OF YOR: SHORT SWORD', ctx.sent())
        self.assertIn('2. BRIANNA: DAGGER', ctx.sent())
        self.assertIsNone(bri.readied_weapon)
        self.assertIsNotNone(alan.readied_weapon)


if __name__ == '__main__':
    unittest.main(verbosity=2)
