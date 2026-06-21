#!/bin/env python3
"""
simple_server.py

Asyncio TCP server for TADA.

Connection lifecycle:
    TCP connect
        -> terminal negotiation   (GameContext.for_guest or PETSCIINetworkContext.for_guest)
        -> login                  (GuestPlayer -> real Player on success)
        -> game loop              (ctx drives all I/O)

Two ports:
    DEFAULT_PORT  (34083) — JSON wire protocol (Python client, ANSI terminals)
    PETSCII_PORT  (34064) — Raw PETSCII bytes  (Commodore 64/128)
"""

import asyncio
import logging
from pathlib import Path

import net_common as nc
from net_client import Client
from network_context import GameContext, PETSCIINetworkContext, GuestPlayer
from formatting import flatten_send_args, format_lines, codec_for_settings, ANSI_COLOR_CODES
from tada_utilities import a_or_an, grammatical_list, list_players_in_room, oxford_comma_list
from base_classes import Map, compass_txts
from items import Item, Rations, Weapon
from characters import Monster
from commands.command_processor import create_command_processor
from commands.base_command import Mode
from terminal import Translation

DEFAULT_PORT = 34083
PETSCII_PORT = 34064


# ---------------------------------------------------------------------------
# Handshake Init object
# ---------------------------------------------------------------------------

