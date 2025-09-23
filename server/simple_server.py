import asyncio
import logging

# Assuming these are in your net_common and net_client files
from net_common import Message, MessageType, Mode, to_jsonb, from_jsonb
from net_client import Client
from tada_utilities import a_or_an

class Init:
    # server_id, server_key, protocol_version, type must all match between server + client.
    # character translation (e.g. 'utf-8', 'petscii', etc.) can be whatever the client wants.
    def __init__(self, server_id="test_server", server_key="test_key", protocol_version=1,
                 translation="utf-8", type='init'):
        self.server_id = server_id
        self.server_key = server_key
        self.protocol_version = protocol_version
        self.translation = translation
        self.type = 'init'


# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Server:
    """
    Manages the server state and client connections.
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
            translation='utf-8'  # Default translation
        )
        logging.info(f"Server configured with ID: {self.server_init_object.server_id}")

    async def send_message(self, writer, obj):
        writer.write(to_jsonb(obj) + b'\n')
        await writer.drain()

    async def receive_message(self, reader):
        data = await reader.readline()
        if not data:
            return None
        return from_jsonb(data)

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
                    break

                # Dispatch by mode
                if getattr(client, 'mode', Mode.login) == Mode.login:
                    await self.handle_login_mode(client, in_message, writer)
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
            # If you want to support screen size, add: client.screen_size = getattr(client_init, 'screen_size', None)
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
        login_message = Message(lines=login_text, mode=Mode.login, prompt="login> ", type=MessageType.regular)
        await self.send_message(writer, login_message)

    async def handle_login_command(self, writer, username=None):
        # This is a mock login handler. In a real system, you'd check credentials here.
        await asyncio.sleep(1)  # Simulate some processing delay
        if not username:
            username = "Guest"

        login_lines = [
            f"Login successful! Welcome, {username}.",
            "Here are the commands you can use:",
            "To test message types, type 'testmsg'.",
            f"To talk to everyone, type 'say <message>' or '{self.quotation_mark}<message>",
            "To connect to an existing character, type 'connect <username> <password>'",
            "To look around as a guest, type 'guest'.",
            "To create a new character, type 'new <username>'."
        ]
        login_message = Message(lines=login_lines, mode=Mode.login, type=MessageType.regular, prompt="main> ")
        await self.send_message(writer, login_message)

    async def handle_login_mode(self, client, in_message, writer):
        handled = False
        if in_message.lines and isinstance(in_message.lines, list):
            for line in in_message.lines:
                cmd = line.strip().lower()
                args = line.strip().split()
                if cmd.startswith('connect') and len(args) >= 2:
                    username = args[1]
                    # Optionally, check for password: args[2]
                    # Ensure username is unique
                    usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                    if username in usernames:
                        await self.send_message(writer, Message(lines=[f"Username '{username}' is already taken."],
                                                                type=MessageType.system, mode=Mode.login,
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
                                                                type=MessageType.system, mode=Mode.login, prompt="login> "))
                        handled = True
                        break
                    client.username = username
                    client.mode = Mode.app  # Set mode before sending login command
                    await self.handle_login_command(writer, username=username)
                    handled = True
                    break
        if not handled:
            # Default: echo response in login mode
            response = Message(lines=[f"[LOGIN] Echo: {' '.join(in_message.lines)}"], type=MessageType.regular, mode=Mode.login, prompt="login> ")
            await self.send_message(writer, response)

    async def handle_app_mode(self, client, in_message, writer, addr):
        handled = False
        if in_message.lines and isinstance(in_message.lines, list):
            for line in in_message.lines:
                cmd = ''
                args = line.strip().split()
                if len(args) > 0:
                    cmd = args[0].lower()

                # SAY command: broadcast to all clients
                if cmd == 'say' or cmd.startswith('"'):
                    if cmd == 'say':
                        say_msg = args[1:]
                    else:  # cmd starts with a quote
                        say_msg = [' '.join(args)[1:]]
                    if not say_msg or not say_msg[0]:
                        await self.send_message(writer, Message(lines=[f"Usage: say <message>, or {self.quotation_mark}<message>"],
                                                                type=MessageType.system,
                                                                mode=Mode.app, prompt="main> "))
                        handled = True
                        break
                    # Determine verb based on punctuation
                    last_word = say_msg[-1]
                    verb = "say"
                    if last_word.endswith('?'):
                        verb = "ask"
                    if last_word.endswith('!'):
                        verb = 'exclaim'
                    say_msg = ' '.join(say_msg)
                    phrase = f", {self.quotation_mark}{say_msg}{self.quotation_mark}"
                    to_self = f"You {verb}{phrase}"
                    to_others = f"{client.username} {verb}s{phrase}"
                    message_type = MessageType.say
                    # message for the speaker
                    await self.send_message(writer, Message(lines=[to_self],
                                                            type=message_type, mode=Mode.app))
                    # Broadcast to all other connected clients (exclude the sender)
                    for c_addr, c in self.clients.items():
                        if getattr(c, 'username', None) != getattr(client, 'username', None):
                            await self.send_message(c.writer, Message(lines=[to_others], type=message_type, mode=Mode.app))
                    # Always send a prompt after handling a command
                    await self.send_message(writer, Message(lines=[], mode=Mode.app, prompt="main> "))
                    handled = True
                    break
                elif cmd =='testmsg':
                    for msg in MessageType:
                        msg_type = msg.name.capitalize()
                        test_line = f"[{msg_type}] This is a test of {a_or_an(msg_type)} message."
                        test_message = Message(lines=[test_line], type=msg_type, mode=Mode.app)
                        await self.send_message(writer, test_message)
                    handled = True
                    # send message about the next command prompt will return to an echo server
                    await self.send_message(writer, Message(lines=["Returning to echo server mode."],
                                                            type=MessageType.system, mode=Mode.app, prompt="main> "))
                    break
                else:
                    # Default: echo response in app mode
                    response = Message(lines=[f"[APP] Echo: {' '.join(in_message.lines)}"], type=MessageType.regular, mode=Mode.app, prompt="main> ")
                    await self.send_message(writer, response)
                    handled = True
                    break

if __name__ == '__main__':
    server = Server('127.0.0.1', 8888)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer shut down.")
