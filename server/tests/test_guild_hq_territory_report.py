"""tests/test_guild_hq_territory_report.py — guild_hq/main.py's Territory
report menu option: reads run/server/guild_control.json (written by
tools/nightly_guild_maintenance.py) and shows the calling guild's held
room percentages.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

import net_common
from guild_hq.main import _territory_report


class _FakeCtx:
    def __init__(self):
        self.sent: list = []

    async def send(self, *lines):
        self.sent.extend(lines)


def _flat(sent) -> list[str]:
    out = []
    for item in sent:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


class TestTerritoryReport(unittest.TestCase):
    def setUp(self):
        self._orig_run_server_dir = getattr(net_common, 'run_server_dir', None)
        self.tmp = Path('run') / 'server' / 'test_guild_hq_territory_report'
        self.tmp.mkdir(parents=True, exist_ok=True)
        net_common.run_server_dir = self.tmp

    def tearDown(self):
        import shutil
        net_common.run_server_dir = self._orig_run_server_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, guild_key='CLAW'):
        ctx = _FakeCtx()
        info = {'key': guild_key, 'name': 'Mark of the Claw'}
        asyncio.run(_territory_report(ctx, player=None, state={}, info=info))
        return _flat(ctx.sent)

    def test_reports_missing_file_gracefully(self):
        lines = self._run()
        self.assertTrue(any('No territory report yet' in ln for ln in lines))

    def test_shows_per_level_and_overall_percentages(self):
        report = {
            'generated_at': '2026-08-03T03:00:00+00:00',
            'levels': {
                '1': {'total': 100, 'counts': {'claw': 10}, 'pct': {'claw': 10.0, 'fist': 0.0, 'sword': 0.0}},
                '2': {'total': 50, 'counts': {'claw': 0}, 'pct': {'claw': 0.0, 'fist': 0.0, 'sword': 0.0}},
            },
            'overall': {'total': 150, 'counts': {'claw': 10}, 'pct': {'claw': 6.7, 'fist': 0.0, 'sword': 0.0}},
        }
        (self.tmp / 'guild_control.json').write_text(json.dumps(report))

        lines = self._run(guild_key='CLAW')
        joined = '\n'.join(lines)
        self.assertIn('Level  1', joined)
        self.assertIn('10.0%', joined)
        self.assertIn('(10/100 rooms)', joined)
        self.assertIn('Overall', joined)
        self.assertIn('6.7%', joined)
        self.assertIn('(10/150 rooms)', joined)

    def test_handles_corrupt_report_without_raising(self):
        (self.tmp / 'guild_control.json').write_text('{not valid json')
        lines = self._run()
        self.assertTrue(any('broken' in ln for ln in lines))


if __name__ == '__main__':
    unittest.main()
