"""tests/commands/test_play.py

Covers commands/play.py -- PlayCommand streams sid_engine's stub tune to
PETSCII (real C64) connections and refuses everyone else, since only a
real SID chip can do anything with the byte stream. The stub tune is
gated behind the `#test` switch, independent of TUNES_DIR; a plain name
looks up a pre-rendered .frames file there (see tools/sid_to_frames.py).
"""
from __future__ import annotations

import json
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
        self.assertEqual(stream[1], frames.STREAM_CONFIRM)
        length = stream[2] | (stream[3] << 8)
        self.assertEqual(length, len(stream) - 4)

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

    async def test_hash_stop_switch_sends_stop_byte(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, '#stop')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [bytes([frames.STOP])])

    async def test_hash_about_switch_lists_credits(self):
        ctx = _FakePetsciiCtx()
        result = await PlayCommand().execute(ctx, '#about')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [])
        flat = ' '.join(str(line) for lines in ctx.sent for line in
                         (lines if isinstance(lines, list) else [lines]))
        self.assertIn('py65', flat)
        self.assertIn('Claude', flat)


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


class TestPlaySubtunesWithManifest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tunes_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)

        self.streams = {n: frames.encode_stream([{0: n}]) for n in (1, 2, 3)}
        for n, stream in self.streams.items():
            (self.tunes_dir / f'ultima3.song{n}.frames').write_bytes(stream)
        (self.tunes_dir / 'ultima3.frames').write_bytes(self.streams[1])  # start_song=1

        manifest = {
            'title': 'Ultima III - Exodus', 'author': 'Kenneth W. Arnold',
            'released': '1983 Origin Systems', 'num_songs': 3, 'start_song': 1,
            'source': 'HVSC test fixture', 'subtune_names': {'2': 'Wander'},
        }
        (self.tunes_dir / 'ultima3.json').write_text(json.dumps(manifest))

    async def test_plain_name_plays_start_song_with_header(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'ultima3')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [self.streams[1]])
        flat = ' '.join(str(line) for line in ctx.sent)
        self.assertIn('Kenneth W. Arnold', flat)
        self.assertIn('subtune 1/3', flat)

    async def test_trailing_number_selects_subtune_and_shows_its_name(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'ultima3', '2')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [self.streams[2]])
        flat = ' '.join(str(line) for line in ctx.sent)
        self.assertIn('subtune 2/3', flat)
        self.assertIn('Wander', flat)

    async def test_subtune_without_a_stil_name_still_plays(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'ultima3', '3')

        self.assertTrue(result.success)
        self.assertEqual(ctx.raw_sent, [self.streams[3]])

    async def test_out_of_range_subtune_is_an_error(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, 'ultima3', '9')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'subtune_not_found')
        self.assertEqual(ctx.raw_sent, [])


class TestPlayDirSwitch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tunes_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)

    def _flat_sent(self, ctx) -> str:
        return ' '.join(str(line) for lines in ctx.sent for line in
                         (lines if isinstance(lines, list) else [lines]))

    async def test_empty_library_says_so(self):
        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, '#dir')

        self.assertTrue(result.success)
        self.assertIn('empty', self._flat_sent(ctx).lower())

    async def test_lists_tune_without_manifest_by_key_only(self):
        stream = frames.encode_stream([{0: 1}])
        (self.tunes_dir / 'vibratotest.frames').write_bytes(stream)

        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, '#dir')

        self.assertTrue(result.success)
        self.assertIn('vibratotest', self._flat_sent(ctx))
        self.assertEqual(ctx.raw_sent, [])  # #dir only lists, never streams

    async def test_lists_tune_with_manifest_and_subtune_count(self):
        stream = frames.encode_stream([{0: 1}])
        (self.tunes_dir / 'ultima3.frames').write_bytes(stream)
        (self.tunes_dir / 'ultima3.song1.frames').write_bytes(stream)
        manifest = {
            'title': 'Ultima III - Exodus', 'author': 'Kenneth W. Arnold',
            'released': '1983 Origin Systems', 'num_songs': 10, 'start_song': 1,
            'source': '', 'subtune_names': {},
        }
        (self.tunes_dir / 'ultima3.json').write_text(json.dumps(manifest))

        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, '#dir')

        flat = self._flat_sent(ctx)
        self.assertTrue(result.success)
        self.assertIn('Ultima III - Exodus', flat)
        self.assertIn('Kenneth W. Arnold', flat)
        self.assertIn('10 subtunes', flat)

    async def test_song_files_are_not_listed_as_separate_tunes(self):
        stream = frames.encode_stream([{0: 1}])
        (self.tunes_dir / 'ultima3.frames').write_bytes(stream)
        (self.tunes_dir / 'ultima3.song1.frames').write_bytes(stream)
        (self.tunes_dir / 'ultima3.song2.frames').write_bytes(stream)

        ctx = _FakePetsciiCtx()
        with patch('commands.play.TUNES_DIR', self.tunes_dir):
            result = await PlayCommand().execute(ctx, '#dir')

        self.assertTrue(result.success)
        self.assertEqual(result.message, 'Listed 1 tune(s).')


class TestPlayOnNonPetscii(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_json_client(self):
        ctx = _FakeJsonCtx()
        result = await PlayCommand().execute(ctx, 'Yankee', 'Doodle')

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_sid_chip')
        self.assertIn("SID chip", ' '.join(ctx.sent))


if __name__ == '__main__':
    unittest.main()
