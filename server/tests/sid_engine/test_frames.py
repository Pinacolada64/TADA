"""tests/sid_engine/test_frames.py

Covers sid_engine/frames.py's wire encoding: (reg,val)...FRAME_END per
tick, wrapped in STREAM_START+STREAM_CONFIRM + a 16-bit length prefix for
a whole tune.
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
    def test_prefixes_body_with_start_confirm_and_length(self):
        tune = [{0: 1}, {}, {1: 2}]
        encoded = frames.encode_stream(tune)

        expected_body = frames.encode_frame({0: 1}) + frames.encode_frame({}) + frames.encode_frame({1: 2})
        self.assertEqual(encoded[0], frames.STREAM_START)
        self.assertEqual(encoded[1], frames.STREAM_CONFIRM)
        self.assertEqual(encoded[2] | (encoded[3] << 8), len(expected_body))
        self.assertEqual(encoded[4:], expected_body)

    def test_length_prefix_survives_a_literal_2_in_the_body(self):
        # The whole point of a length prefix over an in-band end marker:
        # a real register value of 2 must not be mistaken for "stream
        # over" partway through.
        tune = [{0: 2}, {0: 2}, {0: 2}]
        encoded = frames.encode_stream(tune)
        expected_body = frames.encode_frame({0: 2}) * 3
        self.assertEqual(encoded[2] | (encoded[3] << 8), len(expected_body))
        self.assertEqual(encoded[4:], expected_body)

    def test_empty_tune_is_just_the_markers_and_a_zero_length(self):
        self.assertEqual(frames.encode_stream([]),
                          bytes([frames.STREAM_START, frames.STREAM_CONFIRM, 0, 0]))

    def test_stub_tune_encodes_without_error(self):
        encoded = frames.encode_stream(stub_tune.generate())
        self.assertGreater(len(encoded), 4)
        self.assertEqual(encoded[0], frames.STREAM_START)
        self.assertEqual(encoded[1], frames.STREAM_CONFIRM)
        length = encoded[2] | (encoded[3] << 8)
        self.assertEqual(length, len(encoded) - 4)

    def _split_chunks(self, encoded: bytes) -> list[bytes]:
        """Walk a possibly-multi-chunk transmission and return each
        chunk's body, asserting every header is well-formed along the
        way -- shared helper for the chunking tests below."""
        bodies = []
        i = 0
        while i < len(encoded):
            self.assertEqual(encoded[i], frames.STREAM_START)
            self.assertEqual(encoded[i + 1], frames.STREAM_CONFIRM)
            length = encoded[i + 2] | (encoded[i + 3] << 8)
            i += 4
            bodies.append(encoded[i:i + length])
            i += length
        self.assertEqual(i, len(encoded), 'trailing bytes past the last chunk')
        return bodies

    def test_a_tune_under_the_cap_is_a_single_chunk(self):
        tune = [{0: 1}] * 100
        bodies = self._split_chunks(frames.encode_stream(tune))
        self.assertEqual(len(bodies), 1)

    def test_a_tune_over_the_cap_splits_into_multiple_chunks_on_frame_boundaries(self):
        # Each frame is 3 bytes (reg, val, FRAME_END); force a split with
        # a tiny cap instead of a real ~65535-byte tune, so the test
        # stays fast and the boundary math stays checkable by hand.
        frame = {0: 1}
        frame_bytes = frames.encode_frame(frame)
        tune = [frame] * 10
        old_cap, frames.MAX_CHUNK_BODY = frames.MAX_CHUNK_BODY, len(frame_bytes) * 3
        try:
            bodies = self._split_chunks(frames.encode_stream(tune))
        finally:
            frames.MAX_CHUNK_BODY = old_cap
        # 10 frames at 3-per-chunk: three full chunks + a one-frame tail.
        self.assertEqual([len(b) // len(frame_bytes) for b in bodies], [3, 3, 3, 1])
        self.assertEqual(b''.join(bodies), frame_bytes * 10)

    def test_no_chunk_ever_exceeds_max_chunk_body(self):
        frame = {0: 1}
        frame_bytes = frames.encode_frame(frame)
        tune = [frame] * 10
        old_cap, frames.MAX_CHUNK_BODY = frames.MAX_CHUNK_BODY, len(frame_bytes) * 3
        try:
            bodies = self._split_chunks(frames.encode_stream(tune))
        finally:
            frames.MAX_CHUNK_BODY = old_cap
        for body in bodies:
            self.assertLessEqual(len(body), len(frame_bytes) * 3)


if __name__ == '__main__':
    unittest.main()
