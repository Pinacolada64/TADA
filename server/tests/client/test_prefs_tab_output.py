"""tests/client/test_prefs_tab_output.py

Covers two related additions:
  1. formatting.py's generalized |entity:count| token syntax (extends the
     existing |entity| bracket-token pipeline with an optional ':N' repeat
     count), and the new 'tab' entity built on top of it -- |tab| / |tab:N|
     expand to the player's own client_settings.tab_settings.tab_output
     (a real '\\t' or N simulated spaces, per PREFS 'K'), repeated N times.
  2. PREFS 'K' (Tab Key) now shows a "You type:"/"You get:" token-syntax
     demo table (_tab_token_demo()) so a player can see what their current
     setting actually looks like, both before and after changing it --
     shown regardless of whether the client has a real Tab key.
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import _pick_tab_settings, _tab_token_demo
from formatting import (
    ansi_encode, petscii_encode, plain_encode, format_lines,
    _expand_tab_tokens,
)
from terminal import ClientSettings, TabSettings


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _settings(has_tab_key: bool = True, tab_width: int = 8) -> ClientSettings:
    cs = ClientSettings()
    cs.tab_settings = TabSettings()
    cs.tab_settings.has_tab_key = has_tab_key
    if has_tab_key:
        cs.tab_settings.tab_output = '\t'
    else:
        cs.tab_settings.tab_width  = tab_width
        cs.tab_settings.tab_output = ' ' * tab_width
    return cs


class TestExpandTabTokens(unittest.TestCase):

    def test_single_tab_expands_to_next_tab_stop(self):
        # 'A' occupies column 0, so |tab| (tab_width=4) advances to column
        # 4 -- 3 spaces, not a flat tab_width-space repeat -- see
        # formatting._expand_tab_tokens()'s real-tab-stop-math comment.
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A|tab|B', cs), 'A   B')

    def test_tab_with_count_advances_stop_by_stop(self):
        # Each |tab| in |tab:3| advances to the *next* stop from wherever
        # the previous one landed, not tab_width spaces each: col 0 -> 4
        # (3 spaces) -> 8 (4 spaces) -> 12 (4 spaces).
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A|tab:3|B', cs), 'A           B')

    def test_tab_advances_fewer_spaces_from_a_mid_stop_column(self):
        # 'Alexandria' is 10 chars (columns 0-9), so from column 10 a
        # |tab| with tab_width=4 only needs 2 spaces to reach column 12,
        # not a flat 4.
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('Alexandria|tab|B', cs),
                         'Alexandria  B')

    def test_real_tab_key_expands_to_literal_tab_char(self):
        cs = _settings(has_tab_key=True)
        self.assertEqual(_expand_tab_tokens('A|tab|B', cs), 'A\tB')

    def test_no_tab_settings_falls_back_to_literal_tab_char(self):
        class _Bare:
            pass
        self.assertEqual(_expand_tab_tokens('A|tab|B', _Bare()), 'A\tB')

    def test_format_lines_expands_tab_before_wrapping(self):
        # col 0 'A' -> stop at 4 (3 sp); col 5 'B' -> stop at 8 (3 sp) ->
        # stop at 12 (4 sp); 'C' appended -- real stop-by-stop math, not a
        # flat tab_width-space repeat per token.
        cs = _settings(has_tab_key=False, tab_width=4)
        lines = format_lines(['A|tab|B|tab:2|C'], cs)
        self.assertEqual(lines, ['A   B       C'])


class TestTokenCountSyntax(unittest.TestCase):
    """|entity:count| generalized to the existing color-token pipelines too,
    even though repeating a color escape code is a visual no-op -- exercises
    the same regex/count-handling path 'tab' relies on."""

    def test_ansi_encode_repeats_code_for_count(self):
        once  = ansi_encode('|red|x')
        twice = ansi_encode('|red:2|x')
        # The color code itself appears twice in the twice-repeated output.
        from formatting import ANSI_COLOR_CODES
        code = ANSI_COLOR_CODES['red']
        self.assertEqual(twice, code * 2 + 'x')
        self.assertEqual(once, code + 'x')

    def test_petscii_encode_repeats_control_byte_for_count(self):
        from formatting import PETSCII_CONTROL_CODES
        code = PETSCII_CONTROL_CODES['red']
        result = petscii_encode('|red:3|')
        self.assertEqual(result, bytes([code]) * 3)

    def test_plain_encode_strips_tokens_with_count(self):
        self.assertEqual(plain_encode('A|red:5|B'), 'AB')

    def test_unknown_token_with_count_left_intact_by_ansi(self):
        result = ansi_encode('|bogus:5|x')
        self.assertEqual(result, '|bogus:5|x')


class TestTokenEscapeSyntax(unittest.TestCase):
    """||token||/||token:N|| -- an escape mirroring highlight_brackets()'s
    [[literal]] -> [literal]: renders as the literal |token|/|token:N|
    (single pipes) instead of being color/tab-interpreted. Added so
    commands/help.py's 'colors' topic can show raw |token| syntax to a
    player without it actually being applied."""

    def test_ansi_encode_escape_renders_literal_single_pipes(self):
        self.assertEqual(ansi_encode('||red||text||reset||'), '|red|text|reset|')

    def test_ansi_encode_escape_with_count_renders_literal(self):
        self.assertEqual(ansi_encode('||red:5||'), '|red:5|')

    def test_ansi_encode_unescaped_token_still_applies(self):
        from formatting import ANSI_COLOR_CODES
        self.assertEqual(ansi_encode('|red|x|reset|'),
                         ANSI_COLOR_CODES['red'] + 'x' + ANSI_COLOR_CODES['reset'])

    def test_petscii_encode_escape_renders_literal_bytes(self):
        # '|' isn't representable in the PETSCII charset (falls back to '?'
        # via errors='replace'), but the point is it does NOT become the
        # red control byte -- it stays literal (mangled) text either way.
        from formatting import PETSCII_CONTROL_CODES
        result = petscii_encode('||red||')
        self.assertNotIn(bytes([PETSCII_CONTROL_CODES['red']]), result)

    def test_petscii_encode_unescaped_token_still_applies(self):
        from formatting import PETSCII_CONTROL_CODES
        result = petscii_encode('|red|')
        self.assertEqual(result, bytes([PETSCII_CONTROL_CODES['red']]))

    def test_plain_encode_escape_survives_as_literal(self):
        self.assertEqual(plain_encode('||red||text||reset||'), '|red|text|reset|')

    def test_plain_encode_unescaped_token_is_stripped(self):
        self.assertEqual(plain_encode('|red|text|reset|'), 'text')

    def test_expand_tab_tokens_ignores_escaped_form(self):
        """_expand_tab_tokens() deliberately leaves ||tab|| doubled and
        untouched -- ansi_encode()/petscii_encode()/plain_encode() collapse
        it to the literal |tab| later. Collapsing it here too would hand
        those a bare |tab| indistinguishable from a real token (see
        test_escaped_tab_survives_full_pipeline_to_plain below)."""
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A||tab||B', cs), 'A||tab||B')

    def test_expand_tab_tokens_ignores_escaped_form_with_count(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('||tab:5||', cs), '||tab:5||')

    def test_escaped_tab_survives_full_pipeline_to_plain(self):
        """Regression: _expand_tab_tokens() used to collapse ||tab|| to a
        bare |tab| immediately, which plain_encode() then stripped as if it
        were live markup -- found while writing the 'colors' help topic,
        whose usage table silently lost its |tab| example under PLAIN."""
        cs = _settings(has_tab_key=False, tab_width=4)
        expanded = _expand_tab_tokens('||tab||', cs)
        self.assertEqual(plain_encode(expanded), '|tab|')

    def test_escaped_tab_does_not_expand_to_real_tab_char(self):
        cs = _settings(has_tab_key=True)
        expanded = _expand_tab_tokens('A||tab||B', cs)
        self.assertNotIn('\t', expanded)


class TestTabTokenDemo(unittest.TestCase):
    """_tab_token_demo()'s raw Table output -- before it's ever handed to
    ctx.send(). The ||tab||-style doubled delimiters seen here are the
    pre-escaped source form; they only resolve down to the single-pipe
    text a player would actually see once the real ansi_encode()/
    petscii_encode() pipeline runs (see TestTabTokenDemoEscapeResolution
    below), which this raw-render check deliberately doesn't invoke."""

    def _ctx(self, **tab_kwargs) -> object:
        class _Ctx:
            pass
        ctx = _Ctx()
        ctx.player = Player()
        if tab_kwargs:
            for k, v in tab_kwargs.items():
                setattr(ctx.player.client_settings.tab_settings, k, v)
        return ctx

    def test_shows_type_and_get_headers(self):
        text = '\n'.join(_tab_token_demo(self._ctx()))
        self.assertIn('You type:', text)
        self.assertIn('You get:', text)

    def test_shows_pre_escaped_tab_tokens_and_counts(self):
        # 'A'/'B' markers wrap every example (both columns) so the tab's
        # effect -- how much space lands between them -- stays visible
        # even on the escaped, never-expanding 'You type:' side.
        text = '\n'.join(_tab_token_demo(self._ctx()))
        self.assertIn('A||tab||B', text)
        self.assertIn('A||tab:2||B', text)
        self.assertIn('A||tab:3||B', text)

    def test_shows_triple_escaped_row_for_the_escape_itself(self):
        # One more delimiter than a player would type -- _petscii_/
        # _token_strip_replace's single resolution pass consumes just the
        # innermost pair, so '|||tab|||' (3 pipes) is what's needed here
        # to have '||tab||' (2 pipes -- the literal escape a player
        # actually types) survive as visible text after that one pass.
        text = '\n'.join(_tab_token_demo(self._ctx()))
        self.assertIn('A|||tab|||B', text)
        self.assertIn('A||tab||B', text)

    def test_petscii_client_uses_bang_delimiter(self):
        from terminal import Translation
        ctx = self._ctx()
        ctx.player.client_settings.translation = Translation.PETSCII
        text = '\n'.join(_tab_token_demo(ctx))
        self.assertIn('A!!tab!!B', text)
        self.assertNotIn('||tab||', text)


