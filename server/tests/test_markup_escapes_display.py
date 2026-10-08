"""Escaped ||token|| markup must *display* as the literal |token| --
the line editor's '.h colors' topic (text_editor._COLOR_TOPIC_TEXT), the
table.py layout it goes through, and tools/gen_help_pdf.py's PDF export."""
import sys
import unittest
from pathlib import Path

import table
from formatting import PlainCodec, highlight_brackets, plain_encode
from text_editor import _COLOR_TOPIC_TEXT, _format_help_text


def _shown(line: str) -> str:
    """What a plain-text player sees for one sent line."""
    return highlight_brackets(plain_encode(line), PlainCodec())


class TestEditorColorsTopic(unittest.TestCase):

    def test_syntax_is_shown_not_applied(self):
        text = '\n'.join(_shown(l) for l in _format_help_text(_COLOR_TOPIC_TEXT, 78))
        self.assertIn('|red|word|reset| colors', text)
        self.assertIn('|red|Stop!|reset|', text)
        self.assertIn('|command|.s|reset|', text)
        self.assertNotIn('||', text)

    def test_examples_intact_at_40_columns(self):
        lines = [_shown(l) for l in _format_help_text(_COLOR_TOPIC_TEXT, 40)]
        examples = lines[lines.index('Examples:') + 1:]
        self.assertTrue(examples[0].startswith('  |red|Stop!|reset|'))
        stop_col = examples[0].index('Shows')
        command_row = next(l for l in examples if '|command|' in l)
        self.assertTrue(command_row.startswith('  |command|.s|reset|'))
        self.assertEqual(command_row.index('Shows'), stop_col)   # aligned
        self.assertTrue(all(len(l) <= 40 for l in examples), examples)


class TestTableEscapes(unittest.TestCase):

    def test_visible_len_counts_escapes_as_displayed(self):
        self.assertEqual(table._visible_len('||red||Hi||reset||'), len('|red|Hi|reset|'))
        self.assertEqual(table._visible_len('|red|Hi|reset|'), 2)

    def test_wrap_measures_visible_width_and_keeps_words_whole(self):
        lines = table._wrap_cell('Shows |red|Warning!|reset| in red, then resets', 16)
        self.assertEqual([plain_encode(l) for l in lines],
                         ['Shows Warning!', 'in red, then', 'resets'])

    def test_wrap_never_splits_markup(self):
        lines = table._wrap_cell('||command||.h||reset|| x', 8)
        self.assertIn('||command||.h||reset||', lines)

    def test_truncation_keeps_escapes_escaped(self):
        out = table._fit('||red||abcdefgh', 8, table.Align.LEFT)
        self.assertTrue(out.startswith('||red||'), out)
        self.assertEqual(table._visible_len(out), 8)


class TestEditorColorsPetsciiBang(unittest.IsolatedAsyncioTestCase):
    """'.h colors' adds a paragraph on '!' as a stand-in for '|' -- only
    for Commodore (PETSCII) players, the only ones '!' works for."""

    async def _colors_help(self, petscii: bool) -> str:
        from unittest.mock import AsyncMock, MagicMock, patch
        from text_editor import run_editor
        ctx = MagicMock()
        ctx.player.client_settings.screen_columns = 40
        ctx.player.query_flag = MagicMock(return_value=False)
        ctx.player.is_expert = True
        replies = iter(['.h colors', '.s'])
        ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(replies, None))
        ctx.send = AsyncMock()
        with patch('commands.help._is_petscii_viewer', return_value=petscii):
            await run_editor(ctx)
        sent = []
        for call in ctx.send.await_args_list:
            for arg in call.args:
                sent.extend(arg if isinstance(arg, list) else [arg])
        return '\n'.join(str(x) for x in sent)

    async def test_commodore_player_sees_bang_paragraph(self):
        text = await self._colors_help(petscii=True)
        self.assertIn('On a Commodore, ! works exactly like |', text)
        self.assertIn('use | instead', text)

    async def test_other_players_do_not(self):
        text = await self._colors_help(petscii=False)
        self.assertIn('||red||word||reset||', text)          # the main topic is there
        self.assertNotIn('On a Commodore', text)

    def test_paragraph_shows_bang_syntax_on_a_commodore(self):
        import formatting
        from text_editor import _COLOR_TOPIC_PETSCII_TEXT
        lines = _format_help_text(_COLOR_TOPIC_PETSCII_TEXT, 40)
        shown = '\n'.join(formatting._PETSCII_TOKEN_RE.sub(
            formatting._petscii_token_strip_replace, l) for l in lines)
        self.assertIn('!red!word!reset! is the same as |red|word|reset|', shown)
        self.assertIn("(!red| isn't one)", shown)
        self.assertNotIn('!!', shown)

    def test_paragraph_encodes_cleanly(self):
        from formatting import petscii_encode
        from text_editor import _COLOR_TOPIC_PETSCII_TEXT
        with self.assertNoLogs('root', level='WARNING'):
            for line in _format_help_text(_COLOR_TOPIC_PETSCII_TEXT, 40):
                petscii_encode(line)


class TestHelpPdfStripTokens(unittest.TestCase):

    def test_strip_tokens_matches_plain_client(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
        import gen_help_pdf
        self.assertEqual(gen_help_pdf.strip_tokens('then ||reset|| returns, |red|word|reset| [[x]] 5%%'),
                         'then |reset| returns, word [x] 5%')

    def test_editor_pdf_includes_commodore_paragraph(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
        import gen_help_pdf
        entries, _intro = gen_help_pdf.collect_editor_entries()
        colors = next(e for e in entries if e['name'] == '.h colors')
        text = '\n'.join(colors['lines'])
        self.assertIn('Commodore (PETSCII) connections only:', text)
        self.assertIn('!red!word!reset!', text)
        self.assertNotIn('!!', text)


if __name__ == '__main__':
    unittest.main()
