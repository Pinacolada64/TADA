import subprocess
import sys
from pathlib import Path


def test_player_instantiation_subprocess():
    """Run a separate Python process to instantiate Player to avoid import-time side effects.

    This prevents pytest from importing `player` during collection (which can start server components).
    Run the subprocess with cwd set to the server directory so local imports work.
    """
    repo_server_dir = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(repo_server_dir / 'tools' / 'check_player_instantiation.py')]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_server_dir))
    # show stdout/stderr in pytest output if something goes wrong
    if res.returncode != 0:
        print('STDOUT:\n', res.stdout)
        print('STDERR:\n', res.stderr)
    assert res.returncode == 0
    assert 'Player instantiation checks passed' in (res.stdout + res.stderr)
