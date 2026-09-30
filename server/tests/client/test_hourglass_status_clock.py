"""Hourglass clock on a Commodore connection: PETSCII translation sends it
as a CLOCK_STREAM_CONFIRM stream (painted on the right side of the C64
client's status row -- commands/c64_display.py's encode_clock()) instead
of prefixing it onto the prompt; ASCII translation keeps the old inline
"[hh:mm] " prefix. Turning Hourglass off clears the client's clock once.
"""
from __future__ import annotations

import asyncio
import unittest

from flags import PlayerFlags
from player import Player
from terminal import Translation
from network_context import PETSCIINetworkContext
from commands.c64_display import (STREAM_START, CLOCK_STREAM_CONFIRM,
                                  CLOCK_MAX, encode_clock)

CLOCK_HEADER = bytes([STREAM_START, CLOCK_STREAM_CONFIRM])


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

    async def _read_cr():
        raise asyncio.IncompleteReadError(b'', None)
    ctx.reader = type('R', (), {'readuntil': staticmethod(lambda _: _read_cr())})()
    return ctx, writer


class TestEncodeClock(unittest.TestCase):

    def test_framing(self):
        self.assertEqual(encode_clock(b'12:34'),
                         CLOCK_HEADER + bytes([5, 0]) + b'12:34')

    def test_empty_hides(self):
        self.assertEqual(encode_clock(b''), CLOCK_HEADER + bytes([0, 0]))

    def test_truncated_to_client_width(self):
        out = encode_clock(b'x' * (CLOCK_MAX + 5))
        self.assertEqual(out[2], CLOCK_MAX)
        self.assertEqual(len(out), 4 + CLOCK_MAX)


class TestHourglassPrompt(unittest.IsolatedAsyncioTestCase):

    async def test_petscii_sends_status_clock_not_prefix(self):
        ctx, writer = _make_ctx(Translation.PETSCII)
        ctx.player.set_flag(PlayerFlags.HOURGLASS)
        await ctx.prompt('main')
        blob = b''.join(writer.chunks)
        self.assertTrue(blob.startswith(CLOCK_HEADER))
        self.assertGreater(blob[2], 0)
        self.assertNotIn(b'[', blob)

    async def test_ascii_keeps_inline_prefix(self):
        ctx, writer = _make_ctx(Translation.ASCII)
        ctx.player.set_flag(PlayerFlags.HOURGLASS)
        await ctx.prompt('main')
        blob = b''.join(writer.chunks)
        self.assertNotIn(CLOCK_HEADER, blob)
        self.assertTrue(blob.startswith(b'['))
        self.assertIn(b'main > ', blob)

    async def test_off_sends_nothing_until_it_was_shown(self):
        ctx, writer = _make_ctx(Translation.PETSCII)
        ctx.player.clear_flag(PlayerFlags.HOURGLASS)
        await ctx.prompt('main')
        self.assertNotIn(CLOCK_HEADER, b''.join(writer.chunks))

    async def test_turning_off_clears_clock_once(self):
        ctx, writer = _make_ctx(Translation.PETSCII)
        ctx.player.set_flag(PlayerFlags.HOURGLASS)
        await ctx.prompt('main')
        ctx.player.clear_flag(PlayerFlags.HOURGLASS)

        writer.chunks.clear()
        await ctx.prompt('main')
        self.assertTrue(b''.join(writer.chunks).startswith(encode_clock(b'')))

        writer.chunks.clear()
        await ctx.prompt('main')
        self.assertNotIn(CLOCK_HEADER, b''.join(writer.chunks))


if __name__ == '__main__':
    unittest.main()
