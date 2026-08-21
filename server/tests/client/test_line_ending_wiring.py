"""tests/client/test_line_ending_wiring.py

PREFS 'L' (Line Ending) previously only stored the player's CR/LF/CRLF
choice on client_settings.line_ending -- PETSCIINetworkContext always sent
the hardcoded Commodore CR (b'\\r') regardless. This verifies the raw
PETSCII send path now actually honors the stored preference.

Run with:
    python -m pytest tests/client/test_line_ending_wiring.py -v
"""
from __future__ import annotations

import unittest

from player import Player
from terminal import LineEnding, Translation
from network_context import PETSCIINetworkContext


class _FakeWriter:
    def __init__(self):
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        pass


def _make_ctx(line_ending: str) -> tuple[PETSCIINetworkContext, _FakeWriter]:
    player = Player()
    player.client_settings.translation = Translation.PETSCII
    player.client_settings.line_ending = line_ending
    writer = _FakeWriter()
    ctx = PETSCIINetworkContext(player=player, reader=None, writer=writer,
                                 server=None, client=None)
    return ctx, writer


class TestLineEndingWiring(unittest.IsolatedAsyncioTestCase):

    async def test_lf_preference_used_on_send(self):
        ctx, writer = _make_ctx(LineEnding.LF)
        await ctx._send_formatted(['one', 'two'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'\n', blob)
        self.assertNotIn(b'\r', blob)

    async def test_crlf_preference_used_on_send(self):
        ctx, writer = _make_ctx(LineEnding.CRLF)
        await ctx._send_formatted(['one', 'two'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'\r\n', blob)

    async def test_cr_preference_used_on_send(self):
        ctx, writer = _make_ctx(LineEnding.CR)
        await ctx._send_formatted(['one', 'two'])
        blob = b''.join(writer.chunks)
        self.assertIn(b'\r', blob)
        self.assertNotIn(b'\n', blob)

    async def test_unset_line_ending_falls_back_to_class_default(self):
        ctx, writer = _make_ctx(LineEnding.CR)
        ctx.player.client_settings.line_ending = ''
        await ctx._send_formatted(['one'])
        blob = b''.join(writer.chunks)
        self.assertIn(PETSCIINetworkContext.LINE_ENDING, blob)


if __name__ == '__main__':
    unittest.main()
