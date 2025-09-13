#!/bin/env python3
import logging
import socket
import sys
import os
import json
import cmd
import shlex
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Set, Callable
from threading import Event
from enum import Enum, auto

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('client.log')
    ]
)
logger = logging.getLogger(__name__)


# TADA-specific imports
# Use relative imports since we're in the server package
import server.net_common as nc
from server.terminal import Translation
from server.net_common import Mode

# These are local imports, keep them as is

@dataclass
class Init:
    id: str
    key: str
    protocol: int
    translation: Translation
    
    def __post_init__(self):
        self.translation = Translation(**self.translation) if isinstance(self.translation, dict) else self.translation

class Client:
    """Basic client that connects to the TADA server."""
    
    def __init__(self):
        self.user_id = None
        self.mode = Mode.init
        self._connected = False
        self._shutdown_event = threading.Event()
        self.client_socket = None
        self._receive_thread = None
        
    def set_user(self, user_id):
        """Set the current user ID."""
        self.user_id = user_id
        logger.debug(f"User set to: {user_id}")
    
    def start(self, host, port, user_id, key, protocol, translation=None):
        """Start the client and connect to the server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            user_id: User ID for authentication
            key: Authentication key
            protocol: Protocol version
            translation: Optional translation settings
            
        Raises:
            ConnectionError: If connection to the server fails
        """
        try:
            self.user_id = user_id
            self.host = host
            self.port = port
            self.key = key
            self.protocol = protocol
            self.translation = translation
            
            logger.info(f"Attempting to connect to {host}:{port}...")
            
            # Initialize socket with TCP/IP
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options
            self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.client_socket.settimeout(10.0)  # 10 second timeout for operations
            
            # Connect to the server
            logger.debug(f"Connecting to {host}:{port}...")
            self.client_socket.connect((host, port))
            self._connected = True
            logger.info("Socket connected, sending initialization data...")
            
            # Prepare initialization data
            init_data = {
                'mode': 'init',  # Use string literal to ensure compatibility
                'id': user_id,
                'key': key,
                'protocol': protocol,
            }
            
            # Handle translation if provided
            if translation is not None:
                if hasattr(translation, '_asdict'):  # For namedtuple
                    init_data['translation'] = translation._asdict()
                elif hasattr(translation, '__dict__'):  # For objects with __dict__
                    init_data['translation'] = translation.__dict__
                else:
                    init_data['translation'] = str(translation)
            
            # Send initialization data
            logger.debug(f"Sending init data: {init_data}")
            nc.to_jsonb_socket(self.client_socket, init_data)
            
            # Start the receive thread
            self._shutdown_event.clear()
            self._receive_thread = threading.Thread(
                target=self._receive_messages,
                name="ClientReceiveThread",
                daemon=True
            )
            self._receive_thread.start()
            logger.info("Receive thread started")
            
            # Wait briefly to ensure the connection is established
            time.sleep(0.1)
            
            if not self._connected:
                raise ConnectionError("Failed to establish connection")
                
            logger.info(f"Successfully connected to {host}:{port} as {user_id}")
            return True
            
        except socket.timeout as e:
            error_msg = f"Connection to server timed out after 10 seconds: {e}"
            logger.error(error_msg)
            self._connected = False
            self._cleanup()
            raise ConnectionError(error_msg) from e
            
        except ConnectionRefusedError as e:
            error_msg = f"Connection refused by server at {host}:{port}. Is the server running?"
            logger.error(error_msg)
            self._connected = False
            self._cleanup()
            raise ConnectionError(error_msg) from e
            
        except socket.gaierror as e:
            error_msg = f"Failed to resolve hostname '{host}': {e}"
            logger.error(error_msg)
            self._connected = False
            self._cleanup()
            raise ConnectionError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to connect to server: {e}"
            logger.error(error_msg, exc_info=True)
            self._connected = False
            self._cleanup()
            raise ConnectionError(error_msg) from e
    
    def default(self, command):
        """Send a command to the server."""
        if not self._connected:
            print("Not connected to server")
            return
            
        try:
            self._send_data({
                'type': 'command',
                'text': command
            })
        except Exception as e:
            logger.error(f"Error sending command: {e}")
    
    def close(self):
        """Close the client connection and clean up resources."""
        if self._connected:
            logger.info("Closing connection...")
            self._cleanup()
            logger.info("Connection closed")
    
    def _cleanup(self):
        """Clean up resources and close connections."""
        try:
            self._shutdown_event.set()
            
            # Close the socket if it exists
            if hasattr(self, 'client_socket') and self.client_socket:
                try:
                    self.client_socket.shutdown(socket.SHUT_RDWR)
                    self.client_socket.close()
                except Exception as e:
                    logger.debug(f"Error closing socket: {e}")
                finally:
                    self.client_socket = None
            
            # Wait for receive thread to finish
            if hasattr(self, '_receive_thread') and self._receive_thread:
                try:
                    self._receive_thread.join(timeout=1.0)
                except Exception as e:
                    logger.debug(f"Error joining receive thread: {e}")
                finally:
                    self._receive_thread = None
            
            self._connected = False
            logger.info("Connection cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def _send_data(self, data):
        """Send data to the server."""
        try:
            if not self._connected or not self.client_socket:
                raise ConnectionError("Not connected to server")
                
            nc.to_jsonb_socket(self.client_socket, data)
            logger.debug(f"Sent data: {data}")
            
        except (ConnectionResetError, ConnectionAbortedError) as e:
            logger.error(f"Connection error while sending data: {e}")
            self._connected = False
            raise ConnectionError("Connection lost") from e
            
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            self._connected = False
            raise
    
    def _receive_messages(self):
        """Handle incoming messages from the server."""
        logger.info("Starting message receiver thread")
        
        while self._connected and not self._shutdown_event.is_set():
            try:
                # Check if we should still be connected
                if not self._connected:
                    break
                    
                # Wait for data with a timeout to allow for clean shutdown
                ready = select.select([self.client_socket], [], [], 1.0)
                if not ready[0]:
                    continue  # No data ready, check again
                
                # Receive the message
                message = nc.from_jsonb_socket(self.client_socket)
                if message is None:
                    logger.info("Server closed the connection")
                    self._connected = False
                    break
                
                logger.debug(f"Received message: {message}")
                
                # Process the message
                try:
                    if isinstance(message, dict):
                        # Update mode if present in message
                        if 'mode' in message:
                            new_mode = message['mode']
                            if new_mode != self.mode:
                                logger.debug(f"Mode changed from {self.mode} to {new_mode}")
                                self.mode = new_mode
                        
                        # Process the message based on its content
                        self._process_mode(message)
                    else:
                        logger.warning(f"Received non-dict message: {message}")
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
            
            except (ConnectionResetError, ConnectionAbortedError) as e:
                logger.error(f"Connection error: {e}")
                self._connected = False
                break
                
            except socket.timeout:
                # Expected timeout, continue the loop
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error in receive thread: {e}", exc_info=True)
                self._connected = False
                break
                
        logger.info("Message receiver thread exiting")
        self._connected = False

    def _process_mode(self, request):
        """Process the response from the server based on the mode.
        
        Args:
            request: The request dictionary from the server
        """
        try:
            if not isinstance(request, dict):
                logger.warning(f"Received non-dict message: {request}")
                return
                
            mode = request.get('mode')
            if not mode:
                logger.warning("Received message without mode")
                return
                
            logger.debug(f"Processing mode: {mode}")
            
            # Handle different modes
            if mode == 'command_result':
                self._handle_command_result(request)
            elif mode == 'room_change':
                self._handle_room_change(request)
            elif mode == 'room_data':
                self._handle_room_data(request)
            elif mode == 'error':
                error_msg = request.get('error', 'Unknown error')
                logger.error(f"Server error: {error_msg}")
                print(f"Error: {error_msg}")
            elif mode == 'message':
                # Handle simple text messages from the server
                if 'text' in request:
                    print(request['text'])
            elif mode == 'login':
                # Handle login response
                if 'success' in request:
                    if request['success']:
                        print("Login successful!")
                        self.mode = Mode.app  # Switch to app mode
                        
                        # Save login if available
                        if hasattr(self, 'login') and hasattr(self.login, 'save'):
                            self.login.save()
                        
                        # Update prompt after successful login
                        self.prompt = '> '
                        print(self.prompt, end='', flush=True)
                    else:
                        error_msg = request.get('error', 'Login failed')
                        print(f"Login failed: {error_msg}")
            else:
                logger.warning(f"Unhandled mode: {mode}")
                print(f"Server: {request}")  # Fallback for unhandled messages
            
            # Handle prompt if present in the request
            if 'prompt' in request:
                self.current_prompt = request['prompt']
                print(self.current_prompt, end='', flush=True)
                
        except Exception as e:
            logging.error(f"Error processing server response: {e}", exc_info=True)
            return None

    def _handle_command_result(self, result: Dict[str, Any]) -> None:
        """Handle command result messages from the server."""
        try:
            # Print the message if present
            if 'message' in result and result['message']:
                print(result['message'])
            
            # Handle error cases
            if not result.get('success', True):
                error_msg = result.get('error', 'An unknown error occurred')
                error_code = result.get('error_code', 'error')
                print(f"Error ({error_code}): {error_msg}")
            
            # Handle room data if present
            if 'data' in result and 'room' in result['data']:
                self._handle_room_data(result['data']['room'])
                
        except Exception as e:
            logging.error(f"Error handling command result: {e}", exc_info=True)
    
    def _handle_room_change(self, data: Dict[str, Any]) -> None:
        """Handle room change events from the server."""
        try:
            user_id = data.get('user_id')
            room_id = data.get('room')
            message = data.get('message', '')
            
            if message:
                print(message)
                
            # If it's the current user who changed rooms, update local state
            if user_id == self.user_id and room_id is not None:
                self.current_room = room_id
                
        except Exception as e:
            logging.error(f"Error handling room change: {e}", exc_info=True)
    
    def _handle_room_data(self, room_data: Dict[str, Any]) -> None:
        """Handle room data from the server."""
        try:
            # Print room name and description
            print(f"\n{room_data.get('name', 'Unknown Room')}")
            print(f"{room_data.get('description', '')}\n")
            
            # Print exits
            exits = room_data.get('exits', {})
            if exits:
                exit_list = [f"{direction.capitalize()}" for direction in exits.keys()]
                print(f"Exits: {', '.join(exit_list)}")
            
            # Print other players in the room
            players = room_data.get('players', [])
            if players:
                player_list = ", ".join(players)
                print(f"\nAlso here: {player_list}")
                
        except Exception as e:
            logging.error(f"Error handling room data: {e}", exc_info=True)
            return None

    def close(self):
        """Close the client connection and clean up resources."""
        logger.info("Closing client connection")
        self._shutdown_event.set()
        if hasattr(self, 'client_socket') and self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                logger.error(f"Error closing socket: {e}")
        self._connected = False
        
    def process_request(self, request):
        """Process a request from the server.
        
        Args:
            request: The request data from the server
            
        Returns:
            Response to send back to the server
        """
        self._print_common(request)
        text = input('> ')
        return {'text': text}


class CommodoreClient(Client):
    """Client that sends just lines of text for Commodore clients."""
    
    def __init__(self, client):
        super().__init__(client)
    
    def _send_data(self, message):
        # Handle PETSCII translation if needed
        if isinstance(message, dict):
            if getattr(self.client, 'translation', None) == Translation.PETSCII:
                """
                send data to socket, but break down Message object into "key: value" lines
                and send each one separately. so if we were sending a Message object with
                
                lines=["line 1", "line 2", "line 3"], mode="login", error="", error_line=""]

                we would send:
                
                line: "line 1"
                line: "line 2"
                line: "line 3"
                mode: "login"
                error: ""
                error_line: ""
                end: <etx> # [ctrl-d] for commodoreserver compatability
                """
                for key, value in message.items():
                    self.client.send_data(cmd(text=f"{key}: {value}"))
                self.client.send_data(cmd(text="end: {chr(4)}"))  # etx, invisible in terminals

    def _receive_data(self):
        """
        Commodore clients expect '\r' as line separator
        TODO: messages received from the Commodore client will just be one string per line:
        (an abbreviated Message object, I guess):
        
        line: "line 1"
        line: "line 2"
        line: "line 3"
        mode: "login"
        error: ""
        error_line: ""
        end: <etx> # [ctrl-d]

        "end: <etx>" is the CommodoreServer way of indicating the end of a message.  
        would convert server-side to:
        Message(lines=["line 1", "line 2", "line 3"], mode="login", error="", error_line="")
        """
        # loop until either:
        # - we get a series of lines followed by an EOT [end of text] byte
        # - a timeout delay of 20 seconds elapses (not sure if this will be reliable enough)
        if getattr(self.client, 'translation', None) == Translation.PETSCII:
            while self._receive_message(message.get('lines', []) != "end: {4}"):
                time.sleep(0.1)
            
        return Message(lines=lines, mode=mode.app, error="")

def main():
    import argparse
    import time
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='TADA Client')
    parser.add_argument('host', help='Server hostname or IP')
    parser.add_argument('port', type=int, help='Server port')
    parser.add_argument('--user', default='player1', help='Username')
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Create client instance
    client = Client()
    
    try:
        # Use test credentials if available, otherwise use provided args
        user_id = getattr(nc, 'Test', None) and nc.Test.id or args.user
        key = getattr(nc, 'Test', None) and nc.Test.key or 'test_key'
        protocol = getattr(nc, 'Test', None) and nc.Test.protocol or 1
        
        print(f"Connecting to {args.host}:{args.port} as {user_id}...")
        client.start(args.host, args.port, user_id, key, protocol)
        
        # Main input loop
        while client._connected and not client._shutdown_event.is_set():
            try:
                # This will be handled by the receive thread
                time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nDisconnecting...")
                break
                
    except Exception as e:
        logger.error(f"Client error: {e}", exc_info=True)
        return 1
    finally:
        client.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
