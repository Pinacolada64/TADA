"""
Client manager for handling connected clients and their sessions.
"""
import json
import logging
from typing import Dict, Set, Optional, Any, Union

class ClientManager:
    """Manages connected clients and their sessions."""
    
    def __init__(self):
        """Initialize the client manager."""
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._user_to_client: Dict[str, str] = {}
        self._lock = None  # Will be set by the server
    
    def set_lock(self, lock):
        """Set the thread lock for thread-safe operations.
        
        Args:
            lock: The threading.Lock instance to use
        """
        self._lock = lock
    
    def add_client(self, client_id: str, client_data: Dict[str, Any]) -> None:
        """Add a new client to the manager.
        
        Args:
            client_id: Unique identifier for the client
            client_data: Client data including transport, protocol, etc.
        """
        with self._lock:
            self._clients[client_id] = client_data
            logging.debug("Added client %s", client_id)
    
    def remove_client(self, client_id: str) -> None:
        """Remove a client from the manager.
        
        Args:
            client_id: The ID of the client to remove
        """
        with self._lock:
            client = self._clients.pop(client_id, None)
            if client and 'user_id' in client:
                self._user_to_client.pop(client['user_id'], None)
            logging.debug("Removed client %s", client_id)
    
    def authenticate_client(self, client_id: str, user_id: str) -> None:
        """Authenticate a client with a user ID.
        
        Args:
            client_id: The client ID
            user_id: The user ID to authenticate with
        """
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id]['user_id'] = user_id
                self._user_to_client[user_id] = client_id
                logging.info("Authenticated client %s as user %s", client_id, user_id)
    
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client data by client ID.
        
        Args:
            client_id: The client ID
            
        Returns:
            Optional[Dict]: The client data, or None if not found
        """
        return self._clients.get(client_id)
    
    def get_client_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get client data by user ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[Dict]: The client data, or None if not found
        """
        client_id = self._user_to_client.get(user_id)
        return self.get_client(client_id) if client_id else None
    
    def is_online(self, user_id: str) -> bool:
        """Check if a user is online.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            bool: True if the user is online, False otherwise
        """
        return user_id in self._user_to_client
    
    def get_online_players(self) -> Set[str]:
        """Get a set of online player user IDs.
        
        Returns:
            Set[str]: Set of online user IDs
        """
        with self._lock:
            return {client['user_id'] for client in self._clients.values() 
                   if 'user_id' in client}
    
    def send_to(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Send data to a specific user.
        
        Args:
            user_id: The user ID to send to
            data: The data to send
            
        Returns:
            bool: True if the data was sent, False otherwise
        """
        client = self.get_client_by_user(user_id)
        if not client or 'transport' not in client:
            return False
        
        try:
            client['transport'].write(data)
            return True
        except Exception as e:
            logging.error("Error sending data to user %s: %s", user_id, e)
            return False
    
    def send_to_room(
        self, 
        room_id: Union[str, int], 
        data: Dict[str, Any], 
        exclude_user: Optional[str] = None
    ) -> None:
        """Send data to all clients in a specific room.
        
        Args:
            room_id: The ID of the room to send the message to
            data: The data to send (will be JSON-encoded)
            exclude_user: Optional user ID to exclude from receiving the message
        """
        if room_id is None:
            logging.warning("Attempted to send to room with no room_id")
            return
            
        room_id = str(room_id)  # Ensure room_id is a string for consistent comparison
            
        try:
            # Convert data to JSON once
            message = json.dumps(data).encode('utf-8')
            
            with self._lock:
                for client_id, client in list(self._clients.items()):
                    if ('transport' in client and 
                        'user_id' in client and 
                        'room_id' in client and 
                        str(client['room_id']) == room_id):
                        
                        # Skip excluded user if specified
                        if exclude_user and client.get('user_id') == exclude_user:
                            continue
                            
                        try:
                            client['transport'].write(message)
                        except Exception as e:
                            logging.error(
                                "Error sending to client %s in room %s: %s", 
                                client_id, room_id, e
                            )
        except json.JSONEncodeError as e:
            logging.error("Failed to encode message for room %s: %s", room_id, e)
        except Exception as e:
            logging.error("Unexpected error in send_to_room: %s", e, exc_info=True)
    def broadcast(self, data: Dict[str, Any], exclude_user: Optional[str] = None) -> None:
        """Broadcast data to all connected clients.
        
        Args:
            data: The data to broadcast
            exclude_user: Optional user ID to exclude from the broadcast
        """
        with self._lock:
            for client_id, client in list(self._clients.items()):
                if 'transport' in client and 'user_id' in client:
                    if exclude_user and client['user_id'] == exclude_user:
                        continue
                    try:
                        client['transport'].write(data)
                    except Exception as e:
                        logging.error("Error broadcasting to client %s: %s", client_id, e)
