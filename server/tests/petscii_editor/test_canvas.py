"""tests/petscii_editor/test_canvas.py

Covers petscii_editor/canvas.py: the Canvas model, the wire format
(STREAM_START+STREAM_CONFIRM+length-prefixed chars+colors, mirroring
sid_engine/frames.py's convention), and render_lines()'s `{$xx}`/
`|token|` text output.
"""
from __future__ import annotations

import unittest

from petscii_editor import canvas as canvas_wire
from petscii_editor.canvas import CELLS, Canvas, HEIGHT, WIDTH


class TestCanvas(unittest.TestCase):
    def test_default_canvas_is_blank_white(self):
        cv = Canvas()
        self.assertEqual(len(cv.chars), CELLS)
        self.assertEqual(len(cv.colors), CELLS)
        self.assertTrue(all(c == canvas_wire.BLANK_CHAR for c in cv.chars))
        self.assertTrue(all(c == canvas_wire.BLANK_COLOR for c in cv.colors))

    def test_wrong_size_chars_raises(self):
        with self.assertRaises(ValueError):
            Canvas(chars=bytearray(10), colors=bytearray(CELLS))

    def test_wrong_size_colors_raises(self):
        with self.assertRaises(ValueError):
            Canvas(chars=bytearray(CELLS), colors=bytearray(10))


class TestEncodeDownload(unittest.TestCase):
    def test_header_markers_and_length(self):
        cv = Canvas()
        encoded = canvas_wire.encode_download(cv)
        self.assertEqual(encoded[0], canvas_wire.STREAM_START)
        self.assertEqual(encoded[1], canvas_wire.STREAM_CONFIRM)
        body_len = encoded[2] | (encoded[3] << 8)
        self.assertEqual(body_len, CELLS * 2)
        self.assertEqual(len(encoded), 4 + CELLS * 2)

    def test_confirm_byte_differs_from_sid_engine(self):
        from sid_engine import frames
        self.assertNotEqual(canvas_wire.STREAM_CONFIRM, frames.STREAM_CONFIRM)

    def test_body_is_chars_then_colors(self):
        cv = Canvas()
        cv.chars[0] = 0x41
        cv.colors[0] = 2
        encoded = canvas_wire.encode_download(cv)
        self.assertEqual(encoded[4], 0x41)
        self.assertEqual(encoded[4 + CELLS], 2)


class TestDecodeUpload(unittest.TestCase):
    def test_round_trips_through_encode_download(self):
        cv = Canvas()
        cv.chars[5] = 0x99
        cv.colors[5] = 7
        cv.chars[-1] = 0x20
        decoded = canvas_wire.decode_upload(canvas_wire.encode_download(cv))
        self.assertEqual(decoded.chars, cv.chars)
        self.assertEqual(decoded.colors, cv.colors)

    def test_bad_markers_raise(self):
        cv = Canvas()
        encoded = bytearray(canvas_wire.encode_download(cv))
        encoded[1] = 0xff  # wrong confirm byte
        with self.assertRaises(ValueError):
            canvas_wire.decode_upload(bytes(encoded))

    def test_truncated_body_raises(self):
        cv = Canvas()
        encoded = canvas_wire.encode_download(cv)
        with self.assertRaises(ValueError):
            canvas_wire.decode_upload(encoded[:-1])

    def test_too_short_for_header_raises(self):
        with self.assertRaises(ValueError):
            canvas_wire.decode_upload(bytes([canvas_wire.STREAM_START]))


class TestRenderLines(unittest.TestCase):
    def test_produces_one_line_per_row(self):
        cv = Canvas()
        lines = canvas_wire.render_lines(cv)
        self.assertEqual(len(lines), HEIGHT)

    def test_emits_glyph_token_per_cell(self):
        cv = Canvas()
        cv.chars[0] = 0x41  # 'A'
        lines = canvas_wire.render_lines(cv)
        self.assertIn('{$41}', lines[0])
        # blank cells (space, $20) still get a glyph token
        self.assertIn('{$20}', lines[0])

    def test_color_token_only_on_change(self):
        cv = Canvas()  # all white by default
        lines = canvas_wire.render_lines(cv)
        # exactly one |white| token for the whole first row -- not one per cell
        self.assertEqual(lines[0].count('|white|'), 1)

    def test_color_change_mid_row_emits_new_token(self):
        cv = Canvas()
        cv.colors[1] = 2  # red, second cell of row 0
        lines = canvas_wire.render_lines(cv)
        self.assertIn('|white|', lines[0])
        self.assertIn('|red|', lines[0])

    def test_render_output_round_trips_through_petscii_encode(self):
        import formatting
        cv = Canvas()
        cv.chars[0] = 0x41
        cv.colors[0] = 2  # red
        lines = canvas_wire.render_lines(cv)
        encoded = formatting.petscii_encode(lines[0])
        self.assertEqual(encoded[0], formatting.PETSCII_CONTROL_CODES['red'])
        self.assertEqual(encoded[1], 0x41)


if __name__ == '__main__':
    unittest.main()
