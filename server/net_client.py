#!/bin/env python3
import logging
import select
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
    mode: Mode.init
    protocol: int
    translation: Translation
    
    def __post_init__(self):
        self.translation = Translation(**self.translation) if isinstance(self.translation, dict) else self.translation

class Client:
    """Basic client that connects to the TADA server."""
    
    def __init__(self):
        self.user_id = None
        self.password = None
        self.mode = Mode.init
        self._connected = False
        self._shutdown_event = threading.Event()
        self.client_socket = None
        self._receive_thread = None
        
    def set_user(self, user_id: None):
        """Set the current user ID."""
        self.user_id = user_id
        logger.debug(f"User set to: {user_id}")

    def set_password(self, password: None):
        """Set the current password."""
        self.password = password
        logger.debug(f"Password set to: {password}")
    
    def connect(self, host, port, server_id, server_key, protocol_version, translation: Translation=None):
        """Start the client and connect to the server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            server_id: Server ID for authentication
            server_key: Server key for authentication
            protocol_version: Protocol version
            translation: Optional translation settings
            
        Raises:
            ConnectionError: If connection to the server fails
        """
        try:
            self.server_id = server_id
            self.server_key = server_key
            self.host = host
            self.port = port
            self.protocol_version = protocol_version
            self.translation = translation
            
            logger.info(f"Attempting to connect to {host}:{port}...")
            
            # Initialize socket with TCP/IP
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set socket options - ensure it's in blocking mode initially
            self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.client_socket.setblocking(True)  # Start with blocking mode
            self.client_socket.settimeout(10.0)  # 10 second timeout for operations
            
            # Connect to the server
            logger.debug(f"Connecting to {host}:{port}...")
            try:
                self.client_socket.connect((host, port))
                self._connected = True
                logger.info("Socket connected, sending initialization data...")
                
                # Keep socket in blocking mode for the initial handshake
                # We'll set it to non-blocking after sending the initialization data
            except Exception as e:
                logger.error(f"Failed to connect to {host}:{port}: {e}")
                self._cleanup()
                raise
            
            # Prepare initial data
            init_data = {
                'mode': 'init',              # Server mode (must initially be 'init')
                'server_id': 'test_server',  # Server ID
                'server_key': 'test_key',    # Server key
                'protocol_version': 1,       # Protocol version
                'translation': 'UTF-8'       # Default translation
            }
            
            # Send initial handshake data first (socket is still in blocking mode)
            logger.debug("Sending initial handshake data...")
            self._send_data(init_data)
            logger.info("Initial handshake data sent to server")
            
            # Now that we've sent the initial handshake data, set to non-blocking for select()
            self.client_socket.setblocking(False)
            
            # Start the receive thread after sending init data and setting non-blocking
            self._shutdown_event.clear()
            self._receive_thread = threading.Thread(
                target=self._receive_messages,
                name="ClientReceiveThread",
                daemon=True
            )
            self._receive_thread.start()
            logger.info("Receive thread started")
            
            # Wait for the connection to be established or fail
            max_wait = 5.0  # Maximum time to wait for connection (5 seconds)
            start_time = time.time()
            
            while not self._connected and (time.time() - start_time) < max_wait:
                time.sleep(0.1)  # Small sleep to prevent busy-waiting
            
            if not self._connected:
                error_msg = "Failed to establish connection: No response from server"
                logger.error(error_msg)
                self._cleanup()
                raise ConnectionError(error_msg)
                
            logger.info("Connection established successfully")
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
        """Send a command to the server.
        
        This method handles all command processing, including login and guest commands.
        It formats the command appropriately based on the current mode and sends it to the server.
        """
        if not self._connected:
            print("Not connected to server")
            return
            
        command = command.strip()
        if not command:
            return
            
        try:
            # Handle guest login
            if command.lower() == 'guest' and self.mode == Mode.login:
                self._send_data({
                    'mode': 'guest',
                    'type': 'command',
                    'text': 'guest',
                    'user_id': 'guest',
                    'password': 'guest'
                })
                return
                
            # Handle login command with 'login' prefix
            if command.lower().startswith('login '):
                parts = command[6:].strip().split()  # Remove 'login ' prefix and split
                if len(parts) >= 1:  # At least username provided
                    username = parts[0]
                    password = parts[1] if len(parts) > 1 else ''
                    self._send_data({
                        'mode': 'login',
                        'type': 'command',
                        'user_id': username,
                        'password': password
                    })
                    return
            
            # Handle login without 'login' prefix (just username and password)
            if self.mode == Mode.login and ' ' in command:
                username, password = command.split(' ', 1)
                self._send_data({
                    'mode': 'login',
                    'type': 'command',
                    'user_id': username,
                    'password': password
                })
                return
                
            # For all other commands, send them as-is with the current mode
            self._send_data({
                'mode': str(self.mode),  # Convert Mode enum to string
                'type': 'command',
                'text': command
            })
            
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            print(f"Error: {e}")
    
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
        """Send data to the server with proper length prefixing."""
        if not self._connected or not self.client_socket:
            raise ConnectionError("Not connected to server")
            
        # Save the original timeout
        original_timeout = self.client_socket.gettimeout()
        
        try:
            # Set a reasonable timeout for sending
            self.client_socket.settimeout(10.0)
            
            # Ensure data is a dictionary
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data).__name__}")
            
            # Convert data to JSON and encode as bytes
            json_data = json.dumps(data).encode('utf-8')
            logger.debug(f"Sending data: {data}")
            
            # Create length prefix (4-byte big-endian)
            length_prefix = len(json_data).to_bytes(4, byteorder='big')
            
            # Combine length prefix and data
            message = length_prefix + json_data
            total_sent = 0
            
            # Log the exact bytes being sent
            logger.debug(f"Sending message (hex): {message.hex()}")
            logger.debug(f"  Length prefix: {length_prefix.hex()} ({int.from_bytes(length_prefix, 'big')} bytes)")
            logger.debug(f"  JSON data: {json_data.decode('utf-8', errors='replace')}")
            
            # Send the complete message, handling partial sends
            try:
                while total_sent < len(message):
                    try:
                        sent = self.client_socket.send(message[total_sent:])
                        if sent == 0:
                            raise ConnectionError("Socket connection broken")
                        logger.debug(f"Sent {sent} bytes")
                        total_sent += sent
                    except BlockingIOError:
                        # Wait for the socket to be ready for writing
                        select.select([], [self.client_socket], [])
                
                logger.info(f"Successfully sent {total_sent} bytes (JSON: {len(json_data)} bytes)")
                return total_sent
                
            except Exception as e:
                logger.error(f"Error sending data: {e}")
                raise
            
        except (ConnectionResetError, ConnectionAbortedError) as e:
            logger.error(f"Connection error while sending data: {e}")
            self._connected = False
            raise ConnectionError("Connection lost") from e
            
        except Exception as e:
            logger.error(f"Error sending data: {e}", exc_info=True)
            self._connected = False
            raise
            
        finally:
            # Restore the original timeout
            self.client_socket.settimeout(original_timeout)
    
    def _receive_messages(self):
        """Handle incoming messages from the server."""
        logger.info("Starting message receiver thread")
        
        try:
            # Initial connection is established, notify the main thread
            self._connected = True
            
            while self._connected and not self._shutdown_event.is_set():
                try:
                    # Check if we should still be connected
                    if not self._connected:
                        break
                        
                    # Wait for data with a timeout to allow for clean shutdown
                    try:
                        # Use a short timeout for select to allow for clean shutdown
                        ready = select.select([self.client_socket], [], [], 1.0)
                        if not ready[0]:
                            # No data ready, check if we should still be running
                            if self._shutdown_event.is_set():
                                logger.debug("Shutdown event set, exiting receive loop")
                                break
                            continue
                        
                        # Set a reasonable timeout for the actual receive operation
                        self.client_socket.settimeout(10.0)
                        
                        # Receive the message
                        logger.debug("Socket is ready, attempting to receive message...")
                        try:
                            message = nc.from_jsonb_socket(self.client_socket)
                            if message is None:
                                logger.info("Connection closed by server")
                                self._connected = False
                                break
                                
                            logger.info(f"Received message: {message}")
                            
                            # Process the message if it's a dictionary
                            if isinstance(message, dict):
                                logger.debug(f"Processing message with keys: {message.keys()}")
                                self._process_mode(message)
                            else:
                                logger.warning(f"Received non-dictionary message: {message}")
                                
                        except socket.timeout:
                            logger.debug("Timeout while waiting for message data")
                            continue
                            
                        except (ConnectionResetError, ConnectionAbortedError) as e:
                            logger.error(f"Connection error while receiving: {e}")
                            self._connected = False
                            break
                            
                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)
                            continue
                            
                    except Exception as e:
                        logger.error(f"Error in receive loop: {e}", exc_info=True)
                        self._connected = False
                        break
                        
                        # If we receive a welcome message with lines, print them
                        if 'lines' in message and isinstance(message['lines'], list):
                            for line in message['lines']:
                                if isinstance(line, str):
                                    print(line)
                                else:
                                    print(str(line))
                        
                        # If we're in login mode, prompt for credentials
                        if self.mode == Mode.login:
                            print("\nPlease log in with 'login <username> <password>' or type 'guest' to continue as a guest.")
                            print("TADA> ", end='', flush=True)
                
                except socket.timeout:
                    logger.debug("Timeout while waiting for server response")
                    continue
                    
                except (ConnectionResetError, ConnectionAbortedError) as e:
                    logger.error(f"Connection error: {e}")
                    print("\nConnection to server lost.")
                    self._connected = False
                    break
                
                except Exception as e:
                    logger.error(f"Error in message receiver: {e}", exc_info=True)
                    print(f"\nError: {e}")
                    self._connected = False
                    break
                    
        except Exception as e:
            logger.error(f"Fatal error in message receiver: {e}", exc_info=True)
            print(f"\nFatal error: {e}")
        finally:
            logger.info("Message receiver thread exiting")
            self._connected = False

    def init_success_lines(self, request):
        logging.debug(f"init_success_lines: received data: {request}")
        self.mode = Mode.app
        if 'lines' in request and isinstance(request['lines'], list):
            for line in request['lines']:
                # Format the line with any available user_id
                if '{user_id}' in line and 'user_id' in request:
                    line = line.format(user_id=request['user_id'])
                print(line)

    def _process_mode(self, request):
        """Process the response from the server based on the mode.
        
        Args:
            request: The request dictionary or Message object from the server
        """
        logger.debug(f"Processing mode with request: {request}")
        
        # Convert request to dict if it's a Message object
        try:
            if hasattr(request, 'to_dict'):
                request = request.to_dict()
        except Exception as e:
            logger.error(f"Error converting request to dict: {e}")
            return
        
        # If request is None or not a dict, log error and return
        if not request or not isinstance(request, dict):
            logger.error(f"Invalid request format: {request}")
            return
            
        # Print any lines from the response
        if 'lines' in request and isinstance(request['lines'], list):
            for line in request['lines']:
                print(line)
                
        # Update mode if specified in the response
        if 'mode' in request:
            new_mode = request['mode']
            if new_mode != self.mode:
                logger.debug(f"Mode changed from {self.mode} to {new_mode}")
                self.mode = new_mode
                
        # Print any error messages
        if 'error' in request and request['error']:
            print(f"Error: {request['error']}")
            if 'error_line' in request and request['error_line']:
                print(f"At: {request['error_line']}")
            logger.error(f"Invalid request format: {request}")
            return
            
        mode = request.get('mode', '').lower()
        logger.debug(f"Processing mode: {mode}. Current mode: {self.mode}")
        
        # Handle different modes first, as they might affect how we process the message
        if mode == 'command_result':
            self._handle_command_result(request)
            return
        elif mode == 'room_change':
            self._handle_room_change(request)
            return
        elif mode == 'room_data':
            self._handle_room_data(request)
            return
        elif mode == 'error':
            error_msg = request.get('error', 'Unknown error')
            logger.error(f"Server error: {error_msg}")
            print(f"Error: {error_msg}")
            return
            
        # Process any message lines with proper formatting
        if 'lines' in request and isinstance(request['lines'], list):
            for line in request['lines']:
                if isinstance(line, str):  # Only process string lines
                    if '{user_id}' in line and 'user_id' in request:
                        line = line.format(user_id=request['user_id'])
                    print(line)
        
        # Handle mode-specific processing that should happen after displaying messages
        if mode in ['init', Mode.init.value]:
            # Initial connection, server is ready for login
            logger.debug("Connection initialized, processing welcome message")
            
            # Display any welcome message from the server
            if 'lines' in request and isinstance(request['lines'], list) and request['lines']:
                print("\n" + "\n".join(str(line) for line in request['lines']))
            
            # Only show login prompt if we don't already have a user_id
            # This prevents the prompt from appearing multiple times
            if not self.user_id:
                print("\nPlease log in or type 'guest' to continue as a guest.")
                print("Available commands: login <username> <password>, guest, help\n")

        elif mode == Mode.login.value:
            # Handle login response
            if not request.get('success', False):
                # Login failed
                error_msg = request.get('error', 'Login failed')
                logger.warning(f"Login failed: {error_msg}")
                print(f"\nError: {error_msg}")
                
                # Display any additional error messages
                if 'lines' in request and isinstance(request['lines'], list) and request['lines']:
                    print("\n".join(str(line) for line in request['lines']))
                    
                # Show login prompt again
                print("\nPlease try again or type 'guest' to continue as a guest.")
                print("Available commands: login <username> <password>, guest, help\n")
            else:
                # Login successful
                if 'user_id' in request:
                    self.user_id = request['user_id']
                    self.mode = Mode.app  # Switch to app mode on successful login
                
                # Display welcome messages
                if 'lines' in request and isinstance(request['lines'], list) and request['lines']:
                    print("\n" + "\n".join(str(line) for line in request['lines']))
                    
                # Show command prompt
                print("\nType 'help' for a list of available commands.\n")
        
        elif mode == Mode.guest.value:
            # Handle guest login
            logger.debug(f"Processing guest response: {request}")
            if request.get('success', False):
                # Update user info if provided
                if 'user_id' in request:
                    self.user_id = request['user_id']
                
                # Update mode to app for guest
                self.mode = Mode.app
                
                # Display welcome messages
                if 'lines' in request and isinstance(request['lines'], list) and request['lines']:
                    print("\n" + "\n".join(str(line) for line in request['lines']))
                else:
                    print("\nWelcome, guest!")
                
                # Show command prompt
                print("\nType 'help' for a list of available commands.\n")
            else:
                # Guest login failed
                error_msg = request.get('error', 'Guest login failed')
                logger.warning(f"Guest login failed: {error_msg}")
                print(f"\nError: {error_msg}")
                
                # Display any additional error messages
                if 'lines' in request and isinstance(request['lines'], list) and request['lines']:
                    print("\n".join(str(line) for line in request['lines']))
                
                # Show login prompt again
                print("\nPlease try again or type 'login <username> <password>' to log in.\n")
                
                logger.info(f"Successfully logged in as {self.user_id or 'unknown'}")
                
                # Print any additional welcome messages
                if 'lines' in request and isinstance(request['lines'], list):
                    for line in request['lines']:
                        if isinstance(line, str):
                            if '{user_id}' in line and 'user_id' in request:
                                line = line.format(user_id=request['user_id'])
                            print(line)
                    
        elif mode == Mode.guest.value:
            # Handle guest login
            logger.debug(f"Processing guest response: {request}")
            if request.get('success', False):
                # Update user info first
                if 'user_id' in request:
                    self.user_id = request['user_id']
                    
                # Print welcome messages
                if 'lines' in request and isinstance(request['lines'], list):
                    for line in request['lines']:
                        if isinstance(line, str):
                            if '{user_id}' in line and 'user_id' in request:
                                line = line.format(user_id=request['user_id'])
                            print(line)
                    
                # Switch to guest mode after successful login
                self.mode = Mode.guest
                logger.debug(f"Mode changed to {self.mode} for user {self.user_id}")
                
                # Update prompt
                self.prompt = f'{self.user_id}> '
                print(self.prompt, end='', flush=True)
            else:
                error_msg = request.get('error', 'Guest login failed')
                print(f"Guest login failed: {error_msg}")
                
        elif mode == Mode.bye.value:
            # Server is disconnecting us
            print("\nDisconnected by server")
            if 'lines' in request and isinstance(request['lines'], list):
                for line in request['lines']:
                    print(line)
            elif 'error' in request and request['error']:
                print(f"Error: {request['error']}")
            self._connected = False
            return
                
        # Print any message lines for other modes
        if 'lines' in request and isinstance(request['lines'], list):
            for line in request['lines']:
                if '{user_id}' in line and 'user_id' in request:
                    line = line.format(user_id=request['user_id'])
                print(line)

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
                print(f"Ye may travel: {', '.join(exit_list)}")
            
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

