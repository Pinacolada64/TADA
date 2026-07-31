"""tests/combat/test_duel_grovel.py — combat/duel.py's `duel grovel`
(SPUR.DUEL.S:74-77 "gvl.chk" / SPUR.DUEL2.S:198-211 "grovel"): a riskier
alternative to `duel decline` -- may fail and force the duel to start,
or succeed and drop the defender's silver in hand.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace, PlayerMoneyTypes
from combat.duel import _resolve_grovel
from items import Weapon
from player import Player


class _FakeClient:
    def __init__(self, room):
        self.room = room
        self.ctx = None


class _FakeServer:
    def __init__(self):
        self.clients: dict = {}
        self.game_map = None


class _FakeCtx:
    def __init__(self, player, server, client):
        self.player = player
        self.server = server
        self.client = client
        self.sent: list = []
        client.ctx = self

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_pending_challenge():
    server = _FakeServer()
    challenger = _make_duelist('Ardent')
    defender = _make_duelist('Belwin')
    challenger_client = _FakeClient(room=1)
    defender_client = _FakeClient(room=1)
    challenger_ctx = _FakeCtx(challenger, server, challenger_client)
    defender_ctx = _FakeCtx(defender, server, defender_client)
    server.clients = {'a': challenger_client, 'b': defender_client}
    defender.pending_duel_challenge = challenger.name
    return challenger_ctx, defender_ctx


class TestGrovelNoChallenge(unittest.IsolatedAsyncioTestCase):
    async def test_no_pending_challenge_fails(self):
        _, defender_ctx = _make_pending_challenge()
        defender_ctx.player.pending_duel_challenge = None
        result = await _resolve_grovel(defender_ctx)
        self.assertFalse(result.success)
        self.assertIn('Nobody has challenged you', _flat(defender_ctx))


class TestGrovelFails(unittest.IsolatedAsyncioTestCase):
    async def test_failed_roll_forces_the_duel_to_start(self):
        challenger_ctx, defender_ctx = _make_pending_challenge()
        with patch('combat.duel.random.randint', return_value=51):
            result = await _resolve_grovel(defender_ctx)
        self.assertTrue(result.success)
        self.assertIn('Groveling will do you no good!', _flat(defender_ctx))
        # Forced into _resolve_challenge(accept=True): an active duel starts.
        self.assertIsNotNone(defender_ctx.player.active_duel)
        self.assertIsNotNone(challenger_ctx.player.active_duel)


class TestGrovelSucceeds(unittest.IsolatedAsyncioTestCase):
    async def test_success_without_gold_drop(self):
        challenger_ctx, defender_ctx = _make_pending_challenge()
        defender_ctx.player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100)
        with patch('combat.duel.random.randint', side_effect=[50, 50]):
            with patch('combat.duel.net_common.append_battle_log') as log:
                result = await _resolve_grovel(defender_ctx)
        self.assertTrue(result.success)
        self.assertIn('snickers, and waves you on.', _flat(defender_ctx))
        self.assertIsNone(defender_ctx.player.pending_duel_challenge)
        self.assertIsNone(getattr(defender_ctx.player, 'active_duel', None))
        self.assertEqual(defender_ctx.player.get_silver(PlayerMoneyTypes.IN_HAND), 100)
        log.assert_called_once()
        self.assertIn('GROVELED BEFORE Ardent', log.call_args.args[0])

    async def test_success_with_silver_drop(self):
        challenger_ctx, defender_ctx = _make_pending_challenge()
        defender_ctx.player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100)
        with patch('combat.duel.random.randint', side_effect=[50, 51]):
            with patch('combat.duel.net_common.append_battle_log'):
                await _resolve_grovel(defender_ctx)
        self.assertEqual(defender_ctx.player.get_silver(PlayerMoneyTypes.IN_HAND), 0)
        self.assertIn('dropped your silver sack', _flat(defender_ctx))

    async def test_challenger_notified_of_grovel(self):
        challenger_ctx, defender_ctx = _make_pending_challenge()
        with patch('combat.duel.random.randint', side_effect=[50, 51]):
            with patch('combat.duel.net_common.append_battle_log'):
                await _resolve_grovel(defender_ctx)
        self.assertIn('grovels before you and slinks away.', _flat(challenger_ctx))


if __name__ == '__main__':
    unittest.main()
