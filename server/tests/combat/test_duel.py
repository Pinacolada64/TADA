"""tests/test_duel.py — live tactic-loop SPORT DUEL tests.

Covers combat/duel.py's DuelSession (pure player-object mutation, no ctx
I/O beyond a fake .send()) and guild_standings.py's tally persistence.
DuelCommand's challenge/accept/tactic UX is exercised indirectly through
DuelSession here; full command-level bot testing is done live (see
session notes), not duplicated as unit tests for this rough draft.
"""
from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import (
    DuelSession, DuelTactic, _is_predictable, _offense_rating, _STREAK_LEN,
)
from item_system import ItemType
from items import Item, ItemCategory, Weapon
from player import Player

# Note: a decisive DuelSession._end() sends the loser a mail notice
# (mail.add_system_message(), see combat/duel.py) -- tests/conftest.py's
# session-scoped _isolate_mail_dir autouse fixture keeps that out of the
# real run/server/mail/ directory, no per-file patching needed here.


class _FakeClient:
    def __init__(self, room):
        self.room = room
        self.ctx = None


class _FakeServer:
    def __init__(self):
        self.clients: dict = {}


class _FakeCtx:
    def __init__(self, server=None, client=None):
        self.sent: list = []
        self.server = server
        self.client = client

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name, *, char_class=PlayerClass.FIGHTER, char_race=PlayerRace.HUMAN,
                   hit_points=30, weapon_number=1):
    p = Player(name=name, id=name.lower())
    p.char_class = char_class
    p.char_race = char_race
    p.hit_points = hit_points
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=weapon_number, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session():
    a = _make_duelist('Ardent')
    b = _make_duelist('Belwin')
    session = DuelSession(a, _FakeCtx(), b, _FakeCtx())
    return session, a, b


class TestOffenseRating(unittest.TestCase):
    def test_no_weapon_still_returns_a_rating(self):
        p = _make_duelist('Rulan')
        self.assertGreaterEqual(_offense_rating(p, None), 3)

    def test_rating_is_clamped_3_to_9(self):
        p = _make_duelist('Rulan')
        rating = _offense_rating(p, p.readied_weapon)
        self.assertGreaterEqual(rating, 3)
        self.assertLessEqual(rating, 9)


