"""Quick runner to validate Player instantiation without running pytest.
This avoids pytest importing other test modules that start server subsystems.
"""
import sys
from pathlib import Path

# Ensure server directory is on sys.path so 'import player' works when running from tools/ dir
repo_server_dir = Path(__file__).resolve().parent.parent
if str(repo_server_dir) not in sys.path:
    sys.path.insert(0, str(repo_server_dir))

from player import Player


if __name__ == '__main__':
    p = Player()
    assert p is not None
    assert hasattr(p, 'name')
    assert hasattr(p, 'stats')
    assert hasattr(p, 'silver')
    assert hasattr(p, 'flags')
    # default name should be a string
    assert isinstance(p.name, str)
    p2 = Player(name='RunnerTest')
    assert p2.name == 'RunnerTest'
    print('Player instantiation checks passed')
