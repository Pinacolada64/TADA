"""tests/test_reload.py

Unit tests for commands/reload.py: hot-reloading command/support modules
without restarting the server (importlib.reload() picks up an edited .py
file that Python's module cache would otherwise keep stale), plus #list
for inspecting what's loaded/available.
"""
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.reload import ReloadCommand, _list_command_modules, _list_other_loaded_modules, _resolve_module_name
from flags import PlayerFlags


def make_ctx(*, is_admin=True, clients=None):
    player = MagicMock()
    player.name = 'Admin'
    player.query_flag = MagicMock(side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin)

    server = MagicMock()
    server.clients = clients or {}

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.send = AsyncMock()
    return ctx


class TestResolveModuleName(unittest.TestCase):
    def test_bare_name_expands_to_commands_prefix(self):
        self.assertEqual(_resolve_module_name('movement'), 'commands.movement')

    def test_dotted_name_used_as_is(self):
        self.assertEqual(_resolve_module_name('base_classes.Room'), 'base_classes.Room')

    def test_already_loaded_top_level_module_used_as_is(self):
        import base_classes  # noqa: F401 -- ensure it's really in sys.modules
        self.assertEqual(_resolve_module_name('base_classes'), 'base_classes')


class TestListHelpers(unittest.TestCase):
    def test_list_command_modules_finds_reload_itself(self):
        loaded, not_loaded = _list_command_modules()
        self.assertIn('commands.reload', loaded + not_loaded)

    def test_other_loaded_modules_excludes_commands_and_venv(self):
        other = _list_other_loaded_modules()
        self.assertNotIn('commands.reload', other)
        self.assertFalse(any('.venv' in n for n in other))
        # A real first-party module that's always loaded by this point.
        self.assertIn('flags', other)


class TestReloadPermission(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_denied(self):
        cmd = ReloadCommand()
        ctx = make_ctx(is_admin=False)
        res = await cmd.execute(ctx, 'movement')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_admin_no_args_fails(self):
        cmd = ReloadCommand()
        ctx = make_ctx(is_admin=True)
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')


class TestReloadExecution(unittest.IsolatedAsyncioTestCase):
    async def test_reloads_named_module(self):
        cmd = ReloadCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, 'flags')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Reloaded: flags', sent)

    async def test_unknown_module_reported_as_failed(self):
        cmd = ReloadCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, 'no_such_module_xyz')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'reload_failed')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Failed', sent)

    async def test_rebuilds_connected_clients_command_processors(self):
        client = MagicMock()
        client.command_processor = MagicMock(current_mode='GAME')
        cmd = ReloadCommand()
        ctx = make_ctx(clients={'addr1': client})
        await cmd.execute(ctx, 'flags')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Rebuilt command tables for 1 connected client', sent)

    async def test_skips_clients_without_a_command_processor(self):
        client = MagicMock()
        client.command_processor = None
        cmd = ReloadCommand()
        ctx = make_ctx(clients={'addr1': client})
        await cmd.execute(ctx, 'flags')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Rebuilt command tables for 0 connected client', sent)


class TestReloadList(unittest.IsolatedAsyncioTestCase):
    async def test_list_switch_shows_command_modules(self):
        cmd = ReloadCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, '#list')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Command modules', sent)
        self.assertIn('commands.reload', sent)

    async def test_list_switch_shows_other_loaded_modules(self):
        cmd = ReloadCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '#list')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Other loaded project modules', sent)

    async def test_list_denied_for_non_admin(self):
        cmd = ReloadCommand()
        ctx = make_ctx(is_admin=False)
        res = await cmd.execute(ctx, '#list')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')


if __name__ == '__main__':
    unittest.main()
