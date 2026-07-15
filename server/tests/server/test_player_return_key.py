"""tests/test_player_return_key.py

Player.return_key -- a shortcut for client_settings.return_key so callers
don't have to repeat that whole path (replaces the TODO in
create_character.py:530 asking for exactly this). terminal.ClientSettings
now declares return_key: str = 'Enter' as a real default, so a fresh
Player already has one; the getattr(..., 'Enter') fallback in the
property itself only matters for client_settings objects that predate
that field (e.g. old test doubles/mocks that don't set it).
"""
from __future__ import annotations

import unittest


class TestPlayerReturnKey(unittest.TestCase):

    def test_defaults_to_enter(self):
        from player import Player
        p = Player(name='Rulan')
        self.assertEqual(p.return_key, 'Enter')
        self.assertEqual(p.return_key, p.client_settings.return_key)

    def test_reflects_client_settings_value(self):
        from player import Player
        p = Player(name='Rulan')
        p.client_settings.return_key = 'Return'
        self.assertEqual(p.return_key, 'Return')

    def test_falls_back_to_enter_when_client_settings_lacks_the_attr(self):
        """Some test doubles/mocks stand in for client_settings without
        return_key set -- the property must not crash on those."""
        from player import Player

        class _BareSettings:
            pass

        p = Player(name='Rulan')
        p.client_settings = _BareSettings()
        self.assertEqual(p.return_key, 'Enter')


if __name__ == '__main__':
    unittest.main(verbosity=2)
