"""tests/commands/test_play.py

Covers commands/play.py -- PlayCommand streams sid_engine's stub tune to
PETSCII (real C64) connections and refuses everyone else, since only a
real SID chip can do anything with the byte stream. The stub tune is
gated behind the `#test` switch -- there's no real tune library yet, so
a plain name never plays anything.
"""
from __future__ import annotations

import unittest

from commands.play import PlayCommand
from network_context import PETSCIINetworkContext
from sid_engine import frames


class _FakePetsciiCtx(PETSCIINetworkContext):
    """Minimal PETSCIINetworkContext stand-in -- isinstance() must hold for
    PlayCommand's gate, but real construction needs a live reader/writer/
    server/client, none of which this test touches."""

    def __init__(self):
        self.sent: list = []
        self.raw_sent: list[bytes] = []

    async def send(self, *lines):
        self.sent.extend(lines)

    async def send_raw(self, data: bytes):
        self.raw_sent.append(data)


class _FakeJsonCtx:
    """Plain object -- deliberately NOT a PETSCIINetworkContext."""

    def __init__(self):
        self.sent: list = []

    async def send(self, *lines):
        self.sent.extend(lines)


class TestPlayOnPetscii(unittest.IsolatedAsyncioTestCase):
    async def test_hash_test_switch_streams_encoded_stub_tune(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, '#test')

        self.assertTrue(result.success)
        self.assertEqual(len(ctx.raw_sent), 1)
        stream = ctx.raw_sent[0]
        self.assertEqual(stream[0], frames.STREAM_START)
        self.assertEqual(stream[-1], frames.STREAM_END)

    async def test_hash_test_switch_works_alongside_a_name(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle', '#test')

        self.assertTrue(result.success)
        self.assertEqual(len(ctx.raw_sent), 1)

    async def test_no_tune_name_is_an_error(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx)

        self.assertFalse(result.success)
        self.assertEqual(ctx.raw_sent, [])

    async def test_plain_name_without_switch_does_not_play_anything(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_tune_library')
        self.assertEqual(ctx.raw_sent, [])
        self.assertTrue(any('Yankee Doodle' in str(line) for line in ctx.sent))


class TestPlayOnNonPetscii(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_json_client(self):
        ctx = _FakeJsonCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_sid_chip')
        self.assertIn("SID chip", ' '.join(ctx.sent))


if __name__ == '__main__':
    unittest.main()
