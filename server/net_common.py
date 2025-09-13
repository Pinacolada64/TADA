import logging
import os
import json
import enum
import datetime
import bcrypt
import threading
import time
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass, field

run_server_dir = 'run/server'
invite_dir = os.path.join(run_server_dir, 'invite')
net_dir = os.path.join(run_server_dir, 'net')


class K(str, enum.Enum):
    """keys for dictionary use, so that we can avoid 'stringly' typed
    anti-pattern.  When adding new entries make sure the key matches
    the string.

    (see https://www.google.com/search?q=%22stringly%22+typed)
    """
    id = 'id'
    password = 'password'
    code = 'code'
    hash = 'hash'
    salt = 'salt'
    invite = 'invite'
    user = 'user'
    translation = 'translation'


class Mode(str, enum.Enum):
    # initial client connection (exchange protocol, terminal type, app_version, key,
    # and send connect banner):
    init = 'init'
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


def to_jsonb(obj):
    """turn arbitrary object into JSON string with length prefix"""
    logging.debug(f"to_jsonb: {obj=}")
    
    def default_serializer(o):
        if hasattr(o, '__dataclass_fields__'):
            return {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
        return o.__dict__
    
    json_out = json.dumps(obj, default=default_serializer)
    json_bytes = bytes(json_out, 'utf-8')
    # Prefix with 4-byte length (big-endian)
    length = len(json_bytes)
    return length.to_bytes(4, 'big') + json_bytes


def to_jsonb_socket(sock, data):
    """
    Send a length-prefixed JSON message over a socket
    :param sock: socket to write to
    :param data: data to send (will be JSON-encoded)
    :return: number of bytes sent or None on error
    """
    try:
        # Convert data to JSON and encode as bytes
        json_data = json.dumps(data).encode('utf-8')
        
        # Create a length prefix (4-byte big-endian)
        length = len(json_data)
        length_prefix = length.to_bytes(4, byteorder='big')
        
        # Send length prefix + JSON data
        sock.sendall(length_prefix + json_data)
        return length + 4  # Return total bytes sent
    except Exception as e:
        logging.error(f"Error sending JSON data: {e}")
        return None


def from_jsonb_socket(sock):
    """
    Read a length-prefixed JSON message from a socket
    :param sock: socket to read from
    :return: parsed JSON object or None if connection closed or error
    """
    try:
        # Set a timeout to prevent blocking forever
        sock.settimeout(30.0)  # 30 second timeout
        
        # First, read the 4-byte length prefix
        length_bytes = b''
        while len(length_bytes) < 4:
            try:
                chunk = sock.recv(4 - len(length_bytes))
                if not chunk:  # Connection closed by peer
                    return None
                length_bytes += chunk
            except TimeoutError:
                # No data available yet within the timeout
                return None
        
        # Convert length from big-endian bytes to int
        length = int.from_bytes(length_bytes, 'big')
        if length > 10 * 1024 * 1024:  # Sanity check: max 10MB
            logging.warning(f"Suspicious message length: {length} bytes")
            return None
            
        # Now read exactly 'length' bytes of JSON data
        json_bytes = b''
        while len(json_bytes) < length:
            try:
                chunk = sock.recv(min(4096, length - len(json_bytes)))
                if not chunk:  # Connection closed by peer
                    return None
                json_bytes += chunk
            except TimeoutError:
                logging.debug("Timeout while reading message data")
                return None
        
        # Parse the JSON
        try:
            json_str = str(json_bytes, 'utf-8')
            return json.loads(json_str)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logging.error(f"Failed to parse JSON: {e}")
            return None
            
    except ConnectionResetError:
        logging.debug("Connection reset by peer")
        return None
    except OSError as e:
        if e.errno == 9:  # Bad file descriptor
            logging.debug("Socket closed")
        else:
            logging.error(f"Socket error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in from_jsonb_socket: {e}", exc_info=True)
        return None


def from_jsonb(bytes):
    """
    Legacy function for compatibility - parse JSON from bytes
    :param bytes: data
    :return None: if file not found
    """
    logging.debug(f"from_jsonb: {bytes=}")
    try:
        json_in = str(bytes, 'utf-8')
        if len(json_in) == 0:
            return None
        return json.loads(json_in)
    except FileNotFoundError:
        return None


@dataclass
class Invite(object):
    id: str
    email: str
    code: str
    generated: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @staticmethod
    def _json_path(user_id):
        Path(invite_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(invite_dir, f"user-{user_id}.json")

    @staticmethod
    def load(user_id):
        path = Invite._json_path(user_id)
        if path.exists():
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return Invite(**lh_data)
        else:
            return None

    def save(self):
        with open(Invite._json_path(self.id), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                                                      in o.__dict__.items() if v}, indent=4)

    def delete(self):
        Path(Invite._json_path(self.id)).unlink()


@dataclass
class User(object):
    id: str
    salt: int = 0
    hash: str = ''

    def hash_password(self, password):
        salt = bcrypt.gensalt()
        self.salt = salt.hex()
        self.hash = bcrypt.hashpw(bytes(password, 'utf-8'), salt).hex()

    def match_password(self, password):
        salt = bytes.fromhex(self.salt)
        hash = bcrypt.hashpw(bytes(password, 'utf-8'), salt).hex()
        return self.hash == hash

    @staticmethod
    def _json_path(user_id):
        Path(net_dir).mkdir(parents=True, exist_ok=True)
        return Path(net_dir) / f"user-{user_id}.json"

    @staticmethod
    def load(user_id):
        path = User._json_path(user_id)
        logging.debug(f"in User.load: {path=}")
        if path.exists():
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return User(**lh_data)
        else:
            return None

    def save(self):
        logging.debug(f"in User.save: {self.id=}")
        with open(User._json_path(self.id), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                                                      in o.__dict__.items() if v}, indent=4)

    def delete(self):
        os.remove(User._json_path(self.id))


