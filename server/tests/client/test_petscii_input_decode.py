"""tests/client/test_petscii_input_decode.py

Unit tests for network_context._petscii_input_to_ascii() -- the raw
keyboard-byte-to-ASCII decode used only for real PETSCII-port (C64
hardware) connections.

Covers the underscore fix: Shift+Space (raw byte 0xA0, the C64's own
stock KERNAL keyboard-decode-table value for that key combo -- verified
via py65 disassembly of kernal-901246-01.bin, matrix position 60) now
decodes to '_', while the back-arrow key (0x5F) is deliberately left
unhandled/discarded, reserved for the map/overview display's directional
arrows on the output side instead.

Run with:
    python -m pytest tests/client/test_petscii_input_decode.py -v
"""
from __future__ import annotations

import unittest

from network_context import _petscii_input_to_ascii


class TestPetsciiInputDecode(unittest.TestCase):

    def test_space_stays_space(self):
        self.assertEqual(_petscii_input_to_ascii(bytes([0x20])), ' ')

    def test_shift_space_decodes_to_underscore(self):
        self.assertEqual(_petscii_input_to_ascii(bytes([0xA0])), '_')

    def test_up_arrow_key_decodes_to_caret(self):
        self.assertEqual(_petscii_input_to_ascii(bytes([0x5E])), '^')

    def test_back_arrow_key_is_discarded_not_underscore(self):
        # Reserved for the map/overview display's directional arrows on
        # the output side -- deliberately NOT a stand-in for underscore
        # on input (an earlier version of this mapping used it).
        self.assertEqual(_petscii_input_to_ascii(bytes([0x5F])), '')

    def test_raw_byte_0x64_is_not_underscore(self):
        # An earlier, buggy version of this mapping treated 0x64 as
        # underscore input, colliding with plain lowercase 'd' (0x64
        # falls inside the 0x61-0x7A a-z range) and breaking typing 'd'.
        self.assertEqual(_petscii_input_to_ascii(bytes([0x64])), 'd')

    def test_unshifted_letters_lowercase(self):
        self.assertEqual(_petscii_input_to_ascii(bytes([0x41, 0x5A])), 'az')

    def test_shifted_letters_uppercase(self):
        self.assertEqual(_petscii_input_to_ascii(bytes([0xC1, 0xDA])), 'AZ')

    def test_password_with_shift_space_round_trips_as_underscore(self):
        # 'se_cret' typed with Shift+Space for the underscore.
        raw = bytes([0x53, 0x45, 0xA0, 0x43, 0x52, 0x45, 0x54])
        self.assertEqual(_petscii_input_to_ascii(raw), 'se_cret')


if __name__ == '__main__':
    unittest.main(verbosity=2)
