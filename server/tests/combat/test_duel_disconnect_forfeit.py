"""tests/combat/test_duel_disconnect_forfeit.py — combat/duel.py's
DuelSession.forfeit() (SPUR.DUEL.S's "dropped" label): a duelist who
disconnects mid-fight is treated as an automatic loss, same consequences
as being defeated fairly, with the win notice pushed straight to the
still-connected opponent.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import DuelSession
from items import Weapon
from player import Player

# Note: forfeit() -> _end() sends the loser a mail notice
# (mail.add_system_message(), see combat/duel.py) -- tests/conftest.py's
# session-scoped _isolate_mail_dir autouse fixture keeps that out of the
# real run/server/mail/ directory, no per-file patching needed here.


class _FakeCtx:
    def __init__(self):
        self.sent: list = []
        self.server = None
        self.client = None

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name, *, hit_points=30):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.hit_points = hit_points
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session():
    a = _make_duelist('Ardent')
    b = _make_duelist('Belwin')
    ctx_a, ctx_b = _FakeCtx(), _FakeCtx()
    session = DuelSession(a, ctx_a, b, ctx_b)
    a.active_duel = session
    b.active_duel = session
    return session, a, b, ctx_a, ctx_b


class TestDuelForfeit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # This class asserts exact mailbox contents (a disconnected
        # loser's forfeit-notice mail); tests/conftest.py's
        # _isolate_mail_dir autouse fixture is session-scoped (one dir
        # shared for the whole run) and 'Ardent'/'Belwin' are reused by
        # other duel test files too, so give this class its own fresh
        # mailbox rather than asserting against accumulated messages.
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self._patcher = patch('mail.MAIL_DIR', Path(self._tmp.name))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    async def test_forfeit_marks_duel_done(self):
        session, a, b, _ctx_a, _ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)
        self.assertTrue(session.done)

    async def test_disconnecting_player_loses_active_duel_and_hp(self):
        session, a, b, _ctx_a, _ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)
        self.assertIsNone(a.active_duel)
        self.assertIsNone(b.active_duel)
        self.assertEqual(a.hit_points, 15)  # _MIN_HP_AFTER_LOSS, same as a fair loss

    async def test_opponent_gets_the_win_and_personal_record(self):
        session, a, b, _ctx_a, ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)
        self.assertEqual(b.duel_wins, 1)
        self.assertEqual(a.duel_losses, 1)
        self.assertIn('forfeit', _flat(ctx_b).lower())

    async def test_disconnected_players_ctx_is_never_sent_to(self):
        session, a, b, ctx_a, ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)
        self.assertEqual(ctx_a.sent, [])
        self.assertNotEqual(ctx_b.sent, [])

    async def test_either_side_can_be_the_one_that_disconnects(self):
        session, a, b, ctx_a, _ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(b)
        self.assertEqual(a.duel_wins, 1)
        self.assertEqual(b.duel_losses, 1)
        self.assertIn('forfeit', _flat(ctx_a).lower())

    async def test_battle_log_notes_the_disconnect(self):
        session, a, b, _ctx_a, _ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log') as log:
            await session.forfeit(a)
        log.assert_called_once()
        (entry,), _kwargs = log.call_args
        self.assertIn('disconnected', entry.lower())
        self.assertIn(a.name, entry)
        self.assertIn(b.name, entry)

    async def test_disconnected_loser_gets_a_mail_notice(self):
        import mail

        session, a, b, _ctx_a, _ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)
        inbox = mail.load_mailbox(a.name)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['from'], mail.SYSTEM_SENDER)
        self.assertIn('disconnected', inbox[0]['body'].lower())
        self.assertIn(b.name, inbox[0]['body'])

    async def test_forfeit_is_a_no_op_if_duel_already_over(self):
        session, a, b, _ctx_a, ctx_b = _make_session()
        with patch('combat.duel.net_common.append_battle_log'):
            await session.forfeit(a)  # first call resolves it
            ctx_b.sent.clear()
            await session.forfeit(b)  # already done -- must not double-resolve
        self.assertEqual(ctx_b.sent, [])
        self.assertEqual(b.duel_wins, 1)  # unchanged by the second call


if __name__ == '__main__':
    unittest.main()
