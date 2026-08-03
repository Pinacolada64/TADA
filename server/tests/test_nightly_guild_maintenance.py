"""tests/test_nightly_guild_maintenance.py — nightly guild territory job:
bakes room_alignment.py sidecar overrides into level_<N>.json and writes
run/server/guild_control.json for guild_hq's territory report.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from base_classes import RoomAlignment


class _TempDirs(unittest.TestCase):
    def setUp(self):
        import room_alignment
        import tools.nightly_guild_maintenance as m

        self._orig_state_dir = room_alignment._STATE_DIR
        self._orig_server_dir = m._SERVER_DIR

        self.tmp = Path('run') / 'server' / 'test_nightly_guild_maintenance'
        self.tmp.mkdir(parents=True, exist_ok=True)

        room_alignment._STATE_DIR = self.tmp / 'sidecars'
        m._SERVER_DIR = self.tmp

        self.m = m

    def tearDown(self):
        import room_alignment
        import shutil
        room_alignment._STATE_DIR = self._orig_state_dir
        self.m._SERVER_DIR = self._orig_server_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_level(self, level: int, rooms: list) -> None:
        (self.tmp / f'level_{level}.json').write_text(json.dumps({'rooms': rooms}))


class TestBakeOverrides(_TempDirs):
    def test_bakes_override_into_level_file(self):
        from room_alignment import record_capture
        self._write_level(1, [
            {'number': 1, 'name': 'A', 'room_alignment': 'neutral'},
            {'number': 2, 'name': 'B', 'room_alignment': 'neutral'},
        ])
        record_capture(1, 2, RoomAlignment.CLAW)

        changed = self.m._bake_overrides(1)
        self.assertEqual(changed, 1)

        data = json.loads((self.tmp / 'level_1.json').read_text())
        rooms = {r['number']: r['room_alignment'] for r in data['rooms']}
        self.assertEqual(rooms, {1: 'neutral', 2: 'claw'})

    def test_clears_sidecar_after_baking(self):
        from room_alignment import record_capture, load_overrides
        self._write_level(1, [{'number': 2, 'name': 'B', 'room_alignment': 'neutral'}])
        record_capture(1, 2, RoomAlignment.CLAW)

        self.m._bake_overrides(1)
        self.assertEqual(load_overrides(1), {})

    def test_hq_room_is_never_overwritten(self):
        from room_alignment import record_capture
        self._write_level(1, [{'number': 2, 'name': 'B', 'room_alignment': 'hq'}])
        record_capture(1, 2, RoomAlignment.CLAW)

        changed = self.m._bake_overrides(1)
        self.assertEqual(changed, 0)
        data = json.loads((self.tmp / 'level_1.json').read_text())
        self.assertEqual(data['rooms'][0]['room_alignment'], 'hq')

    def test_free_fire_room_is_never_overwritten(self):
        from room_alignment import record_capture
        self._write_level(1, [{'number': 2, 'name': 'B', 'room_alignment': 'free_fire'}])
        record_capture(1, 2, RoomAlignment.CLAW)

        changed = self.m._bake_overrides(1)
        self.assertEqual(changed, 0)
        data = json.loads((self.tmp / 'level_1.json').read_text())
        self.assertEqual(data['rooms'][0]['room_alignment'], 'free_fire')

    def test_no_overrides_is_a_no_op(self):
        self._write_level(1, [{'number': 2, 'name': 'B', 'room_alignment': 'neutral'}])
        changed = self.m._bake_overrides(1)
        self.assertEqual(changed, 0)

    def test_missing_level_file_is_a_no_op(self):
        changed = self.m._bake_overrides(1)
        self.assertEqual(changed, 0)


class TestTallyLevel(_TempDirs):
    def test_tallies_counts_and_percentages(self):
        self._write_level(1, [
            {'number': 1, 'name': 'A', 'room_alignment': 'neutral'},
            {'number': 2, 'name': 'B', 'room_alignment': 'claw'},
            {'number': 3, 'name': 'C', 'room_alignment': 'claw'},
            {'number': 4, 'name': 'D', 'room_alignment': 'fist'},
        ])
        tally = self.m._tally_level(1)
        self.assertEqual(tally['total'], 4)
        self.assertEqual(tally['counts']['claw'], 2)
        self.assertEqual(tally['counts']['fist'], 1)
        self.assertEqual(tally['pct']['claw'], 50.0)
        self.assertEqual(tally['pct']['fist'], 25.0)
        self.assertEqual(tally['pct']['sword'], 0.0)


class TestRun(_TempDirs):
    def test_writes_guild_control_report(self):
        from room_alignment import record_capture
        self._write_level(1, [
            {'number': 1, 'name': 'A', 'room_alignment': 'neutral'},
            {'number': 2, 'name': 'B', 'room_alignment': 'neutral'},
        ])
        record_capture(1, 2, RoomAlignment.SWORD)
        # Levels 2-7 absent -- run() should just skip them, not raise.

        report = self.m.run()

        self.assertIn('1', report['levels'])
        self.assertEqual(report['levels']['1']['counts']['sword'], 1)
        self.assertEqual(report['overall']['total'], 2)
        self.assertEqual(report['overall']['pct']['sword'], 50.0)

        out_file = self.tmp / 'run' / 'server' / 'guild_control.json'
        self.assertTrue(out_file.exists())
        on_disk = json.loads(out_file.read_text())
        self.assertEqual(on_disk['overall']['counts']['sword'], 1)


if __name__ == '__main__':
    unittest.main()
