"""tests/client/test_tada_client_transcript_log.py

Covers tada_client.py's --log transcript writing: _append_output()
mirrors every line it appends to the output buffer into _transcript_fp
when one is set. Found live 2026-08-27 that --log alone (without
--debug) produced an effectively empty file, because it only ever
controlled Python's own logging.basicConfig() filename -- this module
has no log.debug()/info() calls at all, so there was nothing for that
mechanism to capture. _append_output() is the one choke point every
line shown on screen passes through (server output, disconnect
notices, and the '> <text>' echo of what the player typed), so mirroring
it there captures the actual gameplay session instead.
"""
from __future__ import annotations

import io
import unittest

from prompt_toolkit.buffer import Buffer

import tada_client as tc


class TestTranscriptLogging(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, tc, '_transcript_fp', tc._transcript_fp)
        tc._transcript_fp = None

    def test_no_transcript_fp_does_not_raise(self):
        buf = Buffer(name='output')
        tc._append_output(buf, ['hello'])  # must not raise with no fp set

    def test_lines_written_to_transcript_fp(self):
        fp = io.StringIO()
        tc._transcript_fp = fp
        buf = Buffer(name='output')
        tc._append_output(buf, ['Date: Saturday, Jul 25, 2026 10:31 AM', 'Title: Test post'])
        self.assertEqual(fp.getvalue(),
                          'Date: Saturday, Jul 25, 2026 10:31 AM\nTitle: Test post\n')

    def test_typed_input_echo_is_captured(self):
        # _input_loop() calls _append_output(output_buffer, [f'> {text}'])
        # to echo what the player typed -- a transcript needs that too,
        # not just server output.
        fp = io.StringIO()
        tc._transcript_fp = fp
        buf = Buffer(name='output')
        tc._append_output(buf, ['> look'])
        self.assertIn('> look', fp.getvalue())

    def test_empty_lines_list_writes_nothing(self):
        fp = io.StringIO()
        tc._transcript_fp = fp
        buf = Buffer(name='output')
        tc._append_output(buf, [])
        self.assertEqual(fp.getvalue(), '')

    def test_multiple_appends_accumulate_in_order(self):
        fp = io.StringIO()
        tc._transcript_fp = fp
        buf = Buffer(name='output')
        tc._append_output(buf, ['first'])
        tc._append_output(buf, ['second'])
        self.assertEqual(fp.getvalue(), 'first\nsecond\n')


if __name__ == '__main__':
    unittest.main()
