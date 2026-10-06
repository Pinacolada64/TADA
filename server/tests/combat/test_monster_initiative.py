"""tests/combat/test_monster_initiative.py

Monsters striking first (SPUR.MAIN.S advent -> advent5 `gosub m.attack`,
run at the top of every turn before the player's command is read):

  - CombatSession._run_loop()'s round order: the monster swings before
    the player's prompt each round, except the opening round of a fight
    the player started. READY/e[X]it/a blocked FLEE therefore cost a
    turn; a refused CHARGE/LURK re-prompts for free.
  - First strike (missile/pole/mounted) pre-empts the monster's opening
    swing -- but not after an ambush, and a missile never for a LIGHT
    weapon (SPUR.COMBAT.S m.attack).
  - "m$ LOST SIGHT OF YOU!" (zs=999) for a Thief/Assassin/Ring wearer.
  - flee_attempt()'s "blocks the path" roll, broken by a hardcoded xp=1.
  - encounters/monster.py's room-entry engagement (try_monster_encounter()
    -> player.pending_engage -> try_monster_engage()), with the tactical
    ambush rolled there once instead of again at fight start.
  - Regular commands at the combat prompt: USE/CAST/... spend the turn,
    INV/STATS/LOOK/HELP are free, movement is refused, QUIT closes.
  - A JSON client's Mode.bye reads as a disconnect at any prompt.

Run with:
    .venv/bin/python3 -m pytest tests/combat/test_monster_initiative.py -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import PlayerClass
from combat.engine import CombatSession, lost_sight_roll
from combat.resolution import AttackResult, MonsterAttackResult, flee_attempt
from flags import PlayerFlags


class _FakePlayer:
    def __init__(self, *, char_class=None, flags=None, ammo_rounds=0, weapon=None,
                 is_expert=False):
        self.name = 'Rulan'
        self.is_expert = is_expert
        self.hit_points = 20
        self.stats = {}
        self.readied_weapon = weapon
        self.ammo_rounds = ammo_rounds
        self.char_class = char_class
        self.unsaved_changes = False
        self.return_key = 'Enter'
        self._flags = flags or {}

    def query_flag(self, flag):
        return bool(self._flags.get(flag, False))


def _harness(responses, *, monster_initiated, player=None, monster=None):
    """Session + ctx whose prompt/monster swing/player swing each log a
    letter into *events* ('P'/'M'/'S'), so tests can assert on order."""
    monster = monster or {'name': 'Troll', 'hit_points': 999, 'to_hit': 4}
    session = CombatSession(monster, room_no=1)
    session.monster_initiated = monster_initiated

    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()

    events: list[str] = []
    it = iter(responses)

    def prompt(*a, **kw):
        events.append('P')
        return next(it, None)
    ctx.prompt = AsyncMock(side_effect=prompt)

    session._try_class_tame = AsyncMock(return_value=False)
    session._check_crystal_pendant = AsyncMock(return_value=None)
    session._check_tactical_ambush = AsyncMock(return_value=None)
    return session, ctx, events


async def _run(session, ctx, events):
    def monster_swing(*a, **kw):
        events.append('M')
        return MonsterAttackResult(hit=False, damage=0)

    def player_swing(*a, **kw):
        events.append('S')
        return AttackResult(hit=False, damage=0)

    with patch('combat.engine.monster_attacks', side_effect=monster_swing), \
         patch.object(session, '_swing', side_effect=player_swing):
        await session._run_loop(ctx)


def _sent(ctx) -> str:
    return '\n'.join(str(c.args[0]) for c in ctx.send.call_args_list if c.args)


class TestRoundOrder(unittest.IsolatedAsyncioTestCase):

    async def test_monster_started_fight_swings_before_first_prompt(self):
        session, ctx, events = _harness(['a', None], monster_initiated=True)
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P', 'S', 'M', 'P'])
        self.assertIn('Troll attacks you!', _sent(ctx))

    async def test_player_started_fight_swings_first(self):
        session, ctx, events = _harness(['a', None], monster_initiated=False)
        await _run(session, ctx, events)
        self.assertEqual(events, ['P', 'S', 'M', 'P'])
        self.assertIn('You face', _sent(ctx))

    async def test_skipping_a_turn_still_gives_the_monster_its_swing(self):
        session, ctx, events = _harness(['x', None], monster_initiated=True)
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P', 'M', 'P'])

    async def test_refused_charge_reprompts_without_a_free_monster_swing(self):
        session, ctx, events = _harness(['c', None], monster_initiated=True)
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P', 'P'])
        self.assertIn('You can not CHARGE now.', _sent(ctx))


class TestFirstStrike(unittest.IsolatedAsyncioTestCase):

    async def test_loaded_missile_preempts_the_opening_swing(self):
        player = _FakePlayer(ammo_rounds=3, weapon=SimpleNamespace(name='LONG BOW'))
        session, ctx, events = _harness(['a', None], monster_initiated=True, player=player)
        await _run(session, ctx, events)
        self.assertEqual(events, ['P', 'S', 'M', 'P'])
        self.assertIn('MISSILE: FIRST STRIKE!', _sent(ctx))

    async def test_light_weapon_never_gets_missile_first_strike(self):
        player = _FakePlayer(ammo_rounds=3, weapon=SimpleNamespace(name='LIGHT SABRE'))
        session, ctx, events = _harness(['a', None], monster_initiated=True, player=player)
        await _run(session, ctx, events)
        self.assertEqual(events[0], 'M')
        self.assertNotIn('FIRST STRIKE', _sent(ctx))

    async def test_ambush_beats_first_strike_and_lands_before_first_prompt(self):
        player = _FakePlayer(ammo_rounds=3, weapon=SimpleNamespace(name='LONG BOW'))
        session, ctx, events = _harness([None], monster_initiated=True, player=player)
        session._ambush_first_strike = True    # enter_combat(ambushed=True)

        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'M', 'P'])   # normal swing + "Surprise attack.."
        self.assertIn('Surprise attack..', _sent(ctx))
        self.assertNotIn('FIRST STRIKE', _sent(ctx))

    async def test_mounted_roll_on_monster_opening_swing_offers_charge(self):
        player = _FakePlayer(flags={PlayerFlags.MOUNTED: True})
        session, ctx, events = _harness([None], monster_initiated=True, player=player)
        with patch('combat.engine._roll_charge_first_strike', return_value=True):
            await _run(session, ctx, events)
        self.assertEqual(events, ['P'])     # first strike -- no monster swing
        preamble = ctx.prompt.await_args_list[0].kwargs['preamble_lines'][0]
        self.assertIn('[C]harge', preamble)
        self.assertIn('Mounted- you manage to get first strike! '
                      '(|command|CHARGE|reset| if you want)', _sent(ctx))

    async def test_charge_hint_hidden_in_expert_mode(self):
        player = _FakePlayer(flags={PlayerFlags.MOUNTED: True}, is_expert=True)
        session, ctx, events = _harness([None], monster_initiated=True, player=player)
        with patch('combat.engine._roll_charge_first_strike', return_value=True):
            await _run(session, ctx, events)
        self.assertIn('Mounted- you manage to get first strike!', _sent(ctx))
        self.assertNotIn('CHARGE', _sent(ctx))

    async def test_failed_mounted_roll_message(self):
        player = _FakePlayer(flags={PlayerFlags.MOUNTED: True})
        session, ctx, events = _harness([None], monster_initiated=True, player=player)
        with patch('combat.engine._roll_charge_first_strike', return_value=False):
            await _run(session, ctx, events)
        self.assertIn("Mounted- oops, didn't get first strike..", _sent(ctx))
        self.assertEqual(events, ['M', 'P'])


class TestLostSight(unittest.IsolatedAsyncioTestCase):

    async def test_thief_slips_out_of_sight_until_attacking_again(self):
        player = _FakePlayer(char_class=PlayerClass.THIEF)
        session, ctx, events = _harness(['x', None], monster_initiated=True, player=player)
        with patch('combat.engine.random.randint', return_value=99):
            await _run(session, ctx, events)
        self.assertNotIn('M', events)
        self.assertEqual(_sent(ctx).count('Troll lost sight of you!'), 2)
        self.assertTrue(session._lost_sight)

    async def test_attacking_clears_lost_sight(self):
        player = _FakePlayer(char_class=PlayerClass.THIEF)
        session, ctx, events = _harness(['a', None], monster_initiated=True, player=player)
        # Lost on the opening swing, found again after the player's attack.
        with patch('combat.engine.random.randint', side_effect=[99, 0]):
            await _run(session, ctx, events)
        self.assertEqual(events, ['P', 'S', 'M', 'P'])

    def test_roll_odds_by_class_and_ring(self):
        ring_wearer = _FakePlayer(flags={PlayerFlags.RING_WORN: True},
                                  char_class=PlayerClass.FIGHTER)
        cases = [
            (_FakePlayer(char_class=PlayerClass.THIEF), 65),
            (_FakePlayer(char_class=PlayerClass.ASSASSIN), 85),
            (ring_wearer, 50),
        ]
        monster = {'name': 'Troll', 'flags': {}}
        for player, z in cases:
            with patch('combat.engine.random.randint', return_value=z):
                self.assertFalse(lost_sight_roll(player, monster))
            with patch('combat.engine.random.randint', return_value=z + 1):
                self.assertTrue(lost_sight_roll(player, monster))

    def test_never_for_other_classes_tough_monsters_or_after_surprise(self):
        thief = _FakePlayer(char_class=PlayerClass.THIEF)
        with patch('combat.engine.random.randint', return_value=99):
            self.assertFalse(lost_sight_roll(_FakePlayer(char_class=PlayerClass.FIGHTER),
                                             {'flags': {}}))
            self.assertFalse(lost_sight_roll(thief, {'flags': {'tough': True}}))
            self.assertFalse(lost_sight_roll(thief, {'flags': {}}, is_surprise=True))


class TestFleeBlock(unittest.TestCase):

    def _player(self, xp_level):
        return SimpleNamespace(hit_points=20, xp_level=xp_level)

    def test_tough_monster_blocks_a_high_level_player(self):
        with patch('combat.resolution.random.randint', return_value=1):
            result = flee_attempt(self._player(30), {'flags': {'tough': True}})
        self.assertTrue(result.blocked_by_monster)

    def test_ordinary_monster_never_blocks(self):
        with patch('combat.resolution.random.randint', return_value=1):
            result = flee_attempt(self._player(30), {'flags': {}})
        self.assertTrue(result.escaped)

    def test_low_level_player_is_never_blocked(self):
        # xp//3 == 1, and rnd.10z is 1-10 -- z<1 can't happen.
        with patch('combat.resolution.random.randint', return_value=1):
            result = flee_attempt(self._player(3), {'flags': {'tough': True}})
        self.assertTrue(result.escaped)

    def test_monster_that_lost_sight_cannot_block(self):
        with patch('combat.resolution.random.randint', return_value=1):
            result = flee_attempt(self._player(30), {'flags': {'tough': True}},
                                  monster_is_following=False)
        self.assertTrue(result.escaped)


# ---------------------------------------------------------------------------
# Room-entry engagement (encounters/monster.py)
# ---------------------------------------------------------------------------

def _engage_ctx(*, monster_flags=None, monster_no=5, char_class=None, char_race='Human',
                room_no=2, pending=True):
    monster = {'number': monster_no, 'name': 'TROLL', 'to_hit': 4, 'strength': 10,
               'flags': monster_flags or {}}
    room = SimpleNamespace(monster=monster_no, flags=[])
    player = SimpleNamespace(
        name='Rulan', map_level=1, hit_points=20, char_class=char_class,
        char_race=char_race, dead_monsters=[], charmed_monsters=[], fled_monsters=[],
        pending_engage=({'level': 1, 'room_no': room_no, 'monster_number': monster_no}
                        if pending else None),
        query_flag=lambda flag: False,
    )
    ctx = MagicMock()
    ctx.player = player
    ctx.client = SimpleNamespace(room=room_no)
    ctx.server = SimpleNamespace(
        monsters=[monster], active_combats={},
        game_map=SimpleNamespace(get_room=lambda level, n: room if n == room_no else None),
    )
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx, monster


class TestTryMonsterEngage(unittest.IsolatedAsyncioTestCase):

    async def test_queued_monster_starts_a_monster_initiated_fight(self):
        from encounters.monster import try_monster_engage
        ctx, monster = _engage_ctx()
        with patch('combat.engine.enter_combat', new=AsyncMock()) as enter:
            await try_monster_engage(ctx)
        enter.assert_awaited_once()
        self.assertTrue(enter.await_args.kwargs['monster_initiated'])
        self.assertIsNone(ctx.player.pending_engage)

    async def test_stale_queue_for_another_room_is_dropped(self):
        from encounters.monster import try_monster_engage
        ctx, _ = _engage_ctx()
        ctx.player.pending_engage['room_no'] = 99
        with patch('combat.engine.enter_combat', new=AsyncMock()) as enter:
            await try_monster_engage(ctx)
        enter.assert_not_awaited()
        self.assertIsNone(ctx.player.pending_engage)

    async def test_monster_already_killed_does_not_engage(self):
        from encounters.monster import try_monster_engage
        ctx, _ = _engage_ctx()
        ctx.player.dead_monsters = [5]
        with patch('combat.engine.enter_combat', new=AsyncMock()) as enter:
            await try_monster_engage(ctx)
        enter.assert_not_awaited()

    async def test_thief_slips_past_unnoticed(self):
        from encounters.monster import try_monster_engage
        ctx, _ = _engage_ctx(char_class=PlayerClass.THIEF)
        with patch('combat.engine.enter_combat', new=AsyncMock()) as enter, \
             patch('combat.engine.random.randint', return_value=99):
            await try_monster_engage(ctx)
        enter.assert_not_awaited()
        ctx.send.assert_awaited_with('The TROLL lost sight of you!')


class TestWhoEngages(unittest.IsolatedAsyncioTestCase):

    def test_charmable_friendly_and_tada_npcs_never_engage(self):
        from encounters.monster import _monster_engages
        ctx, monster = _engage_ctx()
        self.assertTrue(_monster_engages(ctx, monster, 5))
        self.assertFalse(_monster_engages(ctx, {'flags': {'charmable': True}}, 120))
        self.assertFalse(_monster_engages(ctx, monster, 136))   # WILD HORSE
        self.assertFalse(_monster_engages(ctx, monster, 137))   # THE DWARF
        elf_ctx, _ = _engage_ctx(char_race='Elf')
        self.assertFalse(_monster_engages(elf_ctx, {'flags': {'good': True}}, 5))

    async def test_mechanical_monster_skips_rolls_but_still_engages(self):
        from encounters.monster import try_monster_encounter
        ctx, _ = _engage_ctx(monster_flags={'mechanical': True}, pending=False)
        with patch('combat.engine.roll_tactical_ambush', new=AsyncMock(return_value=False)):
            await try_monster_encounter(ctx, level=1, room_no=2)
        self.assertEqual(ctx.player.pending_engage,
                         {'level': 1, 'room_no': 2, 'monster_number': 5, 'ambushed': False})



# ---------------------------------------------------------------------------
# Regular commands at the combat prompt (USE/CAST/...)
# ---------------------------------------------------------------------------

class _FakeProcessor:
    """find_command()/process_input() stand-in: *names* maps a typed word
    to a canonical command name; *on_run* is called with the session's
    ctx as the "command" runs."""
    def __init__(self, names, on_run=None, data=None):
        self.names = names
        self.on_run = on_run
        self.data = data or {}
        self.ran = []

    def find_command(self, token):
        name = self.names.get(token.lower())
        return (SimpleNamespace(name=name) if name else None), False

    async def process_input(self, text, ctx=None):
        self.ran.append(text)
        if self.on_run:
            self.on_run(ctx)
        return SimpleNamespace(data=dict(self.data), success=True)


_NAMES = {'use': 'use', 'cast': 'cast', 'inv': 'inv', 'i': 'inv', 'quit': 'quit',
          'n': 'go', 'say': 'say'}


def _dispatch_harness(responses, **proc_kw):
    session, ctx, events = _harness(responses, monster_initiated=True)
    processor = _FakeProcessor(_NAMES, **proc_kw)
    ctx.client = SimpleNamespace(command_processor=processor, room=1)
    ctx.player.map_level = 1
    session.attackers = [ctx]
    return session, ctx, events, processor


class TestCommandsMidFight(unittest.IsolatedAsyncioTestCase):

    async def test_use_spends_the_turn(self):
        session, ctx, events, proc = _dispatch_harness(['use potion', None])
        await _run(session, ctx, events)
        self.assertEqual(proc.ran, ['use potion'])
        self.assertEqual(events, ['M', 'P', 'M', 'P'])

    async def test_cast_is_a_command_not_a_charge(self):
        session, ctx, events, proc = _dispatch_harness(['cast', None])
        await _run(session, ctx, events)
        self.assertEqual(proc.ran, ['cast'])
        self.assertNotIn('CHARGE', _sent(ctx))

    async def test_inventory_is_free(self):
        session, ctx, events, proc = _dispatch_harness(['i', None])
        await _run(session, ctx, events)
        self.assertEqual(proc.ran, ['i'])
        self.assertEqual(events, ['M', 'P', 'P'])

    async def test_movement_is_refused_for_free(self):
        session, ctx, events, proc = _dispatch_harness(['n', None])
        await _run(session, ctx, events)
        self.assertEqual(proc.ran, [])
        self.assertEqual(events, ['M', 'P', 'P'])
        self.assertIn("You can't do that in the middle of a fight!", _sent(ctx))

    async def test_unknown_word_is_huh_for_free(self):
        session, ctx, events, proc = _dispatch_harness(['xyzzy', None])
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P', 'P'])
        self.assertIn('Huh?', _sent(ctx))

    async def test_confirmed_quit_ends_the_fight_and_closes(self):
        session, ctx, events, proc = _dispatch_harness(['quit', 'a'], data={'quit': True})
        ctx.closing = False
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P'])     # no further prompt or swing
        self.assertTrue(ctx.closing)
        self.assertTrue(session._done.is_set())

    async def test_spell_that_kills_the_monster_ends_the_fight(self):
        session, ctx, events, proc = _dispatch_harness(
            ['cast', 'a'], on_run=lambda c: session._done.set())
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P'])

    async def test_teleporting_away_leaves_the_fight(self):
        def teleport(c):
            c.client.room = 77
        session, ctx, events, proc = _dispatch_harness(['use amulet', 'a'], on_run=teleport)
        await _run(session, ctx, events)
        self.assertEqual(events, ['M', 'P'])
        self.assertNotIn(ctx, session.attackers)
        self.assertTrue(session._done.is_set())


# ---------------------------------------------------------------------------
# bye during a prompt (network_context.GameContext.prompt)
# ---------------------------------------------------------------------------

class TestByeClosesPrompts(unittest.IsolatedAsyncioTestCase):

    def _ctx(self, raw_lines):
        from network_context import GameContext
        reader = MagicMock()
        reader.readline = AsyncMock(side_effect=raw_lines)
        server = MagicMock()
        server.send_message = AsyncMock()
        player = _FakePlayer()
        player.pending_pages = []
        ctx = GameContext(player=player, reader=reader, writer=MagicMock(),
                          server=server, client=MagicMock())
        return ctx, reader

    async def test_bye_reads_as_disconnect_and_sticks(self):
        ctx, reader = self._ctx([b'{"lines": [], "mode": "bye"}\n'])
        self.assertIsNone(await ctx.prompt('Command'))
        self.assertTrue(ctx.closing)
        # Later prompts don't even read -- the client is gone.
        self.assertIsNone(await ctx.prompt('main'))
        self.assertEqual(reader.readline.await_count, 1)

    async def test_ordinary_blank_answer_is_still_blank(self):
        ctx, _ = self._ctx([b'{"lines": [""], "mode": "app"}\n'])
        self.assertEqual(await ctx.prompt('Command'), '')
        self.assertFalse(ctx.closing)


# ---------------------------------------------------------------------------
# Tactical ambush: rolled once, on room entry
# ---------------------------------------------------------------------------

class TestTacticalOncePerEncounter(unittest.IsolatedAsyncioTestCase):

    async def test_room_entry_rolls_tactical_once_and_carries_the_ambush(self):
        from encounters.monster import try_monster_encounter, try_monster_engage
        ctx, _ = _engage_ctx(pending=False)
        with patch('encounters.monster._try_surprise', new=AsyncMock(return_value=False)), \
             patch('encounters.monster._try_spontaneous_charm', new=AsyncMock(return_value=False)), \
             patch('encounters.ringwraith.try_recognition_scene', new=AsyncMock(return_value=False)), \
             patch('combat.engine.roll_tactical_ambush', new=AsyncMock(return_value=True)) as tactical:
            await try_monster_encounter(ctx, level=1, room_no=2)
        tactical.assert_awaited_once()
        self.assertTrue(ctx.player.pending_engage['ambushed'])

        with patch('combat.engine.enter_combat', new=AsyncMock()) as enter:
            await try_monster_engage(ctx)
        self.assertTrue(enter.await_args.kwargs['ambushed'])

    async def test_surprised_monster_gets_no_tactical_roll(self):
        from encounters.monster import try_monster_encounter
        ctx, _ = _engage_ctx(pending=False)
        with patch('encounters.monster._try_surprise', new=AsyncMock(return_value=True)), \
             patch('encounters.ringwraith.try_recognition_scene', new=AsyncMock(return_value=False)), \
             patch('combat.engine.roll_tactical_ambush', new=AsyncMock()) as tactical:
            await try_monster_encounter(ctx, level=1, room_no=2)
        tactical.assert_not_awaited()
        self.assertIsNone(ctx.player.pending_engage)

    async def test_fight_start_no_longer_rolls_tactical(self):
        session, ctx, events = _harness([None], monster_initiated=True)
        session._check_tactical_ambush = AsyncMock()
        await _run(session, ctx, events)
        session._check_tactical_ambush.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
