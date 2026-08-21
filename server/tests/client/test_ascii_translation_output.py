"""tests/client/test_ascii_translation_output.py

Ryan: "The whole point of being able to change translation to ASCII is so
that the client receives ASCII despite being on a Commodore machine."

Before this, a real PETSCII connection (PETSCIINetworkContext) always
text-encoded outgoing bytes via cbmcodecs2's 'petscii_c64en_lc' codec
(network_context.py's CODEC_NAME), regardless of client_settings.
translation -- switching PREFS 'T' Client Type to ASCII/Plain only
stripped color tokens (PlainCodec), it never actually changed the byte
encoding. A Commodore machine that picked ASCII still received
PETSCII-transliterated screen codes, not real ASCII bytes -- e.g. 'Hello'
encoded as b'\\xc8ELLO' via petscii_c64en_lc, not b'Hello'.

_text_codec_name() (network_context.py) now switches the codec_name to
Python's builtin 'ascii' when translation is Translation.ASCII, and
apply_overrides=False (formatting.py's petscii_encode/petscii_encode_lines/
_encode_petscii_segment) disables the PETSCII-specific '_'/'^' glyph
substitutions that only make sense for genuine PETSCII output.

Run with:
    python -m pytest tests/client/test_ascii_translation_output.py -v
"""
from __future__ import annotations

import unittest

from player import Player
from terminal import Translation
from network_context import PETSCIINetworkContext


class _FakeWriter:
    def __init__(self):
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        pass


def _make_ctx(translation) -> tuple[PETSCIINetworkContext, _FakeWriter]:
    player = Player()
    player.client_settings.translation = translation
    writer = _FakeWriter()
    ctx = PETSCIINetworkContext(player=player, reader=None, writer=writer,
                                 server=None, client=None)
    return ctx, writer


class TestAsciiTranslationSendsRealAscii(unittest.IsolatedAsyncioTestCase):

    async def test_petscii_translation_transliterates_to_screen_codes(self):
        """Baseline: PETSCII translation still sends real PETSCII bytes,
        not plain ASCII -- 'Hello World' does NOT round-trip byte-for-byte."""
        ctx, writer = _make_ctx(Translation.PETSCII)
        await ctx._send_formatted(['Hello World'])
        blob = b''.join(writer.chunks)
        self.assertNotIn(b'Hello World', blob)

    async def test_ascii_translation_sends_literal_ascii_bytes(self):
        """The actual point of the feature: picking ASCII must make the
        wire bytes real ASCII, byte-for-byte, not PETSCII-transliterated
        text with just the color codes removed."""
        ctx, writer = _make_ctx(Translation.ASCII)
        await ctx._send_formatted(['Hello World'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'Hello World', blob)

    async def test_ascii_translation_preserves_case(self):
        """petscii_c64en_lc swaps upper/lowercase in its byte mapping --
        confirm ASCII translation does not carry that transliteration
        over (real ASCII: 'A' == 0x41, 'a' == 0x61)."""
        ctx, writer = _make_ctx(Translation.ASCII)
        await ctx._send_formatted(['AaBbCc'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'AaBbCc', blob)

    async def test_ascii_translation_keeps_literal_underscore_and_caret(self):
        """_encode_petscii_segment substitutes '_'/'^' for PETSCII glyph
        bytes (0x64/0x5E) by default -- genuine ASCII output must keep
        their real ASCII byte values (0x5F/0x5E-as-ascii) instead."""
        ctx, writer = _make_ctx(Translation.ASCII)
        await ctx._send_formatted(['under_score^caret'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'under_score^caret', blob)

    async def test_ascii_translation_strips_color_tokens_no_control_bytes(self):
        """|token| color markup must vanish (PlainCodec via format_lines
        upstream), not turn into PETSCII control bytes."""
        ctx, writer = _make_ctx(Translation.ASCII)
        from formatting import codec_for_settings, format_lines
        codec = codec_for_settings(ctx.player.client_settings)
        formatted = format_lines(['|red|Warning|reset|: watch out'],
                                  ctx.player.client_settings, codec)
        await ctx._send_formatted(formatted)
        blob = b''.join(writer.chunks)
        self.assertIn(b'Warning', blob)
        self.assertIn(b'watch out', blob)
        # No PETSCII red (0x1C) or reverse-off (0x92) control bytes.
        self.assertNotIn(b'\x1c', blob)
        self.assertNotIn(b'\x92', blob)

    async def test_ascii_prompt_text_is_real_ascii(self):
        """prompt() writes prompt text directly (not via _send_formatted)
        -- confirm it also honors ASCII translation."""
        ctx, writer = _make_ctx(Translation.ASCII)

        async def _read_cr():
            raise __import__('asyncio').IncompleteReadError(b'', None)
        ctx.reader = type('R', (), {'readuntil': staticmethod(lambda _: _read_cr())})()
        await ctx.prompt('main')
        blob = b''.join(writer.chunks)
        self.assertIn(b'main > ', blob)


if __name__ == '__main__':
    unittest.main()
