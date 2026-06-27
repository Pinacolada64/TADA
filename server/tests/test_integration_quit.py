import asyncio
import tempfile
from pathlib import Path
import sys
import types
import json
from dataclasses import dataclass, field

# Ensure server package root is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Create a minimal net_common stub before importing commands.quit to avoid circular imports
net_common = types.ModuleType('net_common')
from enum import Enum
class Mode(Enum):
    init = 'init'
    guest = 'guest'
    new_player = 'new_player'
    login = 'login'
    app = 'app'
    bye = 'bye'
net_common.Mode = Mode
net_common.BYE = 'bye'
net_common.run_server_dir = None

@dataclass
class Message:
    lines: list | str = field(default_factory=list)
    changes: dict = field(default_factory=dict)
    choices: dict = field(default_factory=dict)
    prompt: str = ''
    error: str = ''
    error_line: str = ''
    mode: Mode = Mode.app

net_common.Message = Message
sys.modules['net_common'] = net_common

# Create a minimal simple_client stub so player import doesn't try to load heavy network code
simple_client = types.ModuleType('simple_client')
async def send_message(writer, obj):
    return None
simple_client.send_message = send_message
sys.modules['simple_client'] = simple_client

# Now import the QuitCommand
from commands.quit import QuitCommand


def test_quit_command_calls_player_quit_and_saves(tmp_path):
    # Prepare temporary run dir for saved files
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    net_common.run_server_dir = run_dir

    # Use the real Player implementation for this integration test
    from player import Player

    # instantiate a real Player (defaults are fine), set deterministic id
    player = Player(name='IntegrationTest')
    player.id = 'test123'
    # Mark unsaved_changes so save() actually writes
    player.unsaved_changes = True

    # Fake client with player attribute and mode
    class FakeClient:
        def __init__(self, player):
            self.player = player
            self.mode = None

    client = FakeClient(player)

    # Context as the command expects (dict or handler)
    context = {'client': client, 'player': player}

    cmd = QuitCommand()

    # Run the async execute
    result = asyncio.run(cmd.execute(None, None, context, []))

    # Assert CommandResult indicates success
    assert getattr(result, 'success', True) is True

    # The real Player implementation should have saved the file on quit
    # and cleared the unsaved_changes flag.
    assert player.unsaved_changes is False

    # The command should set client.mode to bye (using net_common.Mode.bye) and mark disconnect
    assert client.mode == net_common.Mode.bye
    assert context.get('disconnect') is True

    # Ensure save file was created by player.quit()
    expected_file = run_dir / 'player-test123.json'
    assert expected_file.exists()

    # Basic contents
    with open(expected_file) as f:
        data = json.load(f)
    assert data.get('name') == 'IntegrationTest'


if __name__ == '__main__':
    # allow running the test directly
    import pytest
    pytest.main([__file__])
