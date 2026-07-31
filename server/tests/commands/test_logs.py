"""tests/commands/test_logs.py

Covers commands/logs.py (admin/DM tool to browse server-side log
sources) and combat.engine.load_all_statues() (the startup snapshot of
every monster's memorial file, wired into simple_server.Server via
self.statues -- see combat/engine.py's _record_statue()/
first_statue_victim(), the read/write pair this snapshot mirrors):

  - Non-admin/DM players are refused outright.
  - Bare `logs` shows the numbered source menu, then a day sub-menu;
    any day but Today reports "not available yet" (log rotation isn't
    implemented).
  - `logs #system` / `logs #statues` / `logs #battle` skip the source
    menu and go straight to the day prompt.
  - The statues view renders every monster's full victim list, oldest
    first, sourced from ctx.server.statues (falling back to
    load_all_statues() if the server has none cached).
  - The system/battle views tail the last lines of run/server/log and
    run/server/battle.log.
  - Each view accepts an optional player filter (system: `player`
    column match; battle: substring anywhere in the line; statues:
    victim-name match), and the system view additionally accepts an
    optional module filter (`module.funcName` prefix match).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from combat.engine import _record_statue, load_all_statues
from commands.logs import LogsCommand
from flags import PlayerFlags


class _FakeCtx:
    def __init__(self, player, server, prompt_answers=None):
        self.player = player
        self.server = server
        self.client = MagicMock()
        self._sent: list = []
        self._prompt_answers = list(prompt_answers or [])

    async def send(self, *args, **kwargs):
        for a in args:
            if isinstance(a, list):
                self._sent.extend(str(x) for x in a)
            else:
                self._sent.append(str(a))

    async def prompt(self, *args, **kwargs):
        return self._prompt_answers.pop(0) if self._prompt_answers else ''

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _player(*, admin=False):
    p = MagicMock()
    p.query_flag.side_effect = lambda flag: admin and flag in (
        PlayerFlags.ADMIN, PlayerFlags.DUNGEON_MASTER)
    p.client_settings.screen_columns = 78
    p.client_settings.border_style = 'single'
    p.client_settings.codec = None
    return p


def _server():
    s = MagicMock()
    s.statues = {}
    return s


class _IsolatedRunDirTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import net_common
        self.tmpdir = tempfile.mkdtemp(prefix='tada-logs-test-')
        self._orig_run_dir = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self.tmpdir

    def tearDown(self):
        import net_common, shutil
        net_common.run_server_dir = self._orig_run_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestPermissions(_IsolatedRunDirTest):
    async def test_non_admin_refused(self):
        ctx = _FakeCtx(_player(admin=False), _server())
        result = await LogsCommand().execute(ctx)
        self.assertFalse(result.success)
        self.assertIn("don't have permission", ctx.sent())


class TestSourceMenu(_IsolatedRunDirTest):
    async def test_bare_logs_shows_numbered_menu(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=[''])
        await LogsCommand().execute(ctx)
        out = ctx.sent()
        self.assertIn('1. System logs', out)
        self.assertIn('2. Statue memorials', out)
        self.assertIn('3. Battle log', out)

    async def test_cancel_on_blank_source_choice(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=[''])
        result = await LogsCommand().execute(ctx)
        self.assertTrue(result.success)
        self.assertNotIn('Which day?', ctx.sent())

    async def test_numeric_choice_then_today_shows_statues(self):
        _record_statue('MEDUSA', 'Alice')
        server = _server()
        server.statues = load_all_statues()
        ctx = _FakeCtx(_player(admin=True), server, prompt_answers=['2', '', ''])
        await LogsCommand().execute(ctx)
        self.assertIn('Hall of Statues', ctx.sent())
        self.assertIn('Alice', ctx.sent())


class TestDayMenu(_IsolatedRunDirTest):
    async def test_non_today_day_reports_unavailable(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['mon'])
        await LogsCommand().execute(ctx, '#statues')
        self.assertIn("isn't available yet", ctx.sent())
        self.assertIn('log rotation', ctx.sent())

    async def test_invalid_day_choice(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['nonsense'])
        await LogsCommand().execute(ctx, '#statues')
        self.assertIn('Invalid selection.', ctx.sent())


class TestStatuesView(_IsolatedRunDirTest):
    async def test_shows_all_victims_oldest_first(self):
        _record_statue('MEDUSA', 'Alice')
        _record_statue('MEDUSA', 'Bilbo')
        server = _server()
        server.statues = load_all_statues()
        ctx = _FakeCtx(_player(admin=True), server, prompt_answers=['', ''])
        await LogsCommand().execute(ctx, '#statues')
        out = ctx.sent()
        self.assertIn('MEDUSA', out)
        self.assertIn('Alice', out)
        self.assertIn('Bilbo', out)
        self.assertLess(out.index('Alice'), out.index('Bilbo'))

    async def test_falls_back_to_load_all_statues_when_server_has_none(self):
        _record_statue('GORGON', 'Carol')
        server = _server()
        server.statues = None
        ctx = _FakeCtx(_player(admin=True), server, prompt_answers=['', ''])
        await LogsCommand().execute(ctx, '#statues')
        self.assertIn('Carol', ctx.sent())

    async def test_no_statues_yet(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', ''])
        await LogsCommand().execute(ctx, '#statues')
        self.assertIn('No statues have been carved yet.', ctx.sent())


class TestSystemAndBattleViews(_IsolatedRunDirTest):
    async def test_system_log_tail(self):
        Path(self.tmpdir, 'log').write_text('line1\nline2\nline3\n')
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', ''])
        await LogsCommand().execute(ctx, '#system')
        out = ctx.sent()
        self.assertIn('line1', out)
        self.assertIn('line3', out)

    async def test_missing_system_log(self):
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', ''])
        await LogsCommand().execute(ctx, '#system')
        self.assertIn('No system log found.', ctx.sent())

    async def test_battle_log_tail(self):
        Path(self.tmpdir, 'battle.log').write_text('[stamp] Goblin slain by Rulan\n')
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=[''])
        await LogsCommand().execute(ctx, '#battle')
        self.assertIn('Goblin slain by Rulan', ctx.sent())


class TestFiltering(_IsolatedRunDirTest):
    async def test_system_log_filtered_by_player(self):
        Path(self.tmpdir, 'log').write_text(
            '2026-07-31 07:00:00,000 | INFO     | Rulan            | simple_server.foo: hello\n'
            '2026-07-31 07:00:01,000 | INFO     | Bilbo            | simple_server.foo: hi\n'
        )
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', 'Rulan', ''])
        await LogsCommand().execute(ctx, '#system')
        out = ctx.sent()
        self.assertIn('Rulan', out)
        self.assertNotIn('Bilbo', out)
        self.assertIn('player=Rulan', out)

    async def test_system_log_filtered_by_module(self):
        Path(self.tmpdir, 'log').write_text(
            '2026-07-31 07:00:00,000 | INFO     | Rulan            | combat.engine.foo: fight\n'
            '2026-07-31 07:00:01,000 | INFO     | Rulan            | commands.say.foo: talk\n'
        )
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', '', 'combat.engine'])
        await LogsCommand().execute(ctx, '#system')
        out = ctx.sent()
        self.assertIn('fight', out)
        self.assertNotIn('talk', out)

    async def test_system_log_no_matches(self):
        Path(self.tmpdir, 'log').write_text(
            '2026-07-31 07:00:00,000 | INFO     | Rulan            | combat.engine.foo: fight\n'
        )
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', 'Nobody', ''])
        await LogsCommand().execute(ctx, '#system')
        self.assertIn('No system log entries match', ctx.sent())
        self.assertIn('player=Nobody', ctx.sent())

    async def test_battle_log_filtered_by_player(self):
        Path(self.tmpdir, 'battle.log').write_text(
            '[stamp] Goblin slain by Rulan\n[stamp] Orc slain by Bilbo\n'
        )
        ctx = _FakeCtx(_player(admin=True), _server(), prompt_answers=['', 'Rulan'])
        await LogsCommand().execute(ctx, '#battle')
        out = ctx.sent()
        self.assertIn('Goblin slain by Rulan', out)
        self.assertNotIn('Orc slain by Bilbo', out)

    async def test_statues_filtered_by_player(self):
        _record_statue('MEDUSA', 'Alice')
        _record_statue('GORGON', 'Bilbo')
        server = _server()
        server.statues = load_all_statues()
        ctx = _FakeCtx(_player(admin=True), server, prompt_answers=['', 'Alice'])
        await LogsCommand().execute(ctx, '#statues')
        out = ctx.sent()
        self.assertIn('MEDUSA', out)
        self.assertNotIn('GORGON', out)

    async def test_statues_filtered_by_player_no_matches(self):
        _record_statue('MEDUSA', 'Alice')
        server = _server()
        server.statues = load_all_statues()
        ctx = _FakeCtx(_player(admin=True), server, prompt_answers=['', 'Nobody'])
        await LogsCommand().execute(ctx, '#statues')
        self.assertIn('No statues match', ctx.sent())


class TestLoadAllStatues(_IsolatedRunDirTest):
    async def test_empty_when_no_statues_dir(self):
        self.assertEqual(load_all_statues(), {})

    async def test_collects_all_monster_files(self):
        _record_statue('MEDUSA', 'Alice')
        _record_statue('GORGON', 'Carol')
        statues = load_all_statues()
        self.assertEqual(statues, {'MEDUSA': ['Alice'], 'GORGON': ['Carol']})

    async def test_preserves_victim_order(self):
        _record_statue('MEDUSA', 'Alice')
        _record_statue('MEDUSA', 'Bilbo')
        statues = load_all_statues()
        self.assertEqual(statues['MEDUSA'], ['Alice', 'Bilbo'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
