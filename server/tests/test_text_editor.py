"""tests/test_text_editor.py — text_editor.py: the ctx-aware ed-style line
editor with dot-commands. Architecture per Ryan's gist (see text_editor.py's
own module docstring for exactly what was kept vs. filled in vs. deferred).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from text_editor import (
    Buffer, DefaultLineRange, Editor, Justification, Line, LineFlag,
    _sanitize_filename, make_box, process_line_range_string, run_editor,
)


def _make_buffer(*texts: str) -> Buffer:
    return Buffer(lines=[Line(text=t) for t in texts])


class TestProcessLineRangeString(unittest.TestCase):
    """Mirrors the old text_editor branch's own doctests for its
    parse_line_range() against a 5-line buffer with ALL_LINES default --
    the one part of that earlier attempt that was actually finished and
    tested; the parsing logic here is unchanged from that (and from the
    gist), just with stricter out-of-range clamping."""

    def setUp(self):
        self.buffer = _make_buffer('one', 'two', 'three', 'four', 'five')

    def _range(self, s):
        return process_line_range_string(s, self.buffer, DefaultLineRange.ALL_LINES)

    def test_empty_defaults_to_whole_buffer(self):
        r = self._range('')
        self.assertEqual((r.start, r.end), (1, 5))

    def test_single_line(self):
        r = self._range('3')
        self.assertEqual((r.start, r.end), (3, 3))

    def test_dash_y_means_start_to_y(self):
        r = self._range('-3')
        self.assertEqual((r.start, r.end), (1, 3))

    def test_x_dash_y(self):
        r = self._range('3-5')
        self.assertEqual((r.start, r.end), (3, 5))

    def test_x_dash_means_x_to_end(self):
        r = self._range('2-')
        self.assertEqual((r.start, r.end), (2, 5))

    def test_out_of_range_clamps(self):
        r = self._range('1-99')
        self.assertEqual((r.start, r.end), (1, 5))
        r = self._range('99')
        self.assertEqual((r.start, r.end), (5, 5))

    def test_reversed_range_collapses_to_start(self):
        r = self._range('5-2')
        self.assertEqual((r.start, r.end), (5, 5))

    def test_malformed_digits_return_none_range(self):
        r = self._range('abc')
        self.assertIsNone(r.start)
        self.assertIsNone(r.end)

    def test_no_default_returns_none_range(self):
        r = process_line_range_string('', self.buffer, DefaultLineRange.NONE)
        self.assertIsNone(r.start)
        self.assertIsNone(r.end)

    def test_empty_buffer_still_returns_well_formed_range(self):
        empty = Buffer(lines=[])
        r = process_line_range_string('', empty, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (1, 1))


class TestJustification(unittest.TestCase):
    def test_left_is_unpadded(self):
        self.assertEqual(Line('hi', Justification.LEFT).render(10), 'hi')

    def test_center(self):
        self.assertEqual(Line('hi', Justification.CENTER).render(10), 'hi'.center(10))

    def test_right(self):
        self.assertEqual(Line('hi', Justification.RIGHT).render(10), 'hi'.rjust(10))

    def test_expand_distributes_spaces_between_words(self):
        rendered = Line('one two three', Justification.EXPAND).render(17)
        self.assertEqual(len(rendered), 17)
        self.assertTrue(rendered.startswith('one'))
        self.assertTrue(rendered.endswith('three'))

    def test_expand_single_word_unchanged(self):
        self.assertEqual(Line('hi', Justification.EXPAND).render(10), 'hi')

    def test_text_already_at_or_over_width_unchanged(self):
        self.assertEqual(Line('a very long line', Justification.CENTER).render(5), 'a very long line')


class TestMakeBox(unittest.TestCase):
    def test_box_has_border_and_padded_content(self):
        box = make_box(['hi'], width=10)
        self.assertEqual(box[0], '+--------+')
        self.assertEqual(box[-1], '+--------+')
        self.assertEqual(box[1], '| hi     |')

    def test_custom_border_char(self):
        box = make_box(['hi'], width=10, border_char='*')
        self.assertEqual(box[0], '+********+')

    def test_long_line_truncated_to_interior(self):
        box = make_box(['this is way too long for the box'], width=10)
        self.assertEqual(len(box[1]), 10)


class TestSanitizeFilename(unittest.TestCase):
    def test_strips_path_traversal(self):
        self.assertNotIn('/', _sanitize_filename('../../etc/passwd'))
        self.assertNotIn('..', _sanitize_filename('../../etc/passwd'))

    def test_strips_leading_dot(self):
        self.assertEqual(_sanitize_filename('.hidden'), 'hidden')

    def test_keeps_safe_chars(self):
        self.assertEqual(_sanitize_filename('my-file_1.txt'), 'my-file_1.txt')

    def test_empty_after_sanitizing_falls_back(self):
        self.assertEqual(_sanitize_filename('///'), 'unnamed')


def _make_ctx(responses, screen_columns=80, admin=False):
    """responses: list of strings to return from successive ctx.prompt()
    calls, in order; None once exhausted (simulates disconnect)."""
    ctx = MagicMock()
    ctx.player.client_settings.screen_columns = screen_columns
    ctx.player.query_flag = MagicMock(return_value=admin)
    it = iter(responses)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    ctx.send = AsyncMock()
    return ctx


def _sent_text(ctx) -> str:
    """Flatten every ctx.send() call's arguments into one searchable string."""
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


