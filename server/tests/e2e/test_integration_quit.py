"""tests/test_integration_quit.py

Integration test: QuitCommand.execute() + Server._player_quit() together
save a real Player to disk.

Rewritten against the current architecture. The previous version of this
test called QuitCommand.execute(None, None, context, []) with an old
dict-shaped context ({'client': ..., 'player': ...}) and expected the
command itself to set client.mode = Mode.bye and context['disconnect'] =
True -- none of that exists anymore. QuitCommand.execute(ctx, *args) now
only handles the interaction (Y/N prompt, session bonus, party farewells,
stat restoration) and signals intent to quit via
CommandResult(success=True, data={'quit': True}); the actual save-to-disk
happens in a separate step, Server._player_quit(ctx), called by the game
loop when it sees that data flag (simple_server.py's _game_loop()).
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from commands.quit import QuitCommand


def test_quit_command_calls_player_quit_and_saves(tmp_path):
    import net_common
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    net_common.run_server_dir = run_dir

    from player import Player
    player = Player(name='IntegrationTest')
    player.id = 'test123'
    player.unsaved_changes = True

    ctx = MagicMock()
    ctx.player = player
    ctx.client.room = 1
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt = AsyncMock(return_value='Y')   # confirm the "Leave SPUR [Y/N]?" prompt

    cmd = QuitCommand()
    result = asyncio.run(cmd.execute(ctx))

    assert result.success is True
    assert result.data.get('quit') is True

    # The game loop's job after seeing data['quit'] -- actually persists
    # the player to disk (simple_server.py's _game_loop()).
    server = Server('127.0.0.1', 0)
    asyncio.run(server._player_quit(ctx))

    assert player.unsaved_changes is False

    expected_file = run_dir / 'player-test123.json'
    assert expected_file.exists()

    with open(expected_file) as f:
        data = json.load(f)
    assert data.get('name') == 'IntegrationTest'
