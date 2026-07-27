"""tests/sid_engine/test_frames.py

Covers sid_engine/frames.py's wire encoding: (reg,val)...FRAME_END per
tick, wrapped in STREAM_START + a 16-bit length prefix for a whole tune.
"""
from __future__ import annotations

import unittest

from sid_engine import frames, stub_tune


class TestEncodeFrame(unittest.TestCase):
    def test_empty_frame_is_just_the_terminator(self):
        self.assertEqual(frames.encode_frame({}), bytes([0xff]))

    def test_single_write(self):
        self.assertEqual(frames.encode_frame({0: 0x67}), bytes([0, 0x67, 0xff]))

    def test_multiple_writes_preserve_dict_order(self):
        # dicts preserve insertion order in modern Python; the encoder
        # must not reorder registers, since some players rely on write
        # order (e.g. control register after frequency).
        writes = {frames.FREQ_LO: 0x67, frames.FREQ_HI: 0x11, frames.CONTROL: 0x11}
        encoded = frames.encode_frame(writes)
        self.assertEqual(encoded, bytes([0, 0x67, 1, 0x11, 4, 0x11, 0xff]))

    def test_register_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            frames.encode_frame({25: 0})
        with self.assertRaises(ValueError):
            frames.encode_frame({-1: 0})

    def test_value_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            frames.encode_frame({0: 256})
        with self.assertRaises(ValueError):
            frames.encode_frame({0: -1})


class TestEncodeStream(unittest.TestCase):
    def test_prefixes_body_with_start_marker_and_length(self):
        tune = [{0: 1}, {}, {1: 2}]
        encoded = frames.encode_stream(tune)

        expected_body = frames.encode_frame({0: 1}) + frames.encode_frame({}) + frames.encode_frame({1: 2})
        self.assertEqual(encoded[0], frames.STREAM_START)
        self.assertEqual(encoded[1] | (encoded[2] << 8), len(expected_body))
        self.assertEqual(encoded[3:], expected_body)

    def test_length_prefix_survives_a_literal_2_in_the_body(self):
        # The whole point of a length prefix over an in-band end marker:
        # a real register value of 2 must not be mistaken for "stream
        # over" partway through.
        tune = [{0: 2}, {0: 2}, {0: 2}]
        encoded = frames.encode_stream(tune)
        expected_body = frames.encode_frame({0: 2}) * 3
        self.assertEqual(encoded[1] | (encoded[2] << 8), len(expected_body))
        self.assertEqual(encoded[3:], expected_body)

    def test_empty_tune_is_just_the_marker_and_a_zero_length(self):
        self.assertEqual(frames.encode_stream([]), bytes([frames.STREAM_START, 0, 0]))

    def test_stub_tune_encodes_without_error(self):
        encoded = frames.encode_stream(stub_tune.generate())
        self.assertGreater(len(encoded), 3)
        self.assertEqual(encoded[0], frames.STREAM_START)
        length = encoded[1] | (encoded[2] << 8)
        self.assertEqual(length, len(encoded) - 3)


if __name__ == '__main__':
    unittest.main()
