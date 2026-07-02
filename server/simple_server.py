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
import contextvars
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
from monsters import load_monsters
from commands.command_processor import create_command_processor
from commands.base_command import Mode
from terminal import Translation

DEFAULT_PORT = 34083
PETSCII_PORT = 34064

# ---------------------------------------------------------------------------
# Per-connection logging context
# ---------------------------------------------------------------------------

# Set once per asyncio task; logging.Filter injects it into every LogRecord
# so the format string can show %(player)s without touching individual calls.
_player_ctx: contextvars.ContextVar[str] = contextvars.ContextVar('player', default='-')


class _PlayerFilter(logging.Filter):
    def filter(self, record):
        record.player = _player_ctx.get()
        return True


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
        try:
            self.monsters = load_monsters(str(script_dir / 'monsters.json'))
        except Exception as e:
            logging.warning("Could not load 'monsters.json': %s", e)
            self.monsters = []
        self.weapons  = _try_load(Weapon,  'weapons.json',  'read_weapons')
        self.rations  = _try_load(Rations, 'rations.json',  'read_rations')
        # Items dropped by players during this session: room_number → list of InventoryEntry
        self.room_items: dict[int, list] = {}
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
        _player_ctx.set(str(addr))
        logging.debug('ENTER port=%d', local_port)
        logging.info('New connection from %s on port %d', addr, local_port)

        from datetime import datetime
        client = Client()
        client.addr         = addr
        client.reader       = reader
        client.writer       = writer
        client.server       = self
        # to track connect/idle time for WHO:
        client.connected_at = datetime.now()
        client.last_input   = datetime.now()

        # Choose context type based on which port was connected to
        is_petscii = (local_port == self.petscii_port)
        if is_petscii:
            ctx = PETSCIINetworkContext.for_guest(reader, writer, self, client)
            logging.info('%s: PETSCII connection', addr)
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

            if not await self._negotiate_terminal(ctx):
                return

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
        logging.debug('ENTER')
        try:
            await self.send_message(ctx.writer, self.server_init)

            data = await self.receive_message(ctx.reader)
            if not data:
                logging.warning('no Init received')
                logging.debug('EXIT False (no Init received)')
                return False

            client_init = Init(**{k: v for k, v in data.items()
                                  if k in ('server_id', 'server_key',
                                           'protocol_version', 'translation')})

            if client_init.server_id != self.server_init.server_id:
                logging.warning('handshake failed — server ID mismatch (got %r)', client_init.server_id)
                await ctx.send('Handshake failed: server ID mismatch.')
                logging.debug('EXIT False (server_id mismatch)')
                return False
            if client_init.server_key != self.server_init.server_key:
                logging.warning('handshake failed — server key mismatch')
                await ctx.send('Handshake failed: server key mismatch.')
                logging.debug('EXIT False (server_key mismatch)')
                return False

            await self.send_message(
                ctx.writer,
                nc.Message(lines=['Handshake successful.'], mode=nc.Mode.login),
            )
            logging.info('handshake OK')
            logging.debug('EXIT True')
            return True

        except Exception:
            logging.exception('handshake error')
            logging.debug('EXIT False (exception)')
            return False

    # -----------------------------------------------------------------------
    # Terminal negotiation
    # -----------------------------------------------------------------------

    async def _negotiate_terminal(self, ctx: GameContext) -> bool:
        """
        Ask the player which terminal type / screen size they're using
        and update ctx.player.client_settings accordingly.

        PETSCII clients are already configured by PETSCIINetworkContext.for_guest();
        this step lets them confirm or adjust screen width (40 vs 80 col C128).

        Returns True to continue to login, False to disconnect immediately.
        """
        logging.debug('ENTER')
        translation = ctx.player.client_settings.translation

        if translation == Translation.PETSCII:
            while True:
                await ctx.send(
                    # Switch C64 to lowercase/uppercase character set so that
                    # bytes 0x41-0x5A display as lowercase a-z instead of
                    # uppercase A-Z (the default uppercase/graphics mode).
                    '|lowercase|TADA server',
                    '',
                    'Commodore client detected.',
                    '',
                    '4. 40 columns (C64 / C128 40-col)',
                    '8. 80 columns (C128 80-col)',
                    'Q. Quit',
                    ''
                    # TODO: in case client connected to wrong port or user's terminal in wrong mode,
                    #  offer option to switch to ASCII/ANSI
                )
                raw = await ctx.prompt('Screen width [4/8]')
                if raw is None:
                    logging.debug('EXIT False (disconnect)')
                    return False
                if raw.strip() == '8':
                    ctx.player.client_settings.screen_columns = 80
                    await ctx.send('80 column mode set.')
                    logging.info('80-column PETSCII mode set.')
                    break
                elif raw.strip() == '4':
                    ctx.player.client_settings.screen_columns = 40
                    await ctx.send('40 column mode set.')
                    logging.info('40-column PETSCII mode set.')
                    break
                elif raw.strip().lower() == 'q':
                    await ctx.send('Disconnecting - hope to see you again soon!')
                    await self._graceful_close(ctx.writer)
                    logging.debug('EXIT False (quit)')
                    return False
        else:
            # For ANSI/JSON clients, offer ANSI vs plain
            await ctx.send(
                '',
                'TADA — Terminal negotiation',
                '  A.  ANSI color (default)',
                '  P.  Plain text (no color)',
                '  Q.  Quit',
                '',
            )
            while True:
                raw = await ctx.prompt('Terminal type [A/P/Q]')
                if raw is None:
                    logging.debug('EXIT False (disconnect)')
                    return False
                choice = raw.strip().upper()
                if choice == 'P':
                    try:
                        ctx.player.client_settings.translation = Translation.ASCII
                        await ctx.send('Plain text mode set.')
                        logging.info('Plain text mode set.')
                        break
                    except Exception:
                        pass
                elif choice == 'A':
                    try:
                        ctx.player.client_settings.translation = Translation.ANSI
                        await ctx.send('ANSI color mode set.')
                        logging.info('ANSI color mode set.')
                        break
                    except Exception:
                        pass
                elif choice == 'Q':
                    await ctx.send('Disconnecting - hope to see you again soon!')
                    await self._graceful_close(ctx.writer)
                    logging.debug('EXIT False (quit)')
                    return False
        logging.debug('EXIT True')
        return True

    # -----------------------------------------------------------------------
    # Login
    # -----------------------------------------------------------------------

    async def _login(self, ctx: GameContext) -> bool:
        """
        Handle the login / character creation phase.
        Returns True if the player authenticated and should enter the game loop.
        Returns False on quit or disconnect.
        """
        logging.debug('ENTER')
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
                logging.debug('EXIT False (disconnect)')
                return False                    # clean disconnect
            if not raw.strip():
                continue

            logging.debug('login input: %r', raw.strip())
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
                _player_ctx.set(getattr(ctx.player, 'name', str(ctx.client.addr)))
                logging.debug('EXIT True (authenticated)')
                return True

            # QuitCommand signals that we should drop the connection
            if result.data.get('quit'):
                logging.debug('EXIT False (quit)')
                return False

    async def _authenticate(self, ctx: GameContext,
                            username: str, password: str):
        """
        Verify credentials and return a Player on success, None on failure.
        Sends its own error message on failure so the caller can just check
        the return value.
        """
        logging.debug('ENTER username=%r', username)
        import json
        user_file = Path('run') / 'server' / 'net' / f'login-{username}.json'
        try:
            if not user_file.exists():
                await ctx.send('Invalid username or password.')
                logging.debug('EXIT None (no user file)')
                return None
            with open(user_file) as f:
                data = json.load(f)
            if data.get('password') != password:
                await ctx.send('Invalid username or password.')
                logging.debug('EXIT None (wrong password)')
                return None
            # Load or create the Player object
            from player import Player
            p = Player(name=username, id=username)
            logging.info('authenticated as %s', username)
            logging.debug('EXIT Player(name=%r, hit_points=%r)', username, getattr(p, 'hit_points', '?'))
            return p
        except Exception:
            logging.exception('authentication error for %s', username)
            await ctx.send('Error accessing user data. Please try again.')
            logging.debug('EXIT None (exception)')
            return None

    # -----------------------------------------------------------------------
    # Game loop
    # -----------------------------------------------------------------------

    async def _game_loop(self, ctx: GameContext) -> None:
        """Main command loop for an authenticated (or guest) player."""
        logging.debug('ENTER')
        if not getattr(ctx.client, 'room', None):
            ctx.client.room = int(getattr(ctx.player, 'map_room', 1) or 1)
        await self._show_room(ctx)

        processor = ctx.client.command_processor

        while True:
            raw = await ctx.prompt('main')
            if raw is None:                     # clean EOF / disconnect
                logging.debug('EXIT (disconnect)')
                await self._player_quit(ctx)
                return
            if not raw.strip():
                continue

            logging.debug('command: %r hp=%r', raw.strip(), getattr(ctx.player, 'hit_points', '?'))
            from datetime import datetime
            ctx.client.last_input = datetime.now()
            result = await processor.process_input(raw, ctx=ctx)

            # QuitCommand sets data={'quit': True} to signal clean exit
            if result.data.get('quit'):
                logging.debug('EXIT (quit command)')
                await self._player_quit(ctx)
                return

            if not result.success and result.error == 'unknown_command':
                await ctx.send(f"Unknown command '{raw.strip().split()[0]}'. "
                               "Type 'help' for a list.")

            # Hunger/thirst tick (SPUR.COMBAT.S:12-20).
            from survival import survival_tick
            warnings = survival_tick(ctx.player)
            if warnings:
                await ctx.send(warnings)
            logging.debug('survival tick: hp=%r food=%r drink=%r',
                          getattr(ctx.player, 'hit_points', '?'),
                          getattr(ctx.player, 'food', '?'),
                          getattr(ctx.player, 'drink', '?'))
            if getattr(ctx.player, 'hit_points', 1) <= 0:
                logging.debug('death triggered')
                await self._player_dies(ctx)

    # -----------------------------------------------------------------------
    # Room display
    # -----------------------------------------------------------------------

    async def _show_room(self, ctx: GameContext) -> None:
        """Build and send the room description to ctx."""
        logging.debug('ENTER room=%r', getattr(ctx.client, 'room', '?'))
        lines = self._describe_room(ctx.client)
        await ctx.send(lines)
        logging.debug('EXIT room=%r lines=%d', getattr(ctx.client, 'room', '?'), len(lines))

    def _describe_room(self, client) -> list[str]:
        """Return a list of strings describing the client's current room."""
        logging.debug('ENTER room=%r', getattr(client, 'room', '?'))
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

        player     = getattr(getattr(client, 'ctx', None), 'player', None)
        picked_up  = getattr(player, 'picked_up_items', [])
        inventory  = getattr(player, 'inventory', None)

        for attr, collection in (('item',    self.items),
                                  ('food',    self.rations),
                                  ('weapon',  self.weapons)):
            try:
                idx = int(getattr(room, attr, 0) or 0) - 1
                if 0 <= idx < len(collection):
                    raw     = collection[idx]
                    name    = (raw.get('name') if isinstance(raw, dict)
                               else getattr(raw, 'name', None))
                    item_id = (raw.get('id_number', idx + 1) if isinstance(raw, dict)
                               else getattr(raw, 'id_number', idx + 1))
                    in_inventory = (inventory is not None and
                                    inventory.find(item_id=item_id) is not None)
                    if name and item_id not in picked_up and not in_inventory:
                        seen.append(name)
            except Exception:
                pass

        # Items dropped by players this session
        for entry in self.room_items.get(int(room_no), []):
            name = getattr(entry.item, 'name', None)
            if name:
                seen.append(name)

        try:
            mon_idx = int(getattr(room, 'monster', 0) or 0) - 1
            if 0 <= mon_idx < len(self.monsters):
                m = self.monsters[mon_idx]
                name    = m.get('name') if isinstance(m, dict) else getattr(m, 'name', 'a monster')
                size    = m.get('size') if isinstance(m, dict) else getattr(m, 'size', None)
                flags   = (m.get('flags') or {}) if isinstance(m, dict) else {}
                mon_num = m.get('number') if isinstance(m, dict) else None
                player  = getattr(getattr(client, 'ctx', None), 'player', None)
                mk      = getattr(player, 'monsters_killed', []) if player else []
                if mon_num is not None and mon_num in mk:
                    # Monster is dead for this player
                    if flags.get('mechanical'):
                        lines += ['', f'The wrecked remains of {name} lie here.']
                    else:
                        lines += ['', f'You see a dead {name} here.']
                    # TODO: fled (md=2) case — show tracks when monster-flee is implemented
                else:
                    lines += ['', f"There is {f'{size} ' if size else ''}{name} here."]
        except Exception:
            pass

        if seen:
            lines += ['', f"You see {grammatical_list(seen)}."]

        # Other players in the room
        try:
            others = []
            for addr, c in self.clients.items():
                if c is client or getattr(c, 'room', None) != room_no:
                    continue
                if getattr(c, 'virtual_location', None):
                    continue
                player = getattr(getattr(c, 'ctx', None), 'player', None)
                name = getattr(player, 'name', None) or getattr(c, 'username', None) or 'someone'
                others.append(name)
            if others:
                lines += ['', list_players_in_room(others)]
        except Exception:
            pass

        # Items: skip listing it in room contents if the item is already in the player's inventory.
        # Historically, this was the way The Land of Spur did it. It makes even more sense in a multiplayer
        # game: one player could hoard an item and others wouldn't be able to acquire it.

        try:
            debug = getattr(player, 'is_debug', False)
            exits_str = room.exits_txt(debug)
            if exits_str:
                lines += ['', f"Ye may travel {exits_str}."]
        except Exception:
            pass

        logging.debug('EXIT room=%r lines=%d', room_no, len(lines))
        return lines

    # -----------------------------------------------------------------------
    # Movement
    # -----------------------------------------------------------------------

    async def _move(self, ctx: GameContext, direction: str) -> None:
        """Move the player one step in direction — normal map exits only.

        Special exits (shoppe elevator, bar) are handled in MoveCommand
        before this method is called.
        """
        logging.debug('ENTER direction=%r room=%r', direction, getattr(ctx.client, 'room', '?'))
        room_no = getattr(ctx.client, 'room', 1) or 1
        room    = (self.game_map.rooms.get(int(room_no))
                   if self.game_map else None)
        if not room:
            await ctx.send("Can't go there.")
            logging.debug('EXIT (no room) direction=%r', direction)
            return

        dest = getattr(room, 'exits', {}).get(direction)
        if not dest:
            await ctx.send(f"Can't go {compass_txts[direction].lower()}.")
            logging.debug('EXIT (no exit) direction=%r room=%r', direction, room_no)
            return

        ctx.client.room = int(dest)
        ctx.player.map_room = int(dest)
        ctx.player.unsaved_changes = True
        logging.debug('EXIT moved to room=%r', dest)
        await self._show_room(ctx)
        from ally_events import try_ally_find_gold
        await try_ally_find_gold(ctx)

    # -----------------------------------------------------------------------
    # Broadcast
    # -----------------------------------------------------------------------

    @staticmethod
    async def _graceful_close(writer) -> None:
        """Flush pending writes and close the write-side of the socket.

        Calling writer.close() immediately after a send() can race with the
        client reading the last message: if there is still unread data in the
        receive buffer the OS may send RST instead of FIN, discarding data in
        the send buffer before the client sees it.  Draining then waiting for
        the close to complete gives the TCP stack time to deliver the farewell
        message before tearing down the connection.
        """
        try:
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

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
    # Player death
    # -----------------------------------------------------------------------

    async def _player_dies(self, ctx: GameContext) -> None:
        """Handle player death: send messages, strip penalties, respawn at room 1.

        Mirrors SPUR's DIE routine: player keeps their character but loses
        silver in hand and is returned to the starting room with minimum HP.
        Poison and disease are cleared (death cures everything).
        The game loop continues after this returns — no disconnect.
        """
        logging.debug('ENTER hp=%r', getattr(ctx.player, 'hit_points', '?'))
        player = ctx.player

        await ctx.send([
            '',
            '|red|* * * Y O U   H A V E   D I E D * * *|reset|',
            '',
        ])

        # Lose all silver carried in hand (SPUR death penalty).
        try:
            from base_classes import PlayerMoneyTypes
            lost = player.get_silver(PlayerMoneyTypes.IN_HAND)
            if lost:
                player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
                await ctx.send(f'You lost {lost:,} silver.')
        except Exception:
            logging.exception('could not strip silver')

        # Death cures poison and disease.
        player.poisoned = False
        player.diseased = False

        # Revive with minimum HP and full food/drink.
        player.hit_points = 10
        player.food       = 20
        player.drink      = 20

        # Respawn at room 1.
        player.map_room   = 1
        ctx.client.room   = 1
        player.unsaved_changes = True

        await ctx.send('You wake up at the entrance, confused but alive.')
        logging.debug('EXIT (respawned at room 1)')
        await self._show_room(ctx)

    # -----------------------------------------------------------------------
    # Player quit
    # -----------------------------------------------------------------------

    async def _player_quit(self, ctx: GameContext) -> None:
        """Save player state and clean up on quit or disconnect."""
        logging.debug('ENTER hp=%r', getattr(ctx.player, 'hit_points', '?'))
        player = ctx.player
        if player and not isinstance(player, GuestPlayer):
            try:
                # Sync room from client to player as a safety net in case any
                # movement path forgot to update player.map_room directly.
                current_room = getattr(ctx.client, 'room', None)
                if current_room is not None:
                    player.map_room = int(current_room)
                player.unsaved_changes = True
                player.save(force=True)
                logging.info('player saved on quit')
            except Exception:
                logging.exception('failed to save player on quit')
        logging.debug('EXIT')

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
        level  = logging.DEBUG,
        format = '%(asctime)s | %(levelname)-8s | %(player)-16s | %(module)s.%(funcName)s: %(message)s',
        force  = True,   # override any basicConfig() called by imported modules
    )
    logging.getLogger().handlers[0].addFilter(_PlayerFilter())

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
