#!/bin/env python3
import asyncio
import enum
import logging
from pathlib import Path
import select
import socket
import json
import threading

from net_client import Client
from commands.command_processor import create_command_processor
# Avoid importing Init/MessageType/Message at module-import time to prevent circular imports
# Use net_common as nc (imported later) and define a small local Init dataclass for handshake
from dataclasses import dataclass

import net_common as nc
Mode = nc.Mode
import socketserver
from dataclasses import field


@dataclass
class Init:
    server_id: str = "test_server"
    server_key: str = "test_key"
    protocol_version: int = 1
    translation: object = None
    type: str = 'init'


connected_users = set()
server_lock = threading.Lock()


class Error(str, enum.Enum):
    server1 = 'server1'
    server2 = 'server2'
    # missing user ID?:
    user_id = 'user_id'
    login1 = 'login1'
    login2 = 'login2'
    # multiple connections:
    # can't have multiple connections with same user id
    multiple = 'multiple'


# Use net_common.Message as the authoritative Message type
Message = nc.Message


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    class Server:
        """
        Manages the server state and client connections.
        From simple_server.py
        1. self.handle_new_connection: Accepts new client connections.
        2. self._perform_handshake: Performs handshake and authentication.
        3. self.handle_<xxx>_mode: Manages client modes (login, app).
        4. self.process_message: Processes messages from clients based on their mode.
        5. self.broadcast Broadcasts messages to all connected clients.
        6. self._disconnect: Handles client disconnections and cleanup.
        7. Uses asyncio for asynchronous I/O operations.
        8. Uses JSON (wrapped in a Message class) for message serialization.
        """
        # for use in strings:
        quotation_mark = '"'
        apostrophe = "'"

        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.server = None
            self.clients = {}  # A dictionary to store connected clients by address

            # Create the server-wide Init object ONCE
            self.server_init_object = Init(
                server_id="test_server",
                server_key="test_key",
                protocol_version=1,
                translation=Translation.ANSI  # Default translation
            )
            logging.info(f"Server configured with ID: {self.server_init_object.server_id}")

            # Load map and game data (level, objects, monsters, weapons, rations)
            try:
                script_dir = Path(__file__).parent
                self.game_map = Map()
                for lvl in range(1, 8):
                    level_file = script_dir / f"level_{lvl}.json"
                    if level_file.exists():
                        self.game_map.read_map(str(level_file), level=lvl)
                        logging.info(f"Loaded level {lvl} map with {len(self.game_map.levels[lvl])} rooms")
            except Exception:
                logging.exception("Failed to load map or game data; room descriptions may be limited")

        async def send_message(self, writer, obj):
            writer.write(nc.to_jsonb(obj) + b'\n')
            await writer.drain()

        async def receive_message(self, reader):
            data = await reader.readline()
            if not data:
                return None
            return nc.from_jsonb(data)

        async def handle_connection(self, reader, writer):
            """
            This method is the primary callback for each new client connection.
            It handles the entire lifecycle of a client.
            """
            addr = writer.get_extra_info('peername')
            logging.info(f"New connection from {addr}.")

            client = None
            try:
                # Perform the handshake
                client = await self._perform_handshake(reader, writer, addr)
                if not client:
                    # Handshake failed, connection is already closed.
                    return

                # Set initial mode to login
                client.mode = Mode.login

                # Store the authenticated client
                self.clients[addr] = client
                logging.info(f"Client {addr} handshake successful. Entering main loop.")

                await self._handle_login(reader, writer, addr, client)

                # Enter the main message processing loop for this client
                while True:
                    data = await self.receive_message(reader)
                    if not data:
                        logging.info(f"Connection closed by client {addr}.")
                        break

                    try:
                        in_message = Message(**data)
                    except Exception as e:
                        logging.error(f"Could not decode message from {addr}: {e}")
                        continue

                    if in_message.mode == Mode.bye:
                        logging.info(f"Client {addr} sent 'bye'. Closing connection.")
                        # Delegate persistence to the centralized helper which prefers quit()
                        try:
                            await self._save_client_state(client)
                        except Exception:
                            logging.exception(f"Failed to persist state for client {addr} on bye")
                        break

                    # Dispatch by mode
                    if getattr(client, 'mode', Mode.login) == Mode.login:
                        await self.handle_login_mode(client, in_message, writer)
                        # If the client was promoted to app mode during login handling, ensure a CommandProcessor is attached
                        if getattr(client, 'mode', None) == Mode.app and not getattr(client, 'command_processor', None):
                            try:
                                client.command_processor = create_command_processor(client)
                            except Exception:
                                logging.exception("Failed to create command processor for client")
                    else:
                        await self.handle_app_mode(client, in_message, writer, addr)

            except asyncio.CancelledError:
                logging.warning(f"Connection task for {addr} was cancelled.")
            except Exception as e:
                logging.error(f"An unexpected error occurred with client {addr}: {e}")
            finally:
                if addr in self.clients:
                    del self.clients[addr]
                logging.info(f"Closing connection for {addr}. Total clients: {len(self.clients)}")
                writer.close()
                await writer.wait_closed()

        async def _perform_handshake(self, reader, writer, addr) -> Client | None:
            """
            Handles the initial handshake process with a new client.
            Returns a Client object on success, or None on failure.
            Only server_id and server_key are strictly checked; other fields are accepted as provided by the client.
            """
            try:
                # Send the server's Init object to the client
                await self.send_message(writer, self.server_init_object)

                # Wait for the client's Init response
                client_init_data = await self.receive_message(reader)
                if not client_init_data:
                    logging.error(f"Handshake failed: Client {addr} disconnected before sending Init.")
                    return None

                client_init = Init(**client_init_data)

                # Strictly check server_id and server_key
                if client_init.server_id != self.server_init_object.server_id:
                    raise ValueError("Server ID mismatch")
                if client_init.server_key != self.server_init_object.server_key:
                    raise ValueError("Server key mismatch")
                # protocol_version is not strictly checked, but you can add a warning if you want
                if client_init.protocol_version != self.server_init_object.protocol_version:
                    logging.warning(
                        f"Protocol version mismatch: client {client_init.protocol_version}, server {self.server_init_object.protocol_version}")

                # Accept and store other fields (e.g., translation, screen size)
                client = Client()
                client.addr = addr
                client.translation = client_init.translation
                client.writer = writer
                client.server = self
                # default starting room
                client.room = 1
                logging.info(f"Client {addr} translation set to {client.translation}")

                # Send success message and switch client to login mode
                success_msg = Message(lines=["Handshake successful. Welcome!"], mode=Mode.login)
                await self.send_message(writer, success_msg)

                return client

            except Exception as e:
                logging.error(f"Handshake failed for {addr}: {e}")
                failure_msg = Message(lines=[f"Handshake failed: {str(e)}"], mode=Mode.bye)
                await self.send_message(writer, failure_msg)
                return None

        async def start(self):
            """Starts the asyncio server."""
            self.server = await asyncio.start_server(
                self.handle_connection, self.host, self.port)

            addr = self.server.sockets[0].getsockname()
            logging.info(f'Server listening on {addr}')

            async with self.server:
                await self.server.serve_forever()

        async def _handle_login(self, reader, writer, addr, client):
            login_text = [
                "Welcome to:",
                "",
                "Totally",
                " Awesome",
                "  Dungeon",
                "   Adventure",
                "",
                "To connect to an existing character, type 'connect <username> <password>'.",
                "To look around as a guest, type 'guest'.",
                "To create a new character, type 'new'."
            ]
            login_message = Message(lines=login_text, mode=Mode.login, prompt="login> ", type=nc.MessageType.REGULAR)
            await self.send_message(writer, login_message)

        async def handle_login_command(self, writer, username=None):
            # This is a mock login handler. In a real system, you'd check credentials here.
            await asyncio.sleep(1)  # Simulate some processing delay
            if not username:
                username = "Guest"

            login_lines = [
                f"Login successful! Welcome, {username}.",
                "Here are some commands you can use:",
                "To test message types, type 'testmsg'.",
                f"To talk to everyone, type 'say <message>' or '{self.quotation_mark}<message>",
                # "To connect to an existing character, type 'connect <username> <password>'",
                # "To look around as a guest, type 'guest'.",
                # "To create a new character, type 'new <username>'."
            ]
            login_message = Message(lines=login_lines, mode=Mode.login, type=MessageType.REGULAR, prompt="main> ")
            await self.send_message(writer, login_message)

        async def handle_login_mode(self, client, in_message, writer):
            handled = False
            if in_message.lines and isinstance(in_message.lines, list):
                for line in in_message.lines:
                    cmd = line.strip().lower()
                    args = line.strip().split()
                    if cmd.startswith('connect') and len(args) >= 2:
                        username = args[1]
                        password = args[2] if len(args) >= 3 else ''
                        usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                        if username in usernames:
                            await self.send_message(writer, Message(lines=[f"Username '{username}' is already taken."],
                                                                    type=MessageType.SYSTEM, mode=Mode.login,
                                                                    prompt="login> "))
                            handled = True
                            break
                        client.username = username
                        client.mode = Mode.app  # Set mode before sending login command
                        await self.handle_login_command(writer, username=username)
                        handled = True
                        break
                    elif cmd == 'guest':
                        base = "Guest"
                        n = 1
                        usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                        while f"{base}{n}" in usernames:
                            n += 1
                        client.username = f"{base}{n}"
                        client.mode = Mode.app  # Set mode before sending login command
                        await self.handle_login_command(writer, username=client.username)
                        handled = True
                        break
                    elif cmd.startswith('new') and len(args) >= 2:
                        username = args[1]
                        usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                        if username in usernames:
                            await self.send_message(writer, Message(lines=[f"Username '{username}' is already taken."],
                                                                    type=MessageType.SYSTEM, mode=Mode.login,
                                                                    prompt="login> "))
                            handled = True
                            break
                        client.username = username
                        client.mode = Mode.app  # Set mode before sending login command
                        await self.handle_login_command(writer, username=username)
                        handled = True
                        break
            if not handled:
                # Default: echo response in login mode
                response = Message(lines=[f"[LOGIN] Echo: {' '.join(in_message.lines)}"], type=MessageType.REGULAR,
                                   mode=Mode.login, prompt="login> ")
                await self.send_message(writer, response)

        async def handle_app_mode(self, client, in_message, writer, addr):
            # Ensure a command processor exists for this client
            if not getattr(client, 'command_processor', None):
                try:
                    client.command_processor = create_command_processor(client)
                except Exception:
                    logging.exception("Failed to create command processor for client in app mode")

            proc = getattr(client, 'command_processor', None)
            if in_message.lines and isinstance(in_message.lines, list):
                for line in in_message.lines:
                    text = (line or '').strip()
                    if not text:
                        # Ignore empty input but still send prompt
                        await self.send_message(writer, Message(lines=[], mode=Mode.app, prompt="main> "))
                        continue

                    # Process the input line via CommandProcessor
                    try:
                        if proc is None:
                            # Fallback echo if no processor
                            result = None
                        else:
                            result = await proc.process_input(text)
                    except Exception:
                        logging.exception("Command processing raised an exception")
                        result = None

                    if result is None:
                        # Could not process; echo back
                        await self.send_message(writer, Message(lines=[f"[APP] Echo: {text}"], mode=Mode.app, prompt="main> "))
                        continue

                    # Normalize CommandResult -> Message
                    lines_out = []
                    try:
                        # Prefer explicit lines
                        if getattr(result, 'lines', None):
                            lines_out = list(result.lines)
                        elif getattr(result, 'message', None):
                            msg = result.message
                            if isinstance(msg, list):
                                lines_out = msg
                            else:
                                lines_out = [str(msg)]
                    except Exception:
                        logging.exception("Failed to normalize CommandResult to lines")
                        lines_out = [str(getattr(result, 'message', ''))]

                    # Build response Message
                    msg_obj = Message(lines=lines_out, mode=Mode.app, prompt="main> ")
                    # If command signaled disconnect via context, or processor moved client.mode, honor it
                    try:
                        await self.send_message(writer, msg_obj)
                    except Exception:
                        logging.exception("Failed to send command response to client")

        async def _save_client_state(self, client):
            """Persist minimal client state to disk under ./player_data/<username>.json."""
            try:
                def _sync_save():
                    try:
                        base_dir = Path(__file__).parent / "player_data"
                        base_dir.mkdir(parents=True, exist_ok=True)
        
                        username = getattr(client, "username", None)
                        if not username:
                            addr = getattr(client, "addr", None)
                            username = f"guest_{addr[0]}_{addr[1]}" if isinstance(addr, (list, tuple)) and len(addr) >= 2 else "guest"
        
                        # sanitize filename
                        safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(username))
                        filename = base_dir / f"{safe_name}.json"
        
                        data = {}
                        for k, v in getattr(client, "__dict__", {}).items():
                            # Skip non-serializable / runtime-only attributes
                            if k in ("writer", "server", "command_processor"):
                                continue
                            try:
                                # attempt to JSON-serialize directly
                                json.dumps(v)
                                data[k] = v
                            except TypeError:
                                # fallback to string representation
                                data[k] = str(v)
        
                        with filename.open("w", encoding="utf-8") as fh:
                            json.dump(data, fh, indent=2, ensure_ascii=False)
        
                        logging.info(f"Saved state for {username} -> {filename}")
                    except Exception:
                        logging.exception("Error during synchronous client state save")
        
                await asyncio.to_thread(_sync_save)
            except Exception:
                logging.exception("Failed to save client state")
                return False
            return True

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
        return ['Please try again.']


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
        return None


async def handle_new_connection(self, reader, writer):
        pass


def start(host, port, _id, key, protocol, handler_class):
    global server_id, server_key, server_protocol, server_instance
    server_id = _id
    server_key = key
    server_protocol = protocol

    # Prefer the asyncio reader/writer-based Server implementation (inner Server.Server)
    # and run it on a dedicated event loop in a background thread. This modernizes
    # the server to use the newer async `handle_connection(reader, writer)` flow.
    try:
        # Instantiate the asyncio-style server class defined inside this module
        async_server = Server.Server(host, port)
        server_instance = async_server

        # Create and run an event loop dedicated to the server in a background thread
        loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_server.start())
            except Exception:
                logging.exception("Async server loop terminated with an error")

        server_thread = threading.Thread(target=_run_loop, name="net_server_async", daemon=False)
        server_thread.start()

        logging.info("Async server.start launched (%s:%s)" % (host, port))
        return server_instance

    except Exception:
        logging.exception("Failed to start async server; falling back to socketserver start() not implemented")
