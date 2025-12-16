"""
Client manager for handling connected clients and their sessions.
"""
import json
import logging
from json import JSONEncoder
from typing import Dict, Set, Optional, Any, Union

try:
    import net_common
    _DELEGATE = getattr(net_common, 'client_manager', None)
except Exception:
    _DELEGATE = None

class ClientManager:
    """Wrapper ClientManager that delegates to net_common.client_manager when available.

    This keeps the rest of the codebase using `from client_manager import ClientManager` working,
    while ensuring there is a single shared registry (net_common.client_manager).
    """

    def __init__(self):
        if _DELEGATE is not None:
            self._delegate = _DELEGATE
            logging.debug("ClientManager: delegating to net_common.client_manager")
        else:
            self._delegate = None
            logging.debug("ClientManager: operating in stand-alone mode")
            self._clients: Dict[str, Dict[str, Any]] = {}
            self._user_to_client: Dict[str, str] = {}
            import threading
            self._lock = threading.Lock()

    def set_lock(self, lock):
        if self._delegate:
            # delegate doesn't need external lock
            return
        self._lock = lock

    def add_client(self, client_id: str, client_data: Dict[str, Any]) -> None:
        if self._delegate:
            try:
                # delegate expects (user_id, handler)
                # if client_data contains 'handler' use it, otherwise pass the dict
                handler = client_data.get('handler') if isinstance(client_data, dict) and 'handler' in client_data else client_data
                self._delegate.add_client(client_id, handler)
                return
            except Exception:
                logging.exception("Delegated add_client failed")
        # fallback implementation
        with self._lock:
            self._clients[client_id] = client_data
            if isinstance(client_data, dict) and 'user_id' in client_data:
                self._user_to_client[client_data['user_id']] = client_id
            logging.debug("Added client %s", client_id)

    def remove_client(self, client_id: str) -> None:
        if self._delegate:
            try:
                return self._delegate.remove_client(client_id)
            except Exception:
                logging.exception("Delegated remove_client failed")
        with self._lock:
            client = self._clients.pop(client_id, None)
            if client and isinstance(client, dict) and 'user_id' in client:
                self._user_to_client.pop(client['user_id'], None)
            logging.debug("Removed client %s", client_id)

    def authenticate_client(self, client_id: str, user_id: str) -> None:
        if self._delegate:
            try:
                if hasattr(self._delegate, 'authenticate_client'):
                    return self._delegate.authenticate_client(client_id, user_id)
            except Exception:
                logging.exception("Delegated authenticate_client failed")
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id]['user_id'] = user_id
                self._user_to_client[user_id] = client_id
                logging.info("Authenticated client %s as user %s", client_id, user_id)

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        if self._delegate:
            try:
                c = self._delegate.get_client(client_id)
                # net_common.ClientInfo -> return dict-like
                if c is None:
                    return None
                try:
                    return {
                        'user_id': getattr(c, 'user_id', None),
                        'handler': getattr(c, 'handler', None),
                        'connected_time': getattr(c, 'connected_time', None),
                        'last_active': getattr(c, 'last_active', None)
                    }
                except Exception:
                    return None
            except Exception:
                logging.exception("Delegated get_client failed")
        return self._clients.get(client_id)

    def get_client_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self._delegate:
            try:
                return self._delegate.get_client(user_id)
            except Exception:
                logging.exception("Delegated get_client_by_user failed")
        client_id = self._user_to_client.get(user_id)
        return self.get_client(client_id) if client_id else None

    def is_online(self, user_id: str) -> bool:
        if self._delegate:
            try:
                return self._delegate.is_online(user_id)
            except Exception:
                logging.exception("Delegated is_online failed")
        return user_id in self._user_to_client

    def get_online_player_ids(self) -> Set[str]:
        if self._delegate:
            try:
                return set(self._delegate.get_online_player_ids())
            except Exception:
                logging.exception("Delegated get_online_player_ids failed")
        with self._lock:
            return {client['user_id'] for client in self._clients.values() if isinstance(client, dict) and 'user_id' in client}

    def get_online_player_names(self) -> Set[str]:
        if self._delegate:
            try:
                return set(self._delegate.get_online_player_names())
            except Exception:
                logging.exception("Delegated get_online_player_names failed")
        with self._lock:
            return {client['player_name'] for client in self._clients.values() if isinstance(client, dict) and 'player_name' in client}

    def get_online_client_info(self):
        if self._delegate:
            try:
                return set(self._delegate.get_online_client_info())
            except Exception:
                logging.exception("Delegated get_online_client_info failed")
        with self._lock:
            return {client for client in self._clients.values() if isinstance(client, dict) and 'user_id' in client}

    # Simple send helpers: these assume 'transport' holds a writer-like object accepting bytes
    def send_to(self, user_id: str, data: Dict[str, Any]) -> bool:
        if self._delegate:
            try:
                return self._delegate.send_to(user_id, data)
            except Exception:
                logging.exception("Delegated send_to failed")
        client = self.get_client_by_user(user_id)
        if not client or 'transport' not in client:
            return False
        try:
            client['transport'].write(data)
            return True
        except Exception as e:
            logging.error("Error sending data to user %s: %s", user_id, e)
            return False

    def send_to_room(self, room_id: Union[str, int], data: Dict[str, Any], exclude_user: Optional[str] = None) -> None:
        if self._delegate:
            try:
                return self._delegate.send_to_room(room_id, data, exclude_user)
            except Exception:
                logging.exception("Delegated send_to_room failed")
        if room_id is None:
            logging.warning("Attempted to send to room with no room_id")
            return
        room_id = str(room_id)
        with self._lock:
            for client_id, client in list(self._clients.items()):
                if ('transport' in client and 'user_id' in client and 'room_id' in client and str(client['room_id']) == room_id):
                    if exclude_user and client.get('user_id') == exclude_user:
                        continue
                    try:
                        client['transport'].write(data)
                    except Exception as e:
                        logging.error("Error sending to client %s in room %s: %s", client_id, room_id, e)

    def broadcast(self, data: Dict[str, Any], exclude_user: Optional[str] = None) -> None:
        if self._delegate:
            try:
                return self._delegate.broadcast(data, exclude_user)
            except Exception:
                logging.exception("Delegated broadcast failed")
        with self._lock:
            for client_id, client in list(self._clients.items()):
                if 'transport' in client and 'user_id' in client:
                    if exclude_user and client['user_id'] == exclude_user:
                        continue
                    try:
                        client['transport'].write(data)
                    except Exception as e:
                        logging.error("Error broadcasting to client %s: %s", client_id, e)

# Provide module-level singleton for compatibility with older code
client_manager = ClientManager()
