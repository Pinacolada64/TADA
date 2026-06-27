# ...existing code...
import sys
from pathlib import Path

# Ensure the server directory is first on sys.path so imports like `net_common` and
# `commands` resolve when pytest runs in the server folder.
repo_server_dir = Path(__file__).parent.resolve()
repo_root = repo_server_dir.parent.resolve()

# Insert server and repo root at the front of sys.path (if not already present)
for p in (str(repo_server_dir), str(repo_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

