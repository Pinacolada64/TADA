#!/bin/env python3
import logging
from pathlib import Path
import select
import socket
import json
import threading

# Set up logging
logger = logging.getLogger(__name__)
import sys
import os
import traceback
import threading
import socketserver
import json
import time
from dataclasses import dataclass, field
from typing import ClassVar, Optional, Dict, Any, Set, List, Union, Tuple
import enum
import importlib.util

# TADA-specific imports
import server.net_common as nc

K = nc.K
Mode = nc.Mode

server_id = None
server_key = None
server_protocol = None
server_lock = threading.Lock()


class Error(str, enum.Enum):
    server1 = 'server1'
    server2 = 'server2'
    # missing user ID?:
    user_id = 'user_id'
    login1 = 'login1'
    login2 = 'login2'
    # multiple connections:
    multiple = 'multiple'


@dataclass
class Message(object):
    lines: list
    mode: Mode = None  # Will be set in __post_init__
    changes: dict = field(default_factory=lambda: {})
    choices: dict = field(default_factory=lambda: {})
    prompt: str = ''
    error: str = ''
    error_line: str = ''
    
    def __post_init__(self):
        # Set default mode if not provided
        if self.mode is None:
            self.mode = Mode.app
            
    def to_dict(self) -> dict:
        """Convert the Message to a dictionary for JSON serialization."""
        return {
            'lines': self.lines,
            'mode': self.mode.value if self.mode is not None else None,
            'changes': self.changes,
            'choices': self.choices,
            'prompt': self.prompt,
            'error': self.error,
            'error_line': self.error_line
        }


connected_users = set()
server_lock = threading.Lock()