class TestTabTokenDemoEscapeResolution(unittest.TestCase):
    """The doubled-delimiter source _tab_token_demo() emits really does
    resolve to what a player should see, once run through the same
    pipeline ctx.send() actually uses."""

    def test_ansi_resolves_type_column_to_single_pipe(self):
        from formatting import ansi_encode
        self.assertEqual(ansi_encode('A||tab||B'), 'A|tab|B')
        self.assertEqual(ansi_encode('A||tab:2||B'), 'A|tab:2|B')

    def test_ansi_resolves_escape_row_to_the_literal_escape(self):
        from formatting import ansi_encode
        # 'You type:' cell for the escape row.
        self.assertEqual(ansi_encode('A|||tab|||B'), 'A||tab||B')
        # 'You get:' cell for the same row -- what typing that escape
        # itself resolves to: literal '|tab|' text, not an actual tab.
        self.assertEqual(ansi_encode('A||tab||B'), 'A|tab|B')


class TestPrefsTabTokenDemoWiring(unittest.IsolatedAsyncioTestCase):

    async def test_shown_before_prompting(self):
        ctx = _FakeCtx([''], Player())
        await _pick_tab_settings(ctx)
        flat = ctx._flat()
        self.assertIn('You type:', flat)
        self.assertIn('You get:', flat)

    async def test_shown_again_after_enabling_real_tab_key(self):
        ctx = _FakeCtx(['y'], Player())
        await _pick_tab_settings(ctx)
        self.assertEqual(ctx._flat().count('You type:'), 2)

    async def test_shown_again_after_setting_tab_width(self):
        ctx = _FakeCtx(['n', '4'], Player())
        await _pick_tab_settings(ctx)
        self.assertEqual(ctx._flat().count('You type:'), 2)
        self.assertEqual(ctx.player.client_settings.tab_settings.tab_output, '    ')


if __name__ == '__main__':
    unittest.main(verbosity=2)
