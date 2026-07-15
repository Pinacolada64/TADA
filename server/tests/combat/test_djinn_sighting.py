"""tests/combat/test_djinn_sighting.py — encounters/djinn_sighting.py:
the random Blue Djinn debt-collection trigger (skip branch's
SPUR.MISC6.S "djinn" label -- not present in master at all).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, Room
from flags import PlayerFlags


def _make_map():
    m = Map()
    rooms = {
        1: Room(number=1, name='Room One', desc='', exits={}, monster=0),
        2: Room(number=2, name='Room Two', desc='', exits={}, monster=5),
    }
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def _make_player(seen=False, loan_amount=0, loan_days=0):
    player = MagicMock()
    player.name = 'Testerson'
    player.once_per_day = ['djinn_sighting_seen'] if seen else []
    player.loan_amount = loan_amount
    player.loan_days = loan_days
    flag_state = {}

    def _set_flag(flag, verbose=False):
        flag_state[flag] = True
        return True, None
    player.set_flag = MagicMock(side_effect=_set_flag)
    player._flag_state = flag_state
    return player


def _make_ctx(room_no=1, player=None, game_map=None):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    ctx.player.map_level = 1
    ctx.server.game_map = game_map or _make_map()
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _sent_text(ctx):
    out = []
    for call in ctx.send.await_args_list:
        for a in call.args:
            if isinstance(a, list):
                out.extend(str(x) for x in a)
            else:
                out.append(str(a))
    return ' '.join(out)


class TestGating(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_if_already_seen(self):
        from encounters.djinn_sighting import try_encounter
        ctx = _make_ctx(player=_make_player(seen=True))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_if_room_has_monster(self):
        from encounters.djinn_sighting import try_encounter
        ctx = _make_ctx(room_no=2)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_when_roll_fails(self):
        from encounters.djinn_sighting import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=99.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_marks_seen_on_trigger(self):
        from encounters.djinn_sighting import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn('djinn_sighting_seen', ctx.player.once_per_day)

    async def test_always_shows_sighting_line(self):
        from encounters.djinn_sighting import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn('You think you see the Blue Djinn in the distance!', _sent_text(ctx))


class TestNoDebt(unittest.IsolatedAsyncioTestCase):
    async def test_vanishes_harmlessly_with_no_loan(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=0, loan_days=0)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn('HE VANISHES', _sent_text(ctx))
        player.set_flag.assert_not_called()


class TestWithDebt(unittest.IsolatedAsyncioTestCase):
    async def test_loan_amount_triggers_thug_flag_and_contract(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=500, loan_days=0)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('bar.blue_djinn.add_contract') as mock_add_contract:
            await try_encounter(ctx)
        player.set_flag.assert_called_once_with(PlayerFlags.THUG_ATTACK)
        mock_add_contract.assert_called_once_with(
            target_name='Testerson', attacker_display='Vinny',
            attacker_real='Vinny', gold_paid=0,
        )
        self.assertNotIn('HE VANISHES', _sent_text(ctx))

    async def test_loan_days_alone_also_triggers(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=0, loan_days=3)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('bar.blue_djinn.add_contract'):
            await try_encounter(ctx)
        player.set_flag.assert_called_once_with(PlayerFlags.THUG_ATTACK)


class TestBystanderBroadcast(unittest.IsolatedAsyncioTestCase):
    def _room_text(self, ctx):
        return ' '.join(
            str(a) for call in ctx.send_room.await_args_list for a in call.args
        )

    async def test_uneasy_line_always_broadcasts(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=0, loan_days=0)
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn('Killerella stares off into the distance, looking uneasy',
                       self._room_text(ctx))
        for call in ctx.send_room.await_args_list:
            self.assertTrue(call.kwargs.get('exclude_self'))

    async def test_pale_line_only_broadcasts_with_debt(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=0, loan_days=0)
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertNotIn('suddenly looks pale', self._room_text(ctx))

    async def test_pale_line_broadcasts_when_debt_triggers_ambush(self):
        from encounters.djinn_sighting import try_encounter
        player = _make_player(loan_amount=500)
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('bar.blue_djinn.add_contract'):
            await try_encounter(ctx)
        self.assertIn('Killerella suddenly looks pale.', self._room_text(ctx))


if __name__ == '__main__':
    unittest.main()
