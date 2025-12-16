import pytest
import types
import asyncio
import textwrap

# Ensure package imports work when running tests from the repo root
import sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from commands import help as help_mod
from commands.help import HelpCommand, format_help


class DummyCommand:
    def __init__(self):
        self._name = 'test'
        self._aliases = ['t']

    @property
    def name(self):
        return self._name

    @property
    def aliases(self):
        return self._aliases

    def help_text(self):
        return "This is help text for the test command."


class DummyManager:
    def __init__(self, cmd):
        # return mapping by name
        self._commands = {cmd.name: cmd}

    def get_all_commands(self):
        return self._commands

    def get_command(self, name):
        return self._commands.get(name)


def test_helpcommand_instantiation_and_basic_help_text():
    hc = HelpCommand()
    # attach a dummy processor so help_text() can enumerate commands
    dummy = DummyCommand()
    mgr = DummyManager(dummy)
    hc.context = {'command_processor': mgr}

    summary = hc.help_text()
    assert isinstance(summary, str)
    assert 'test' in summary or 'test' in '\n'.join(summary.splitlines())


def test_format_help_produces_sections():
    class H:
        summary = 'short'
        description = 'Longer description here that explains the command.'
        usage = [('cmd <arg>', 'Does something.')]
        examples = [('cmd foo', 'Example usage')]
        notes = ['note one']

    out = format_help(H, 'cmd')
    assert out is not None
    assert 'Usage:' in out
    assert 'Examples:' in out
    assert 'Notes:' in out
    assert 'cmd' in out


@pytest.mark.asyncio
async def test_execute_help_for_specific_command():
    hc = HelpCommand()
    dummy = DummyCommand()
    mgr = DummyManager(dummy)
    result = await hc.execute(None, None, {'command_processor': mgr}, ['test'])
    assert isinstance(result, dict)
    assert result.get('success') is True
    msg = result.get('message')
    assert isinstance(msg, str)
    assert 'This is help text' in msg


@pytest.mark.asyncio
async def test_help_categories_list():
    hc = HelpCommand()
    dummy = DummyCommand()
    mgr = DummyManager(dummy)
    result = await hc.execute(None, None, {'command_processor': mgr}, ['categories'])
    assert isinstance(result, dict)
    assert result.get('success') is True
    msg = result.get('message')
    # message from categories is a string listing available categories
    assert isinstance(msg, str)
    assert 'Available help categories' in msg or '- General' in msg


@pytest.mark.asyncio
async def test_help_search_finds_command():
    hc = HelpCommand()
    dummy = DummyCommand()
    mgr = DummyManager(dummy)
    # search by partial term
    result = await hc.execute(None, None, {'command_processor': mgr}, ['search', 'tes'])
    assert isinstance(result, dict)
    assert result.get('success') is True
    msg = result.get('message')
    # allow string or list message formats
    if isinstance(msg, list):
        combined = '\n'.join(str(x) for x in msg)
    else:
        combined = str(msg)
    assert 'test' in combined.lower()


@pytest.mark.asyncio
async def test_help_nonexistent_command_returns_not_found():
    hc = HelpCommand()
    dummy = DummyCommand()
    mgr = DummyManager(dummy)
    result = await hc.execute(None, None, {'command_processor': mgr}, ['no_such_command'])
    assert isinstance(result, dict)
    assert result.get('success') is False
    assert 'No help found' in result.get('message')


@pytest.mark.asyncio
async def test_help_for_category_shows_commands():
    hc = HelpCommand()
    # create a dummy command that has help_info with a category
    cmd = DummyCommand()
    cmd._name = 'go'
    # attach help_info with category
    cmd.help_info = types.SimpleNamespace(category=help_mod.HelpCategory.MOVEMENT)
    mgr = DummyManager(cmd)

    result = await hc.execute(None, None, {'command_processor': mgr}, ['movement'])
    assert isinstance(result, dict)
    assert result.get('success') is True
    msg = result.get('message')
    if isinstance(msg, list):
        assert any('Commands in' in str(x) for x in msg)
        assert 'go' in '\n'.join(msg)
    else:
        assert 'Commands in' in msg and 'go' in msg


@pytest.mark.asyncio
async def test_help_alias_lookup_works():
    hc = HelpCommand()
    dummy = DummyCommand()
    # Create a manager that exposes both the name and alias as keys
    mgr = DummyManager(dummy)
    mgr._commands['t'] = dummy
    result = await hc.execute(None, None, {'command_processor': mgr}, ['t'])
    assert isinstance(result, dict)
    assert result.get('success') is True
    msg = result.get('message')
    combined = msg if isinstance(msg, str) else '\n'.join(msg)
    assert 'This is help text' in combined


def test_help_text_format_80_cols():
    hc = HelpCommand()
    command = "help ep"
    # try 80 column formatting:
    formatted_80_cols = textwrap.dedent("""
    Usage:
        editplayer           Edit your own character interactively
        editplayer <flag>    Toggle a flag for yourself
        editplayer <name>    Edit another player's character (admin only)
    """).strip()

    out_80 = format_help(command, width=80)
    assert 'Usage:' in out_80
    assert 'editplayer' in out_80


def test_help_text_format_40_cols():
    formatted_40_cols = textwrap.dedent("""
    Usage:
        editplayer
            Edit your own character
            interactively
        editplayer <flag>
            Toggle a flag for yourself
        editplayer <name>
            Edit another player's character
            (admin only)
    """).strip()
    out_40 = format_help("help ep", width=40)
    assert 'Usage:' in out_40
    assert 'editplayer' in formatted_40_cols