def get_input(prompt, hidden=False):
    """Get input from user, optionally hiding the input."""
    if hidden:
        import getpass
        return getpass.getpass(prompt)
    return input(prompt)

def main():
    import argparse
    import time
    import getpass
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='TADA Client')
    parser.add_argument('host', nargs='?', default='localhost', help='Server hostname or IP (default: localhost)')
    parser.add_argument('port', nargs='?', type=int, default=4000, help='Server port (default: 4000)')
    parser.add_argument('--user', help='Username (if not provided, will prompt)')
    parser.add_argument('--guest', action='store_true', help='Login as guest')
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,  # Changed to INFO to reduce debug noise
        format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s',
        handlers=[
            logging.FileHandler('client.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # Create client instance
    client = Client()
    
    # Get connection details
    host = args.host
    port = args.port
    
    # Determine if using guest login
    if args.guest:
        user_id = 'guest'
        password = 'guest'
    else:
        # Prompt for username if not provided
        user_id = args.user or get_input('Username: ').strip()
        if not user_id:
            user_id = 'guest'
            password = 'guest'
            print("No username provided, defaulting to guest login")
        else:
            password = getpass.getpass('Password: ')
    
    # Use test credentials if available, otherwise use provided credentials
    test_mode = getattr(nc, 'Test', None)
    if test_mode:
        key = test_mode.key
        protocol = test_mode.protocol
    else:
        key = 'client_key'  # This should match server's expected key
        protocol = 1
    
    print(f"Connecting to {host}:{port}...")
    try:
        client.connect(host, port, user_id, key, protocol)
        
        # Main input loop
        while client._connected and not client._shutdown_event.is_set():
            try:
                # Display appropriate prompt based on mode
                if client.mode == Mode.app:
                    prompt = f"{user_id}> "
                elif client.mode == Mode.login:
                    prompt = "Login (username password) or 'guest' to continue: "
                else:
                    prompt = "> "
                
                try:
                    command = input(prompt).strip()
                    
                    # Handle special commands
                    if command.lower() in ('quit', 'exit', 'q'):
                        print("Disconnecting...")
                        break
                    
                    # Send the command to the server
                    if command:
                        client.default(command)
                        
                except EOFError:
                    print("\nUse 'quit' or 'exit' to disconnect")
                    continue
                time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in input loop: {e}", exc_info=True)
                break
                
    except Exception as e:
        logger.error(f"Client error: {e}", exc_info=True)
        return 1
        
    finally:
        client.close()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
