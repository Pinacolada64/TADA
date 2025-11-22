import asyncio
import logging
from pathlib import Path

import player
from net_common import Message, MessageType, Mode, to_jsonb, from_jsonb
from net_client import Client
from tada_utilities import a_or_an, grammatical_list, list_players_in_room, oxford_comma_list

# Game/map imports
from terminal import Translation
from base_classes import Map, compass_txts
from items import Item, Rations, Weapon
from characters import Monster
from commands.command_processor import create_command_processor

class Init:
    # server_id, server_key, protocol_version, type must all match between server + client.
    # character translation (e.g. 'utf-8', 'petscii', etc.) can be whatever the client wants.
    def __init__(self, server_id="test_server", server_key="test_key", protocol_version=1,
                 translation=Translation.ANSI, type=MessageType.INIT):
        self.type = type
        self.server_id = server_id
        self.server_key = server_key
        self.protocol_version = protocol_version
        self.translation: Translation = translation
        self.type: MessageType = MessageType.INIT


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
            translation=Translation.ANSI  # Default translation as enum
        )
        logging.info(f"Server configured with ID: {self.server_init_object.server_id}")

        # Load map and game data (level, objects, monsters, weapons, rations)
        try:
            script_dir = Path(__file__).parent
            self.game_map = Map()
            self.game_map.read_map(str(script_dir / "level_1.json"))
            try:
                self.items = Item.read(str(script_dir / "objects.json"))
            except Exception:
                self.items = []
            try:
                self.monsters = Monster.read_monsters(str(script_dir / "monsters.json"))
            except Exception:
                self.monsters = []
            try:
                self.weapons = Weapon.read_weapons(str(script_dir / "weapons.json"))
            except Exception:
                self.weapons = []
            try:
                self.rations = Rations.read_rations(str(script_dir / "rations.json"))
            except Exception:
                self.rations = []
            logging.info(f"Loaded map with {len(self.game_map.rooms)} rooms")
        except Exception:
            logging.exception("Failed to load map or game data; room descriptions will be unavailable")

    def _register_client_global(self, client):
        """Register a client in the global net_common.client_manager if not already present."""
        try:
            import net_common as _nc
            uid = getattr(client, 'username', None)
            if not uid:
                return
            # avoid re-registering existing user_id
            if uid in _nc.client_manager.clients:
                return
            _nc.client_manager.add_client(uid, client)
            logging.info(f"Registered client in global client_manager: {uid}")
        except Exception:
            logging.exception("Failed to register client in global client_manager")

    def _describe_room(self, client_or_player) -> list:
        """Return a list of lines describing the client's current room.

        Accepts either a Client-like object (as before) or a Player object (which
        exposes .query_flag()). The function will detect the passed object and
        prefer using the Player's .query_flag() to determine whether to show room
        numbers in exits.
        """
        lines = []
        try:
            # Normalize inputs:
            # - If a Player object was passed (has query_flag), use it as player_obj.
            # - Otherwise, try to get a Player from client_or_player.player if present.
            player_obj = None
            client = client_or_player
            if hasattr(client_or_player, 'query_flag'):
                player_obj = client_or_player
                # If the Player object references a client/handler, expose it as client
                client = getattr(client_or_player, 'client', client_or_player)
            else:
                player_obj = getattr(client_or_player, 'player', None)

            room_no = getattr(client, 'room', 1) or 1
            room = self.game_map.rooms.get(int(room_no)) if hasattr(self, 'game_map') else None
            if not room:
                return ["You are nowhere (map not loaded)."]

            # Header: room name + guild alignment
            header = [f"{room.name}", f" [{room.alignment}]" if getattr(room, 'alignment', None) else "Neutral"]
            lines.append(''.join(header))

            # Description
            if getattr(room, 'desc', None):
                lines.append("")
                lines.append(room.desc)

            # Build aggregated 'you see' list for objects in the room
            seen = []

            # Items: skip listing it in room contents if the item is already in the player's inventory.
            try:
                if getattr(room, 'item', 0):
                    idx = int(room.item) - 1
                    if 0 <= idx < len(self.items):
                        seen.append(self.items[idx]['name'])
            except Exception:
                pass

            # Food / rations
            try:
                if getattr(room, 'food', 0):
                    idx = int(room.food) - 1
                    if 0 <= idx < len(self.rations):
                        seen.append(self.rations[idx]['name'])
            except Exception:
                pass

            # Weapon
            try:
                if getattr(room, 'weapon', 0):
                    idx = int(room.weapon) - 1
                    if 0 <= idx < len(self.weapons):
                        seen.append(self.weapons[idx]['name'])
            except Exception:
                pass

            # Monster
            try:
                if getattr(room, 'monster', 0):
                    idx = int(room.monster) - 1
                    if 0 <= idx < len(self.monsters):
                        m = self.monsters[idx]
                        # don't list this monster if it is already in player's dead_monsters list:
                        dead_monsters = getattr(client, 'dead_monsters', [])
                        if isinstance(m, dict):
                            m_id = m.get('id', None)
                        mon_name = m.get('name', 'a monster') if isinstance(m, dict) else getattr(m, 'name', 'a monster')
                        mon_size = m.get('size', None) if isinstance(m, dict) else getattr(m, 'size', None)
                        lines.append("")
                        lines.append(f"There is {mon_size} {mon_name} here.")
            except Exception:
                pass

            # If any seen objects, add a combined line using grammatical_list (handles "a book", "an orange", "some coins")
            if seen:
                lines.append("")
                try:
                    seen_text = grammatical_list(seen)
                except Exception:
                    seen_text = ', '.join(seen)
                lines.append(f"You see {seen_text}")

            # List other players present in the same room (exclude the current player)
            try:
                import net_common as _nc
                other_names = []
                for uid, info in _nc.client_manager.clients.items():
                    try:
                        handler = info.handler
                        # handler should be the client object stored earlier
                        if handler is client:
                            continue
                        # TODO: compare room and level numbers if available
                        if getattr(handler, 'room', None) is None:
                            continue
                        if int(getattr(handler, 'room')) == int(room_no):
                            name = getattr(handler, 'username', None) or uid
                            # skip if same as the current client username
                            if name and name != getattr(client, 'username', None):
                                other_names.append(name)
                    except Exception:
                        continue
                if other_names:
                    lines.append("")
                    try:
                        players_text = list_players_in_room(other_names)
                    except Exception:
                        players_text = (f"{other_names[0]} is here." if len(other_names) == 1 else f"{', '.join(other_names)} are here.")
                    lines.append(players_text)
            except Exception:
                # fail silently if client_manager isn't available
                pass

            # Exits
            try:
                exits_list = []
                # cardinal directions
                for k in getattr(room, 'exits', {}).keys():
                    if k in compass_txts:
                        exits_list.append(compass_txts[k])
                # up/down transport handling
                try:
                    rc = int(getattr(room, 'exits', {}).get('rc', 0) or 0)
                except Exception:
                    rc = 0
                try:
                    rt = int(getattr(room, 'exits', {}).get('rt', 0) or 0)
                except Exception:
                    rt = 0
                if rc in (1, 2):
                    dirname = 'Up' if rc == 1 else 'Down'
                    if rt == 0:
                        exits_list.append(f"{dirname} (to Shoppe)")
                    else:
                        # Determine whether to show room number using Player.query_flag() if available,
                        # otherwise fall back to module-level player.debug_mode.
                        try:
                            debug_mode = False
                            if player_obj and hasattr(player_obj, 'query_flag'):
                                try:
                                    debug_mode = bool(player_obj.query_flag('DEBUG_MODE'))
                                except Exception:
                                    try:
                                        debug_mode = bool(player_obj.query_flag('debug_mode'))
                                    except Exception:
                                        debug_mode = getattr(player_obj, 'debug_mode', False)
                            else:
                                debug_mode = getattr(player, 'debug_mode', False)
                        except Exception:
                            debug_mode = False
                        exits_list.append(f"{dirname}{f' (to #{rt})' if debug_mode else ''}")
                if exits_list:
                    lines.append("")
                    try:
                        # For two elements prefer explicit Oxford comma: 'A, and B'
                        exits_text = oxford_comma_list(exits_list)
                    except Exception:
                        exits_text = ', '.join(exits_list)
                    lines.append(f"Ye may travel {exits_text}.")
            except Exception:
                pass

        except Exception:
            logging.exception("Error building room description")
            return ["(Error showing room)"]

        return lines

        # (self, client) -> list:
        """Return a list of lines describing the client's current room.

        Includes header information (usually room name and guild alignment) , description, exits, visible objects,
         monsters.
        """
        lines = []
        try:
            room_no = getattr(client, 'room', 1) or 1
            room = self.game_map.rooms.get(int(room_no)) if hasattr(self, 'game_map') else None
            if not room:
                return ["You are nowhere (map not loaded)."]

            # Header: room name + guild alignment
            header = [f"{room.name}", f" [{room.alignment}]" if getattr(room, 'alignment', None) else "Neutral"]
            lines.append(''.join(header))

            # Description
            if getattr(room, 'desc', None):
                lines.append("")
                lines.append(room.desc)

            # Build aggregated 'you see' list for objects in the room
            seen = []

            # Items: skip listing it in room contents if the item is already in the player's inventory.
            # Historically, this was the way The Land of Spur did it. If  but it makes even more sense in a multiplayer
            # game: one player could hoard an item and others wouldn't be able to acquire it.
            try:
                if getattr(room, 'item', 0):
                    idx = int(room.item) - 1
                    if 0 <= idx < len(self.items):
                        seen.append(self.items[idx]['name'])
            except Exception:
                pass

            # Food / rations
            try:
                if getattr(room, 'food', 0):
                    idx = int(room.food) - 1
                    if 0 <= idx < len(self.rations):
                        seen.append(self.rations[idx]['name'])
            except Exception:
                pass

            # Weapon
            try:
                if getattr(room, 'weapon', 0):
                    idx = int(room.weapon) - 1
                    if 0 <= idx < len(self.weapons):
                        seen.append(self.weapons[idx]['name'])
            except Exception:
                pass

            # Monster
            try:
                if getattr(room, 'monster', 0):
                    idx = int(room.monster) - 1
                    if 0 <= idx < len(self.monsters):
                        m = self.monsters[idx]
                        # don't list this monster if it is already in player's dead_monsters list:
                        dead_monsters = getattr(client, 'dead_monsters', [])
                        if isinstance(m, dict):
                            m_id = m.get('id', None)
                        mon_name = m.get('name', 'a monster') if isinstance(m, dict) else getattr(m, 'name', 'a monster')
                        mon_size = m.get('size', None) if isinstance(m, dict) else getattr(m, 'size', None)
                        lines.append("")
                        lines.append(f"There is {mon_size} {mon_name} here.")
            except Exception:
                pass

            # If any seen objects, add a combined line using grammatical_list (handles "a book", "an orange", "some coins")
            if seen:
                lines.append("")
                try:
                    seen_text = grammatical_list(seen)
                except Exception:
                    seen_text = ', '.join(seen)
                lines.append(f"You see {seen_text}")

            # List other players present in the same room (exclude the current player)
            try:
                import net_common as _nc
                other_names = []
                for uid, info in _nc.client_manager.clients.items():
                    try:
                        handler = info.handler
                        # handler should be the client object stored earlier
                        if handler is client:
                            continue
                        # TODO: compare room and level numbers if available
                        if getattr(handler, 'room', None) is None:
                            continue
                        if int(getattr(handler, 'room')) == int(room_no):
                            name = getattr(handler, 'username', None) or uid
                            # skip if same as the current client username
                            if name and name != getattr(client, 'username', None):
                                other_names.append(name)
                    except Exception:
                        continue
                if other_names:
                    lines.append("")
                    try:
                        players_text = list_players_in_room(other_names)
                    except Exception:
                        players_text = (f"{other_names[0]} is here." if len(other_names) == 1 else f"{', '.join(other_names)} are here.")
                    lines.append(players_text)
            except Exception:
                # fail silently if client_manager isn't available
                pass

            # Exits
            try:
                exits_list = []
                # cardinal directions
                for k in getattr(room, 'exits', {}).keys():
                    if k in compass_txts:
                        exits_list.append(compass_txts[k])
                # up/down transport handling
                try:
                    rc = int(getattr(room, 'exits', {}).get('rc', 0) or 0)
                except Exception:
                    rc = 0
                try:
                    rt = int(getattr(room, 'exits', {}).get('rt', 0) or 0)
                except Exception:
                    rt = 0
                if rc in (1, 2):
                    dirname = 'Up' if rc == 1 else 'Down'
                    if rt == 0:
                        exits_list.append(f"{dirname} (to Shoppe)")
                    else:
                        # Check player's debug mode to decide whether to show room number
                        debug_mode = getattr(player, 'debug_mode', False)
                        # debug_mode = player.query_flag(PlayerFlag.DEBUG_MODE)
                        # Append the exit description with or without the room number based on debug mode
                        exits_list.append(f"{dirname}{f' (to #{rt})' if debug_mode else ''}")
                if exits_list:
                    lines.append("")
                    try:
                        # For two elements prefer explicit Oxford comma: 'A, and B'
                        # if len(exits_list) == 1:
                        #     exits_text = exits_list[0]
                        # elif len(exits_list) == 2:
                        #     exits_text = f"{exits_list[0]}, and {exits_list[1]}"
                        # else:
                        #     exits_text = oxford_comma_list(exits_list)
                        exits_text = oxford_comma_list(exits_list)
                    except Exception:
                        exits_text = ', '.join(exits_list)
                    lines.append(f"Ye may travel {exits_text}.")
            except Exception:
                pass

        except Exception:
            logging.exception("Error building room description")
            return ["(Error showing room)"]

        return lines

    async def send_message(self, writer, obj):
        try:
            # Normalize Message.lines to a flat list of strings to avoid accidentally
            # sending a single string that is the repr() of a list (causes double-brackets).
            try:
                if hasattr(obj, 'lines'):
                    lines = getattr(obj, 'lines')
                    # If lines is a single string, keep as-is; otherwise flatten
                    if isinstance(lines, list):
                        flat = []
                        for item in lines:
                            if isinstance(item, list):
                                for sub in item:
                                    flat.append(str(sub))
                            else:
                                flat.append(str(item))
                        obj.lines = flat
            except Exception:
                # swallow normalization errors; we'll serialize anyway
                pass

            raw = to_jsonb(obj)
        except Exception as e:
            logging.exception(f"Failed to serialize object for send: {e}")
            raise
        # Log outgoing raw JSON bytes for debugging
        logging.debug(f"Sending raw bytes to client {getattr(writer, 'get_extra_info', lambda k: None)('peername')}: {raw!r}")
        writer.write(raw + b'\n')
        await writer.drain()

    async def receive_message(self, reader):
        data = await reader.readline()
        # Log raw incoming bytes for debugging
        logging.debug(f"Received raw bytes from client: {data!r}")
        if not data:
            return None
        try:
            obj = from_jsonb(data)
            logging.debug(f"Decoded incoming object: {obj}")
            # If the decoded object is a dict coming from a Message, convert
            # known string fields into their Enum counterparts so the rest of
            # the code can compare enums directly.
            if isinstance(obj, dict):
                # coerce mode
                try:
                    if 'mode' in obj and isinstance(obj['mode'], str):
                        obj['mode'] = Mode(obj['mode'])
                        logging.debug(f"Coerced 'mode' to enum: {obj['mode']}")
                except Exception:
                    logging.debug(f"Could not coerce mode value: {obj.get('mode')}")
                # coerce type
                try:
                    if 'type' in obj and isinstance(obj['type'], str):
                        tval = obj['type']
                        # Try by member name first (case-sensitive), then case-insensitive name
                        try:
                            obj['type'] = MessageType[tval]
                        except KeyError:
                            # Try matching case-insensitive by name
                            matched = None
                            for m in MessageType:
                                if m.name.lower() == str(tval).lower() or str(m.value).lower() == str(tval).lower():
                                    matched = m
                                    break
                            if matched is not None:
                                obj['type'] = matched
                            else:
                                # No MessageType match found; log and leave as string
                                logging.debug(f"No MessageType match for value: {tval}")
                        logging.debug(f"Coerced 'type' to enum: {obj['type']}")
                except Exception:
                    logging.debug(f"Could not coerce type value: {obj.get('type')}")
            return obj
        except Exception:
            logging.exception(f"Failed to decode incoming data: {data!r}")
            # Return raw data for higher-level handling
            return None

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
            # Log full stack trace for unexpected errors so we can diagnose root cause
            logging.exception(f"An unexpected error occurred with client {addr}:")
        finally:
            if addr in self.clients:
                # attempt to remove from client_manager by username if present
                try:
                    import net_common as _nc
                    cobj = self.clients.get(addr)
                    if cobj and getattr(cobj, 'username', None):
                        _nc.client_manager.remove_client(cobj.username)
                except Exception:
                    pass
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
                # TODO: fall back to asking questions manually
                logging.error(f"Handshake failed: Client {addr} disconnected before sending Init.")
                return None

            # Expect a dict-like structure; instantiate Init with it
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
            # Make the server instance available on the client object so commands
            # can access server helpers like _describe_room and broadcast_message.
            client.server = self
            client.addr = addr
            client.translation = client_init.translation
            client.writer = writer
            # Store the reader on the client so commands can prompt/read directly
            client.reader = reader
            # Create a per-client command processor with default guest permissions
            client.command_processor = create_command_processor(client, context={'username': None, 'is_authenticated': False})

            # TODO: If you want to support screen size, add: client.screen_size = getattr(client_init, 'screen_size', None)
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
        # (commands imported dynamically by command processor when needed)
        logging.info("In _handle_login()")
        # Display the login welcome message and options
        login_text = [
            "Welcome to:",
            "",
            "Totally",
            " Awesome",
            "  Dungeon",
            "   Adventure",
            "",
            "To connect to an existing character, type 'connect <username> <password>'.",
            "To look around as a guest, type 'connect guest'.",
            "To create a new character, type 'new'.",
            "To leave, type 'quit'."
        ]
        login_message = Message(lines=login_text, mode=Mode.login, prompt="login> ", type=MessageType.REGULAR)
        await self.send_message(writer, login_message)
        # handle commands in login mode until the client switches to app mode
        # The main loop in handle_connection will now receive the next client message;
        # do not pre-consume it here.

    async def handle_login_command(self, writer, username=None):
        # This is a mock login handler. In a real system, you'd check credentials here.
        logging.info("username: %s" % username)
        if not username:
            username = "Guest"

        login_lines = [
            f"Login successful! Welcome, {username}.",
            '',
            "Here are the commands you can use:",
            '',
            "To test message types, type 'testmsg'.",
            f"To talk to everyone in the same room, type 'say <message>' or '{self.quotation_mark}<message>",
            # "To connect to an existing character, type 'connect <username> <password>'",
            # "To look around as a guest, type 'guest'.",
            # "To create a new character, type 'new <username>'."
            "To move around, type a direction (n, e, s, w, u, d).",
        ]
        login_message = Message(lines=login_lines, mode=Mode.login, type=MessageType.REGULAR, prompt="main> ")
        await self.send_message(writer, login_message)

    async def handle_login_mode(self, client, in_message, writer):
        logging.info("In _handle_login_mode()")
        handled = False
        if in_message.lines and isinstance(in_message.lines, list):
            for line in in_message.lines:
                raw = line.strip()
                cmd = raw.lower()
                args = raw.split()

                # 1) Try the per-client command processor first (preferred)
                processor = getattr(client, 'command_processor', None)
                if processor:
                    try:
                        result = await processor.process_input(raw)
                        logging.debug(f"Processor returned (raw): {result!r}")
                    except Exception as e:
                        logging.exception("Error executing login command via processor")
                        await self.send_message(writer, Message(lines=[f"Login command error: {e}"], type=MessageType.SYSTEM if hasattr(MessageType, 'SYSTEM') else MessageType.REGULAR, mode=Mode.login, prompt="login> "))
                        continue

                    # Normalize result to a dict-like structure
                    try:
                        if result is None:
                            # No output from command
                            success = False
                            message = None
                            data = {}
                            error = None
                        elif isinstance(result, dict):
                            success = result.get('success', False)
                            message = result.get('message')
                            data = result.get('data', {})
                            error = result.get('error')
                        elif hasattr(result, 'to_dict'):
                            # dataclass-like CommandResult
                            rdict = result.to_dict() if callable(getattr(result, 'to_dict', None)) else None
                            if isinstance(rdict, dict):
                                success = rdict.get('success', False)
                                message = rdict.get('message')
                                data = rdict.get('data', {}) or {}
                                error = rdict.get('error')
                            else:
                                success = getattr(result, 'success', False)
                                message = getattr(result, 'message', None)
                                data = getattr(result, 'data', {}) or {}
                                error = getattr(result, 'error', None)
                        elif isinstance(result, str):
                            # simple string -> send as message
                            success = True
                            message = result
                            data = {}
                            error = None
                        else:
                            # Fallback: try attribute access; this may raise and be caught below
                            success = getattr(result, 'success', False)
                            message = getattr(result, 'message', None)
                            data = getattr(result, 'data', {}) or {}
                            error = getattr(result, 'error', None)
                    except Exception:
                        # Log full debug info and continue without crashing the server
                        logging.exception("Failed to normalize processor result")
                        await self.send_message(writer, Message(lines=["Internal server error while processing command."], type=MessageType.SYSTEM if hasattr(MessageType, 'SYSTEM') else MessageType.REGULAR, mode=Mode.login, prompt="login> "))
                        continue

                    # Send returned message(s)
                    out_lines = []
                    if isinstance(message, list):
                        out_lines.extend(message)
                    elif message is not None:
                        out_lines.append(str(message))
                    if error:
                        out_lines.append(f"Error: {error}")
                    if out_lines:
                        await self.send_message(writer, Message(lines=out_lines, type=MessageType.SYSTEM, mode=Mode.login, prompt="login> "))

                    # If the command returned data indicating a state change, apply it
                    if data:
                        # Guest: set username and switch to app
                        if data.get('mode') == Mode.guest or (data.get('authenticated') is False and data.get('username', '').lower().startswith('guest')):
                            client.username = data.get('username', getattr(client, 'username', 'Guest'))
                            client.mode = Mode.app
                            # recreate processor for guest (not authenticated)
                            try:
                                client.player = player.Player(name=client.username)
                            except Exception:
                                client.player = getattr(client, 'player', None)
                            client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': False})
                            # Register into global client_manager for 'who' and broadcasts
                            try:
                                import net_common as _nc
                                _nc.client_manager.add_client(client.username, client)
                            except Exception:
                                logging.debug('Could not register client with client_manager')
                            # ensure they have a room set and send the room description
                            if not getattr(client, 'room', None):
                                client.room = 1
                            room_lines = self._describe_room(client)
                            await self.send_message(writer, Message(lines=[f"Connected as {client.username}."] + room_lines, mode=Mode.app, prompt="main> "))
                            handled = True
                            break

                        # Authenticated/login success
                        if data.get('authenticated') is True or data.get('mode') == Mode.app:
                            client.username = data.get('username', getattr(client, 'username', None)) or client.username
                            client.mode = Mode.app
                            try:
                                client.player = player.Player(name=client.username)
                            except Exception:
                                client.player = getattr(client, 'player', None)
                            client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': True})
                            # Register into global client_manager for 'who' and broadcasts
                            try:
                                import net_common as _nc
                                _nc.client_manager.add_client(client.username, client)
                            except Exception:
                                logging.debug('Could not register client with client_manager')
                            # ensure they have a room set and send the room description
                            if not getattr(client, 'room', None):
                                client.room = 1
                            room_lines = self._describe_room(client)
                            await self.send_message(writer, Message(lines=[f"Login successful. Welcome, {client.username}."] + room_lines, mode=Mode.app, prompt="main> "))
                            handled = True
                            break

                    # If processor handled the command (success) but didn't switch modes, mark handled
                    if success:
                        handled = True
                        break

                # 2) Fallback to old inline handlers if processor didn't handle it
                # inline connect <username> <password>
                if cmd.startswith('connect') and len(args) >= 2:
                    username = args[1]
                    usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                    if username in usernames:
                        await self.send_message(writer, Message(lines=[f"Username '{username}' is already taken."], type=MessageType.SYSTEM, mode=Mode.login, prompt="login> "))
                        handled = True
                        break
                    client.username = username
                    client.mode = Mode.app
                    # Ensure a Player instance exists on the client for command context
                    try:
                        client.player = player.Player(name=client.username)
                    except Exception:
                        client.player = getattr(client, 'player', None)
                    client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': True})
                    # Register into global client_manager so 'who' and broadcasts include this client
                    try:
                        import net_common as _nc
                        _nc.client_manager.add_client(client.username, client)
                    except Exception:
                        logging.debug('Could not register client with client_manager (connect path)')
                    # ensure they have a room set and send the room description (consistent with processor path)
                    if not getattr(client, 'room', None):
                        client.room = 1
                    room_lines = self._describe_room(client)
                    await self.send_message(writer, Message(lines=[f"Login successful. Welcome, {client.username}."] + room_lines, mode=Mode.app, prompt="main> "))
                    await self.handle_login_command(writer, username=username)
                    handled = True
                    break

                # inline guest fallback (if no processor handled it)
                if cmd == 'guest':
                    base = "Guest"
                    n = 1
                    usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                    while f"{base}{n}" in usernames:
                        n += 1
                    client.username = f"{base}{n}"
                    client.mode = Mode.app
                    try:
                        client.player = player.Player(name=client.username)
                    except Exception:
                        client.player = getattr(client, 'player', None)
                    client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': False})
                    # Register guest into global client_manager
                    try:
                        import net_common as _nc
                        _nc.client_manager.add_client(client.username, client)
                    except Exception:
                        logging.debug('Could not register client with client_manager (guest path)')
                    # ensure they have a room set and send the room description (consistent with processor path)
                    if not getattr(client, 'room', None):
                        client.room = 1
                    room_lines = self._describe_room(client)
                    await self.send_message(writer, Message(lines=[f"Connected as {client.username}."] + room_lines, mode=Mode.app, prompt="main> "))
                    await self.handle_login_command(writer, username=client.username)
                    handled = True
                    break

                # inline new <username>
                if cmd.startswith('new') and len(args) >= 2:
                    username = args[1]
                    usernames = {getattr(c, 'username', None) for c in self.clients.values()}
                    if username in usernames:
                        await self.send_message(writer, Message(lines=[f"Username '{username}' is already taken."], type=MessageType.SYSTEM, mode=Mode.login, prompt="login> "))
                        handled = True
                        break
                    client.username = username
                    client.mode = Mode.app
                    try:
                        client.player = player.Player(name=client.username)
                    except Exception:
                        client.player = getattr(client, 'player', None)
                    client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': True})
                    # Register new player into client_manager
                    try:
                        import net_common as _nc
                        _nc.client_manager.add_client(client.username, client)
                    except Exception:
                        logging.debug('Could not register client with client_manager (new path)')
                    # ensure they have a room set and send the room description (consistent with processor path)
                    if not getattr(client, 'room', None):
                        client.room = 1
                    room_lines = self._describe_room(client)
                    await self.send_message(writer, Message(lines=[f"Login successful. Welcome, {client.username}."] + room_lines, mode=Mode.app, prompt="main> "))
                    await self.handle_login_command(writer, username=username)
                    handled = True
                    break
        if not handled:
            # If a command processor exists on the client, hand the raw lines to it.
            processor = getattr(client, 'command_processor', None)
            if processor:
                # Process each incoming line through the per-client processor.
                for line in in_message.lines:
                    # update last_activity in client_manager
                    try:
                        import net_common as _nc
                        if getattr(client, 'username', None):
                            _nc.client_manager.update_activity(client.username)
                    except Exception:
                        pass
                    try:
                        result = await processor.process_input(line)
                    except Exception as e:
                        logging.exception("Error executing login command via processor")
                        await self.send_message(writer, Message(lines=[f"Login command error: {e}"], type=MessageType.SYSTEM if hasattr(MessageType, 'SYSTEM') else MessageType.REGULAR, mode=Mode.login, prompt="login> "))
                        continue

                    # normalize result (commands may return dicts or CommandResult objects)
                    if isinstance(result, dict):
                        success = result.get('success', False)
                        message = result.get('message')
                        data = result.get('data', {})
                        error = result.get('error')
                    else:
                        success = getattr(result, 'success', False)
                        message = getattr(result, 'message', None)
                        data = getattr(result, 'data', {}) or {}
                        error = getattr(result, 'error', None)

                    # Send any returned text back to client in login mode
                    out_lines = []
                    if isinstance(message, list):
                        out_lines.extend(message)
                    elif message is not None:
                        out_lines.append(str(message))
                    if error:
                        out_lines.append(f"Error: {error}")
                    if out_lines:
                        await self.send_message(writer, Message(lines=out_lines, type=MessageType.SYSTEM, mode=Mode.login, prompt="login> "))

                    # If command returned data indicating a state change, apply it
                    if data:
                        # handle guest/login/new success cases
                        if data.get('mode') == Mode.guest or data.get('authenticated') is False and data.get('username') == 'guest':
                            client.username = data.get('username', getattr(client, 'username', 'Guest'))
                            client.mode = Mode.app
                            # recreate processor for guest (not authenticated)
                            try:
                                client.player = player.Player(name=client.username)
                            except Exception:
                                client.player = getattr(client, 'player', None)
                            client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': False})
                            # send a welcome in app mode
                            await self.send_message(writer, Message(lines=[f"Connected as {client.username}."], mode=Mode.app, prompt="main> "))
                            handled = True
                            break
                        if data.get('authenticated') is True or data.get('mode') == Mode.app:
                            client.username = data.get('username', getattr(client, 'username', None)) or client.username
                            client.mode = Mode.app
                            # recreate an authenticated command processor
                            try:
                                client.player = player.Player(name=client.username)
                            except Exception:
                                client.player = getattr(client, 'player', None)
                            client.command_processor = create_command_processor(client, context={'username': client.username, 'is_authenticated': True})
                            # send a welcome in app mode
                            await self.send_message(writer, Message(lines=[f"Login successful. Welcome, {client.username}."], mode=Mode.app, prompt="main> "))
                            handled = True
                            break

                if not handled:
                    # If none of the commands transitioned the client, prompt again
                    await self.send_message(writer, Message(lines=["Please enter 'login <user> <pass>', 'login guest', or 'new <username>'."], type=MessageType.SYSTEM, mode=Mode.login, prompt="login> "))
            else:
                # Default: keep looping asking for login info
                response = Message(lines=[f"Please supply a user name and password: 'login <username> <password>', "
                                          "or 'guest' to connect as a guest, or 'new <username>' to create a new "
                                          "character."], type=MessageType.SYSTEM, mode=Mode.login, prompt="login> ")
                await self.send_message(writer, response)

    async def handle_app_mode(self, client, in_message, writer, addr):
        logging.info("In _handle_app_mode()")
        handled = False
        if in_message.lines and isinstance(in_message.lines, list):
            for line in in_message.lines:
                args = line.strip().split()
                if not args:
                    continue

                cmd = args[0].lower()

                # Built-in test command (sends all MessageType examples)
                if cmd == 'testmsg':
                    for msg in MessageType:
                        msg_type = msg.name.capitalize()
                        test_line = f"[{msg_type}] This is a test of {a_or_an(msg_type)} message."
                        test_message = Message(lines=[test_line], type=msg, mode=Mode.app)
                        await self.send_message(writer, test_message)
                    handled = True
                    # send message about the next command prompt will return to an echo server
                    await self.send_message(writer, Message(lines=["Returning to echo server mode."],
                                                            type=MessageType.SYSTEM, mode=Mode.app, prompt="main> "))
                    break

                # Built-in say command: broadcast to all OTHER clients
                if cmd == 'say' and len(args) >= 2:
                    say_text = ' '.join(args[1:])
                    broadcast_msg = Message(lines=[f"{getattr(client, 'username', 'Someone')} says, '{say_text}'"],
                                            type=MessageType.REGULAR, mode=Mode.app, prompt="main> ")
                    await self.broadcast_message(addr, broadcast_msg)
                    # Acknowledge locally to sender (optional): send a simple prompt
                    await self.send_message(writer, Message(lines=["You say: " + say_text], type=MessageType.REGULAR, mode=Mode.app, prompt="main> "))
                    handled = True
                    break

                # If a per-client command processor exists, hand off the raw line to it
                processor = getattr(client, 'command_processor', None)
                if processor:
                    # process_input expects the full input string
                    try:
                        result = await processor.process_input(line)
                        # Convert CommandResult to messages; be conservative about structure
                        result_lines = []
                        # Normalize message: if it's a list, treat each element as a line.
                        if result and getattr(result, 'message', None) is not None:
                            msg = getattr(result, 'message')
                            if isinstance(msg, list):
                                # ensure all elements are strings
                                result_lines.extend([str(x) for x in msg])
                            else:
                                result_lines.append(str(msg))
                        if result and getattr(result, 'error', None):
                            result_lines.append(f"Error: {result.error}")
                        if not result_lines:
                            result_lines = ["(no output)"]
                        await self.send_message(writer, Message(lines=result_lines, type=MessageType.SYSTEM, mode=Mode.app, prompt="main> "))
                        handled = True
                        break
                    except Exception as e:
                        logging.exception("Error processing command via processor")
                        await self.send_message(writer, Message(lines=[f"Command error: {e}"], type=MessageType.SYSTEM, mode=Mode.app, prompt="main> "))
                        handled = True
                        break

                # Look command: describe the current room
                if cmd in ['l', 'look']:
                    # send room description
                    room_lines = self._describe_room(client)
                    await self.send_message(writer, Message(lines=room_lines, type=MessageType.REGULAR, mode=Mode.app, prompt="main> "))
                    handled = True
                    break

                # Default: echo response in app mode
                response = Message(lines=[f"[APP] Echo: {line.strip()}"], type=MessageType.REGULAR, mode=Mode.app, prompt="main> ")
                await self.send_message(writer, response)
                handled = True
                break

    async def broadcast_message(self, sender_addr, message_obj):
        """Send a Message object to all connected clients except the sender."""
        for addr, client in list(self.clients.items()):
            try:
                if addr == sender_addr:
                    continue
                writer = getattr(client, 'writer', None)
                if writer:
                    await self.send_message(writer, message_obj)
            except Exception:
                logging.exception(f"Failed to send broadcast to {addr}")

    def show_available_commands(self, client):
        """Return a sorted list of available command names for the client's command processor."""
        processor = getattr(client, 'command_processor', None)
        if not processor:
            return []
        # Gather unique command names
        names = sorted([c.name for c in processor.get_all_commands()])
        # If client is authenticated, filter out login-only commands
        is_auth = False
        try:
            ctx = getattr(processor, 'context', {})
            is_auth = bool(ctx.get('is_authenticated') or ctx.get('is_authenticated') or ctx.get('is_authenticated', False))
        except Exception:
            is_auth = False
        if is_auth:
            names = [n for n in names if n.lower() not in ('guest', 'new')]
        return names


if __name__ == '__main__':
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    server = Server('127.0.0.1', 8888)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer shut down.")