class TestBashKnockdownBands(unittest.TestCase):
    """SPUR.DUEL.S:424-484 "tac.bash", full re-port: a wide advantage score
    `a` (clamped 60-140) compared against a d100+50 roll in three bands.
    Both duelists' shields are equalized (30/30) and races left at the
    default HUMAN (carrying-capacity 10, no size term) so each test can
    isolate a single term by patching random.randint (the only randint
    call left in _resolve_bash is the final roll)."""

    def _bare(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        # Player() rolls random stats -- equalize EGY/DEX/STR so the
        # mismatch terms (DUEL.S:456-463) don't perturb these tests.
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.PARRY
        return session, a, b, side_a, side_b

    def test_bare_advantage_is_100(self):
        # shield terms cancel (30/3 - 30/3=0), size terms cancel (equal
        # race), +10 base bash, -10 opp-parries = net 100 (_BASH_BASE).
        session, a, b, side_a, side_b = self._bare()
        with patch('random.randint', return_value=50):  # roll = 100
            session._resolve_bash_contest()
        self.assertFalse(side_b.down)
        self.assertFalse(side_a.down)

    def test_high_roll_overextends_the_basher(self):
        session, a, b, side_a, side_b = self._bare()
        with patch('random.randint', return_value=71):  # roll = 121 > 100+20
            session._resolve_bash_contest()
        self.assertTrue(side_a.down)
        self.assertFalse(side_b.down)

    def test_low_roll_knocks_down_the_defender(self):
        session, a, b, side_a, side_b = self._bare()
        with patch('random.randint', return_value=29):  # roll = 79 < 100-20
            session._resolve_bash_contest()
        self.assertTrue(side_b.down)
        self.assertFalse(side_a.down)


def _give_shield(player, condition):
    shield = Item(id_number=4, name='small shield', category=ItemCategory.ITEM)
    shield.type = ItemType.SHIELD
    shield.condition = condition
    player.inventory.add(shield)
    player.active_shield_id = 4
    player.shield = condition


class TestBashShieldCost(unittest.TestCase):
    def test_bashing_always_degrades_the_basher_shield(self):
        """DUEL.S:434 'sh=sh-3' -- costs the basher shield whether the
        bash lands or not."""
        session, a, b = _make_session()
        _give_shield(a, 30)
        b.shield = 30
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.ATTACK
        with patch('random.randint', return_value=1):
            session._resolve_bash_contest()
        self.assertEqual(a.shield, 27)

    def test_shield_floors_at_zero(self):
        session, a, b = _make_session()
        _give_shield(a, 2)
        b.shield = 0
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.ATTACK
        with patch('random.randint', return_value=1):
            session._resolve_bash_contest()
        self.assertEqual(a.shield, 0)


class TestBashMinimumShield(unittest.IsolatedAsyncioTestCase):
    async def test_bash_refused_below_minimum_shield(self):
        from combat.duel import _submit_tactic
        session, a, b = _make_session()
        a.shield = 5
        a.active_duel = session
        ctx = _FakeCtx()
        ctx.player = a
        result = await _submit_tactic(ctx, DuelTactic.BASH)
        self.assertFalse(result.success)
        self.assertIn('Not enough shield', _flat(ctx))
        self.assertIsNone(session.side_for(a).tactic)

    async def test_bash_allowed_at_minimum_shield(self):
        from combat.duel import _submit_tactic
        session, a, b = _make_session()
        a.shield = 6
        a.active_duel = session
        ctx = _FakeCtx()
        ctx.player = a
        result = await _submit_tactic(ctx, DuelTactic.BASH)
        self.assertTrue(result.success)


class TestBashSizeDifferential(unittest.TestCase):
    """DUEL.S:438/441: carrying-capacity (size proxy) differential --
    against a non-parrying opponent, the larger side benefits."""

    def test_larger_carrying_capacity_favors_the_basher(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        a.char_race = PlayerRace.HUMAN   # capacity 10
        b.char_race = PlayerRace.PIXIE   # capacity 7
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.ATTACK
        with patch('random.randint', return_value=1):  # lowest possible roll
            session._resolve_bash_contest()
        self.assertTrue(side_b.down)


class TestBashPredictability(unittest.TestCase):
    """DUEL.S:448 'if zz=3 a=(a-10)-(zp*3)': a bash-heavy streak makes
    bashing into a parry less effective."""

    def test_bash_streak_reduces_advantage_against_parry(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.PARRY
        side_a.bash_streak = 4   # -12 vs. a fresh bash's advantage of 100
        # bare advantage (no streak) is 100; streak drops it to 88, so a
        # roll that would've been a clean whiff at 100 now overextends.
        with patch('random.randint', return_value=59):  # roll = 109 > 88+20
            session._resolve_bash_contest()
        self.assertTrue(side_a.down)


class TestBashStatMismatch(unittest.TestCase):
    def test_strength_gap_favors_the_stronger_basher(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        a.stats[PlayerStat.STR] = 18
        b.stats[PlayerStat.STR] = 10
        a.stats[PlayerStat.DEX] = b.stats[PlayerStat.DEX] = 10
        a.stats[PlayerStat.EGY] = b.stats[PlayerStat.EGY] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = DuelTactic.BASH
        side_b.tactic = DuelTactic.PARRY
        # bare advantage 100, +10 STR mismatch (18 > 10+4) = 110.
        with patch('random.randint', return_value=61):  # roll = 111 > 110? no -- pick a clean whiff check instead
            session._resolve_bash_contest()
        self.assertFalse(side_a.down)
        self.assertFalse(side_b.down)


class TestBashDefenderMirrorModifiers(unittest.TestCase):
    """DUEL.S:450-454: modifiers keyed on the *defending* side's own
    reaction to an incoming bash (previously unported -- the old
    per-basher-only framing could never reach a non-BASH side.tactic).
    Here self.b bashes and self.a reacts, isolating each reaction's term
    via the verified advantage values: standing or attacking into a bash
    both net 80 (100 - 10 opponent-bashed - 10 own-reaction), a bare
    parry nets a full 100 (the two +/-10 terms cancel)."""

    def _reacting(self, a_tactic, **streaks):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_b.tactic = DuelTactic.BASH
        side_a.tactic = a_tactic
        for name, value in streaks.items():
            setattr(side_a, name, value)
        return session, a, b, side_a, side_b

    def test_standing_into_a_bash_costs_advantage(self):
        session, a, b, side_a, side_b = self._reacting(DuelTactic.STAND)
        # advantage 80 (100 - 10 opp-bashed - 10 own-stand); a roll that
        # would've been a clean whiff at 100 now knocks the standing side
        # (self.a) down.
        with patch('random.randint', return_value=51):  # roll = 101 > 80+20
            session._resolve_bash_contest()
        self.assertTrue(side_a.down)

    def test_parrying_a_bash_is_safer_than_standing(self):
        # Same roll as above (101), but reacting with Parry instead of
        # Stand nets the full 100 (the opponent-bashed/own-parry terms
        # cancel) -- 101 no longer clears 100+20, so nobody falls.
        session, a, b, side_a, side_b = self._reacting(DuelTactic.PARRY)
        with patch('random.randint', return_value=51):
            session._resolve_bash_contest()
        self.assertFalse(side_a.down)
        self.assertFalse(side_b.down)

    def test_predictable_attacker_reacting_into_a_bash_is_worse(self):
        # Attacking into a bash (advantage 80, same as Stand) gets worse
        # the more of a habitual attacker self.a has been recently
        # (DUEL.S:452's zn*3 term) -- a fresh attacker (streak 0) nets 80,
        # a 2-in-a-row attacker nets 74.
        session, a, b, side_a, side_b = self._reacting(DuelTactic.ATTACK, attack_streak=2)
        with patch('random.randint', return_value=45):  # roll = 95 > 74+20, but not > 80+20
            session._resolve_bash_contest()
        self.assertTrue(side_a.down)


class TestBashMutual(unittest.TestCase):
    """DUEL.S:443+444 fire as independent `if` statements, not mutually
    exclusive -- when both sides bash, each side's own always-true +10
    (444) and the opponent-bashed -10 (443) cancel, leaving only the
    parry-streak term (there is none to bash-vs-bash, only parry-vs-bash
    per DUEL.S:448) -- net advantage is the bare 100 baseline, adjusted
    only by self.a's own parry_streak."""

    def test_mutual_bash_cancels_to_bare_streak_only(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = side_b.tactic = DuelTactic.BASH
        side_a.parry_streak = 3
        # advantage 100 - 3*3 = 91 (both sides' always-true +/-10 terms
        # cancel on a mutual bash, leaving only self.a's own streak
        # penalty). A roll of 92 clears neither band (91+-20 = 71-111).
        with patch('random.randint', return_value=42):  # roll = 92
            session._resolve_bash_contest()
        self.assertFalse(side_a.down)
        self.assertFalse(side_b.down)

    def test_both_bashers_pay_the_shield_cost(self):
        session, a, b = _make_session()
        _give_shield(a, 30)   # separate players, separate inventories --
        _give_shield(b, 30)   # same item id (4) in each is fine.
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.tactic = side_b.tactic = DuelTactic.BASH
        with patch('random.randint', return_value=1):
            session._resolve_bash_contest()
        self.assertEqual(a.shield, 27)
        self.assertEqual(b.shield, 27)


class TestBashDefenderStillSwings(unittest.IsolatedAsyncioTestCase):
    """The basher's own _resolve_swing() this round is a no-op (their turn
    is fully spent on the bash contest, resolved ahead of the per-side
    loop in _resolve_round()) -- but a defender who reacted with anything
    else still gets their own ordinary swing afterward unless the contest
    itself just knocked them down."""

    async def test_defender_reaction_produces_its_own_swing_commentary(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_a.verbose = True
        side_b.tactic = DuelTactic.BASH
        side_a.tactic = DuelTactic.PARRY
        # advantage 100 (opp-bashed/own-parry terms cancel); roll 100 is a
        # clean whiff, so self.a survives the contest and reaches its own
        # _resolve_swing() call this round.
        with patch('random.randint', return_value=50):
            await session._resolve_round()
        self.assertFalse(side_a.down)
        commentary = '\n'.join(session._commentary)
        self.assertIn('bash contest', commentary)
        self.assertIn('strike chance mod', commentary)

    async def test_basher_gets_no_swing_commentary_of_their_own(self):
        from base_classes import PlayerStat
        session, a, b = _make_session()
        a.shield = b.shield = 30
        for stat in (PlayerStat.EGY, PlayerStat.DEX, PlayerStat.STR):
            a.stats[stat] = b.stats[stat] = 10
        side_a, side_b = session.side_for(a), session.side_for(b)
        side_b.tactic = DuelTactic.BASH
        side_a.tactic = DuelTactic.PARRY
        with patch('random.randint', return_value=50):
            await session._resolve_round()
        # Only one "strike chance mod" line this round -- self.a's swing.
        # The basher (self.b) never reaches _swing() on their own turn.
        strikes = sum('strike chance mod' in line for line in session._commentary)
        self.assertEqual(strikes, 1)


class TestPredictability(unittest.TestCase):
    def test_not_predictable_below_streak_len(self):
        history = [DuelTactic.ATTACK] * (_STREAK_LEN - 1)
        self.assertFalse(_is_predictable(history, DuelTactic.ATTACK))

    def test_predictable_at_streak_len(self):
        history = [DuelTactic.ATTACK] * _STREAK_LEN
        self.assertTrue(_is_predictable(history, DuelTactic.ATTACK))

    def test_mixed_history_not_predictable(self):
        history = [DuelTactic.ATTACK, DuelTactic.PARRY, DuelTactic.ATTACK]
        self.assertFalse(_is_predictable(history, DuelTactic.ATTACK))


class TestDuelSessionSubmit(unittest.IsolatedAsyncioTestCase):
    async def test_first_submission_waits_for_opponent(self):
        session, a, b = _make_session()
        await session.submit(a, DuelTactic.ATTACK)
        self.assertEqual(a.hit_points, 30)
        self.assertEqual(b.hit_points, 30)
        self.assertIn('Waiting for Belwin', ' '.join(str(x) for x in session.a.ctx.sent))

    async def test_second_submission_resolves_round(self):
        session, a, b = _make_session()
        await session.submit(a, DuelTactic.ATTACK)
        await session.submit(b, DuelTactic.PARRY)
        # Round resolved: both tactics cleared, round advanced.
        self.assertIsNone(session.a.tactic)
        self.assertIsNone(session.b.tactic)
        self.assertEqual(session.round_num, 2 if not session.done else session.round_num)

    async def test_duel_ends_when_someone_dies(self):
        session, a, b = _make_session()
        b.hit_points = 1
        # Force a guaranteed hit by stacking dice heavily via repeated rounds.
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)

    async def test_active_duel_cleared_on_both_players_when_done(self):
        session, a, b = _make_session()
        a.active_duel = session
        b.active_duel = session
        b.hit_points = 1
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertIsNone(a.active_duel)
        self.assertIsNone(b.active_duel)

    async def test_loser_left_at_min_hp_not_dead(self):
        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        loser = a if a.hit_points <= 0 or a.hit_points == 15 else b
        # Whichever side actually lost should be sitting at exactly 15 HP.
        self.assertIn(15, (a.hit_points, b.hit_points))


class TestPersonalDuelRecordAndBattleLog(unittest.IsolatedAsyncioTestCase):
    """DuelSession._end()'s personal win/loss counters (SPUR.DUEL2.S's
    "personal" label, distinct from guild_standings.py's guild tally) and
    its net_common.append_battle_log() calls on decisive win/loss and on
    a successful flee (SPUR's "news" label, previously only wired up for
    GROVEL)."""

    async def test_winner_and_loser_records_increment(self):
        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        winner, loser = (a, b) if b.hit_points == 15 else (b, a)
        self.assertEqual(winner.duel_wins, 1)
        self.assertEqual(loser.duel_losses, 1)
        self.assertEqual(winner.duel_losses, 0)
        self.assertEqual(loser.duel_wins, 0)

    async def test_loser_left_unconscious_naming_the_winner(self):
        from flags import PlayerFlags

        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        winner, loser = (a, b) if b.hit_points == 15 else (b, a)
        self.assertTrue(loser.query_flag(PlayerFlags.UNCONSCIOUS))
        self.assertEqual(loser.defeated_by, winner.name)
        self.assertFalse(winner.query_flag(PlayerFlags.UNCONSCIOUS))

    async def test_repeated_wins_accumulate(self):
        session, a, b = _make_session()
        a.duel_wins = 4
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertEqual(a.duel_wins, 5)

    async def test_decisive_win_appends_battle_log_entry(self):
        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log') as log:
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        log.assert_called_once()
        (entry,), _kwargs = log.call_args
        self.assertIn('defeated', entry)
        self.assertIn(b.name, entry)  # loser named regardless of who actually won

    async def test_flee_appends_battle_log_entry(self):
        session, a, b = _make_session()
        with patch('combat.duel.net_common.append_battle_log') as log, \
             patch('random.randint', return_value=100):  # guarantee the escape roll succeeds
            await session.submit(a, DuelTactic.FLEE)
            await session.submit(b, DuelTactic.ATTACK)
        log.assert_called_once()
        (entry,), _kwargs = log.call_args
        self.assertIn('FLED', entry)
        self.assertIn(a.name, entry)
        self.assertIn(b.name, entry)


class TestDuelResultMailNotice(unittest.IsolatedAsyncioTestCase):
    """DuelSession._end() mails the loser a result notice (SPUR.DUEL2.S's
    sendmail label) -- see combat/duel.py. tests/conftest.py's
    _isolate_mail_dir autouse fixture keeps this out of the real
    run/server/mail/ directory, but it's session-scoped (one shared dir
    for the whole run) -- these tests assert exact mailbox contents, so
    each one needs its own fresh mailbox, not one accumulating messages
    from every other test that happens to reuse 'Ardent'/'Belwin'."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self._patcher = patch('mail.MAIL_DIR', Path(self._tmp.name))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_loser_gets_a_mail_notice(self):
        import mail

        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        winner, loser = (a, b) if b.hit_points == 15 else (b, a)

        inbox = mail.load_mailbox(loser.name)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['from'], mail.SYSTEM_SENDER)
        self.assertIn(f'defeated by {winner.name}', inbox[0]['body'])

    async def test_winner_gets_no_mail_notice(self):
        import mail

        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        winner, _loser = (a, b) if b.hit_points == 15 else (b, a)

        self.assertEqual(mail.load_mailbox(winner.name), [])

    async def test_mail_notes_stolen_silver(self):
        import mail
        from base_classes import PlayerMoneyTypes

        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        b.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 50)
        with patch('combat.duel.net_common.append_battle_log'):
            for _ in range(50):
                if session.done:
                    break
                await session.submit(a, DuelTactic.ATTACK)
                await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        _winner, loser = (a, b) if b.hit_points == 15 else (b, a)

        inbox = mail.load_mailbox(loser.name)
        self.assertIn('50 silver', inbox[0]['body'])


class TestChallengeBlockedWhenUnconscious(unittest.IsolatedAsyncioTestCase):
    """SPUR.DUEL2.S chlng2: "You can't duel unconcious people!" --
    combat/duel.py's _send_challenge()."""

    async def test_cannot_challenge_an_unconscious_player(self):
        from combat.duel import _send_challenge
        from flags import PlayerFlags

        challenger = _make_duelist('Ardent')
        target = _make_duelist('Belwin')
        target.set_flag(PlayerFlags.UNCONSCIOUS)
        ctx = _FakeCtx()
        ctx.player = challenger
        target_ctx = _FakeCtx()
        target_ctx.player = target

        result = await _send_challenge(ctx, target_ctx)
        self.assertFalse(result.success)
        self.assertIn("unconscious", _flat(ctx).lower())
        self.assertIsNone(getattr(target, 'pending_duel_challenge', None))

    async def test_can_challenge_a_conscious_player(self):
        from combat.duel import _send_challenge

        challenger = _make_duelist('Ardent')
        target = _make_duelist('Belwin')
        ctx = _FakeCtx()
        ctx.player = challenger
        target_ctx = _FakeCtx()
        target_ctx.player = target

        result = await _send_challenge(ctx, target_ctx)
        self.assertTrue(result.success)
        self.assertEqual(target.pending_duel_challenge, challenger.name)


class TestBystanderBroadcast(unittest.IsolatedAsyncioTestCase):
    """DuelSession._broadcast_bystanders() -- terse room-wide updates for
    players watching a duel who aren't in it (Ryan: "what about
    broadcasting this to bystanders in the room through ctx.send_room()")."""

    def _build(self):
        server = _FakeServer()
        a = _make_duelist('Ardent')
        b = _make_duelist('Belwin')
        client_a = _FakeClient(room=1)
        client_b = _FakeClient(room=1)
        client_bystander = _FakeClient(room=1)
        ctx_a = _FakeCtx(server=server, client=client_a)
        ctx_b = _FakeCtx(server=server, client=client_b)
        ctx_bystander = _FakeCtx(server=server, client=client_bystander)
        client_a.ctx = ctx_a
        client_b.ctx = ctx_b
        client_bystander.ctx = ctx_bystander
        server.clients = {'a': client_a, 'b': client_b, 'c': client_bystander}
        session = DuelSession(a, ctx_a, b, ctx_b)
        return session, ctx_a, ctx_b, ctx_bystander

    async def test_bystander_in_room_receives_terse_note(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertIn('Ardent and Belwin begin a duel!', _flat(ctx_bystander))

    async def test_duelists_are_excluded_from_their_own_broadcast(self):
        session, ctx_a, ctx_b, _ctx_bystander = self._build()
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertEqual(ctx_a.sent, [])
        self.assertEqual(ctx_b.sent, [])

    async def test_bystander_in_a_different_room_is_not_notified(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        ctx_bystander.client.room = 99
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertEqual(ctx_bystander.sent, [])

    async def test_round_resolution_broadcasts_a_terse_note(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        await session.submit(session.a.player, DuelTactic.ATTACK)
        await session.submit(session.b.player, DuelTactic.PARRY)
        # Terse note present, but not the full "--- Round N ---" detail.
        self.assertTrue(len(ctx_bystander.sent) > 0)
        self.assertNotIn('--- Round', _flat(ctx_bystander))


class TestGuildStandings(unittest.TestCase):
    def setUp(self):
        import guild_standings
        self._orig_file = guild_standings._STANDINGS_FILE
        guild_standings._STANDINGS_FILE = Path('run') / 'server' / 'test_guild_standings.json'
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()

    def tearDown(self):
        import guild_standings
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()
        guild_standings._STANDINGS_FILE = self._orig_file

    def test_record_duel_result_increments_both_sides(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 1)
        self.assertEqual(standings['Iron Fist']['losses'], 1)

    def test_repeated_results_accumulate(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 2)
        self.assertEqual(standings['Iron Fist']['losses'], 2)


if __name__ == '__main__':
    unittest.main()
