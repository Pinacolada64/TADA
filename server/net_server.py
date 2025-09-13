#!/bin/env python3
import logging
from pathlib import Path
import select
import socket
import sys
import os
import traceback
import threading
import socketserver
import json
import time
from dataclasses import dataclass, field
from typing import ClassVar, Optional, Dict, Any, Set
import enum

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
    user_id = 'user_id'
    login1 = 'login1'
    login2 = 'login2'
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
    def __init__(self, *args, **kwargs):
        self.user = None
        self.user_id = None
        self.mode = Mode.app
        self.buffer = b''
        self.login_history = LoginHistory()
        self.initialized = False
        self._message_queue = []
        self._message_lock = threading.Lock()
        self._running = True
        self._shutdown_event = threading.Event()
        super().__init__(*args, **kwargs)
        
        # Register with server for proper cleanup on shutdown
        if hasattr(self.server, '_register_handler'):
            self.server._register_handler(self)

    def handle(self):
        client_address = self.client_address[0]
        logging.info(f"New connection from {client_address}")
        
        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    # Check for incoming data with timeout
                    data = self._receive_data(timeout=30.0)  # Increased to 30 seconds
                    
                    if data is None:
                        # No data received within timeout, check if still running
                        continue
                        
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
                        if data.get('mode') == Mode.app and self.user_id and self.user_id in connected_users:
                            response = self.process_message(data)
                            if response:
                                self._send_data(response)
                            else:
                                logging.error('Invalid mode or not logged in: %s' % data.get('mode'))
                                self._send_data(Message(
                                    error=Error.server2,
                                    error_line='invalid mode or not logged in'
                                ))
                                break
                    
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
        """Receive data with optional timeout.
        
        Args:
            timeout: Timeout in seconds, or None for blocking. Defaults to 0.5s.
            
        Returns:
            dict: Parsed JSON data, or None if no data was received within the timeout.
            
        Raises:
            ConnectionError: If the connection was lost or an unrecoverable error occurred.
            TimeoutError: If no data is received within the specified timeout.
        """
        if self._shutdown_event.is_set():
            logging.debug("Shutdown requested, stopping receive")
            return None
            
        try:
            # Set socket timeout
            old_timeout = self.request.gettimeout()
            self.request.settimeout(timeout)
            
            # Check if we should still be running
            if self._shutdown_event.is_set():
                return None
                
            # Try to receive data
            data = nc.from_jsonb_socket(self.request)
            
            # Check if we should still be running after potentially long operation
            if self._shutdown_event.is_set():
                return None
                
            # Restore original timeout
            self.request.settimeout(old_timeout)
            
            if data:
                logging.debug(f"Received data: {data}")
                if 'mode' not in data:
                    logging.warning(f"Received data without 'mode' key: {data}")
                    return None
            return data
            
        except TimeoutError:
            # This is expected when no data is available within the timeout
            return None
            
        except (ConnectionResetError, BrokenPipeError) as e:
            logging.info(f"Connection closed by client: {e}")
            raise ConnectionError("Connection lost") from e
            
        except Exception as e:
            logging.error(f"Error receiving data: {e}", exc_info=True)
            raise ConnectionError("Error receiving data") from e

    def _send_data(self, data):
        self.request.sendall(nc.to_jsonb(data))

    def _process_init(self, data):
        logging.debug(f"_process_init: received data: {data}")
        client_id = data.get('id')
        logging.debug(f"_process_init: client_id={client_id}, server_id={server_id}")
        if client_id == server_id:
            client_key = data.get('key')
            logging.debug(f"_process_init: client_key={client_key}, server_key={server_key}")
            if client_key == server_key:
                logging.debug("_process_init: client authenticated successfully")
                self.initialized = True
                response = Message(lines=self.init_success_lines(), mode=Mode.login)
                logging.debug(f"_process_init: returning response: {response}")
                return response
            else:
                logging.warning(f"_process_init: invalid key from client: {client_key}")
                # TODO: record history in case want to ban
                return None  # poser, ignore them
        else:
            logging.warning(f"_process_init: invalid client_id: {client_id}")
            # TODO: record history in case want to ban
            return None  # poser, ignore them

    def authenticate(self, user_id, password):
        """Basic authentication method for testing.
        
        In a real implementation, this would verify credentials against a database.
        For testing, we accept any non-empty user_id and password.
        """
        return bool(user_id and password)
        
    def _process_login(self, data):
        user_id = data.get('user_id')
        if not user_id:
            self._send_data(Message(error=Error.user_id, error_line='missing user_id'))
            return

        if not self.login_history.is_allowed(user_id):
            return self.error_ban()
            
        # Check if user file exists in run/server/net directory
        user_file = Path('run' / 'server' / 'net' / f'login-{user_id}.json')
        if not user_file.exists():
            self.login_history.no_user(user_id, save=True)
            logging.warning(f"Login attempt with non-existent user: {user_id}")
            return Message(
                error=Error.login2,
                error_line='Invalid username or password',
                lines=['Invalid username or password. Please try again.']
            )

        if not self.authenticate(user_id, data.get('password', '')):
            banned = self.login_history.fail_password(user_id, save=True)
            if banned:
                logging.info(f"ban {self.sender}")
                return self.error_ban()
            else:
                return self.error_login_failed()
        
        self.user_id = user_id
        self.user = User(user_id)  # This would typically be a User object in a real implementation
        
        with server_lock:
            connected_users.add(user_id)
            
        # Register with client manager
        client_manager.add_client(user_id, self)
        
        self.login_history.succeed_user(user_id, save=True)
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
        
    def error_login_failed(self):
        """Return a Message indicating login failure."""
        return Message(
            error=Error.login2,
            error_line='Invalid username or password',
            lines=self.login_fail_lines()
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
