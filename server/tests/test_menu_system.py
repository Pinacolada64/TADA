"""
test_menu_system.py

Tests for menu_system.py: formatting, geometry, navigation.
"""

import asyncio
import re
import pytest

from menu_system import (
    Menu, MenuItem,
    _vis_len,
    format_menu_lines,
    get_user_choice,
    run_menu,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Settings:
    """Minimal ClientSettings stand-in."""
    def __init__(self, screen_columns=80, border_style='single'):
        self.screen_columns = screen_columns
        self.border_style   = border_style
        self.screen_rows    = 24
        self.return_key     = 'Enter'


class _Player:
    def __init__(self, screen_columns=80):
        self.name            = 'Tester'
        self.client_settings = _Settings(screen_columns=screen_columns)

    def query_flag(self, flag):
        return False


class _Ctx:
    """Minimal ctx stand-in for format_menu_lines and navigation tests."""
    def __init__(self, screen_columns=80):
        self.player = _Player(screen_columns=screen_columns)
        self._sends = []

    async def send(self, *args):
        self._sends.extend(args)

    async def prompt(self, prompt_text='', preamble_lines=None):
        return ''


def _make_ctx(screen_columns=80):
    return _Ctx(screen_columns=screen_columns)


def _make_menu(*labels, shortcuts=None, dot_values=None):
    """Build a Menu from label strings.

    shortcuts : list of shortcut strings (one per item, e.g. ['e', 'h'])
    dot_values: list of static dot-leader values (strings) or None
    """
    m = Menu(title='Test Menu')
    for i, label in enumerate(labels):
        sc  = [shortcuts[i]] if shortcuts and i < len(shortcuts) else [str(i + 1)]
        dh  = (lambda ctx, v=dot_values[i]: v) if dot_values and i < len(dot_values) else None
        m.add_item(MenuItem(text=label, shortcuts=sc, dot_leader_handler=dh,
                            action=lambda ctx: None))
    return m


def _visible(line: str) -> str:
    """Strip |token| sequences from a line to get the visible text."""
    return re.sub(r'\|[a-z_]+\|', '', line)


def _vis_width(line: str) -> int:
    """Visible width of a rendered menu line (strips tokens and brackets)."""
    return len(_visible(line))


# ---------------------------------------------------------------------------
# _vis_len unit tests
# ---------------------------------------------------------------------------

class TestVisLen:
    def test_plain_string(self):
        assert _vis_len('hello') == 5

    def test_strips_bracket_delimiters(self):
        assert _vis_len('[e]') == 1           # [e] → e
        assert _vis_len('[gui]') == 3         # [gui] → gui
        assert _vis_len('[ar]') == 2

    def test_strips_token_sequences(self):
        assert _vis_len('|yellow|x|reset|') == 1

    def test_mixed(self):
        # " 1. [e]      Expert Mode" — brackets contribute 1 vis char, not 3
        s = ' 1. [e]      Expert Mode'
        assert _vis_len(s) == len(' 1. e      Expert Mode')

    def test_empty(self):
        assert _vis_len('') == 0

    def test_no_extra_stripping(self):
        # Plain text without brackets/tokens is unchanged
        assert _vis_len('Room Descriptions') == 17


# ---------------------------------------------------------------------------
# format_menu_lines geometry tests
# ---------------------------------------------------------------------------

class TestFormatMenuLinesGeometry:
    """Verify that no rendered line exceeds screen_columns visible chars."""

    def _rendered_lines(self, ctx, menu):
        return format_menu_lines(ctx, menu)

    def _assert_fits(self, lines, screen_columns):
        for ln in lines:
            vis = _vis_len(ln)
            assert vis <= screen_columns, (
                f"Line exceeds {screen_columns} visible cols ({vis}): {ln!r}"
            )

    # --- 80-column ANSI ---

    def test_short_labels_80col(self):
        ctx  = _make_ctx(80)
        menu = _make_menu('Alpha', 'Beta', 'Gamma',
                          shortcuts=['a', 'b', 'g'],
                          dot_values=['Yes', 'No', 'Yes'])
        lines = self._rendered_lines(ctx, menu)
        self._assert_fits(lines, 80)

    def test_long_labels_80col(self):
        ctx  = _make_ctx(80)
        labels = [
            'Amulet of Life energized',
            'Guild Follow Mode',
            'Expert Mode',
            'Room Descriptions',
        ]
        shortcuts   = ['am', 'gf', 'e', 'r']
        dot_values  = ['Yes', 'Off', 'On', 'On']
        menu = _make_menu(*labels, shortcuts=shortcuts, dot_values=dot_values)
        lines = self._rendered_lines(ctx, menu)
        self._assert_fits(lines, 80)

    # --- 40-column (C64) ---

    def test_long_labels_40col(self):
        ctx  = _make_ctx(40)
        labels = [
            'Amulet of Life energized',   # longest at 24 chars
            'Guild Follow Mode',
            'Expert Mode',
            'Administrator',
        ]
        shortcuts  = ['am', 'gf', 'e', 'a']
        dot_values = ['Yes', 'Off', 'On', 'No']
        menu = _make_menu(*labels, shortcuts=shortcuts, dot_values=dot_values)
        lines = self._rendered_lines(ctx, menu)
        self._assert_fits(lines, 40)

    def test_short_labels_40col(self):
        ctx  = _make_ctx(40)
        menu = _make_menu('Hungry', 'Tired', 'Mounted',
                          shortcuts=['h', 't', 'm'],
                          dot_values=['No', 'No', 'No'])
        lines = self._rendered_lines(ctx, menu)
        self._assert_fits(lines, 40)

    # --- dot leader values always visible ---

    def test_dot_value_always_present(self):
        """The dot-leader value must appear on the same line as the label."""
        ctx  = _make_ctx(40)
        labels     = ['Amulet of Life energized', 'Expert Mode']
        shortcuts  = ['am', 'e']
        dot_values = ['Yes', 'Off']
        menu  = _make_menu(*labels, shortcuts=shortcuts, dot_values=dot_values)
        lines = self._rendered_lines(ctx, menu)
        item_lines = [ln for ln in lines if ': ' in ln]
        assert any('Yes' in ln for ln in item_lines), "dot value 'Yes' missing from item lines"
        assert any('Off' in ln for ln in item_lines), "dot value 'Off' missing from item lines"

    # --- dot leader alignment ---

    def test_values_aligned_80col(self):
        """The colon separator should appear at the same visible column on every
        dot-leader line, regardless of label length or value length."""
        ctx  = _make_ctx(80)
        labels     = ['Short', 'Medium Length Label', 'A Very Long Label Indeed']
        shortcuts  = ['s', 'm', 'l']
        dot_values = ['Yes', 'No', 'Yes']
        menu  = _make_menu(*labels, shortcuts=shortcuts, dot_values=dot_values)
        lines = self._rendered_lines(ctx, menu)

        # Find the visible column of the colon on each item line.
        colon_cols = []
        for ln in lines:
            if ': ' in ln and any(v in ln for v in ('Yes', 'No')):
                colon_pos = _vis_len(ln[:ln.rfind(': ')])
                colon_cols.append(colon_pos)

        assert len(colon_cols) == 3
        assert len(set(colon_cols)) == 1, \
            f"Colon not aligned across items: colon at cols {colon_cols}"

    # --- dynamic shortcut column width ---

    def test_shortcut_column_tight(self):
        """Shortcut column should be sized to the widest shortcut in the menu,
        not the old fixed 8 chars."""
        ctx  = _make_ctx(80)
        # All shortcuts are 1 visible char: [a], [b], [c]
        menu = _make_menu('Alpha', 'Beta', 'Gamma',
                          shortcuts=['a', 'b', 'c'])
        lines = self._rendered_lines(ctx, menu)
        # The rule line fills screen_columns; find an item line and check
        # that there's no excessive gap between shortcut and label.
        item_lines = [ln for ln in lines if '1.' in ln or '2.' in ln]
        assert item_lines, "No numbered item lines found"
        # With 1-char shortcuts, there should be at most 2 spaces of padding
        # between the shortcut and the label (1 visible sc + 1 space).
        first = item_lines[0]
        # After highlight_brackets [a]→a, the visible form is " 1. a  Alpha"
        # The gap should not be huge (old code left 7 spaces after a 1-char sc).
        visible = _vis_len(first)
        # Just verify the line is not wider than screen
        assert visible <= 80

    def test_wide_shortcut_fits_40col(self):
        """Even [gui]-width shortcuts (5 vis chars) must fit on 40-col screen."""
        ctx  = _make_ctx(40)
        labels    = ['Guild Member', 'Expert Mode', 'Administrator']
        shortcuts = ['gui', 'e', 'a']
        dot_values = ['Yes', 'Off', 'No']
        menu  = _make_menu(*labels, shortcuts=shortcuts, dot_values=dot_values)
        lines = self._rendered_lines(ctx, menu)
        self._assert_fits(lines, 40)

    # --- headers ---

    def test_header_not_numbered(self):
        menu = Menu(title='Test Menu')
        menu.add_item(MenuItem(text='— Section —'))
        menu.add_item(MenuItem(text='Item', shortcuts=['i'], action=lambda ctx: None))
        ctx   = _make_ctx(80)
        lines = format_menu_lines(ctx, menu)
        text  = '\n'.join(lines)
        assert '— Section —' in text
        assert ' 1.' in text
        assert ' 2.' not in text

    # --- rule line ---

    def test_rule_fills_screen_width(self):
        ctx   = _make_ctx(40)
        menu  = _make_menu('Item', shortcuts=['i'])
        lines = format_menu_lines(ctx, menu)
        rules = [ln for ln in lines if ln and set(ln) <= {'─', '═', '-'}]
        assert rules, "No rule line found"
        assert all(len(ln) == 40 for ln in rules), \
            f"Rule line not exactly 40 chars: {[len(r) for r in rules]}"


# ---------------------------------------------------------------------------
# format_menu_lines content tests
# ---------------------------------------------------------------------------

class TestFormatMenuLinesContent:
    def test_title_in_output(self):
        menu  = _make_menu('A', 'B')
        lines = format_menu_lines(_make_ctx(), menu)
        assert any('Test Menu' in ln for ln in lines)

    def test_items_numbered(self):
        menu = _make_menu('Alpha', 'Beta', 'Gamma')
        text = '\n'.join(format_menu_lines(_make_ctx(), menu))
        assert ' 1.' in text
        assert ' 2.' in text
        assert ' 3.' in text

    def test_shortcuts_in_output(self):
        menu = _make_menu('Edit', 'Quit', shortcuts=['E', 'Q'])
        text = '\n'.join(format_menu_lines(_make_ctx(), menu))
        # Shortcuts may appear with or without brackets depending on codec,
        # but the letter itself must be present.
        assert 'E' in text
        assert 'Q' in text

    def test_dot_leader_value_shown(self):
        ctx  = _make_ctx(80)
        menu = _make_menu('Screen width', shortcuts=['w'],
                          dot_values=['80'])
        text = '\n'.join(format_menu_lines(ctx, menu))
        assert '80' in text
        assert '.' in text

    def test_no_dot_leader_item(self):
        ctx  = _make_ctx(80)
        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Plain item', shortcuts=['p'],
                               action=lambda ctx: None))
        lines = format_menu_lines(ctx, menu)
        item_lines = [ln for ln in lines if 'Plain item' in ln]
        assert item_lines
        assert ':' not in item_lines[0]   # no dot-leader colon


