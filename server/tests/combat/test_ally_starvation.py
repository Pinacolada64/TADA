"""tests/combat/test_ally_starvation.py — encounters/ally_starvation.py:
a weakened owned ally dies (or, if divine, deserts) from lack of
nourishment (SPUR.MISC6.S's "dead.al"/"dead.al2" labels).
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, Room
from bar.ally_data import Ally, AllyFlags, AllyStatus


class _IsolatedBattleLog(unittest.IsolatedAsyncioTestCase):
    """Base class that redirects _append_battle_log()'s writes to a temp
    dir instead of the real run/server/battle.log (same pattern as
    tests/combat/test_dwarf.py's on_killed tests)."""

    def setUp(self):
        import net_common
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_run_server_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_run_server_dir
        self._tmp.cleanup()


def _make_map():
    m = Map()
    rooms = {1: Room(number=1, name='The Wilds', desc='', exits={})}
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def _make_ally(name='Grog', strength=5, flags=None):
    return Ally(name=name, gender='m', strength=strength, to_hit=4, flags=flags)


def _make_player(party=None, honor=1000, wisdom=50, intelligence=50):
    player = MagicMock()
    player.name = 'Testerson'
    player.party = party if party is not None else []
    player.honor = honor
    player.stats = {'Wisdom': wisdom, 'Intelligence': intelligence}
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


class TestGating(_IsolatedBattleLog):
    async def test_no_op_with_no_weakened_ally(self):
        from encounters.ally_starvation import try_encounter
        ctx = _make_ctx(player=_make_player(party=[_make_ally(strength=20)]))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_with_no_allies(self):
        from encounters.ally_starvation import try_encounter
        ctx = _make_ctx(player=_make_player(party=[]))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_when_roll_fails(self):
        from encounters.ally_starvation import try_encounter
        ctx = _make_ctx(player=_make_player(party=[_make_ally(strength=5)]))
        with patch('random.uniform', return_value=99.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_zero_strength_does_not_qualify(self):
        from encounters.ally_starvation import try_encounter
        ctx = _make_ctx(player=_make_player(party=[_make_ally(strength=0)]))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_can_fire_with_no_once_per_day_key(self):
        """Unlike every other encounter, this one has no once-per-session gate."""
        from encounters.ally_starvation import try_encounter
        player = _make_player(party=[_make_ally(strength=5)])
        player.once_per_day = ['ally_starvation_seen']  # should have no effect at all
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster'):
            await try_encounter(ctx)
        ctx.send.assert_awaited()


class TestDeath(_IsolatedBattleLog):
    async def test_mortal_ally_dies_and_is_removed(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Grog', strength=5)
        player = _make_player(party=[ally])
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster') as mock_free:
            await try_encounter(ctx)
        self.assertNotIn(ally, player.party)
        self.assertEqual(ally.status, AllyStatus.DEAD)
        mock_free.assert_called_once_with('Grog', AllyStatus.DEAD, None)
        text = _sent_text(ctx)
        self.assertIn('weakened Grog stumbles and falls', text)
        self.assertIn('Grog is dead', text)

    async def test_stat_penalties_applied(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Grog', strength=5)
        player = _make_player(party=[ally], honor=1000, wisdom=50, intelligence=50)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster'):
            await try_encounter(ctx)
        self.assertEqual(player.honor, 980)
        self.assertEqual(player.stats['Wisdom'], 45)
        self.assertEqual(player.stats['Intelligence'], 45)
        text = _sent_text(ctx)
        self.assertIn('less honorable', text)
        self.assertIn('foolish', text)
        self.assertIn('dumb', text)

    async def test_stat_penalties_respect_floor(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Grog', strength=5)
        player = _make_player(party=[ally], honor=10, wisdom=3, intelligence=3)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster'):
            await try_encounter(ctx)
        self.assertEqual(player.honor, 10)
        self.assertEqual(player.stats['Wisdom'], 3)
        self.assertEqual(player.stats['Intelligence'], 3)
        text = _sent_text(ctx)
        self.assertNotIn('less honorable', text)
        self.assertNotIn('foolish', text)
        self.assertNotIn('dumb', text)


class TestDivineAlly(_IsolatedBattleLog):
    async def test_god_ally_leaves_instead_of_dying(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Zeus', strength=5, flags=[AllyFlags.GOD])
        player = _make_player(party=[ally])
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster') as mock_free:
            await try_encounter(ctx)
        self.assertNotIn(ally, player.party)
        self.assertEqual(ally.status, AllyStatus.FREE)
        mock_free.assert_called_once_with('Zeus', AllyStatus.FREE, None)
        text = _sent_text(ctx)
        self.assertIn('looks annoyed, and flies away', text)
        self.assertNotIn('is dead', text)

    async def test_goddess_ally_also_leaves(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Athena', strength=5, flags=[AllyFlags.GODDESS])
        player = _make_player(party=[ally])
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster'):
            await try_encounter(ctx)
        self.assertEqual(ally.status, AllyStatus.FREE)


class TestEliteAlly(unittest.IsolatedAsyncioTestCase):
    async def test_elite_ally_endures_instead_of_dying_or_deserting(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Ironclad', strength=5, flags=[AllyFlags.ELITE])
        player = _make_player(party=[ally])
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn(ally, player.party)
        text = _sent_text(ctx)
        self.assertIn('looks gaunt', text)
        self.assertIn('endures', text)

    async def test_elite_ally_takes_no_stat_penalty(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Ironclad', strength=5, flags=[AllyFlags.ELITE])
        player = _make_player(party=[ally], honor=1000, wisdom=50, intelligence=50)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertEqual(player.honor, 1000)
        self.assertEqual(player.stats['Wisdom'], 50)
        self.assertEqual(player.stats['Intelligence'], 50)

    async def test_elite_god_ally_also_endures_not_deserts(self):
        """ELITE takes priority over the GOD/GODDESS desertion branch --
        an elite divine ally still just endures, doesn't fly away."""
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Ironclad', strength=5, flags=[AllyFlags.ELITE, AllyFlags.GOD])
        player = _make_player(party=[ally])
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertIn(ally, player.party)
        text = _sent_text(ctx)
        self.assertIn('endures', text)
        self.assertNotIn('flies away', text)


class TestBystanderBroadcast(_IsolatedBattleLog):
    async def test_death_broadcasts_to_room(self):
        from encounters.ally_starvation import try_encounter
        ally = _make_ally('Grog', strength=5)
        player = _make_player(party=[ally])
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('ally_events._free_ally_in_roster'):
            await try_encounter(ctx)
        room_text = ' '.join(
            str(a) for call in ctx.send_room.await_args_list for a in call.args
        )
        self.assertIn('Grog', room_text)
        self.assertIn('Killerella', room_text)
        for call in ctx.send_room.await_args_list:
            self.assertTrue(call.kwargs.get('exclude_self'))


if __name__ == '__main__':
    unittest.main()
