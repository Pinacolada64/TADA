"""
test_menu_system.py

Tests for the refactored menu_system.py using TerminalContext.
All tests use monkeypatch to control input so no real terminal I/O occurs.
"""

import asyncio
import pytest

from menu_system import Menu, MenuItem, format_menu_lines, get_user_choice, navigate_menu, run_menu
from terminal_context import TerminalContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx():
    """A fresh TerminalContext for each test."""
    return TerminalContext(player_name='Tester')


def make_menu(*labels: str, shortcuts: list[str] | None = None) -> Menu:
    """Helper: build a Menu with simple text items."""
    m = Menu(title='Test Menu')
    for i, label in enumerate(labels):
        sc = [shortcuts[i]] if shortcuts and i < len(shortcuts) else [str(i + 1)]
        m.add_item(MenuItem(text=label, shortcuts=sc, action=lambda ctx: None))
    return m


# ---------------------------------------------------------------------------
# format_menu_lines
# ---------------------------------------------------------------------------

class TestFormatMenuLines:
    def test_title_appears(self, ctx):
        menu  = make_menu('Option A', 'Option B')
        lines = format_menu_lines(ctx, menu)
        assert any('Test Menu' in ln for ln in lines)

    def test_items_numbered(self, ctx):
        menu  = make_menu('Alpha', 'Beta', 'Gamma')
        lines = format_menu_lines(ctx, menu)
        text  = '\n'.join(lines)
        assert '1.' in text
        assert '2.' in text
        assert '3.' in text

    def test_shortcuts_shown(self, ctx):
        menu  = make_menu('Edit', 'Quit', shortcuts=['E', 'Q'])
        lines = format_menu_lines(ctx, menu)
        text  = '\n'.join(lines)
        assert '[E]' in text
        assert '[Q]' in text

    def test_header_item_not_numbered(self, ctx):
        menu = Menu(title='Test Menu')
        menu.add_item(MenuItem(text='-- Section --'))          # header
        menu.add_item(MenuItem(text='Do thing', shortcuts=['D'],
                               action=lambda ctx: None))
        lines = format_menu_lines(ctx, menu)
        text  = '\n'.join(lines)
        assert '-- Section --' in text
        assert '1.' in text
        assert '2.' not in text   # only one selectable item

    def test_dot_leader(self, ctx):
        menu = Menu(title='Settings')
        menu.add_item(MenuItem(
            text='Screen width',
            shortcuts=['W'],
            dot_leader_handler=lambda ctx: ctx.player.client_settings.screen_columns,
            action=lambda ctx: None,
        ))
        lines = format_menu_lines(ctx, menu)
        text  = '\n'.join(lines)
        assert '80' in text      # default screen_columns
        assert '.' in text       # dot leader present


# ---------------------------------------------------------------------------
# MenuItem.is_header / Menu.selectable
# ---------------------------------------------------------------------------

class TestMenuProperties:
    def test_is_header_true(self):
        item = MenuItem(text='Section Header')
        assert item.is_header is True

    def test_is_header_false_with_action(self):
        item = MenuItem(text='Do something', action=lambda ctx: None)
        assert item.is_header is False

    def test_is_header_false_with_submenu(self):
        sub  = Menu(title='Sub')
        item = MenuItem(text='Go to sub', submenu=sub)
        assert item.is_header is False

    def test_selectable_excludes_headers(self):
        menu = Menu(title='Mixed')
        menu.add_item(MenuItem(text='Header'))
        menu.add_item(MenuItem(text='Item 1', shortcuts=['1'], action=lambda ctx: None))
        menu.add_item(MenuItem(text='Item 2', shortcuts=['2'], action=lambda ctx: None))
        assert len(menu.selectable) == 2


# ---------------------------------------------------------------------------
# get_user_choice
# ---------------------------------------------------------------------------

class TestGetUserChoice:
    def _run(self, coro):
        return asyncio.run(coro)

    def _patch_prompt(self, ctx, responses: list[str]):
        """Make ctx.prompt() return responses in sequence."""
        it = iter(responses)
        async def _prompt(prompt_text='', preamble_lines=None):
            return next(it, '')
        ctx.prompt = _prompt

    def test_numeric_choice(self, ctx):
        menu = make_menu('Alpha', 'Beta', 'Gamma')
        self._patch_prompt(ctx, ['2'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None
        assert chosen.text == 'Beta'

    def test_shortcut_choice(self, ctx):
        menu = make_menu('Edit', 'Quit', shortcuts=['E', 'Q'])
        self._patch_prompt(ctx, ['Q'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None
        assert chosen.text == 'Quit'

    def test_shortcut_case_insensitive(self, ctx):
        menu = make_menu('Edit', shortcuts=['E'])
        self._patch_prompt(ctx, ['e'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None
        assert chosen.text == 'Edit'

    def test_empty_input_returns_none(self, ctx):
        menu = make_menu('Alpha')
        self._patch_prompt(ctx, [''])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is None

    def test_out_of_range_returns_none(self, ctx):
        menu = make_menu('Only one item')
        self._patch_prompt(ctx, ['99'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is None

    def test_invalid_input_returns_none(self, ctx):
        menu = make_menu('Alpha')
        self._patch_prompt(ctx, ['???'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is None


# ---------------------------------------------------------------------------
# navigate_menu / run_menu
# ---------------------------------------------------------------------------

class TestNavigateMenu:
    def _run(self, coro):
        return asyncio.run(coro)

    def _patch_prompt(self, ctx, responses: list[str]):
        it = iter(responses)
        async def _prompt(prompt_text='', preamble_lines=None):
            return next(it, '')
        ctx.prompt = _prompt

    def test_action_called(self, ctx):
        called = []
        async def my_action(ctx):
            called.append(True)

        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Do it', shortcuts=['D'], action=my_action))
        # Choose 'D', then empty to quit
        self._patch_prompt(ctx, ['D', ''])
        self._run(run_menu(ctx, menu))
        assert called == [True]

    def test_submenu_navigation(self, ctx):
        visited = []
        async def leaf_action(ctx):
            visited.append('leaf')

        sub = Menu(title='Submenu')
        sub.add_item(MenuItem(text='Leaf', shortcuts=['L'], action=leaf_action))

        main = Menu(title='Main')
        main.add_item(MenuItem(text='Go sub', shortcuts=['S'], submenu=sub))

        # Choose 'S' to enter submenu, 'L' to run leaf, '' to exit submenu, '' to exit main
        self._patch_prompt(ctx, ['S', 'L', '', ''])
        self._run(run_menu(ctx, main))
        assert visited == ['leaf']

    def test_empty_input_exits(self, ctx):
        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Item', shortcuts=['I'], action=lambda ctx: None))
        self._patch_prompt(ctx, [''])   # immediately cancel
        self._run(run_menu(ctx, menu))  # should not raise

    def test_sync_action_wrapped(self, ctx):
        """A synchronous (non-async) action should still be called."""
        called = []
        def sync_action(ctx):
            called.append(True)

        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Sync', shortcuts=['S'], action=sync_action))
        self._patch_prompt(ctx, ['S', ''])
        self._run(run_menu(ctx, menu))
        assert called == [True]
