# conftest.py
# Ensure the project server directory is on sys.path for pytest runs.
import sys
from pathlib import Path

# The tests directory is <repo>/server/tests; we want to add <repo>/server to sys.path
_this_tests_dir = Path(__file__).resolve().parent
_server_dir = _this_tests_dir.parent
sys.path.insert(0, str(_server_dir))

# Optionally configure logging for tests
import logging
logging.basicConfig(level=logging.WARNING)