class TestRunEditorBasics(unittest.IsolatedAsyncioTestCase):
    async def test_append_list_edit_save_session(self):
        ctx = _make_ctx(['first line', 'second line', '.l', '.e 2', 'edited second line', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['first line', 'edited second line'])

    async def test_abort_returns_none(self):
        ctx = _make_ctx(['some line', '.a', 'Y'])
        result = await run_editor(ctx)
        self.assertIsNone(result)

    async def test_disconnect_mid_edit_returns_none(self):
        ctx = _make_ctx(['some line'])
        result = await run_editor(ctx)
        self.assertIsNone(result)

    async def test_initial_lines_preloaded_and_editable(self):
        ctx = _make_ctx(['.d 1', '.s'])
        result = await run_editor(ctx, initial_lines=['keep me', 'delete me'])
        self.assertEqual(result, ['delete me'])

    async def test_initial_lines_accept_prebuilt_line_objects(self):
        quoted = Line(text='quoted content', line_flag=LineFlag.IMMUTABLE)
        ctx = _make_ctx(['.s'])
        result = await run_editor(ctx, initial_lines=[quoted])
        self.assertEqual(result, ['quoted content'])

    async def test_save_with_no_lines_returns_empty_list(self):
        ctx = _make_ctx(['.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, [])

    async def test_blank_enter_is_ignored_not_appended(self):
        ctx = _make_ctx(['one', '', 'two', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['one', 'two'])

    async def test_unrecognized_command_does_not_crash_session(self):
        ctx = _make_ctx(['.z', 'a real line', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['a real line'])


class TestInsertMode(unittest.IsolatedAsyncioTestCase):
    async def test_insert_at_line_shifts_rest_down(self):
        ctx = _make_ctx(['one', 'three', '.i 2', 'two', '.i', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['one', 'two', 'three'])

    async def test_insert_toggle_defaults_to_end_of_buffer(self):
        ctx = _make_ctx(['one', '.i', 'two', '.i', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['one', 'two'])


class TestDeleteSkipsImmutable(unittest.IsolatedAsyncioTestCase):
    async def test_delete_skips_immutable_lines_in_range(self):
        ctx = _make_ctx(['.d 1-2', '.s'])
        lines = [Line(text='keep', line_flag=LineFlag.IMMUTABLE), Line(text='delete me')]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(result, ['keep'])


class TestEditSkipsImmutable(unittest.IsolatedAsyncioTestCase):
    async def test_edit_skips_immutable_line(self):
        ctx = _make_ctx(['changed'])
        lines = [Line(text='locked', line_flag=LineFlag.IMMUTABLE), Line(text='editable')]
        editor = Editor(ctx, initial_lines=lines)
        from text_editor import _cmd_edit
        await _cmd_edit(editor, '1-2')
        self.assertEqual(editor.buffer.lines[0].text, 'locked')
        self.assertEqual(editor.buffer.lines[1].text, 'changed')
        self.assertIn('immutable', _sent_text(ctx).lower())


class TestJustify(unittest.IsolatedAsyncioTestCase):
    async def test_justify_center_sets_persistent_style(self):
        ctx = _make_ctx(['.j c 1-2', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two'])
        self.assertEqual(result, ['one'.center(80), 'two'.center(80)])

    async def test_justify_with_no_range_changes_default_for_future_lines(self):
        ctx = _make_ctx(['.j c', 'centered later', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(result, ['centered later'.center(80)])

    async def test_justify_unknown_mode_reports_error(self):
        ctx = _make_ctx(['.j z 1', '.s'])
        result = await run_editor(ctx, initial_lines=['one'])
        self.assertIn('Unknown', _sent_text(ctx))
        self.assertEqual(result, ['one'])

    async def test_justify_pack_collapses_spaces(self):
        ctx = _make_ctx(['.j p 1', '.s'])
        result = await run_editor(ctx, initial_lines=['one    two   three'])
        self.assertEqual(result, ['one two three'])

    async def test_justify_indent_default_amount(self):
        ctx = _make_ctx(['.j i 1', '', '.s'])
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertEqual(result, ['    hi'])

    async def test_justify_unindent_strips_leading_spaces(self):
        ctx = _make_ctx(['.j u 1', '.s'])
        result = await run_editor(ctx, initial_lines=['    hi'])
        self.assertEqual(result, ['hi'])

    async def test_justify_skips_immutable_lines(self):
        ctx = _make_ctx(['.j c 1', '.s'])
        lines = [Line(text='locked', line_flag=LineFlag.IMMUTABLE)]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(result, ['locked'])  # unchanged -- still LEFT-justified


class TestBorder(unittest.IsolatedAsyncioTestCase):
    async def test_border_wraps_range_in_box(self):
        ctx = _make_ctx(['.b 1', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertEqual(len(result), 3)
        self.assertTrue(result[0].startswith('+'))
        self.assertTrue(result[-1].startswith('+'))

    async def test_border_custom_character(self):
        ctx = _make_ctx(['.b * 1', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertTrue(result[0].startswith('+*'))


class TestFindAndReplace(unittest.IsolatedAsyncioTestCase):
    async def test_find_reports_matches(self):
        ctx = _make_ctx(['.f', 'two', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two', 'three'])
        self.assertIn('two', _sent_text(ctx))
        self.assertEqual(result, ['one', 'two', 'three'])

    async def test_search_and_replace_counts_occurrences(self):
        ctx = _make_ctx(['.k', 'cat', 'dog', '.s'])
        result = await run_editor(ctx, initial_lines=['cat sat on the cat mat'])
        self.assertEqual(result, ['dog sat on the dog mat'])
        self.assertIn('Replaced 2', _sent_text(ctx))


class TestColumns(unittest.IsolatedAsyncioTestCase):
    async def test_columns_reports_current_width(self):
        ctx = _make_ctx(['.c', '.s'])
        await run_editor(ctx)
        self.assertIn('80', _sent_text(ctx))

    async def test_columns_sets_new_width(self):
        ctx = _make_ctx(['.c 40', '.l', '.s'])
        result = await run_editor(ctx, initial_lines=['short'])
        self.assertIn('Column width set to 40', _sent_text(ctx))

    async def test_columns_rejects_exceeding_screen_width(self):
        ctx = _make_ctx(['.c 999', '.s'])
        await run_editor(ctx)
        self.assertIn('cannot exceed', _sent_text(ctx))


class TestNewText(unittest.IsolatedAsyncioTestCase):
    async def test_new_text_confirmed_erases_buffer(self):
        ctx = _make_ctx(['.n', 'Y', '.s'])
        result = await run_editor(ctx, initial_lines=['gone'])
        self.assertEqual(result, [])

    async def test_new_text_declined_keeps_buffer(self):
        ctx = _make_ctx(['.n', 'N', '.s'])
        result = await run_editor(ctx, initial_lines=['still here'])
        self.assertEqual(result, ['still here'])


class TestLineNumbersMode(unittest.IsolatedAsyncioTestCase):
    async def test_toggle_reports_state(self):
        ctx = _make_ctx(['.o', '.s'])
        await run_editor(ctx)
        self.assertIn('now on', _sent_text(ctx))


class TestQuery(unittest.IsolatedAsyncioTestCase):
    async def test_query_reports_counts(self):
        ctx = _make_ctx(['.q', '.s'])
        result = await run_editor(ctx, initial_lines=['one two', 'three'])
        text = _sent_text(ctx)
        self.assertIn('Total lines used: 2', text)
        self.assertIn('Total words: 3', text)


class TestHelp(unittest.IsolatedAsyncioTestCase):
    async def test_help_lists_all_commands(self):
        ctx = _make_ctx(['.h', '.s'])
        await run_editor(ctx)
        text = _sent_text(ctx)
        self.assertIn('.s', text)
        self.assertIn('Save Text', text)

    async def test_help_hides_privileged_commands_from_non_admin(self):
        ctx = _make_ctx(['.h', '.s'], admin=False)
        await run_editor(ctx)
        self.assertNotIn('Get File', _sent_text(ctx))

    async def test_help_shows_privileged_commands_to_admin(self):
        ctx = _make_ctx(['.h', '.s'], admin=True)
        await run_editor(ctx)
        self.assertIn('Get File', _sent_text(ctx))

    async def test_help_for_specific_command_shows_docstring(self):
        ctx = _make_ctx(['.h s', '.s'])
        await run_editor(ctx)
        self.assertIn('Save', _sent_text(ctx))


class TestVersionAndScale(unittest.IsolatedAsyncioTestCase):
    async def test_version(self):
        ctx = _make_ctx(['.v', '.s'])
        await run_editor(ctx)
        self.assertIn('version', _sent_text(ctx).lower())

    async def test_scale_shows_ruler(self):
        ctx = _make_ctx(['.#', '.s'], screen_columns=20)
        await run_editor(ctx)
        text = _sent_text(ctx)
        self.assertIn('1', text)


class TestPrivilegedFileCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        import net_common
        self._orig = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig
        self._tmp.cleanup()

    async def test_non_admin_denied_get_file(self):
        ctx = _make_ctx(['.g myfile', '.s'], admin=False)
        await run_editor(ctx)
        self.assertIn('lack the authority', _sent_text(ctx))

    async def test_admin_put_then_get_file_round_trips(self):
        ctx = _make_ctx(['.p notes.txt', '.s'], admin=True)
        await run_editor(ctx, initial_lines=['hello there'])
        self.assertIn('Saved to notes.txt', _sent_text(ctx))

        ctx2 = _make_ctx(['.g notes.txt', '.l', '.s'], admin=True)
        result = await run_editor(ctx2)
        self.assertEqual(result, ['hello there'])

    async def test_put_file_collision_replace(self):
        ctx = _make_ctx(['.p dup.txt', '.s'], admin=True)
        await run_editor(ctx, initial_lines=['first'])

        ctx2 = _make_ctx(['.p dup.txt', 'r', '.s'], admin=True)
        await run_editor(ctx2, initial_lines=['second'])
        self.assertIn('Saved to dup.txt', _sent_text(ctx2))

        ctx3 = _make_ctx(['.g dup.txt', '.l', '.s'], admin=True)
        result = await run_editor(ctx3)
        self.assertEqual(result, ['second'])

    async def test_get_nonexistent_file_reports_error(self):
        ctx = _make_ctx(['.g nope.txt', '.s'], admin=True)
        await run_editor(ctx)
        self.assertIn('No such file', _sent_text(ctx))

    async def test_directory_lists_files(self):
        ctx = _make_ctx(['.p listed.txt', '.s'], admin=True)
        await run_editor(ctx, initial_lines=['content'])

        ctx2 = _make_ctx(['.$', '.s'], admin=True)
        await run_editor(ctx2)
        self.assertIn('listed.txt', _sent_text(ctx2))

    async def test_path_traversal_is_sanitized_away(self):
        ctx = _make_ctx(['.p ../../evil.txt', '.s'], admin=True)
        await run_editor(ctx, initial_lines=['x'])
        from text_editor import _editor_files_dir
        directory = _editor_files_dir()
        # nothing escaped the editor_files directory:
        self.assertTrue((directory / 'evil.txt').exists())
        self.assertFalse((directory.parent / 'evil.txt').exists())


if __name__ == '__main__':
    unittest.main()