@dataclass
class ClientInfo:
    """Information about a connected client."""
    user_id: str
    handler: Any  # Will be set to UserHandler at runtime
    last_active: float  # can calculate idle time from this


class ClientManager:
    """Manages connected clients and handles broadcasting messages."""
    
    def __init__(self):
        self.clients: Dict[str, ClientInfo] = {}
        self.lock = threading.Lock()
        
    def add_client(self, user_id: str, handler: Any) -> None:
        """Add a new client to the manager."""
        with self.lock:
            self.clients[user_id] = ClientInfo(
                user_id=user_id,
                handler=handler,
                last_active=time.time()
            )
            logging.info(f"Client connected: {user_id}")
            
    def remove_client(self, user_id: str) -> None:
        """Remove a client from the manager."""
        with self.lock:
            if user_id in self.clients:
                del self.clients[user_id]
                logging.info(f"Client disconnected: {user_id}")
                
    def get_client(self, user_id: str) -> Optional[ClientInfo]:
        """Get client info by user ID."""
        with self.lock:
            return self.clients.get(user_id)
    
    async def close_all_connections(self) -> None:
        """Close all active client connections gracefully.
        
        This method should be called during server shutdown to ensure all
        client connections are properly closed.
        """
        with self.lock:
            clients = list(self.clients.items())
            
        for user_id, client in clients:
            try:
                if hasattr(client.handler, 'close_connection'):
                    await client.handler.close_connection()
                elif hasattr(client.handler, 'close'):
                    client.handler.close()
                logging.info(f"Closed connection for user: {user_id}")
            except Exception as e:
                logging.error(f"Error closing connection for {user_id}: {e}")
            finally:
                # Ensure the client is removed from our tracking
                self.remove_client(user_id)
    
    def broadcast(self, message: Dict[str, Any], exclude_user_ids: Set[str] = None) -> None:
        """
        Broadcast a message to all connected clients except those in exclude_user_ids.
        
        Args:
            message: The message to broadcast (will be JSON-serialized)
            exclude_user_ids: Optional set of user IDs to exclude from the broadcast
            
        Example:
            # Broadcast to all clients
            client_manager.broadcast({"type": "announcement", "text": "Server restarting soon!"})
            
            # Broadcast to all clients except specific users
            client_manager.broadcast(
                {"type": "message", "text": "New user joined!"},
                exclude_user_ids={current_user_id}
            )
        """
        if exclude_user_ids is None:
            exclude_user_ids = set()
            
        with self.lock:
            for user_id, client in list(self.clients.items()):
                if user_id in exclude_user_ids:
                    continue
                    
                try:
                    client.handler.send_async_message(message)
                except Exception as e:
                    logging.error(f"Error broadcasting to {user_id}: {e}")
                    # If we can't send to this client, remove them
                    self.remove_client(user_id)


# Global instance of the client manager
client_manager = ClientManager()


class Test(object):
    server_port = 5001
    id = 'testing'
    key = '999999999'
    protocol = 1
