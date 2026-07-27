"""tests/sid_engine/test_sid_file.py

Covers sid_engine/sid_file.py's PSID header parser against hand-built
header bytes -- no real .sid file needed.
"""
from __future__ import annotations

import struct
import unittest

from sid_engine import sid_file


def _psid_header(*, version=2, load_address=0x1000, init_address=0x1000,
                  play_address=0x1001, num_songs=1, start_song=1, speed=0,
                  name=b'Test Tune', author=b'Ryan', released=b'2026 TADA') -> bytes:
    header = bytearray(0x76)
    header[0:4] = b'PSID'
    struct.pack_into('>7H', header, 4, version, 0x76, load_address,
                      init_address, play_address, num_songs, start_song)
    struct.pack_into('>I', header, 0x12, speed)
    header[0x16:0x16 + len(name)] = name
    header[0x36:0x36 + len(author)] = author
    header[0x56:0x56 + len(released)] = released
    return bytes(header)


class TestParseValidHeader(unittest.TestCase):
    def test_parses_fields(self):
        raw = _psid_header() + bytes([0xAA, 0xBB])
        sid = sid_file.parse(raw)

        self.assertEqual(sid.load_address, 0x1000)
        self.assertEqual(sid.init_address, 0x1000)
        self.assertEqual(sid.play_address, 0x1001)
        self.assertEqual(sid.num_songs, 1)
        self.assertEqual(sid.start_song, 1)
        self.assertEqual(sid.name, 'Test Tune')
        self.assertEqual(sid.author, 'Ryan')
        self.assertEqual(sid.released, '2026 TADA')
        self.assertEqual(sid.data, bytes([0xAA, 0xBB]))

    def test_zero_init_address_means_same_as_load_address(self):
        raw = _psid_header(init_address=0) + bytes([0x60])
        sid = sid_file.parse(raw)
        self.assertEqual(sid.init_address, sid.load_address)

    def test_embedded_load_address_when_header_load_address_is_zero(self):
        # First two bytes of data are the little-endian load address, same
        # as a raw .prg -- rest of data follows.
        raw = _psid_header(load_address=0, init_address=0x2000, play_address=0x2001) \
            + bytes([0x00, 0x20, 0x60, 0x60])
        sid = sid_file.parse(raw)
        self.assertEqual(sid.load_address, 0x2000)
        self.assertEqual(sid.data, bytes([0x60, 0x60]))

    def test_out_of_range_start_song_defaults_to_one(self):
        raw = _psid_header(num_songs=3, start_song=9) + bytes([0x60])
        sid = sid_file.parse(raw)
        self.assertEqual(sid.start_song, 1)


class TestParseRejectsUnsupported(unittest.TestCase):
    def test_rejects_rsid(self):
        raw = bytearray(_psid_header())
        raw[0:4] = b'RSID'
        with self.assertRaises(sid_file.SidFileError):
            sid_file.parse(bytes(raw))

    def test_rejects_unknown_magic(self):
        raw = bytearray(_psid_header())
        raw[0:4] = b'NOPE'
        with self.assertRaises(sid_file.SidFileError):
            sid_file.parse(bytes(raw))

    def test_rejects_too_short_file(self):
        with self.assertRaises(sid_file.SidFileError):
            sid_file.parse(b'PSID' + b'\x00' * 10)

    def test_rejects_zero_play_address(self):
        raw = _psid_header(play_address=0) + bytes([0x60])
        with self.assertRaises(sid_file.SidFileError):
            sid_file.parse(raw)


if __name__ == '__main__':
    unittest.main()
