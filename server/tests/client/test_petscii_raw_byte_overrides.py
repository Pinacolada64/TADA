"""tests/client/test_petscii_raw_byte_overrides.py

Unit tests for formatting._PETSCII_RAW_BYTE_OVERRIDES / petscii_encode()'s
substitution of '_'/'^' for raw PETSCII bytes cbmcodecs2 has no mapping for.

Covers the underscore fix: '_' now encodes to wire/CHROUT byte 0xE4, not
the earlier (wrong) 0x64. Screen codes (what a raw SCREEN_RAM POKE uses)
and PETSCII/CHROUT transmission codes are different numbering spaces for
the same glyph -- 0x64 is genuinely the underline-ish screen code
('▁', confirmed live via POKE 1024,100 in VICE), but as a *wire* byte
it decodes to 'D' once CHROUT converts it back to a screen code, which is
exactly what rendered as 'D' on Gadget's real hardware. 0xE4 (0x64 + 0x80)
is the wire byte CHROUT itself converts to screen code 0x64.

Run with:
    python -m pytest tests/client/test_petscii_raw_byte_overrides.py -v
"""
from __future__ import annotations

import unittest

from formatting import petscii_encode


class TestPetsciiRawByteOverrides(unittest.TestCase):

    def test_underscore_encodes_to_0xe4_not_0x64(self):
        self.assertEqual(petscii_encode('_'), bytes([0xE4]))

    def test_caret_still_encodes_to_0x5e(self):
        self.assertEqual(petscii_encode('^'), bytes([0x5E]))

    def test_underscore_and_caret_together(self):
        blob = petscii_encode('a_b^c')
        self.assertIn(0xE4, blob)
        self.assertIn(0x5E, blob)
        self.assertNotIn(0x64, blob)


if __name__ == '__main__':
    unittest.main(verbosity=2)
