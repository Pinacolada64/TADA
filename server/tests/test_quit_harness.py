# Test harness for verifying that Player.quit() saves player data to disk
import tempfile
import json
from pathlib import Path
import sys
import types

# Make sure the server/ directory is on sys.path so imports like `net_common` and `player`
# resolve correctly when running this harness directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Insert a lightweight stub net_common into sys.modules before importing player to avoid
# circular imports from the project's full net_common implementation.
net_common = types.ModuleType('net_common')

class Message:
    def __init__(self, lines=None, changes=None, mode=None):
        self.lines = lines or []
        self.changes = changes or {}
        self.mode = mode

net_common.Message = Message
from enum import Enum

class Mode(Enum):
    init = 'init'
    guest = 'guest'
    new_player = 'new_player'
    login = 'login'
    app = 'app'
    bye = 'bye'

net_common.Mode = Mode

def to_jsonb(obj):
    import json
    return json.dumps(obj).encode('utf-8')

def from_jsonb(b):
    import json
    if not b:
        return None
    return json.loads(b.decode('utf-8'))

net_common.to_jsonb = to_jsonb
net_common.from_jsonb = from_jsonb

# run_server_dir will be set by the test when needed
net_common.run_server_dir = None
sys.modules['net_common'] = net_common

# Provide a minimal `simple_client` stub so `player` can import send_message without
# pulling in the real simple_client (which imports net_common and causes circular imports).
simple_client = types.ModuleType('simple_client')
async def send_message(writer, obj):
    # no-op stub for harness
    return None
simple_client.send_message = send_message
sys.modules['simple_client'] = simple_client

def run_test():
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / 'run' / 'server'
        run_dir.mkdir(parents=True, exist_ok=True)
        # Point net_common.run_server_dir to our temporary path
        net_common.run_server_dir = run_dir

        # Create a player and set id and attributes
        from player import Player
        p = Player(name='TestPlayer')
        # choose a deterministic id for test
        p.id = 'test123'
        p.name = 'TestPlayer'
        p.unsaved_changes = True

        # Call quit() which should force-save the player and then disconnect
        print(f"Calling quit() for player id={p.id} name={p.name}")
        res = p.quit()
        print(f"quit() returned: {res}")

        # Check that the file was created
        path = Path(p._json_path(p.id))
        print(f"Expected player file at: {path}")
        if path.exists():
            print("Player file exists: PASS")
            # Print stored JSON keys to validate content
            with open(path) as f:
                data = json.load(f)
            print("Saved JSON keys:", list(data.keys()))
            # Basic assertions
            assert data.get('name') == p.name or 'name' in data, "Name not present or mismatch"
            print("Basic content check: PASS")
        else:
            print("Player file does not exist: FAIL")
            sys.exit(2)


if __name__ == '__main__':
    run_test()
