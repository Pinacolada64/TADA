"""tests/combat/test_charm.py — spells/charm.py: the CHARM POTION mechanic
(SPUR.SUB.S/SPUR.MISC5.S/SPUR.MISC4.S/SPUR.MAIN.S "charm", both branches).
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bar.ally_data import Ally, AllyStatus
from base_classes import Map, Room
from party import Party


def _make_monster(number=50, name='GOBLIN', strength=10, to_hit=5,
                   charmable=True, mechanical=False, tough=False):
    return {
        'number': number, 'name': name, 'strength': strength, 'to_hit': to_hit,
        'flags': {'charmable': charmable, 'mechanical': mechanical, 'tough': tough},
    }


def _make_room(monster=0):
    return Room(number=1, name='The Wilds', desc='', exits={}, monster=monster)


def _make_player(name='Killerella', party=None, charmed_monsters=None,
                  monsters_killed=None, honor=1000):
    player = MagicMock()
    player.name = name
    player.map_level = 1
    player.party = party if party is not None else Party()
    player.charmed_monsters = charmed_monsters if charmed_monsters is not None else []
    player.monsters_killed = monsters_killed if monsters_killed is not None else []
    player.pending_charm = None
    player.honor = honor
    player.unsaved_changes = False
    return player


def _make_ctx(room_no=1, player=None, room=None, monsters=None, active_combats=None):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    game_map = Map()
    game_map.levels[1] = {room_no: room or _make_room()}
    ctx.server.game_map = game_map
    ctx.server.monsters = monsters or []
    ctx.server.active_combats = active_combats or {}
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt = AsyncMock(return_value='')
    return ctx


class _IsolatedBattleLog(unittest.IsolatedAsyncioTestCase):
    """Redirects net_common.append_battle_log()'s writes to a temp dir instead of the
    real run/server/battle.log (same pattern test_dwarf.py/
    test_ally_starvation.py use)."""

    def setUp(self):
        import net_common
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_run_server_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_run_server_dir
        self._tmp.cleanup()


class TestTryCharmPotion(_IsolatedBattleLog):
    async def test_no_monster_in_room(self):
        from spells.charm import try_charm_potion
        ctx = _make_ctx(room=_make_room(monster=0))
        result = await try_charm_potion(ctx)
        self.assertFalse(result)
        self.assertIn('There is no monster here', ' '.join(
            str(a) for c in ctx.send.await_args_list for a in c.args))

    async def test_charmable_monster_sets_pending_charm(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50, name='GOBLIN')
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster])
        result = await try_charm_potion(ctx)
        self.assertTrue(result)
        pending = ctx.player.pending_charm
        self.assertIsNotNone(pending)
        self.assertEqual(pending['monster_number'], 50)
        self.assertEqual(pending['name'], 'GOBLIN')
        self.assertEqual(pending['level'], 1)
        self.assertEqual(pending['room_no'], 1)

    async def test_tough_monster_unaffected(self):
        # SPUR.SUB.S:147 `if mw then if instr(".",wy$) print m$" is
        # unaffected by the charm potion!":return` -- gated on 'tough'
        # ('.'), NOT on 'charmable' (AC flag).
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50, name='DRAGON', charmable=False, tough=True)
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster])
        result = await try_charm_potion(ctx)
        self.assertFalse(result)
        self.assertIsNone(ctx.player.pending_charm)
        self.assertIn('unaffected', ' '.join(
            str(a) for c in ctx.send.await_args_list for a in c.args))

    async def test_non_charmable_non_tough_monster_still_charms(self):
        # The CHARM POTION isn't gated on 'charmable' (AC flag) at all --
        # only 'mechanical' and 'tough' block it (SPUR.SUB.S:146-147). The
        # AC flag only matters to encounters/monster.py's potion-less roll.
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50, name='GOBLIN', charmable=False, tough=False)
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster])
        result = await try_charm_potion(ctx)
        self.assertTrue(result)
        self.assertIsNotNone(ctx.player.pending_charm)

    async def test_mechanical_monster_cannot_be_charmed(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50, name='ROBOT', charmable=True, mechanical=True)
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster])
        result = await try_charm_potion(ctx)
        self.assertFalse(result)
        self.assertIn("don't charm", ' '.join(
            str(a) for c in ctx.send.await_args_list for a in c.args))

    async def test_already_charmed_by_this_player_treated_as_no_monster(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50)
        player = _make_player(charmed_monsters=[50])
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster], player=player)
        result = await try_charm_potion(ctx)
        self.assertFalse(result)

    async def test_already_killed_by_this_player_treated_as_no_monster(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50)
        player = _make_player(monsters_killed=[50])
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster], player=player)
        result = await try_charm_potion(ctx)
        self.assertFalse(result)

    async def test_ends_active_combat_peacefully(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50)
        session = MagicMock()
        session._done.is_set.return_value = False
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster],
                         active_combats={1: session})
        await try_charm_potion(ctx)
        session._done.set.assert_called_once()
        session._remove_attacker.assert_called_once_with(ctx)


class TestCharmGreetingLine(unittest.TestCase):
    def test_no_pending_charm_returns_none(self):
        from spells.charm import charm_greeting_line
        player = _make_player()
        self.assertIsNone(charm_greeting_line(player, 1, 1))

    def test_matching_pending_charm_returns_greeting(self):
        from spells.charm import charm_greeting_line
        player = _make_player(name='Killerella')
        player.pending_charm = {'level': 1, 'room_no': 5, 'monster_number': 50,
                                 'name': 'GOBLIN', 'strength': 10, 'to_hit': 5}
        line = charm_greeting_line(player, 5, 1)
        self.assertEqual(line, 'GOBLIN is charmed: "Gosh, er... hi, Killerella!"')

    def test_different_room_returns_none(self):
        from spells.charm import charm_greeting_line
        player = _make_player()
        player.pending_charm = {'level': 1, 'room_no': 5, 'monster_number': 50,
                                 'name': 'GOBLIN', 'strength': 10, 'to_hit': 5}
        self.assertIsNone(charm_greeting_line(player, 6, 1))

    def test_different_level_returns_none(self):
        from spells.charm import charm_greeting_line
        player = _make_player()
        player.pending_charm = {'level': 1, 'room_no': 5, 'monster_number': 50,
                                 'name': 'GOBLIN', 'strength': 10, 'to_hit': 5}
        self.assertIsNone(charm_greeting_line(player, 5, 2))


class TestTryCharmJoinOffer(_IsolatedBattleLog):
    def _pending(self, **overrides):
        base = {'level': 1, 'room_no': 5, 'monster_number': 50,
                'name': 'GOBLIN', 'strength': 10, 'to_hit': 5}
        base.update(overrides)
        return base

    async def test_no_pending_charm_is_no_op(self):
        from spells.charm import try_charm_join_offer
        player = _make_player()
        ctx = _make_ctx(player=player)
        await try_charm_join_offer(ctx, level=1, room_no=5)
        ctx.send.assert_not_awaited()

    async def test_wrong_room_is_no_op(self):
        from spells.charm import try_charm_join_offer
        player = _make_player()
        player.pending_charm = self._pending(room_no=5)
        ctx = _make_ctx(player=player)
        await try_charm_join_offer(ctx, level=1, room_no=6)
        ctx.send.assert_not_awaited()
        self.assertIsNotNone(player.pending_charm)

    async def test_accept_adds_ally_as_servant(self):
        from spells.charm import try_charm_join_offer
        player = _make_player()
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        ctx.prompt = AsyncMock(return_value='Y')
        await try_charm_join_offer(ctx, level=1, room_no=5)
        self.assertEqual(len(player.party), 1)
        added = list(player.party)[0]
        self.assertEqual(added.name, 'GOBLIN')
        self.assertEqual(added.status, AllyStatus.SERVANT)
        self.assertEqual(added.owner, player.name)
        self.assertEqual(added.hit_points, 10 * 2)
        self.assertIn(50, player.charmed_monsters)
        self.assertIsNone(player.pending_charm)
        self.assertTrue(player.unsaved_changes)

    async def test_decline_applies_honor_penalty(self):
        from spells.charm import try_charm_join_offer
        player = _make_player(honor=1000)
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        ctx.prompt = AsyncMock(return_value='N')
        await try_charm_join_offer(ctx, level=1, room_no=5)
        self.assertEqual(len(player.party), 0)
        self.assertLess(player.honor, 1000)
        self.assertIsNone(player.pending_charm)
        self.assertNotIn(50, player.charmed_monsters)

    async def test_blank_response_declines(self):
        from spells.charm import try_charm_join_offer
        player = _make_player()
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        ctx.prompt = AsyncMock(return_value='')
        await try_charm_join_offer(ctx, level=1, room_no=5)
        self.assertEqual(len(player.party), 0)

    async def test_full_party_auto_declines_without_prompting(self):
        from spells.charm import try_charm_join_offer
        existing = [Ally(name=f'Ally{i}', gender='m', strength=10, to_hit=5) for i in range(3)]
        player = _make_player(party=Party(members=existing))
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        await try_charm_join_offer(ctx, level=1, room_no=5)
        ctx.prompt.assert_not_awaited()
        self.assertEqual(len(player.party), 3)
        self.assertIsNone(player.pending_charm)


class TestBystanderBroadcasts(_IsolatedBattleLog):
    def _room_text(self, ctx):
        return ' '.join(
            str(a) for call in ctx.send_room.await_args_list for a in call.args
        )

    async def test_charming_broadcasts_to_room(self):
        from spells.charm import try_charm_potion
        monster = _make_monster(number=50, name='LION')
        player = _make_player(name='Killerella')
        ctx = _make_ctx(room=_make_room(monster=50), monsters=[monster], player=player)
        await try_charm_potion(ctx)
        text = self._room_text(ctx)
        self.assertIn('Killerella', text)
        self.assertIn('LION', text)
        for call in ctx.send_room.await_args_list:
            self.assertTrue(call.kwargs.get('exclude_self'))

    async def test_accept_broadcasts_to_room(self):
        from spells.charm import try_charm_join_offer
        player = _make_player(name='Killerella')
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        ctx.prompt = AsyncMock(return_value='Y')
        await try_charm_join_offer(ctx, level=1, room_no=5)
        text = self._room_text(ctx)
        self.assertIn('GOBLIN', text)
        self.assertIn('Killerella', text)

    async def test_decline_broadcasts_to_room(self):
        from spells.charm import try_charm_join_offer
        player = _make_player(name='Killerella')
        player.pending_charm = self._pending()
        ctx = _make_ctx(player=player)
        ctx.prompt = AsyncMock(return_value='N')
        await try_charm_join_offer(ctx, level=1, room_no=5)
        text = self._room_text(ctx)
        self.assertIn('GOBLIN', text)
        self.assertIn('Killerella', text)

    def _pending(self, **overrides):
        base = {'level': 1, 'room_no': 5, 'monster_number': 50,
                'name': 'GOBLIN', 'strength': 10, 'to_hit': 5}
        base.update(overrides)
        return base


if __name__ == '__main__':
    unittest.main()
