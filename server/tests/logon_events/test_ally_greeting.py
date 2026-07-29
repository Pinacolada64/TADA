"""tests/logon_events/test_ally_greeting.py — logon_events/ally_greeting.py:
party-waiting-for-you login greeting, split out of commands/connect.py.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


def _waiting_mock_ally(name, flags=None):
    """A bare MagicMock() auto-creates a truthy `.flags` attribute on
    access, which would make `AllyFlags.GOD in flags` spuriously true
    (MagicMock.__contains__ returns another truthy MagicMock) -- set
    `.flags` explicitly so _divine_login_extra() only fires when asked."""
    ally = MagicMock()
    ally.name = name
    ally.flags = flags or []
    return ally


class TestPartyWaitingLines(unittest.TestCase):
    """SPUR.LOGON.S's ally-greeting line ("X is/are waiting for you!"),
    printed at login for each party member (master branch only -- skip
    has no equivalent). Was effectively dead code until player.party
    persistence was fixed (it was always empty on reload before that),
    so this locks in the phrasing now that it actually fires.

    Phrasing is randomized (_WAITING_PHRASINGS) as a TADA addition, and
    party_waiting_lines() returns a list of lines (to allow the optional
    multi-line divine exchange -- see TestDivineLoginExtra), so these
    patch random.choice to the first template for a deterministic
    "X is/are waiting for you!" base string to assert against."""

    def _first_template(self):
        return patch('random.choice', side_effect=lambda pool: pool[0])

    def test_no_party_returns_none(self):
        from logon_events.ally_greeting import party_waiting_lines
        self.assertIsNone(party_waiting_lines(None))
        self.assertIsNone(party_waiting_lines([]))

    def test_one_member(self):
        from logon_events.ally_greeting import party_waiting_lines
        ally = _waiting_mock_ally('Grog')
        with self._first_template():
            self.assertEqual(
                party_waiting_lines([ally]), ['Grog is waiting for you!']
            )

    def test_two_members(self):
        from logon_events.ally_greeting import party_waiting_lines
        a1 = _waiting_mock_ally('Grog')
        a2 = _waiting_mock_ally('Ironclad')
        with self._first_template():
            self.assertEqual(
                party_waiting_lines([a1, a2]), ['Grog and Ironclad are waiting for you!']
            )

    def test_three_members(self):
        from logon_events.ally_greeting import party_waiting_lines
        a1 = _waiting_mock_ally('Grog')
        a2 = _waiting_mock_ally('Ironclad')
        a3 = _waiting_mock_ally('Zeus')
        with self._first_template():
            self.assertEqual(
                party_waiting_lines([a1, a2, a3]),
                ['Grog, Ironclad and Zeus are waiting for you!'],
            )

    def test_divine_ally_gets_extra_lines_appended(self):
        from logon_events.ally_greeting import party_waiting_lines
        mortal = _waiting_mock_ally('Grog')
        deity  = _waiting_mock_ally('Persephone')
        with self._first_template(), \
             patch('logon_events.ally_greeting._divine_login_extra',
                   return_value=["Persephone's presence lights up the room."]):
            lines = party_waiting_lines([mortal, deity])
        self.assertEqual(
            lines,
            [
                'Grog and Persephone are waiting for you!',
                "Persephone's presence lights up the room.",
            ],
        )

    def test_no_divine_ally_means_no_extra_lines(self):
        from logon_events.ally_greeting import party_waiting_lines
        ally = _waiting_mock_ally('Grog')
        with self._first_template():
            lines = party_waiting_lines([ally])
        self.assertEqual(lines, ['Grog is waiting for you!'])


class TestDivineLoginExtra(unittest.TestCase):
    """_divine_login_extra(): the flourish/hunger-exchange line(s)
    appended after the main waiting line when a god/goddess ally shares
    the party. Ryan's idea for the hunger exchange -- a divine ally
    complains of hunger, a mortal ally points out they're divine, the
    divine ally shrugs it off."""

    def test_no_allies_returns_empty(self):
        from logon_events.ally_greeting import _divine_login_extra
        self.assertEqual(_divine_login_extra([]), [])

    def test_mortal_only_party_returns_empty(self):
        from logon_events.ally_greeting import _divine_login_extra
        self.assertEqual(_divine_login_extra([_waiting_mock_ally('Grog')]), [])

    def test_lone_divine_ally_always_gets_the_flourish(self):
        from bar.ally_data import AllyFlags
        from logon_events.ally_greeting import _divine_login_extra
        deity = _waiting_mock_ally('Ares', flags=[AllyFlags.GOD])
        with patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = _divine_login_extra([deity])
        self.assertEqual(len(lines), 1)
        self.assertIn('Ares', lines[0])

    def test_hunger_exchange_uses_god_article(self):
        from bar.ally_data import AllyFlags
        from logon_events.ally_greeting import _divine_login_extra
        deity  = _waiting_mock_ally('Ares', flags=[AllyFlags.GOD])
        mortal = _waiting_mock_ally('Grog')
        with patch('random.random', return_value=0.0), \
             patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = _divine_login_extra([deity, mortal])
        self.assertEqual(lines, [
            'Ares says, "I hope you have some food. I hunger!"',
            'Grog blinks. "But you\'re a god!"',
            'Ares shrugs. "So? I\'m still hungry..."',
        ])

    def test_hunger_exchange_uses_goddess_article(self):
        from bar.ally_data import AllyFlags
        from logon_events.ally_greeting import _divine_login_extra
        deity  = _waiting_mock_ally('Persephone', flags=[AllyFlags.GODDESS])
        mortal = _waiting_mock_ally('Grog')
        with patch('random.random', return_value=0.0), \
             patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = _divine_login_extra([deity, mortal])
        self.assertIn('"But you\'re a goddess!"', lines[1])

    def test_exchange_never_fires_above_the_roll_threshold(self):
        from bar.ally_data import AllyFlags
        from logon_events.ally_greeting import _divine_login_extra
        deity  = _waiting_mock_ally('Ares', flags=[AllyFlags.GOD])
        mortal = _waiting_mock_ally('Grog')
        with patch('random.random', return_value=0.999), \
             patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = _divine_login_extra([deity, mortal])
        self.assertEqual(len(lines), 1)
        self.assertNotIn('hunger', lines[0].lower())


if __name__ == '__main__':
    unittest.main()
