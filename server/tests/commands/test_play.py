"""tests/commands/test_play.py

Covers commands/play.py -- PlayCommand streams sid_engine's stub tune to
PETSCII (real C64) connections and refuses everyone else, since only a
real SID chip can do anything with the byte stream. The stub tune is
gated behind the `#test` switch, independent of TUNES_DIR; a plain name
looks up a pre-rendered .frames file there (see tools/sid_to_frames.py).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        length = stream[1] | (stream[2] << 8)
        self.assertEqual(length, len(stream) - 3)

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

    async def test_unknown_tune_name_is_an_error(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'tune_not_found')
        self.assertEqual(ctx.raw_sent, [])
        self.assertTrue(any('Yankee Doodle' in str(line) for line in ctx.sent))


class TestPlayFromTuneLibrary(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tunes_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)
        self.fixture_stream = frames.encode_stream([{0: 1}, {}, {1: 2}])
        (self.tunes_dir / 'vibratotest.frames').write_bytes(self.fixture_stream)

    async def test_finds_tune_by_exact_name(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'vibratotest')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [self.fixture_stream])

    async def test_lookup_is_case_and_whitespace_insensitive(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'Vibrato', 'Test')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [self.fixture_stream])

    async def test_missing_tune_in_a_populated_library_still_errors(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'nope')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'tune_not_found')
        self.assertEqual(ctx.raw_sent, [])


class TestPlayOnNonPetscii(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_json_client(self):
        ctx = _FakeJsonCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_sid_chip')
        self.assertIn("SID chip", ' '.join(ctx.sent))


if __name__ == '__main__':
    unittest.main()