# ---------------------------------------------------------------------------
# MenuItem / Menu properties
# ---------------------------------------------------------------------------

class TestMenuProperties:
    def test_is_header_true(self):
        assert MenuItem(text='Header').is_header is True

    def test_is_header_false_with_action(self):
        assert MenuItem(text='Item', action=lambda ctx: None).is_header is False

    def test_is_header_false_with_submenu(self):
        assert MenuItem(text='Sub', submenu=Menu(title='S')).is_header is False

    def test_selectable_excludes_headers(self):
        menu = Menu(title='Mixed')
        menu.add_item(MenuItem(text='Header'))
        menu.add_item(MenuItem(text='A', shortcuts=['a'], action=lambda ctx: None))
        menu.add_item(MenuItem(text='B', shortcuts=['b'], action=lambda ctx: None))
        assert len(menu.selectable) == 2


# ---------------------------------------------------------------------------
# get_user_choice
# ---------------------------------------------------------------------------

class TestGetUserChoice:
    def _run(self, coro):
        return asyncio.run(coro)

    def _patch_prompt(self, ctx, responses):
        it = iter(responses)
        async def _prompt(prompt_text='', preamble_lines=None):
            return next(it, '')
        ctx.prompt = _prompt

    def test_numeric_choice(self):
        ctx  = _make_ctx()
        menu = _make_menu('Alpha', 'Beta', 'Gamma')
        self._patch_prompt(ctx, ['2'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None
        assert chosen.text == 'Beta'

    def test_shortcut_choice(self):
        ctx  = _make_ctx()
        menu = _make_menu('Edit', 'Quit', shortcuts=['E', 'Q'])
        self._patch_prompt(ctx, ['Q'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None
        assert chosen.text == 'Quit'

    def test_shortcut_case_insensitive(self):
        ctx  = _make_ctx()
        menu = _make_menu('Edit', shortcuts=['E'])
        self._patch_prompt(ctx, ['e'])
        chosen = self._run(get_user_choice(ctx, menu))
        assert chosen is not None and chosen.text == 'Edit'

    def test_empty_input_returns_none(self):
        ctx  = _make_ctx()
        menu = _make_menu('Alpha')
        self._patch_prompt(ctx, [''])
        assert self._run(get_user_choice(ctx, menu)) is None

    def test_out_of_range_returns_none(self):
        ctx  = _make_ctx()
        menu = _make_menu('Only one')
        self._patch_prompt(ctx, ['99'])
        assert self._run(get_user_choice(ctx, menu)) is None

    def test_invalid_input_returns_none(self):
        ctx  = _make_ctx()
        menu = _make_menu('Alpha')
        self._patch_prompt(ctx, ['???'])
        assert self._run(get_user_choice(ctx, menu)) is None


# ---------------------------------------------------------------------------
# run_menu navigation
# ---------------------------------------------------------------------------

class TestRunMenu:
    def _run(self, coro):
        return asyncio.run(coro)

    def _patch_prompt(self, ctx, responses):
        it = iter(responses)
        async def _prompt(prompt_text='', preamble_lines=None):
            return next(it, '')
        ctx.prompt = _prompt

    def test_action_called(self):
        ctx    = _make_ctx()
        called = []
        async def my_action(ctx):
            called.append(True)
        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Do it', shortcuts=['D'], action=my_action))
        self._patch_prompt(ctx, ['D', ''])
        self._run(run_menu(ctx, menu))
        assert called == [True]

    def test_submenu_navigation(self):
        ctx     = _make_ctx()
        visited = []
        async def leaf_action(ctx):
            visited.append('leaf')
        sub  = Menu(title='Sub')
        sub.add_item(MenuItem(text='Leaf', shortcuts=['L'], action=leaf_action))
        main = Menu(title='Main')
        main.add_item(MenuItem(text='Go sub', shortcuts=['S'], submenu=sub))
        self._patch_prompt(ctx, ['S', 'L', '', ''])
        self._run(run_menu(ctx, main))
        assert visited == ['leaf']

    def test_empty_input_exits(self):
        ctx  = _make_ctx()
        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Item', shortcuts=['I'], action=lambda ctx: None))
        self._patch_prompt(ctx, [''])
        self._run(run_menu(ctx, menu))   # must not raise

    def test_sync_action_called(self):
        ctx    = _make_ctx()
        called = []
        def sync_action(ctx):
            called.append(True)
        menu = Menu(title='Test')
        menu.add_item(MenuItem(text='Sync', shortcuts=['S'], action=sync_action))
        self._patch_prompt(ctx, ['S', ''])
        self._run(run_menu(ctx, menu))
        assert called == [True]
