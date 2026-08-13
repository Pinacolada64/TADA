"""tests/test_formatting_codec_for_settings.py

Unit tests for formatting.py's codec_for_settings() -- specifically the
bug Ryan found: [bracket] highlighting always used ANSICodec()'s own
hardcoded Fore.RED default, ignoring the player's own PREFS '[bracket]
Highlight Color' choice (ClientSettings.colors.highlight_color, a
terminal.ColorName) entirely. The preference was stored (commands/
prefs.py's 'HC' row) and displayed, but never actually read when
building the codec used for highlight_brackets().
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from terminal import Translation, ColorName, ANSIColors
from formatting import codec_for_settings, highlight_brackets, ansi_encode, ANSICodec


def _settings(color: ColorName, translation=Translation.ANSI, text_color=ColorName.WHITE):
    settings = MagicMock()
    settings.translation = translation
    settings.colors.highlight_color = color
    settings.colors.text_color = text_color
    return settings


class TestCodecForSettingsHighlightColor(unittest.TestCase):
    def test_uses_the_players_chosen_highlight_color(self):
        codec = codec_for_settings(_settings(ColorName.CYAN))
        self.assertEqual(codec.highlight_on(), ANSIColors.CYAN.value)

    def test_different_players_get_different_colors(self):
        red_codec = codec_for_settings(_settings(ColorName.RED))
        green_codec = codec_for_settings(_settings(ColorName.DARK_GREEN))
        self.assertNotEqual(red_codec.highlight_on(), green_codec.highlight_on())

    def test_highlight_brackets_uses_the_chosen_color(self):
        codec = codec_for_settings(_settings(ColorName.YELLOW))
        result = highlight_brackets('Use [ATTACK] now', codec)
        self.assertIn(ANSIColors.YELLOW.value, result)
        self.assertNotIn(ANSIColors.RED.value, result)

    def test_color_with_no_colorama_equivalent_falls_back_to_default_red(self):
        # ANSIColors.PURPLE/ORANGE/BROWN are None (colorama has no direct
        # equivalent) -- ANSICodec's own __post_init__ falls back to
        # Fore.RED for a falsy highlight_color, same as before this fix
        # for a player who never set a preference at all.
        codec = codec_for_settings(_settings(ColorName.PURPLE))
        self.assertEqual(codec.highlight_on(), ANSICodec().highlight_on())

    def test_non_ansi_translation_still_returns_the_right_codec_type(self):
        from formatting import PETSCIICodec, PlainCodec
        self.assertIsInstance(
            codec_for_settings(_settings(ColorName.RED, Translation.PETSCII)), PETSCIICodec)
        self.assertIsInstance(
            codec_for_settings(_settings(ColorName.RED, Translation.ASCII)), PlainCodec)


class TestCodecForSettingsResetColor(unittest.TestCase):
    """|reset|/highlight_off() should return to the player's own chosen
    PREFS 'C' Colors -> Text color, not an uncontrolled hard reset to
    whatever the terminal app itself defaults to."""

    def test_reset_uses_the_players_text_color(self):
        codec = codec_for_settings(_settings(ColorName.RED, text_color=ColorName.LIGHT_GREEN))
        self.assertEqual(codec.reset(), ANSIColors.LIGHT_GREEN.value)

    def test_highlight_off_matches_reset(self):
        codec = codec_for_settings(_settings(ColorName.RED, text_color=ColorName.CYAN))
        self.assertEqual(codec.highlight_off(), codec.reset())
        self.assertEqual(codec.highlight_off(), ANSIColors.CYAN.value)

    def test_ansi_encode_reset_token_uses_the_players_text_color(self):
        codec = codec_for_settings(_settings(ColorName.RED, text_color=ColorName.LIGHT_GREEN))
        result = ansi_encode('|red|Alert!|reset| back to normal', reset_color=codec.reset())
        self.assertIn(ANSIColors.LIGHT_GREEN.value, result)
        self.assertNotIn(ANSIColors.RESET.value, result)

    def test_no_reset_color_override_keeps_default_behavior(self):
        # No reset_color passed -- unchanged behavior for callers with no
        # player/settings context (e.g. tests, standalone tools).
        result = ansi_encode('|red|Alert!|reset| plain')
        self.assertIn(ANSIColors.RESET.value, result)

    def test_text_color_with_no_colorama_equivalent_falls_back_to_terminal_reset(self):
        codec = codec_for_settings(_settings(ColorName.RED, text_color=ColorName.ORANGE))
        self.assertEqual(codec.reset(), ANSICodec().reset())


class TestVisibleLenBracketAware(unittest.TestCase):
    """_visible_len() must count a [bracket]-highlighted word at its
    *rendered* width (delimiters gone), not its raw literal width --
    otherwise code that sizes padding/columns from raw un-highlighted
    text (make_box(), table.py's column widths) reserves 2 columns too
    many per highlighted word, and the highlighted word ends up left
    short of the border once highlight_brackets() actually runs
    downstream in ctx.send()'s pipeline. Found via tips.json's [LOOT]
    tags misaligning the TIPS box, and STAT's ally table '[ELITE]'-style
    Notes tags misaligning its columns."""

    def test_bracketed_word_counts_content_only(self):
        from formatting import _visible_len
        self.assertEqual(_visible_len('[LOOT]'), len('LOOT'))

    def test_double_bracket_escape_counts_literal_brackets(self):
        from formatting import _visible_len
        # [[x]] renders as the literal '[x]' (see highlight_brackets()'s
        # own escape rule) -- 2 chars, not 4.
        self.assertEqual(_visible_len('[[optional]]'), len('[optional]'))

    def test_matches_actual_post_highlight_length(self):
        from formatting import _visible_len, highlight_brackets, PlainCodec
        text = 'Use [LOOT] and [GIVE] wisely.'
        rendered = highlight_brackets(text, PlainCodec())
        self.assertEqual(_visible_len(text), len(rendered))


class TestMakeBoxBracketPadding(unittest.TestCase):
    """make_box()'s body-line padding must land the right border at the
    same column whether or not a line contains a [bracket]-highlighted
    word -- see TestVisibleLenBracketAware above for why raw len()-based
    .ljust() gets this wrong."""

    def test_bracketed_and_plain_lines_render_the_same_width_after_highlighting(self):
        from formatting import make_box, highlight_brackets, PlainCodec
        box = make_box(['Use [LOOT] wisely.', 'No brackets here though.'], width=30)
        resolved = [highlight_brackets(line, PlainCodec()) for line in box]
        widths = {len(line) for line in resolved}
        self.assertEqual(widths, {30}, f'expected every rendered line at 30 cols, got {widths}')


class TestReverseVideoTokens(unittest.TestCase):
    """Ryan found: |reverse_on|/|reverse_off| (used by commands/map.py's
    #overview/#visited to highlight a room square) were mapped to
    colorama's Style.BRIGHT/RESET_ALL -- bold intensity, not a real
    foreground/background swap. A bold *space* character looks identical
    to a plain space, so the room squares rendered as invisible blanks
    on a real ANSI terminal even though the arrows/@ marker (real glyphs)
    showed up fine. Fixed by emitting the raw SGR reverse-video escape
    codes (\\x1b[7m / \\x1b[27m) directly, the same way terminal.py's
    cursor-movement constants already do for codes colorama doesn't
    expose."""

    def test_reverse_on_emits_true_sgr_reverse_video(self):
        rendered = ansi_encode('|reverse_on|')
        self.assertIn('\x1b[7m', rendered)

    def test_reverse_off_emits_sgr_reverse_video_off(self):
        rendered = ansi_encode('|reverse_off|')
        self.assertIn('\x1b[27m', rendered)

    def test_reverse_on_is_not_just_bold(self):
        # The bug this guards against: reverse_on and bold used to be the
        # exact same colorama Style.BRIGHT code.
        from formatting import ANSI_COLOR_CODES
        self.assertNotEqual(ANSI_COLOR_CODES['reverse_on'], ANSI_COLOR_CODES['bold'])

    def test_a_space_wrapped_in_reverse_video_is_visibly_different_from_plain(self):
        # The actual failure mode: commands/map.py's #overview draws a
        # room as a plain space wrapped in reverse_on/off. Confirm the
        # rendered bytes for that space differ from an unwrapped space --
        # under the old Style.BRIGHT mapping they'd have been identical
        # once colorama's bold code has no visible effect on whitespace.
        plain = ansi_encode(' ')
        reversed_space = ansi_encode('|reverse_on| |reverse_off|')
        self.assertNotEqual(plain, reversed_space)


if __name__ == '__main__':
    unittest.main()
