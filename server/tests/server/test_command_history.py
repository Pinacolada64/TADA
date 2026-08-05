"""tests/server/test_command_history.py

Coverage for Player.command_history / Player.record_command (the "history"
command's ring buffer) and CommandProcessor.process_input()'s '^N' replay
shortcut.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from commands.base_command import Command, CommandResult
from commands.command_processor import CommandProcessor
from commands.help import Help, HelpCategory
from player import Player


# ---------------------------------------------------------------------------
# Player.record_command() ring buffer
# ---------------------------------------------------------------------------

def test_command_history_caps_at_20_and_evicts_oldest():
    p = Player(name='Rulan')
    for i in range(1, 25):
        p.record_command(f'say {i}')

    assert len(p.command_history) == 20
    assert p.command_history == [f'say {i}' for i in range(5, 25)]


def test_repeated_command_is_not_deduplicated():
    """Unlike ration_history/item_history, repeating the same command is
    the expected use case ('^N' re-running it), so it should burn a new
    slot each time, not be silently dropped."""
    p = Player(name='Rulan')
    p.record_command('look')
    p.record_command('look')

    assert p.command_history == ['look', 'look']


def test_blank_command_not_recorded():
    p = Player(name='Rulan')
    p.record_command('')
    assert p.command_history == []


def test_command_history_round_trips_through_save_load(tmp_path):
    """Unlike ration_history/item_history, command_history is NOT reset on
    login -- it should survive a reconnect exactly as saved."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='cmdhisttest', name='cmdhisttest')
    original.record_command('reload commands.editplayer')
    original.record_command('look')
    assert original.save(force=True)

    relogged = Player(name='cmdhisttest', id='cmdhisttest')
    assert relogged.command_history == ['reload commands.editplayer', 'look']


# ---------------------------------------------------------------------------
# CommandProcessor '^N' replay + auto-recording
# ---------------------------------------------------------------------------

class _EchoCommand(Command):
    name  = 'say'
    help  = Help(summary='echo', category=HelpCategory.GENERAL)

    async def execute(self, ctx, *args) -> CommandResult:
        return CommandResult.ok(' '.join(args))


class TestCommandHistoryDispatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.processor = CommandProcessor()
        self.processor.register_command(_EchoCommand())
        self.player = SimpleNamespace(command_history=[], record_command=None)

        def record_command(text):
            self.player.command_history.append(text)

        self.player.record_command = record_command
        self.ctx = SimpleNamespace(player=self.player)

    async def test_process_input_records_typed_command(self):
        await self.processor.process_input('say hello world', ctx=self.ctx)
        assert self.player.command_history == ['say hello world']

    async def test_caret_n_replays_most_recent(self):
        await self.processor.process_input('say hello', ctx=self.ctx)
        result = await self.processor.process_input('^1', ctx=self.ctx)
        assert result.success
        assert result.message == 'hello'
        # The replayed command is recorded too, as its resolved text.
        assert self.player.command_history == ['say hello', 'say hello']

    async def test_caret_n_out_of_range_fails_cleanly(self):
        result = await self.processor.process_input('^5', ctx=self.ctx)
        assert not result.success
        assert result.error == 'bad_history_index'
        assert self.player.command_history == []

    async def test_caret_n_indexes_from_most_recent(self):
        await self.processor.process_input('say first', ctx=self.ctx)
        await self.processor.process_input('say second', ctx=self.ctx)
        result = await self.processor.process_input('^2', ctx=self.ctx)
        assert result.message == 'first'


if __name__ == '__main__':
    unittest.main()