class Init:
    """Exchanged between client and server to negotiate protocol version."""
    def __init__(self, server_id='test_server', server_key='test_key',
                 protocol_version=1, translation=Translation.ANSI):
        self.type             = nc.MessageType.INIT
        self.server_id        = server_id
        self.server_key       = server_key
        self.protocol_version = protocol_version
        self.translation      = translation


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class Server:
    """Manages server state and all client connections."""

    def __init__(self, host: str,
                 port: int         = DEFAULT_PORT,
                 petscii_port: int = PETSCII_PORT):
        self.host         = host
        self.port         = port
        self.petscii_port = petscii_port
        self.clients: dict = {}   # addr -> Client

        self.server_init = Init()
        self._load_game_data()

    # -----------------------------------------------------------------------
    # Game data
    # -----------------------------------------------------------------------

    def _load_game_data(self):
        script_dir = Path(__file__).parent
        try:
            self.game_map = Map()
            self.game_map.read_map(str(script_dir / 'level_1.json'))
        except Exception:
            logging.exception('Failed to load map')
            self.game_map = None

        def _try_load(cls, filename, method='read'):
            try:
                result = getattr(cls, method)(str(script_dir / filename))
                return result if result is not None else []
            except Exception as e:
                logging.warning("Could not load '%s' via %s.%s: %s", filename, cls.__name__, method, e)
                return []

        self.items    = _try_load(Item,    'objects.json')
        self.monsters = _try_load(Monster, 'monsters.json', 'read_monsters')
        self.weapons  = _try_load(Weapon,  'weapons.json',  'read_weapons')
        self.rations  = _try_load(Rations, 'rations.json',  'read_rations')
        logging.info('Map: %d rooms | %d monsters | %d items | %d weapons',
                     len(self.game_map.rooms) if self.game_map else 0,
                     len(self.monsters), len(self.items), len(self.weapons))

    # -----------------------------------------------------------------------
    # Wire I/O (low-level — use ctx.send() in game code instead)
    # -----------------------------------------------------------------------

    async def send_message(self, writer, obj) -> None:
        """Serialize obj to JSON and write to writer. Used by GameContext."""
        try:
            data = nc.to_jsonb(obj)
            writer.write(data + b'\n')
            await writer.drain()
        except Exception:
            logging.exception('send_message failed')

    async def receive_message(self, reader) -> dict | None:
        """Read one newline-terminated JSON message from reader."""
        try:
            raw = await reader.readline()
            if not raw:
                return None
            return nc.from_jsonb(raw.strip())
        except asyncio.IncompleteReadError:
            return None
        except Exception:
            logging.exception('receive_message failed')
            return None

    # -----------------------------------------------------------------------
    # Connection entry point
    # -----------------------------------------------------------------------

    async def handle_connection(self, reader, writer):
        addr       = writer.get_extra_info('peername')
        local_port = writer.get_extra_info('sockname')[1]
        logging.info('New connection from %s on port %d', addr, local_port)

        client = Client()
        client.addr   = addr
        client.reader = reader
        client.writer = writer
        client.server = self

        # Choose context type based on which port was connected to
        is_petscii = (local_port == self.petscii_port)
        if is_petscii:
            ctx = PETSCIINetworkContext.for_guest(reader, writer, self, client)
            logging.info('%s: PETSCII connection (40 col)', addr)
        else:
            ctx = GameContext.for_guest(reader, writer, self, client)
            logging.info('%s: ANSI/JSON connection', addr)

        client.ctx = ctx
        self.clients[addr] = client

        try:
            if not is_petscii:
                # JSON clients handshake first
                if not await self._handshake(ctx):
                    return

            await self._negotiate_terminal(ctx)

            ctx.client.command_processor = create_command_processor(
                ctx.client,
                context={'is_authenticated': False},
                mode=Mode.LOGIN,
            )

            if await self._login(ctx):
                await self._game_loop(ctx)

        except asyncio.CancelledError:
            logging.warning('%s: connection task cancelled', addr)
        except Exception:
            logging.exception('%s: unexpected error', addr)
        finally:
            if addr in self.clients:
                del self.clients[addr]
            logging.info('%s: connection closed. Total clients: %d',
                         addr, len(self.clients))
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Handshake (JSON clients only)
    # -----------------------------------------------------------------------

    async def _handshake(self, ctx: GameContext) -> bool:
        """
        Exchange Init objects with a JSON client.
        Returns True on success, False on failure.
        PETSCII clients skip this entirely.
        """
        try:
            await self.send_message(ctx.writer, self.server_init)

            data = await self.receive_message(ctx.reader)
            if not data:
                logging.warning('%s: no Init received', ctx.client.addr)
                return False

            client_init = Init(**{k: v for k, v in data.items()
                                  if k in ('server_id', 'server_key',
                                           'protocol_version', 'translation')})

            if client_init.server_id != self.server_init.server_id:
                await ctx.send('Handshake failed: server ID mismatch.')
                return False
            if client_init.server_key != self.server_init.server_key:
                await ctx.send('Handshake failed: server key mismatch.')
                return False

            await self.send_message(
                ctx.writer,
                nc.Message(lines=['Handshake successful.'], mode=nc.Mode.login),
            )
            logging.info('%s: handshake OK', ctx.client.addr)
            return True

        except Exception:
            logging.exception('%s: handshake error', ctx.client.addr)
            return False

    # -----------------------------------------------------------------------
    # Terminal negotiation
    # -----------------------------------------------------------------------

    async def _negotiate_terminal(self, ctx: GameContext) -> None:
        """
        Ask the player which terminal type / screen size they're using
        and update ctx.player.client_settings accordingly.

        PETSCII clients are already configured by PETSCIINetworkContext.for_guest();
        this step lets them confirm or adjust screen width (40 vs 80 col C128).
        """
        translation = ctx.player.client_settings.translation

        if translation == Translation.PETSCII:
            await ctx.send(
                'TADA server',
                'Commodore client detected.',
                '1. 40 columns (C64 / C128 40-col)',
                '2. 80 columns (C128 80-col)',
            )
            raw = await ctx.prompt('Screen width')
            if raw is None:
                return
            if raw.strip() == '2':
                ctx.player.client_settings.screen_columns = 80
                await ctx.send('80 column mode set.')
            else:
                ctx.player.client_settings.screen_columns = 40
                await ctx.send('40 column mode set.')
        else:
            # For ANSI/JSON clients, offer ANSI vs plain
            await ctx.send(
                '',
                'TADA — Terminal negotiation',
                '  A.  ANSI color (default)',
                '  P.  Plain text (no color)',
                '',
            )
            while True:
                raw = await ctx.prompt('Terminal type [A/P]')
                if raw is None:
                    return
                if raw.strip().upper() == 'P':
                    try:
                        ctx.player.client_settings.translation = Translation.ASCII
                        await ctx.send('Plain text mode set.')
                        logging.info("Address %s: Plain text mode set." % ctx.client.host)
                        break
                    except Exception:
                        pass
                if raw.strip().upper() == 'A':
                    try:
                        ctx.player.client_settings.translation = Translation.ANSI
                        await ctx.send('ANSI color mode set.')
                        logging.info("Address %s: ANSI color mode set." % ctx.client.client_socket)
                        break
                    except Exception:
                        pass

    # -----------------------------------------------------------------------
    # Login
    # -----------------------------------------------------------------------

    async def _login(self, ctx: GameContext) -> bool:
        """
        Handle the login / character creation phase.
        Returns True if the player authenticated and should enter the game loop.
        Returns False on quit or disconnect.
        """
        await ctx.send(
            '',
            '|green|Welcome to:',
            '',
              '|red|  Totally',
            '|white|   Awesome',
              '|red|    Dungeon',
            '|white|     Adventure',
            '|green|',
            "Type 'connect <username> <password>' to log in.",
            "Type 'connect guest' to look around as a guest.",
            "Type 'new' to create a new character.",
            "Type 'help' for help.  Type 'quit' to leave.",
            '|light_blue|',
        )

        processor = ctx.client.command_processor
        ctx.set_prompt('login')

        while True:
            raw = await ctx.prompt('login')
            if raw is None:
                return False                    # clean disconnect
            if not raw.strip():
                continue

            result = await processor.process_input(raw, ctx=ctx)

            if not result.success and result.error == 'unknown_command':
                available = sorted(
                    f"'{name}'" for name, cmd in processor.get_all_commands().items()
                    if cmd.is_available_in(processor.current_mode)
                )
                await ctx.send(
                    f"Unknown command '{raw.strip().split()[0]}'.",
                    f"Available commands: {', '.join(available)}",
                )
                continue

            # ConnectCommand (and future auth commands) signal success via data
            if result.data.get('authenticated'):
                processor.current_mode = Mode.GAME
                ctx.set_prompt('main')
                return True

            # QuitCommand signals that we should drop the connection
            if result.data.get('quit'):
                return False

    async def _authenticate(self, ctx: GameContext,
                            username: str, password: str):
        """
        Verify credentials and return a Player on success, None on failure.
        Sends its own error message on failure so the caller can just check
        the return value.
        """
        import json
        user_file = Path('run') / 'server' / 'net' / f'login-{username}.json'
        try:
            if not user_file.exists():
                await ctx.send('Invalid username or password.')
                return None
            with open(user_file) as f:
                data = json.load(f)
            if data.get('password') != password:
                await ctx.send('Invalid username or password.')
                return None
            # Load or create the Player object
            from player import Player
            p = Player(name=username, id=username)
            logging.info('%s: authenticated as %s', ctx.client.addr, username)
            return p
        except Exception:
            logging.exception('Authentication error for %s', username)
            await ctx.send('Error accessing user data. Please try again.')
            return None

    # -----------------------------------------------------------------------
    # Game loop
    # -----------------------------------------------------------------------

    async def _game_loop(self, ctx: GameContext) -> None:
        """Main command loop for an authenticated (or guest) player."""
        await self._show_room(ctx)

        processor = ctx.client.command_processor

        while True:
            raw = await ctx.prompt('main')
            if raw is None:                     # clean EOF / disconnect
                await self._player_quit(ctx)
                return
            if not raw.strip():
                continue

            result = await processor.process_input(raw, ctx=ctx)

            # QuitCommand sets data={'quit': True} to signal clean exit
            if result.data.get('quit'):
                await self._player_quit(ctx)
                return

            if not result.success and result.error == 'unknown_command':
                await ctx.send(f"Unknown command '{raw.strip().split()[0]}'. "
                               "Type 'help' for a list.")

    # -----------------------------------------------------------------------
    # Room display
    # -----------------------------------------------------------------------

    async def _show_room(self, ctx: GameContext) -> None:
        """Build and send the room description to ctx."""
        lines = self._describe_room(ctx.client)
        await ctx.send(lines)

    def _describe_room(self, client) -> list[str]:
        """Return a list of strings describing the client's current room."""
        lines    = []
        room_no  = getattr(client, 'room', 1) or 1
        room     = (self.game_map.rooms.get(int(room_no))
                    if self.game_map else None)
        if not room:
            return ['You are nowhere (map not loaded).']

        alignment = getattr(room, 'alignment', None)
        lines.append(f"{room.name}{f'  [{alignment}]' if alignment else ''}")

        if getattr(room, 'desc', None):
            lines += ['', room.desc]

        seen = []

        # Items: skip listing it in room contents if the item is already in the player's inventory.
        # Historically, this was the way The Land of Spur did it. It it makes even more sense in a multiplayer
        # game: one player could hoard an item and others wouldn't be able to acquire it.

        for attr, collection in (('item',    self.items),
                                  ('food',    self.rations),
                                  ('weapon',  self.weapons)):
            try:
                idx = int(getattr(room, attr, 0) or 0) - 1
                if 0 <= idx < len(collection):
                    name = (collection[idx].get('name')
                            if isinstance(collection[idx], dict)
                            else getattr(collection[idx], 'name', None))
                    if name:
                        seen.append(name)
            except Exception:
                pass

        try:
            mon_idx = int(getattr(room, 'monster', 0) or 0) - 1
            if 0 <= mon_idx < len(self.monsters):
                m = self.monsters[mon_idx]
                name = m.get('name') if isinstance(m, dict) else getattr(m, 'name', 'a monster')
                size = m.get('size') if isinstance(m, dict) else getattr(m, 'size', None)
                lines += ['', f"There is {f'{size} ' if size else ''}{name} here."]
        except Exception:
            pass

        if seen:
            lines += ['', f"You see {grammatical_list(seen)}."]

        # Other players in the room
        try:
            others = [
                getattr(c, 'username', None) or 'someone'
                for addr, c in self.clients.items()
                if c is not client and getattr(c, 'room', None) == room_no
            ]
            if others:
                lines += ['', list_players_in_room(others)]
        except Exception:
            pass

        # TODO: Items: skip listing it in room contents if the item is already in the player's inventory.
        # Historically, this was the way The Land of Spur did it. It makes even more sense in a multiplayer
        # game: one player could hoard an item and others wouldn't be able to acquire it.

        try:
            exits = [compass_txts[k]
                     for k in getattr(room, 'exits', {})
                     if k in compass_txts]
            rc = int(getattr(room, 'exits', {}).get('rc', 0) or 0)
            if rc == 1:
                exits.append('Up')
            elif rc == 2:
                exits.append('Down')
            if exits:
                lines += ['', f"Ye may travel {oxford_comma_list(exits)}."]
        except Exception:
            pass

        return lines

    # -----------------------------------------------------------------------
    # Movement
    # -----------------------------------------------------------------------

    async def _move(self, ctx: GameContext, direction: str) -> None:
        """Move the player one step in direction — normal map exits only.

        Special exits (shoppe elevator, bar) are handled in MoveCommand
        before this method is called.
        """
        room_no = getattr(ctx.client, 'room', 1) or 1
        room    = (self.game_map.rooms.get(int(room_no))
                   if self.game_map else None)
        if not room:
            await ctx.send("Can't go there.")
            return

        dest = getattr(room, 'exits', {}).get(direction)
        if not dest:
            await ctx.send(f"Can't go {compass_txts[direction].lower()}.")
            return

        ctx.client.room = int(dest)
        await self._show_room(ctx)

    # -----------------------------------------------------------------------
    # Broadcast
    # -----------------------------------------------------------------------

    async def broadcast(self, sender_addr, message_obj) -> None:
        """Send a Message to all clients except the sender."""
        for addr, client in list(self.clients.items()):
            if addr == sender_addr:
                continue
            # Prefer sending via the client's own ctx if available
            client_ctx = getattr(client, 'ctx', None)
            if client_ctx:
                await client_ctx.send(message_obj.lines)
            else:
                w = getattr(client, 'writer', None)
                if w:
                    await self.send_message(w, message_obj)

    # -----------------------------------------------------------------------
    # Player quit
    # -----------------------------------------------------------------------

    async def _player_quit(self, ctx: GameContext) -> None:
        """Save player state and clean up on quit or disconnect."""
        player = ctx.player
        if player and not isinstance(player, GuestPlayer):
            try:
                player.save(force=True)
                logging.info('%s: player %s saved on quit',
                             ctx.client.addr, player.name)
            except Exception:
                logging.exception('Failed to save player on quit')

    # -----------------------------------------------------------------------
    # Server startup
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start both the JSON and PETSCII listeners."""
        try:
            json_server = await asyncio.start_server(
                self.handle_connection, self.host, self.port)
            petscii_server = await asyncio.start_server(
                self.handle_connection, self.host, self.petscii_port)
        except OSError:
            logging.exception('Failed to bind server')
            return

        logging.info('JSON server listening on %s:%d', self.host, self.port)
        logging.info('PETSCII server listening on %s:%d',
                     self.host, self.petscii_port)

        async with json_server, petscii_server:
            await asyncio.gather(
                json_server.serve_forever(),
                petscii_server.serve_forever(),
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='TADA server')
    parser.add_argument('--host',         default='127.0.0.1')
    parser.add_argument('--port',         type=int, default=DEFAULT_PORT)
    parser.add_argument('--petscii-port', type=int, default=PETSCII_PORT,
                        dest='petscii_port')
    parser.add_argument('--test-time',    type=float, default=0.0,
                        help='If >0, run the server for this many seconds and exit (useful for CI/diagnostics)')
    args = parser.parse_args()

    logging.basicConfig(
        level  = logging.INFO,
        format = '%(asctime)s %(levelname)s %(funcName)s: %(message)s',
    )

    server = Server(args.host, args.port, args.petscii_port)

    async def _run():
        task = asyncio.create_task(server.start())
        if args.test_time > 0:
            await asyncio.sleep(args.test_time)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        else:
            await task

    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, BrokenPipeError):
        logging.info('Server shut down.')
