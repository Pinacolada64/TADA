import asyncio
import sys
from pathlib import Path
import tempfile
import types
import json
import threading

# Ensure server/ is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Create a fake net_server module before importing player so player picks it up
fake_ns = types.ModuleType('net_server')
fake_ns.server_lock = threading.Lock()
fake_ns.room_players = {1: set()}
fake_ns.players = {}
import sys
sys.modules['net_server'] = fake_ns

# Ensure net_common exists with run_server_dir
import types as _types
import net_common as nc


def test_disconnect_saves_player(tmp_path):
    # set run dir
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    nc.run_server_dir = run_dir

    # import Player after stubbing net_server
    from player import Player

    # create player and register in fake server
    p = Player(name='DisconnectTester')
    p.id = 'disc-test-1'
    p.map_room = 42
    p.map_level = 1
    p.unsaved_changes = True

    # register in fake server data structures
    fake_ns.room_players.setdefault(p.map_room, set()).add(p.id)
    fake_ns.players[p.id] = p

    # Call disconnect (async)
    async def run():
        res = await p.disconnect(None, None)
        return res

    asyncio.run(run())

    # check saved file
    expected = Path(p._json_path(p.id))
    assert expected.exists(), f"Player file not created: {expected}"
    with open(expected) as f:
        data = json.load(f)
    assert int(data.get('map_room', -1)) == 42


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])

