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


if __name__ == '__main__':
    unittest.main()
