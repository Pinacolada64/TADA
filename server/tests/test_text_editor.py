"""tests/test_text_editor.py — text_editor.py: the ctx-aware ed-style line
editor with dot-commands. Architecture per Ryan's gist (see text_editor.py's
own module docstring for exactly what was kept vs. filled in vs. deferred).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from formatting import deserialize_lines, render_lines
from text_editor import (
    Border, BorderRole, Buffer, DefaultLineRange, Editor, Justification, Line,
    LineFlag, _sanitize_filename, find_recovery_file, load_recovery_file,
    process_line_range_string, run_editor,
)


def _make_buffer(*texts: str) -> Buffer:
    return Buffer(lines=[Line(text=t) for t in texts])


def _texts(result: list) -> list:
    """run_editor()'s .S Save result is now a list of serialized Line
    dicts (formatting.serialize_lines()'s output), not pre-rendered
    strings -- Justification/Border are metadata on each dict, not baked
    into 'text'. Tests that only care about plain content use this to
    pull just the text back out; tests that care about formatting check
    the dict fields directly or re-render via formatting.render_lines()."""
    return [d['text'] for d in result]


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


class TestRelativeLineRange(unittest.TestCase):
    """'x-+n' is a relative end: n more lines from x, e.g. '1-+5' is
    lines 1-6 (six lines: x plus n more) -- same idea as ed/vi's own
    ',+n' relative addressing."""

    def setUp(self):
        self.buffer = Buffer(lines=[Line(text=str(i)) for i in range(1, 101)])  # 100 lines

    def test_relative_end_from_ryans_own_examples(self):
        r = process_line_range_string('1-+5', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (1, 6))
        r = process_line_range_string('46-+19', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (46, 65))

    def test_relative_end_clamps_past_buffer_end(self):
        small = Buffer(lines=[Line(text=str(i)) for i in range(1, 6)])  # 5 lines
        r = process_line_range_string('3-+10', small, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (3, 5))

    def test_relative_end_with_omitted_start_defaults_start_to_1(self):
        r = process_line_range_string('-+3', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (1, 4))

    def test_relative_end_with_no_digits_is_malformed(self):
        r = process_line_range_string('1-+', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertIsNone(r.start)
        self.assertIsNone(r.end)

    def test_relative_end_with_non_numeric_offset_is_malformed(self):
        r = process_line_range_string('1-+abc', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertIsNone(r.start)
        self.assertIsNone(r.end)

    def test_relative_end_zero_offset_is_a_single_line(self):
        r = process_line_range_string('5-+0', self.buffer, DefaultLineRange.ALL_LINES)
        self.assertEqual((r.start, r.end), (5, 5))


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


class TestBorderRendering(unittest.TestCase):
    """Border lives on Line (like Justification), not baked into .text --
    same rendered-at-view-time width independence, verified directly."""

    def test_top_and_bottom_are_rule_lines_regardless_of_text(self):
        top = Line(text='ignored', border=Border(char='-', role=BorderRole.TOP))
        self.assertEqual(top.render(10), '+--------+')

    def test_content_line_padded_between_pipes(self):
        content = Line(text='hi', border=Border(char='-', role=BorderRole.CONTENT))
        self.assertEqual(content.render(10), '| hi     |')

    def test_custom_border_char(self):
        top = Line(border=Border(char='*', role=BorderRole.TOP))
        self.assertEqual(top.render(10), '+********+')

    def test_long_content_truncated_to_interior(self):
        content = Line(text='this is way too long for the box',
                        border=Border(role=BorderRole.CONTENT))
        self.assertEqual(len(content.render(10)), 10)

    def test_same_line_renders_wider_at_a_different_width(self):
        # the whole point: no box-drawing characters are baked into .text,
        # so the same Line adapts to whoever's viewing it.
        content = Line(text='hi', border=Border(role=BorderRole.CONTENT))
        narrow = content.render(10)
        wide = content.render(20)
        self.assertNotEqual(narrow, wide)
        self.assertEqual(len(wide), 20)

    def test_content_justification_still_applies_inside_the_box(self):
        content = Line(text='hi', justification=Justification.CENTER,
                        border=Border(role=BorderRole.CONTENT))
        # inner width for a 10-col box is 6 -- 'hi'.center(6) == '  hi  '
        self.assertEqual(content.render(10), '|   hi   |')


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


class TestRelativeLineRangeEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_relative_range_via_list_command(self):
        ctx = _make_ctx(['.l 1-+3', '.s'])
        result = await run_editor(ctx, initial_lines=[str(i) for i in range(1, 11)])
        for n in (1, 2, 3, 4):
            self.assertIn(f'{n}: {n}', _sent_text(ctx))
        self.assertNotIn('5: 5', _sent_text(ctx))
        self.assertEqual(_texts(result), [str(i) for i in range(1, 11)])  # list doesn't mutate

    async def test_relative_range_via_delete_command(self):
        ctx = _make_ctx(['.d 2-+2', '.s'])
        result = await run_editor(ctx, initial_lines=['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(_texts(result), ['a', 'e'])


class TestRunEditorBasics(unittest.IsolatedAsyncioTestCase):
    async def test_append_list_edit_save_session(self):
        ctx = _make_ctx(['first line', 'second line', '.l', '.e 2', 'edited second line', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['first line', 'edited second line'])

    async def test_abort_returns_none(self):
        ctx = _make_ctx(['some line', '.a', 'Y'])
        result = await run_editor(ctx)
        self.assertIsNone(result)

    async def test_disconnect_mid_edit_returns_none(self):
        ctx = _make_ctx(['some line'])
        result = await run_editor(ctx)
        self.assertIsNone(result)

    async def test_disconnect_with_empty_buffer_saves_nothing(self):
        import net_common
        original = getattr(net_common, 'run_server_dir', None)
        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = Path(tmp)
            try:
                ctx = _make_ctx([])  # disconnects on the very first prompt
                ctx.player.name = 'Nobody'
                await run_editor(ctx)
                self.assertIsNone(find_recovery_file('Nobody'))
            finally:
                net_common.run_server_dir = original

    async def test_disconnect_mid_edit_writes_a_recovery_file(self):
        import net_common
        original = getattr(net_common, 'run_server_dir', None)
        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = Path(tmp)
            try:
                ctx = _make_ctx(['some line'])  # types, then disconnects
                ctx.player.name = 'Casey'
                await run_editor(ctx, activity_id='news_post:Test',
                                  activity_label='posting news "Test"')
                path = find_recovery_file('Casey')
                self.assertIsNotNone(path)
                data = load_recovery_file(path)
                self.assertEqual(data['internal_id'], 'news_post:Test')
                self.assertEqual([l['text'] for l in data['lines']], ['some line'])
            finally:
                net_common.run_server_dir = original

    async def test_initial_lines_preloaded_and_editable(self):
        ctx = _make_ctx(['.d 1', '.s'])
        result = await run_editor(ctx, initial_lines=['keep me', 'delete me'])
        self.assertEqual(_texts(result), ['delete me'])

    async def test_initial_lines_accept_prebuilt_line_objects(self):
        quoted = Line(text='quoted content', line_flag=LineFlag.IMMUTABLE)
        ctx = _make_ctx(['.s'])
        result = await run_editor(ctx, initial_lines=[quoted])
        self.assertEqual(_texts(result), ['quoted content'])

    async def test_save_with_no_lines_returns_empty_list(self):
        ctx = _make_ctx(['.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), [])

    async def test_blank_enter_adds_a_blank_line(self):
        ctx = _make_ctx(['one', '', 'two', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one', '', 'two'])

    async def test_unrecognized_command_does_not_crash_session(self):
        ctx = _make_ctx(['.z', 'a real line', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['a real line'])

    async def test_virtual_location_set_while_editing_and_restored_after(self):
        # WHEREAT (commands/whereat.py) reads ctx.client.virtual_location --
        # same convention as commands/news.py's 'Reading news' and
        # commands/new_player.py's 'Creating a character'.
        ctx = _make_ctx(['one', '.s'])
        ctx.client.virtual_location = 'somewhere else'
        seen = {}

        responses = iter(['one', '.s'])
        ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: (
            seen.setdefault('during', ctx.client.virtual_location),
            next(responses, None),
        )[1])
        await run_editor(ctx)

        self.assertEqual(seen['during'], 'Editing Text')
        self.assertEqual(ctx.client.virtual_location, 'somewhere else')  # restored


class TestInsertMode(unittest.IsolatedAsyncioTestCase):
    async def test_insert_at_line_shifts_rest_down(self):
        ctx = _make_ctx(['one', 'three', '.i 2', 'two', '.i', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one', 'two', 'three'])

    async def test_insert_toggle_defaults_to_end_of_buffer(self):
        ctx = _make_ctx(['one', '.i', 'two', '.i', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one', 'two'])


class TestDeleteSkipsImmutable(unittest.IsolatedAsyncioTestCase):
    async def test_delete_skips_immutable_lines_in_range(self):
        ctx = _make_ctx(['.d 1-2', '.s'])
        lines = [Line(text='keep', line_flag=LineFlag.IMMUTABLE), Line(text='delete me')]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(_texts(result), ['keep'])

    async def test_delete_skips_quote_lines_in_range(self):
        # QUOTE gets the same protection as IMMUTABLE -- see
        # commands/board_reply.py, which seeds a threaded-board reply's
        # quoted content this way so it can't be tampered with.
        ctx = _make_ctx(['.d 1-2', '.s'])
        lines = [Line(text='quoted', line_flag=LineFlag.QUOTE), Line(text='delete me')]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(_texts(result), ['quoted'])


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

    async def test_edit_skips_quote_line(self):
        ctx = _make_ctx(['changed'])
        lines = [Line(text='quoted', line_flag=LineFlag.QUOTE), Line(text='editable')]
        editor = Editor(ctx, initial_lines=lines)
        from text_editor import _cmd_edit
        await _cmd_edit(editor, '1-2')
        self.assertEqual(editor.buffer.lines[0].text, 'quoted')
        self.assertEqual(editor.buffer.lines[1].text, 'changed')
        self.assertIn('immutable', _sent_text(ctx).lower())


class TestEditSubcommands(unittest.IsolatedAsyncioTestCase):
    """.E m(ove)/c(opy)/l(ist) <range> [destination]."""

    async def test_move_shifts_range_to_destination(self):
        ctx = _make_ctx(['.e m 4-6 8', '.s'])
        result = await run_editor(ctx, initial_lines=[
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
        ])
        self.assertEqual(_texts(result), [
            'one', 'two', 'three', 'seven', 'four', 'five', 'six', 'eight',
        ])

    async def test_move_to_the_very_end(self):
        ctx = _make_ctx(['.e m 1 4', '.s'])  # dest == used_lines+1 -- append
        result = await run_editor(ctx, initial_lines=['a', 'b', 'c'])
        self.assertEqual(_texts(result), ['b', 'c', 'a'])

    async def test_copy_leaves_source_in_place(self):
        ctx = _make_ctx(['.e c 1-2 4', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two', 'three'])
        self.assertEqual(_texts(result), ['one', 'two', 'three', 'one', 'two'])

    async def test_copy_is_a_real_deep_copy_not_a_shared_reference(self):
        # editing the copy afterward must not also change the original
        ctx = _make_ctx(['.e c 1 3', '.e 1', 'changed', '.s'])
        result = await run_editor(ctx, initial_lines=['original', 'two'])
        self.assertEqual(_texts(result), ['changed', 'two', 'original'])

    async def test_move_skips_immutable_lines_in_range(self):
        # only 'free' (index 1) is actually movable -- 'locked' stays put,
        # and the destination (before original line 3, 'c') places 'free'
        # right back next to where it started:
        ctx = _make_ctx(['.e m 1-2 3', '.s'])
        lines = [Line(text='locked', line_flag=LineFlag.IMMUTABLE), Line(text='free'), Line(text='c')]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(_texts(result), ['locked', 'free', 'c'])

    async def test_move_missing_destination_prompts_for_it(self):
        ctx = _make_ctx(['.e m 1', '3', '.s'])
        result = await run_editor(ctx, initial_lines=['a', 'b', 'c'])
        self.assertEqual(_texts(result), ['b', 'a', 'c'])

    async def test_move_missing_destination_cancelled_on_blank_response(self):
        ctx = _make_ctx(['.e m 1', '', '.s'])
        result = await run_editor(ctx, initial_lines=['a', 'b'])
        self.assertEqual(_texts(result), ['a', 'b'])

    async def test_move_with_no_args_at_all_prompts_for_both(self):
        ctx = _make_ctx(['.e m', '1', '3', '.s'])
        result = await run_editor(ctx, initial_lines=['a', 'b', 'c'])
        self.assertEqual(_texts(result), ['b', 'a', 'c'])

    async def test_list_subcommand_delegates_to_list(self):
        ctx = _make_ctx(['.e l 1-2', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two', 'three'])
        self.assertIn('1: one', _sent_text(ctx))
        self.assertIn('2: two', _sent_text(ctx))
        self.assertNotIn('3: three', _sent_text(ctx))
        self.assertEqual(_texts(result), ['one', 'two', 'three'])  # list doesn't mutate


class TestEditUndoRedo(unittest.IsolatedAsyncioTestCase):
    """.E u(ndo)/r(edo)/s(how) -- multi-level, checkpointed before every
    real buffer mutation."""

    async def test_undo_reverts_last_typed_line(self):
        ctx = _make_ctx(['one', 'two', '.e u', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one'])

    async def test_undo_twice_then_redo_once(self):
        ctx = _make_ctx(['one', 'two', '.e u', '.e u', '.e r', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one'])

    async def test_undo_past_empty_history_is_a_no_op(self):
        ctx = _make_ctx(['one', '.e u', '.e u', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), [])
        self.assertIn('Nothing to undo.', _sent_text(ctx))

    async def test_redo_with_nothing_to_redo_is_a_no_op(self):
        ctx = _make_ctx(['.e r', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), [])
        self.assertIn('Nothing to redo.', _sent_text(ctx))

    async def test_new_change_after_undo_clears_redo_history(self):
        ctx = _make_ctx(['one', 'two', '.e u', 'three', '.e r', '.s'])
        result = await run_editor(ctx)
        # 'two' was undone, 'three' typed instead (clearing redo) -- the
        # trailing '.e r' has nothing to redo and is a no-op:
        self.assertEqual(_texts(result), ['one', 'three'])

    async def test_undo_reverts_delete(self):
        ctx = _make_ctx(['.d 1', '.e u', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two'])
        self.assertEqual(_texts(result), ['one', 'two'])

    async def test_undo_reverts_move(self):
        ctx = _make_ctx(['.e m 1 3', '.e u', '.s'])
        result = await run_editor(ctx, initial_lines=['a', 'b', 'c'])
        self.assertEqual(_texts(result), ['a', 'b', 'c'])

    async def test_show_buffers_reports_stack_depth(self):
        ctx = _make_ctx(['one', 'two', '.e s', '.s'])
        await run_editor(ctx)
        text = _sent_text(ctx)
        self.assertIn('Undo history (2 step(s)', text)
        self.assertIn('Redo history (0 step(s)', text)

    async def test_bare_edit_submenu_undo_choice(self):
        ctx = _make_ctx(['one', '.e', 'u', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), [])

    async def test_bare_edit_submenu_cancel_on_empty_response(self):
        ctx = _make_ctx(['one', '.e', '', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['one'])  # cancelled -- nothing happened

    async def test_bare_edit_submenu_move_prompts_for_range_and_destination(self):
        ctx = _make_ctx(['one', 'two', 'three', '.e', 'm', '1', '3', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['two', 'one', 'three'])


class TestJustify(unittest.IsolatedAsyncioTestCase):
    async def test_justify_center_sets_persistent_style(self):
        # Justification is metadata on the saved Line, not baked into
        # 'text' -- so the raw saved text is unchanged; only re-rendering
        # (formatting.render_lines(), what a viewer's display path does)
        # produces the padded/centered output, and it can do so at any
        # width, not just whatever was active at .J-time.
        ctx = _make_ctx(['.j c 1-2', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two'])
        self.assertEqual(_texts(result), ['one', 'two'])
        self.assertEqual([d.get('justification') for d in result], ['CENTER', 'CENTER'])
        rendered = render_lines(deserialize_lines(result), ctx, 80)
        self.assertEqual(rendered, ['one'.center(80), 'two'.center(80)])

    async def test_justify_with_no_range_changes_default_for_future_lines(self):
        ctx = _make_ctx(['.j c', 'centered later', '.s'])
        result = await run_editor(ctx)
        self.assertEqual(_texts(result), ['centered later'])
        self.assertEqual(result[0].get('justification'), 'CENTER')
        rendered = render_lines(deserialize_lines(result), ctx, 80)
        self.assertEqual(rendered, ['centered later'.center(80)])

    async def test_justify_unknown_mode_reports_error(self):
        ctx = _make_ctx(['.j z 1', '.s'])
        result = await run_editor(ctx, initial_lines=['one'])
        self.assertIn('Unknown', _sent_text(ctx))
        self.assertEqual(_texts(result), ['one'])

    async def test_justify_pack_collapses_spaces(self):
        ctx = _make_ctx(['.j p 1', '.s'])
        result = await run_editor(ctx, initial_lines=['one    two   three'])
        self.assertEqual(_texts(result), ['one two three'])

    async def test_justify_indent_default_amount(self):
        ctx = _make_ctx(['.j i 1', '', '.s'])
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertEqual(_texts(result), ['    hi'])

    async def test_justify_unindent_strips_leading_spaces(self):
        ctx = _make_ctx(['.j u 1', '.s'])
        result = await run_editor(ctx, initial_lines=['    hi'])
        self.assertEqual(_texts(result), ['hi'])

    async def test_justify_skips_immutable_lines(self):
        ctx = _make_ctx(['.j c 1', '.s'])
        lines = [Line(text='locked', line_flag=LineFlag.IMMUTABLE)]
        result = await run_editor(ctx, initial_lines=lines)
        self.assertEqual(_texts(result), ['locked'])  # unchanged -- still LEFT-justified


class TestBorder(unittest.IsolatedAsyncioTestCase):
    async def test_border_wraps_range_in_box(self):
        ctx = _make_ctx(['.b 1', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        rendered = render_lines(deserialize_lines(result), ctx, 10)
        self.assertEqual(len(rendered), 3)
        self.assertTrue(rendered[0].startswith('+'))
        self.assertTrue(rendered[-1].startswith('+'))

    async def test_border_custom_character(self):
        ctx = _make_ctx(['.b * 1', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        rendered = render_lines(deserialize_lines(result), ctx, 10)
        self.assertTrue(rendered[0].startswith('+*'))

    async def test_border_rerenders_at_any_width_since_width_isnt_baked_in(self):
        # the actual point of tagging Line with Border instead of baking
        # box-drawing characters into .text at .B-time: the saved result
        # carries no width at all -- the same saved box re-renders at
        # whatever width a given viewer needs, not stuck at whatever
        # column width was active in the author's session.
        ctx = _make_ctx(['.b 1', '.s'], screen_columns=20)
        result = await run_editor(ctx, initial_lines=['hi'])
        lines = deserialize_lines(result)
        narrow = render_lines(lines, ctx, 10)
        wide = render_lines(lines, ctx, 30)
        self.assertEqual(len(narrow[0]), 10)
        self.assertEqual(len(wide[0]), 30)


class TestUnborder(unittest.IsolatedAsyncioTestCase):
    """.U -- the inverse of .B (text_editor.py's [DONE 7/22/26] TODO)."""

    async def test_unborder_whole_buffer_removes_top_and_bottom(self):
        ctx = _make_ctx(['.b', '.u', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi', 'there'])
        self.assertEqual(_texts(result), ['hi', 'there'])
        self.assertEqual(len(result), 2)  # top/bottom markers gone

    async def test_unborder_clears_border_metadata_on_content_lines(self):
        ctx = _make_ctx(['.b', '.u', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertIsNone(result[0].get('border'))

    async def test_unborder_specific_range(self):
        # After '.b 1-2' the buffer is [TOP, hi, there, BOTTOM] (1-indexed
        # lines 1-4) -- the content lines to un-border are now 2-3.
        ctx = _make_ctx(['.b 1-2', '.u 2-3', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi', 'there'])
        self.assertEqual(_texts(result), ['hi', 'there'])

    async def test_partial_unborder_leaves_markers_for_remaining_content(self):
        """Un-boxing only the first of two boxed lines shouldn't remove
        the TOP marker (line 'there' is still boxed and needs it) or the
        BOTTOM marker (still guarding 'there'). After '.b' the buffer is
        [TOP, hi, there, BOTTOM] (1-indexed lines 1-4) -- 'hi' is line 2."""
        ctx = _make_ctx(['.b', '.u 2', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi', 'there'])
        # top, hi (unboxed), there (still boxed), bottom
        self.assertEqual(len(result), 4)
        self.assertIsNone(result[1].get('border'))
        self.assertIsNotNone(result[2].get('border'))

    async def test_partial_unborder_of_last_line_leaves_markers_for_first(self):
        """Symmetric case: un-boxing only the *last* of two boxed lines
        shouldn't remove the BOTTOM marker (still guarding 'hi') or the
        TOP marker (still guarding 'hi'). After '.b' the buffer is
        [TOP, hi, there, BOTTOM] (1-indexed lines 1-4) -- 'there' is
        line 3. This is the case the naive "only check the one adjacent
        side" version of the fix would still get wrong the other way."""
        ctx = _make_ctx(['.b', '.u 3', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi', 'there'])
        self.assertEqual(len(result), 4)
        self.assertIsNotNone(result[1].get('border'))
        self.assertIsNone(result[2].get('border'))

    async def test_unborder_on_unboxed_buffer_reports_nothing_to_do(self):
        ctx = _make_ctx(['.u', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=['hi'])
        self.assertIn('no bordered lines', _sent_text(ctx).lower())
        self.assertEqual(_texts(result), ['hi'])

    async def test_unborder_empty_buffer(self):
        ctx = _make_ctx(['.u', '.s'], screen_columns=10)
        result = await run_editor(ctx, initial_lines=[])
        self.assertIn('buffer is empty', _sent_text(ctx).lower())


def _make_real_settings_ctx(responses, translation, border_style='single', screen_columns=20):
    """Like _make_ctx(), but with a real terminal.ClientSettings object
    instead of a bare MagicMock -- needed to actually exercise
    formatting.make_box()'s codec/border_style glyph selection, since a
    MagicMock's auto-created attributes accidentally satisfy getattr()
    fallbacks without ever really testing them."""
    from terminal import ClientSettings
    settings = ClientSettings()
    settings.translation = translation
    settings.screen_columns = screen_columns
    settings.border_style = border_style
    ctx = MagicMock()
    ctx.player.client_settings = settings
    ctx.player.query_flag = MagicMock(return_value=False)
    it = iter(responses)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    ctx.send = AsyncMock()
    return ctx


class TestBorderTerminalAwareGlyphs(unittest.IsolatedAsyncioTestCase):
    """.B with no explicit character routes through formatting.make_box()
    for real terminal-correct glyphs -- verified against a real
    ClientSettings, not just a MagicMock's accidental fallback behavior."""

    async def test_ansi_client_gets_unicode_box_drawing(self):
        from terminal import Translation
        ctx = _make_real_settings_ctx(['.b 1', '.s'], Translation.ANSI)
        result = await run_editor(ctx, initial_lines=['hi'])
        rendered = render_lines(deserialize_lines(result), ctx, 20)
        self.assertEqual(rendered[0][0], '┌')
        self.assertEqual(rendered[0][-1], '┐')
        self.assertIn('│', rendered[1])

    async def test_explicit_character_ignores_client_translation(self):
        from terminal import Translation
        ctx = _make_real_settings_ctx(['.b * 1', '.s'], Translation.ANSI)
        result = await run_editor(ctx, initial_lines=['hi'])
        rendered = render_lines(deserialize_lines(result), ctx, 20)
        self.assertTrue(rendered[0].startswith('+*'))


class TestFindAndReplace(unittest.IsolatedAsyncioTestCase):
    async def test_find_reports_matches(self):
        ctx = _make_ctx(['.f', 'two', '.s'])
        result = await run_editor(ctx, initial_lines=['one', 'two', 'three'])
        self.assertIn('two', _sent_text(ctx))
        self.assertEqual(_texts(result), ['one', 'two', 'three'])

    async def test_find_wraps_match_in_brackets_for_highlighting(self):
        # buffer.text itself is untouched -- only the search-results
        # display wraps the match so ctx.send()'s highlight_brackets()
        # pass colors it.
        ctx = _make_ctx(['.f', 'cat', '.s'])
        result = await run_editor(ctx, initial_lines=['the cat sat on the cat mat'])
        self.assertIn('the [cat] sat on the [cat] mat', _sent_text(ctx))
        self.assertEqual(_texts(result), ['the cat sat on the cat mat'])

    async def test_find_no_match_reports_cleanly(self):
        ctx = _make_ctx(['.f', 'nope', '.s'])
        await run_editor(ctx, initial_lines=['one', 'two'])
        self.assertIn("No match for 'nope'", _sent_text(ctx))

    async def test_search_and_replace_counts_occurrences(self):
        ctx = _make_ctx(['.k', 'cat', 'dog', '.s'])
        result = await run_editor(ctx, initial_lines=['cat sat on the cat mat'])
        self.assertEqual(_texts(result), ['dog sat on the dog mat'])
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
        self.assertEqual(_texts(result), [])

    async def test_new_text_declined_keeps_buffer(self):
        ctx = _make_ctx(['.n', 'N', '.s'])
        result = await run_editor(ctx, initial_lines=['still here'])
        self.assertEqual(_texts(result), ['still here'])


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
        self.assertEqual(_texts(result), ['hello there'])

    async def test_put_file_collision_replace(self):
        ctx = _make_ctx(['.p dup.txt', '.s'], admin=True)
        await run_editor(ctx, initial_lines=['first'])

        ctx2 = _make_ctx(['.p dup.txt', 'r', '.s'], admin=True)
        await run_editor(ctx2, initial_lines=['second'])
        self.assertIn('Saved to dup.txt', _sent_text(ctx2))

        ctx3 = _make_ctx(['.g dup.txt', '.l', '.s'], admin=True)
        result = await run_editor(ctx3)
        self.assertEqual(_texts(result), ['second'])

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
