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


# ---------------------------------------------------------------------------
# Network e2e test helpers
# ---------------------------------------------------------------------------
# Shared by tests/test_network_e2e_real_login.py, test_network_e2e_reconnect.py,
# test_move_south_room1.py, and test_abrupt_disconnect.py.

async def answer_terminal_negotiation(reader, writer, choice: str = 'A') -> None:
    """Send the ANSI/Plain terminal-negotiation answer right after handshake.

    simple_server._negotiate_terminal() re-prompts forever until it gets a
    valid A/P/Q answer -- added after these e2e tests were first written, so
    skipping this leaves the server hung waiting on a reply that never comes.
    """
    from simple_client import send_message
    from net_common import Message, Mode
    await send_message(writer, Message(lines=[choice], mode=Mode.app))


async def perform_login_as_guest(reader, writer, timeout: float = 3.0) -> str | None:
    """Complete handshake + terminal negotiation, then log in as a guest.

    Returns the assigned guest username (e.g. 'Guest', 'Guest 2'), or None
    if the server never confirmed the connection within `timeout` seconds.
    'connect guest' is the real command -- bare 'guest' isn't registered.

    Success is detected from the 'Welcome, <name>!' line commands/connect.py's
    _handle_guest() actually sends over the wire -- CommandResult.message
    (e.g. 'Connected as <name>.') is never relayed to the client, so matching
    on that (as this helper used to) waits forever.
    """
    import time
    from simple_client import perform_handshake, send_message, receive_message
    from net_common import Message, Mode

    await perform_handshake(reader, writer)
    await answer_terminal_negotiation(reader, writer)
    await send_message(writer, Message(lines=['connect guest'], mode=Mode.login))

    assigned_username = None
    start = time.time()
    while time.time() - start < timeout:
        msg = await receive_message(reader)
        if not msg:
            break
        lines = msg.get('lines') if isinstance(msg, dict) else None
        if lines:
            for ln in lines:
                if isinstance(ln, str) and ln.startswith('Welcome, ') and ln.endswith('!'):
                    assigned_username = ln[len('Welcome, '):-1]
                    break
        if assigned_username:
            break
    return assigned_username


def seed_test_account(username: str, password: str, *,
                       map_room: int = 1, map_level: int = 1) -> None:
    """Create a real, saved account for e2e login/persistence tests.

    Writes the login-<username>.json credential file and a matching
    player-<username>.json save file so commands/connect.py's real
    'connect <username> <password>' path has something to load. Guest
    sessions are intentionally never saved (see perform_login_as_guest()),
    so tests that check persistence need a real account instead.

    Caller must set net_common.run_server_dir (to an isolated tmp_path)
    before calling this, same as Player._json_path()/net_common.user_dir().
    """
    import json
    from net_common import user_dir
    from player import Player

    udir = user_dir()
    udir.mkdir(parents=True, exist_ok=True)
    (udir / f'login-{username}.json').write_text(
        json.dumps({'password': password}, indent=2)
    )

    player = Player(name=username, id=username)
    player.map_room  = map_room
    player.map_level = map_level
    player.unsaved_changes = True
    assert player.save(force=True), f'failed to seed player save file for {username!r}'


async def perform_login(reader, writer, username: str, password: str,
                         timeout: float = 3.0) -> bool:
    """Complete handshake + terminal negotiation, then log in with real credentials.

    Returns True once the server confirms the login (its 'Welcome, <name>!' line).
    """
    import time
    from simple_client import perform_handshake, send_message, receive_message
    from net_common import Message, Mode

    await perform_handshake(reader, writer)
    await answer_terminal_negotiation(reader, writer)
    await send_message(writer, Message(lines=[f'connect {username} {password}'], mode=Mode.login))

    start = time.time()
    while time.time() - start < timeout:
        msg = await receive_message(reader)
        if not msg:
            break
        lines = msg.get('lines') if isinstance(msg, dict) else None
        if lines and any(isinstance(ln, str) and ln.startswith(f'Welcome, {username}')
                          for ln in lines):
            return True
    return False

