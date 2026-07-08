import logging
import json
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading
import time

# Tests point this at a tmp_path to isolate saved player/credential files;
# defaults to './run/server' otherwise. Read dynamically (not at import
# time) by user_dir() and Player._json_path() so tests can set it after
# these modules are already imported.
run_server_dir: str | None = None


def user_dir() -> Path:
    """Directory holding per-account login-<username>.json credential files.

    Resolved at call time from run_server_dir (the same run directory
    Player._json_path() uses) rather than a fixed relative path, so
    anything that sets run_server_dir to an isolated tmp_path (e2e tests)
    also isolates credential files instead of writing into the real
    project directory.
    """
    base = run_server_dir or Path('run') / 'server'
    return Path(base) / 'net'


class K(str, Enum):
    id = 'id'
    password = 'password'
    code = 'code'
    hash = 'hash'
    salt = 'salt'
    invite = 'invite'
    user = 'user'
    translation = 'translation'


class Mode(str, Enum):
    # initial client connection
    # send client_key, client_id, must match server_key, server_id.
    # does not need to match protocol version.
    # send connect banner, then switch to login mode:
    init = 'init'
    # exchange login/guest credentials, then switch to app mode:
    # initial client connection (exchange protocol, terminal type, app_version, key,
    # and send connect banner):

    # unauthenticated user for "looking around" ("connect guest guest")
    guest = 'guest'
    # new player creation:
    new_player = 'new_player'
    # login ("connect"/"login", "who", "quit", "news" maybe):
    login = 'login'
    # application running (normal gameplay):
    app = 'app'
    # logout ("quit" or socket closed):
    bye = 'bye'


class MessageType(Enum):
    # type of message being sent, in descending order of importance:
    # initial connection message, protocol version, terminal type, etc.:
    INIT = auto()
    # server going down, scheduled maintenance, etc.:
    SYSTEM = auto()
    # event announcement, something important happened:
    ANNOUNCEMENT = auto()
    # not sure what else to call this, but it's not as important as above:
    # (normal messages)
    REGULAR = auto()
    # player communications:
    shout = auto()
    page = auto()
    say = auto()
    mumble = auto()
    emote = auto()
    whisper = auto()


def _default_serializer(o: Any):
    # serialize Enum by name, dataclasses and objects by __dict__
    try:
        from dataclasses import is_dataclass
        if isinstance(o, Enum):
            return o.name
        if is_dataclass(o):
            return asdict(o)
        if hasattr(o, '__dict__'):
            return o.__dict__
    except Exception:
        pass
    return str(o)


def to_jsonb(obj: Any) -> bytes:
    """Serialize an object to JSON bytes. Enums are converted to their names.
    Dataclasses are converted to dicts.
    """
    try:
        j = json.dumps(obj, default=_default_serializer)
        return j.encode('utf-8')
    except Exception:
        logging.exception('to_jsonb failed for object: %r', obj)
        raise


def from_jsonb(b: bytes) -> Optional[Dict[str, Any]]:
    """Deserialize JSON bytes to Python object (usually dict).
    Returns None on empty input.
    """
    if not b:
        return None
    try:
        if isinstance(b, bytes):
            s = b.decode('utf-8')
        else:
            s = str(b)
        if not s:
            return None
        return json.loads(s)
    except Exception:
        logging.exception('from_jsonb failed')
        return None


@dataclass
class Message:
    lines: List[str] | str = field(default_factory=list)
    changes: Dict[str, Any] = field(default_factory=dict)
    choices: Dict[str, Any] = field(default_factory=dict)
    prompt: str = ''
    error: str = ''
    error_line: str = ''
    mode: Mode = field(default_factory=lambda: Mode.app)
    type: MessageType = field(default_factory=lambda: MessageType.REGULAR)

    def __post_init__(self):
        # normalize lines to list
        if isinstance(self.lines, str):
            self.lines = [self.lines]


@dataclass
class ClientInfo:
    """Information about a connected client.

    Fields:
        user_id: str
        handler: Any - the server-side client object/handler
        connected_time: float - epoch seconds when added
        last_active: float - epoch seconds of last activity
    """
    user_id: str
    handler: Any  # Will be set to UserHandler / client object at runtime
    connected_time: float
    last_active: float  # can calculate idle time from this


class ClientManager:
    """Manages connected clients and handles broadcasting messages."""

    def __init__(self):
        self.clients: Dict[str, ClientInfo] = {}
        self.lock = threading.Lock()

    def add_client(self, user_id: str, handler: Any) -> None:
        """Add a new client to the manager."""
        with self.lock:
            now = time.time()
            self.clients[user_id] = ClientInfo(user_id=user_id, handler=handler, connected_time=now, last_active=now)

    def remove_client(self, user_id: str) -> None:
        """Remove a client from the manager."""
        with self.lock:
            if user_id in self.clients:
                del self.clients[user_id]
                logging.info(f"Client disconnected: {user_id}")

    def update_activity(self, user_id: str) -> None:
        with self.lock:
            info = self.clients.get(user_id)
            if info:
                info.last_active = time.time()

    def get_online_client_info(self) -> List[Dict[str, Any]]:
        out = []
        with self.lock:
            for uid, info in self.clients.items():
                h = info.handler
                out.append({
                    'player_name': getattr(h, 'username', None) or uid,
                    'user_id': uid,
                    'connected_time': info.connected_time,
                    'last_activity': info.last_active,
                    'address': getattr(h, 'addr', None),
                    'handler': h,
                })
        return out

        """
        Example:
            # Broadcast to all clients
            client_manager.broadcast({"type": "announcement", "text": "Server restarting soon!"})

            # Broadcast to all clients except specific users
            client_manager.broadcast(
                {"type": "message", "text": "New user joined!"},
                exclude_user_ids={current_user_id}
            )
        """
    def broadcast(self, message: Dict[str, Any], exclude_user_ids: Set[str] = set()) -> None:
        """Broadcast a message to all connected clients, excluding specified user IDs."""
        with self.lock:
            for uid, info in self.clients.items():
                if uid in exclude_user_ids:
                    continue
                handler = info.handler
                try:
                    handler.send_message(message)
                except Exception:
                    logging.exception(f"Failed to send message to client {uid}")

# Global instance
client_manager = ClientManager()


# Backwards-compatible names sometimes used elsewhere
Mode = Mode
MessageType = MessageType
Message = Message
to_jsonb = to_jsonb
from_jsonb = from_jsonb
K = K