@dataclass
class LoginHistory(object):
    """
    Login history of player

    :param addr: IP address?
    :param no_user_attempts: user ID missing?
    :param bad_password_attempts: wrong password entered?
    :param fail_count: failed login?
    :param ban_count: how many times player has been banned?
    :param _fail_limit: how many times player can fail to log in before being banned
    """
    addr: str = ""
    no_user_attempts: dict = field(default_factory=lambda: {})
    bad_password_attempts: dict = field(default_factory=lambda: {})
    fail_count: int = 0
    ban_count: int = 0

    _fail_limit: ClassVar[int] = 10

    def banned(self, update: bool, save=False):
        is_banned = self.fail_count >= LoginHistory._fail_limit
        if is_banned and update:
            self.ban_count += 1
            if save:
                self.save()
        return is_banned

    def no_user(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.no_user_attempts.get(user_id, 0)
        self.no_user_attempts[user_id] = attempts + 1
        if save:
            self.save()
        return self.banned(True, save=save)

    def fail_password(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.bad_password_attempts.get(user_id, 0)
        self.bad_password_attempts[user_id] = attempts + 1
        if save:
            self.save()
        return self.banned(True, save=save)

    def is_allowed(self, user_id):
        """Check if the user is allowed to attempt login.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            bool: True if the user is allowed to attempt login, False if they are banned
        """
        # Check if this IP is banned
        if self.fail_count >= self._fail_limit:
            return False
            
        # Check if this specific user has too many failed attempts
        if (user_id in self.bad_password_attempts and 
            self.bad_password_attempts[user_id] >= 3):  # Allow 3 failed attempts per user
            return False
            
        return True

    def succeed_user(self, user_id, save=False):
        self.fail_count = 0
        if user_id in self.bad_password_attempts:
            self.bad_password_attempts.pop(user_id)
        if save:
            self.save()

    @staticmethod
    def _json_path(addr):
        login_history = Path(nc.net_dir).mkdir(parents=True, exist_ok=True)
        return login_history / f"client-{addr}.json"

    @staticmethod
    def load(addr):
        path = LoginHistory._json_path(addr)
        if path.exists():
            with open(path) as json_file:
                lh_data = json.load(json_file)
            return LoginHistory(**lh_data)
        else:
            return LoginHistory(addr=addr)

    def save(self):
        with open(LoginHistory._json_path(self.addr), 'w') as json_file:
            # json.dump(obj=self, default=lambda o: {k: v for k, v
            #                                      in o.__dict__.items() if v}, indent=4)
            json.dump(obj=self, fp=json_file, default=lambda o: {k: v for k, v
                                                                 # in o.__dict__.items() if v}, indent=4)
                                                                 in o.__dict__.items()}, indent=4)
            logging.debug("Saved '%s'" % self.addr)


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class UserHandler(socketserver.BaseRequestHandler):
    """Handles client connections and command processing."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the user handler with default values."""
        self.user = None
        self.user_id = None
        self.mode = Mode.init
        self.buffer = b''
        self.login_history = LoginHistory()
        self.initialized = False
        self._message_queue = []
        self._message_lock = threading.Lock()
        self._running = True
        self._shutdown_event = threading.Event()
        self._command_handlers = {}
        
        # Initialize command handlers
        self._init_commands()
        
        super().__init__(*args, **kwargs)
        
        # Register with server for proper cleanup on shutdown
        if hasattr(self.server, '_register_handler'):
            self.server._register_handler(self)

    def _init_commands(self):
        """Initialize command handlers for this connection."""
        from .commands.network_commands import register_commands
        
        # Register all network commands
        for cmd in register_commands():
            self._command_handlers[cmd.name] = cmd
            for alias in getattr(cmd, 'aliases', []):
                self._command_handlers[alias] = cmd
    
    def _process_command(self, command: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a command with the given data.
        
        Args:
            command: The command name
            data: Command arguments and context
            
        Returns:
            Optional[Dict]: Command result or None if command not found
        """
        handler = self._command_handlers.get(command.lower())
        if not handler:
            return None
            
        try:
            # Set command context
            handler.context = {
                'user': self.user,
                'user_id': self.user_id,
                'mode': self.mode,
                'handler': self
            }
            
            # Execute the command
            return handler.execute(data)
        except Exception as e:
            logging.error(f"Error executing command {command}: {e}", exc_info=True)
            return {
                'error': 'command_error',
                'message': f'Error executing command: {str(e)}'
            }
    
    def _send_message(self, message: Union[Dict, Message]) -> None:
        """Send a message to the client.
        
        Args:
            message: Message to send (dict or Message object)
        """
        if isinstance(message, Message):
            message = message.to_dict()
            
        try:
            # Ensure the message has the required fields
            if 'type' not in message:
                message['type'] = 'message'
                
            # Send the message using _send_data which handles length prefixing
            self._send_data(message)
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            raise
    
    def _process_input(self, data: Dict[str, Any]) -> None:
        """Process input from the client.
        
        Args:
            data: Dictionary containing command data
        """
        try:
            # Get the command and arguments
            command = data.pop('command', '').lower()
            if not command:
                self._send_message({'error': 'no_command', 'message': 'No command specified'})
                return
            
            # Process the command
            result = self._process_command(command, data)
            
            # Send the response
            if result is not None:
                self._send_message(result)
            
        except Exception as e:
            logging.error(f"Error processing input: {e}", exc_info=True)
            self._send_message({
                'error': 'processing_error',
                'message': f'Error processing command: {str(e)}'
            })
            
    def _process_standard_message(self, message: Dict[str, Any]) -> None:
        """Process a standard message from the client.
        
        Args:
            message: Dictionary containing the message data
        """
        try:
            mode = message.get('mode')
            
            if not self.initialized:
                logging.debug(f"Processing initial message, mode={mode}")
                
                if mode == Mode.init:
                    response = self._process_init(message)
                    if response:
                        self._send_message(response)
                    else:
                        logging.warning(f"Invalid INIT from {self.client_address[0]}")
                        self._shutdown_event.set()
                elif mode == Mode.login:
                    response = self._process_login(message)
                    if response:
                        self._send_message(response)
                    else:
                        logging.warning(f"Login failed for {self.client_address[0]}")
                        self._shutdown_event.set()
                else:
                    logging.warning(f"Invalid initial mode from {self.client_address[0]}: {mode}")
                    self._shutdown_event.set()
            else:
                # Process regular messages for authenticated users
                response = self.process_message(message)
                if response:
                    self._send_message(response)
                    
        except Exception as e:
            logging.error(f"Error processing standard message: {e}", exc_info=True)
            self._send_message({
                'error': 'processing_error',
                'message': f'Error processing message: {str(e)}'
            })
    
    def handle(self):
        """Handle a client connection."""
        client_address = self.client_address[0]
        logging.info(f"New connection from {client_address}")
        
        # Send welcome message
        self._send_message({
            'mode': 'init',
            'lines': [
                'Welcome to:',
                ''
                'Totally',
                ' Awesome',
                '  Dungeon',
                '   Adventure',
                ''
            ]
        })
        
        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    # Check for incoming data with timeout
                    data = self._receive_data(timeout=30.0)  # 30 second timeout
                    
                    # If we get None, it means the connection was closed or timed out
                    if data is None:
                        logger.debug("No data received, connection may be closed")
                        break
                    
                    # Process the received data
                    try:
                        if not isinstance(data, dict):
                            logger.error(f"Expected dict but got {type(data).__name__}: {data}")
                            break
                            
                        # Handle different message types
                        if 'command' in data:
                            # Process as a command
                            self._process_input(data)
                        else:
                            # Process as a standard message
                            self._process_standard_message(data)
                            
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        try:
                            self._send_message({
                                'error': 'processing_error',
                                'message': f'Error processing message: {str(e)}'
                            })
                        except Exception as send_error:
                            logger.error(f"Failed to send error message: {send_error}")
                            break  # If we can't send, the connection is likely dead
                    
                    # Process any queued async messages if still connected
                    if not self._shutdown_event.is_set():
                        try:
                            self._process_queued_messages()
                        except Exception as e:
                            logger.error(f"Error processing queued messages: {e}")
                            break
                    
                except (ConnectionResetError, BrokenPipeError) as e:
                    logger.info(f"Client {client_address} disconnected: {e}")
                    break
                except socket.timeout:
                    # Expected when no data is available within timeout
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error handling client {client_address}: {e}", exc_info=True)
                    break
                        
                    logging.debug(f"Processing message from {client_address}: {data}")
                    
                    if not self.initialized:
                        mode = data.get('mode')
                        logging.debug(f"Processing initial message, mode={mode}")
                        
                        if mode == Mode.init:
                            response = self._process_init(data)
                            if response:
                                self._send_data(response)
                            else:
                                logging.warning(f"Invalid INIT from {client_address}")
                                break
                        elif mode == Mode.login:
                            response = self._process_login(data)
                            if response:
                                self._send_data(response)
                            else:
                                logging.warning(f"Login failed for {client_address}")
                                break
                        else:
                            logging.warning(f"Invalid initial mode from {client_address}: {mode}")
                            self._send_data(Message(
                                error=Error.server1,
                                error_line='invalid initial mode',
                                lines=["Invalid initial mode"]
                            ))
                            break
                    else:
                        mode = data.get('mode')
                        if mode == Mode.bye:
                            # Handle client disconnection
                            logging.info(f"Client {getattr(self, 'user_id', 'unknown')} is disconnecting")
                            if hasattr(self, 'user_id') and self.user_id in connected_users:
                                connected_users.remove(self.user_id)
                            return False  # Signal to close the connection
                        elif mode == Mode.app and self.user_id and self.user_id in connected_users:
                            response = self.process_message(data)
                            if response:
                                self._send_data(response)
                        else:
                            logging.error('Invalid mode or not logged in: %s' % mode)
                            self._send_data(Message(
                                lines=["Invalid mode or not logged in"],
                                mode=Mode.bye  # Tell client to disconnect
                            ))
                            return False  # Close connection on invalid mode
                    
                    # Process any queued async messages
                    self._process_queued_messages()
                    
                except TimeoutError:
                    # Expected when no data is available
                    continue
                except (ConnectionResetError, BrokenPipeError) as e:
                    logging.error('connection error: %s' % e)
                    break
                except Exception as e:
                    logging.error('unhandled exception: %s' % e)
                    traceback.print_exc()
                    break

        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources when the connection is closed."""
        self._shutdown_event.set()
        self._running = False
        
        # Close the socket to unblock any pending recv() calls
        if hasattr(self, 'request') and self.request:
            try:
                # Shutdown the socket to unblock any pending recv() calls
                self.request.shutdown(socket.SHUT_RDWR)
            except (OSError, AttributeError):
                pass  # Socket already closed
            try:
                self.request.close()
            except (OSError, AttributeError):
                pass  # Socket already closed
        
        # Clean up user session
        if self.user_id:
            if self.user_id in connected_users:
                with server_lock:
                    connected_users.remove(self.user_id)
            client_manager.remove_client(self.user_id)
            logging.info('User logged out: %s' % self.user_id)
            
        # Unregister from server
        if hasattr(self, 'server') and hasattr(self.server, '_unregister_handler'):
            self.server._unregister_handler(self)
    
    def _process_queued_messages(self):
        """Process any messages in the async message queue."""
        with self._message_lock:
            if self._message_queue:
                for message in self._message_queue:
                    self._send_data(message)
                self._message_queue.clear()
    
    def send_async_message(self, message: Dict[str, Any]) -> None:
        """Queue an asynchronous message to be sent to the client.
        
        Args:
            message: The message to send (should be a dictionary that can be serialized to JSON)
        """
        with self._message_lock:
            self._message_queue.append(message)
    
    def broadcast(self, message: Dict[str, Any], exclude_user_ids: Set[str] = None) -> None:
        """Broadcast a message to all connected clients except those in exclude_user_ids."""
        client_manager.broadcast(message, exclude_user_ids or set())

    def _receive_data(self, timeout=30.0):  # Increased to 30 seconds to match client
        """Receive data with optional timeout using length-prefixed messages.
        
        Args:
            timeout: Timeout in seconds, or None for blocking. Defaults to 30s.
        Returns:
            dict or None: The parsed JSON message, or None if the connection was closed or an error occurred.
        """
        if self._shutdown_event.is_set():
            logger.debug("Shutdown requested, stopping receive")
            return None
            
        old_timeout = None
        try:
            old_timeout = self.request.gettimeout()
            self.request.settimeout(timeout)
            
            # Read message length (4 bytes, big-endian)
            length_bytes = b''
            try:
                # Log the start of receiving a new message
                logger.debug("Waiting to receive message length (4 bytes)...")
                
                # Try to read exactly 4 bytes for the length
                while len(length_bytes) < 4:
                    chunk = self.request.recv(4 - len(length_bytes))
                    if not chunk:
                        logger.debug("Connection closed by peer while reading length")
                        return None
                    logger.debug(f"Received {len(chunk)} bytes of length prefix: {chunk.hex()}")
                    length_bytes += chunk
                    
                # Verify we got exactly 4 bytes
                if len(length_bytes) != 4:
                    logger.warning(f"Invalid length prefix: got {len(length_bytes)} bytes, expected 4")
                    logger.warning(f"Received bytes: {length_bytes.hex()}")
                    return None
                    
                # Parse message length
                length = int.from_bytes(length_bytes, 'big', signed=False)
                logger.debug(f"Message length prefix: {length_bytes.hex()} = {length} bytes")
                
                # Sanity check for message length (10KB max)
                if length <= 0 or length > 10 * 1024:
                    logger.warning(f"Invalid message length: {length} bytes")
                    logger.debug(f"Raw length bytes: {length_bytes.hex()}")
                    # Try to read and discard the message to resync
                    try:
                        while length > 0:
                            chunk = self.request.recv(min(4096, length))
                            if not chunk:
                                break
                            length -= len(chunk)
                    except:
                        pass
                    return None
                
                # Read message data with a reasonable chunk size
                json_bytes = bytearray()
                remaining = length
                total_read = 0
                
                logger.debug(f"Reading {remaining} bytes of message data...")
                
                while remaining > 0:
                    try:
                        chunk_size = min(4096, remaining)
                        chunk = self.request.recv(chunk_size)
                        if not chunk:
                            logger.debug("Connection closed by peer while reading message data")
                            return None
                            
                        json_bytes.extend(chunk)
                        remaining -= len(chunk)
                        total_read += len(chunk)
                        logger.debug(f"Read {len(chunk)} bytes of message data ({total_read}/{length} total)")
                        
                        # Log the first few chunks to help with debugging
                        if total_read == len(chunk):  # First chunk
                            logger.debug(f"First {min(32, len(chunk))} bytes of data: {chunk[:32].hex(' ')}")
                        
                    except TimeoutError:
                        logger.error(f"Timeout while reading message data (read {total_read}/{length} bytes)")
                        return None
                    except ConnectionResetError:
                        logger.error(f"Connection reset by peer while reading message data (read {total_read}/{length} bytes)")
                        return None
                        if not chunk:
                            logger.debug("Connection closed by peer while reading data")
                            return None
                        json_bytes.extend(chunk)
                        remaining -= len(chunk)
                    except socket.timeout:
                        logger.debug("Timeout while reading message data")
                        return None
                    except (ConnectionResetError, BrokenPipeError) as e:
                        logger.debug(f"Connection lost while reading data: {e}")
                        return None
                
                # Parse JSON data with extra validation
                try:
                    json_str = json_bytes.decode('utf-8')
                    # Basic validation of JSON structure
                    if not json_str.strip():
                        logger.warning("Received empty JSON message")
                        return None
                        
                    json_data = json.loads(json_str)
                    if not isinstance(json_data, dict):
                        logger.warning(f"Expected JSON object, got {type(json_data).__name__}")
                        return None
                        
                    logger.debug(f"Received valid message: {json_data}")
                    return json_data
                    
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to parse JSON: {e}")
                    logger.debug(f"Raw JSON bytes: {json_bytes[:100]}...")
                    return None
                    
            except Exception as e:
                logger.error(f"Error receiving message: {e}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error in _receive_data: {e}", exc_info=True)
            return None
            
        finally:
            # Always restore original timeout
            if old_timeout is not None:
                try:
                    self.request.settimeout(old_timeout)
                except Exception as e:
                    logger.warning(f"Error restoring socket timeout: {e}")
                    # Continue with cleanup even if this fails

    def _send_data(self, data):
        """Send data to the client using length-prefixed JSON format."""
        try:
            logger.debug(f"Sending data: {data}")
            # Convert data to JSON and encode as bytes
            json_data = json.dumps(data).encode('utf-8')
            logger.debug(f"JSON data: {json_data}")
            
            # Create a length prefix (4-byte big-endian)
            length = len(json_data)
            length_prefix = length.to_bytes(4, byteorder='big')
            logger.debug(f"Sending {length} bytes with prefix: {length_prefix}")
            
            # Send length prefix + JSON data
            self.request.sendall(length_prefix + json_data)
            logger.debug("Data sent successfully")
            logger.debug(f"Sent data: {data}")
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            raise

    def _process_init(self, data):
        logging.debug(f"received data: {data}")
        logging.debug(f"server_id={server_id}, server_key={server_key}")
        
        # Get client credentials from the data
        client_id = data.get('server_id')
        client_key = data.get('server_key')
        client_protocol = data.get('protocol_version')
        
        logging.debug(f"client_id={client_id}, client_key={client_key}, client_protocol={client_protocol}")
        
        if not client_id:
            logging.error("No client ID provided in initialization data")
            return None
            
        if not client_key:
            logging.error("No client key provided in initialization data")
            return None
            
        if client_id != server_id:
            logging.warning(f"client ID mismatch. Expected {server_id}, got {client_id}")
            return None
            
        if client_key != server_key:
            logging.warning(f"client key mismatch. Expected {server_key}, got {client_key}")
            return None
            
        if client_protocol != server_protocol:
            logging.warning(f"protocol version mismatch. Expected {server_protocol}, got {client_protocol}")
            return None
            
        logging.debug("client authenticated successfully")
        self.initialized = True
        
        try:
            banner = self.init_success_lines()
            response = {
                'mode': 'login',
                'lines': banner
            }
            logging.debug(f"returning response: {response}")
            return response
        except Exception as e:
            logging.error(f"error generating success response: {e}", exc_info=True)
            return None

    def authenticate(self, user_id, password):
        """Basic authentication method for testing.
        
        In a real implementation, this would verify credentials against a database.
        For testing, we accept any non-empty user_id and password.
        """
        return bool(user_id and password)
        
    def _process_login(self, data):
        from server.config import config
        
        user_id = data.get(K.user_id, '').lower()
        password = data.get(K.password, '')
        invite_code = data.get(K.invite)

        # Check if user exists
        user = nc.User.load(user_id)
        
        if user is None:
            # New user - check if invites are required
            if config.require_invites:
                # Invites are required - verify the invite code
                if not invite_code:
                    self.login_history.no_user(user_id, save=True)
                    return self.error_login_failed("Invite code required for registration")
                    
                invite = nc.Invite.load(user_id)
                if not invite or invite.code != invite_code:
                    self.login_history.no_user(user_id, save=True)
                    return self.error_login_failed("Invalid or expired invite code")
                
                # Create new user
                user = nc.User(id=user_id)
                user.hash_password(password)
                user.save()
                
                # Delete used invite
                invite.delete()
            else:
                # No invite required - create new user directly
                user = nc.User(id=user_id)
                user.hash_password(password)
                user.save()
        else:
            # Existing user - verify password
            if not user.match_password(password):
                self.login_history.bad_password(user_id, save=True)
                return self.error_login_failed("Invalid username or password")
        
        # Update login history
        self.login_history.succeed_user(user_id, save=True)
        
        # Set user and mode
        self.user = user
        self.user_id = user_id
        self.mode = Mode.app
        
        return self.process_login_success(user_id)

    def prompt_request(self, lines: list[str], prompt: str, choices: Optional[dict[str, str]] = None):
        """
        Send a prompt to the client and wait for a response.

        :param lines: list of lines to display
        :param prompt: prompt to display
        :param choices: optional dictionary of choices to display
        :return: response from client
        """
        self._send_data(Message(lines=lines, prompt=prompt, choices=choices))
        return self._receive_data()

    # base implementation for when testing net_client/net_server
    # NOTE: must be overridden by actual app (see client/server)


    def error_ban(self):
        """Return a Message indicating the user is banned."""
        return Message(
            error=Error.login1,
            error_line='Too many failed login attempts. You are temporarily banned.',
            lines=['Too many failed login attempts. Please try again later.']
        )
        
    def error_login_failed(self, message="Login failed. Please check your credentials and try again."):
        """Return a Message indicating login failure.
        
        Args:
            message: Custom error message to display
        """
        return Message(
            lines=[message],
            mode=Mode.login,
            error="login_failed"
        )
        
    def init_success_lines(self):
        """OVERRIDE in subclass
        First server message lines that user sees.  Should tell them to log in.
        """
        return ['Generic Server.', 'Please log in.']


    def login_fail_lines(self):
        """OVERRIDE in subclass
        Login failure message lines back to user.
        """
        return ['please try again.']


    def process_login_success(self, user_id):
        """OVERRIDE in subclass
        First method called on successful login.
        Should do any user initialization and then return Message.
        """
        return Message(lines=[f"Welcome, {user_id}."])


    def process_message(self, data):
        """OVERRIDE in subclass
        Called on all subsequent Cmd messages from client.
        Should do any processing and return Message.
        """
        if 'text' in data:
            cmd = data['text'].split(' ')
            if cmd[0] in ['bye', 'logout']:
                return Message(lines=["Goodbye."], mode=Mode.bye)
            else:
                return Message(lines=["Unknown command."])


def start(host, port, _id, key, protocol, handler_class):
    global server_id, server_key, server_protocol, server_instance
    server_id = _id
    server_key = key
    server_protocol = protocol
    
    class ServerWithShutdown(Server):
        def __init__(self, *args, **kwargs):
            self.handler_class = kwargs.pop('handler_class', None)
            super().__init__(*args, **kwargs)
            self._is_shut_down = threading.Event()
            self._shutdown_request = False
            self._client_handlers = set()
            self._client_handlers_lock = threading.Lock()
            
        def finish_request(self, request, client_address):
            """Finish one request by instantiating RequestHandlerClass."""
            if self.handler_class:
                self.RequestHandlerClass = self.handler_class
            return super().finish_request(request, client_address)
            
        def _register_handler(self, handler):
            """Register a client handler for cleanup on shutdown."""
            with self._client_handlers_lock:
                self._client_handlers.add(handler)
                
        def _unregister_handler(self, handler):
            """Unregister a client handler."""
            with self._client_handlers_lock:
                if handler in self._client_handlers:
                    self._client_handlers.remove(handler)
            
        def serve_forever(self, poll_interval=0.5):
            """Handle one request at a time until shutdown."""
            self._is_shut_down.clear()
            try:
                while not self._shutdown_request:
                    try:
                        r, w, e = select.select([self], [], [], poll_interval)
                        if r:
                            self._handle_request_noblock()
                    except OSError as e:
                        if not self._shutdown_request:
                            logging.error(f"Error in serve_forever: {e}")
                        break
            finally:
                self._shutdown_request = False
                self._is_shut_down.set()
                
        def shutdown(self):
            """Signal the server to shut down and close all client connections."""
            if self._shutdown_request:
                return
                
            logging.info("Initiating server shutdown...")
            self._shutdown_request = True
            
            # Close the server socket to stop accepting new connections
            if hasattr(self, 'socket') and self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    logging.error(f"Error closing server socket: {e}")
            
            # Signal all client handlers to shut down
            with self._client_handlers_lock:
                handlers = list(self._client_handlers)
                
            for handler in handlers:
                try:
                    if hasattr(handler, '_running'):
                        handler._running = False
                    if hasattr(handler, 'request') and handler.request:
                        try:
                            handler.request.shutdown(socket.SHUT_RDWR)
                            handler.request.close()
                        except Exception as e:
                            logging.debug(f"Error closing client socket: {e}")
                except Exception as e:
                    logging.error(f"Error during client handler cleanup: {e}")
            
            # Wait for shutdown to complete
            self._is_shut_down.wait()
            logging.info("Server shutdown complete")
            
        def server_close(self):
            """Clean up the server."""
            super().server_close()
    
    try:
        # Create a custom handler class that has access to the server instance
        class ServerAwareHandler(handler_class):
            def __init__(self, *args, **kwargs):
                # The server instance is passed as the third argument to __init__
                # by the socketserver framework
                request, client_address, server = args[0], args[1], args[2]
                
                # Store the server instance as server_instance before calling parent's __init__
                self.server_instance = server
                
                # Call the parent's __init__ with all original arguments
                super().__init__(*args, **kwargs)
                
                # Log the initialization
                logger.debug(f"Initialized {self.__class__.__name__} for {client_address} with server {server}")
        
        # Create the server with our custom handler class
        server = ServerWithShutdown(
            (host, port), 
            ServerAwareHandler,
            handler_class=handler_class  # Pass the original handler class for reference
        )
        
        server_instance = server
        logging.info("Server.start: server running (%s:%s)" % (host, port))
        
        # Start server in a non-daemon thread to allow proper cleanup
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = False  # Changed to False for proper cleanup
        server_thread.start()
        
        try:
            # Main console loop
            while True:
                try:
                    text = input("Console command (q to quit): ").strip().lower()
                    if text in ['q', 'quit', 'exit']:
                        logging.info("Shutting down server...")
                        break
                except (KeyboardInterrupt, EOFError):
                    logging.info("\nShutting down server...")
                    break
                        
        except Exception as e:
            logging.error(f"Error in server console: {e}")
            raise
            
        finally:
            # Shutdown sequence
            logging.info("Waiting for all connections to close...")
            server.shutdown()
            server.server_close()
            
            # Wait for the server thread to finish
            if server_thread.is_alive():
                server_thread.join(timeout=5.0)
                if server_thread.is_alive():
                    logging.warning("Server thread did not shut down gracefully")
                
                # Force close any remaining client connections
                for thread in threading.enumerate():
                    if thread is not threading.current_thread() and thread is not server_thread:
                        thread.join(timeout=1.0)
                
                logging.info('Server shutdown complete.')
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logging.error("Server.start: Port %s is already in use. Please stop the existing server or use a different port." % port)
            print(f"Error: Port {port} is already in use. Please stop the existing server or use a different port.")
            return False
        else:
            logging.error("Server.start: Failed to start server: %s" % e)
            raise

if __name__ == '__main__':
    """a test of the stub net server"""
    from server import PlayerHandler
    host = 'localhost'
    start(host, nc.Test.server_port, nc.Test.id, nc.Test.key, nc.Test.protocol,
          PlayerHandler)
