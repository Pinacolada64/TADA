"""tests/test_command_processor_get.py

process_input()/process_command() dispatch: help, help help, and unknown
command all return a CommandResult with the right success/error markers.

Rewritten against the current CommandProcessor API (CommandResult objects,
ctx-based dispatch via commands/help.py's real HelpCommand). The previous
version of this test exercised a since-removed dict-returning design
(create_command_processor() used to build an ad-hoc inline Help command
and process_command()/process_input() used to return plain dicts --
see commit a0e2392) -- none of that exists anymore, so every assertion
failed (isinstance(res, dict), res.get(...)) against today's real
CommandResult-based API.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from commands.command_processor import create_command_processor
from commands.base_command import CommandResult


def _make_ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.server.clients = {}
    ctx.player.client_settings.screen_columns = 80   # real int for help.py's column layout
    return ctx


def test_process_input_returns_command_result_and_supports_attribute_access():
    proc = create_command_processor(MagicMock())
    ctx = _make_ctx()
    # help.py's HelpCommand resolves the live processor off
    # ctx.client.command_processor to look up other commands (e.g. "help
    # help") -- without this it finds an unrelated auto-mocked processor
    # with nothing registered on it.
    ctx.client.command_processor = proc

    res = asyncio.run(proc.process_input('help', ctx=ctx))
    assert isinstance(res, CommandResult)
    assert res.success is True

    # Asking for help about help should also succeed (detailed/manpage output).
    res2 = asyncio.run(proc.process_input('help help', ctx=ctx))
    assert isinstance(res2, CommandResult)
    assert res2.success is True

    # Unknown command returns a failure CommandResult with an error code.
    res3 = asyncio.run(proc.process_input('no-such-command-xyz', ctx=ctx))
    assert isinstance(res3, CommandResult)
    assert res3.error == 'unknown_command'
