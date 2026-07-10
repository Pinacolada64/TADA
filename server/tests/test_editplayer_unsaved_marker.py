"""tests/test_editplayer_unsaved_marker.py

Unit tests for commands/editplayer.py's _titled_menu() -- appends an
'(unsaved changes)' tag to a menu's title whenever ctx.player.unsaved_changes
is set, re-evaluated on every redraw via menu_system.Menu.rendered_title
(a callable title, not a static string).

Run with:
    python -m pytest tests/test_editplayer_unsaved_marker.py -v
"""
from __future__ import annotations

import unittest

from commands.editplayer import _titled_menu
from menu_system import format_menu_lines


class _FakePlayer:
    def __init__(self, unsaved_changes=False):
        self.name = 'Rulan'
        self.unsaved_changes = unsaved_changes


class _FakeClientSettings:
    screen_columns = 80
    border_style = 'single'


class _FakeCtx:
    def __init__(self, unsaved_changes=False):
        self.player = _FakePlayer(unsaved_changes)
        self.player.client_settings = _FakeClientSettings()


class TestTitledMenu(unittest.TestCase):

    def test_no_marker_when_saved(self):
        ctx = _FakeCtx(unsaved_changes=False)
        menu = _titled_menu(ctx, 'Money')
        self.assertEqual(menu.rendered_title, 'Money')

    def test_marker_when_unsaved(self):
        ctx = _FakeCtx(unsaved_changes=True)
        menu = _titled_menu(ctx, 'Money')
        self.assertIn('Money', menu.rendered_title)
        self.assertIn('unsaved changes', menu.rendered_title)

    def test_marker_reflects_live_state_not_snapshot(self):
        """The title is a callable re-evaluated per redraw -- toggling
        unsaved_changes after the Menu is built must change what's shown
        without rebuilding the Menu object."""
        ctx = _FakeCtx(unsaved_changes=False)
        menu = _titled_menu(ctx, 'Money')
        self.assertEqual(menu.rendered_title, 'Money')

        ctx.player.unsaved_changes = True
        self.assertIn('unsaved changes', menu.rendered_title)

        ctx.player.unsaved_changes = False
        self.assertEqual(menu.rendered_title, 'Money')

    def test_marker_appears_in_rendered_menu_lines(self):
        ctx = _FakeCtx(unsaved_changes=True)
        menu = _titled_menu(ctx, 'Money')
        lines = format_menu_lines(ctx, menu)
        self.assertTrue(any('unsaved changes' in ln for ln in lines))


if __name__ == '__main__':
    unittest.main()
