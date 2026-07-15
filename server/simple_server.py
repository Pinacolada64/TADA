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
import random
from pathlib import Path

import net_common as nc
from net_client import Client
from network_context import GameContext, PETSCIINetworkContext, GuestPlayer
from formatting import flatten_send_args, format_lines, codec_for_settings, ANSI_COLOR_CODES
from tada_utilities import a_or_an, format_quote, grammatical_list, list_players_in_room, oxford_comma_list
from base_classes import Map, compass_txts
from items import Item, Rations, Weapon
from characters import Monster
from monsters import load_monsters, load_quotes, get_monster
from messages import load_messages, send_message
from commands.command_processor import create_command_processor
from commands.base_command import Mode
from terminal import Translation

DEFAULT_PORT = 34083
PETSCII_PORT = 34064

# Wild horse (monsters.json #136, a TADA extension -- no canonical SPUR
# placement exists) is randomized to one of these level-1 "Edge of Forest"
# rooms each time the server starts. Not persisted to level_1.json, so it
# moves on every restart. See MECHANICS.md's Horses section.
_WILD_HORSE_ROOMS = (30, 52, 68)
_WILD_HORSE_MONSTER_NUMBER = 136

# Matches encounters/dwarf.py's MONSTER_NUMBER -- not imported directly to
# avoid a load-time circular import (same reasoning as
# wild_horse_events.py's own copy of _WILD_HORSE_MONSTER_NUMBER).
_DWARF_MONSTER_NUMBER = 137

# Terminal-negotiation 'H<letter>' help text (Server._negotiate_terminal()) --
# an alpha tester reported being unsure which option to pick, so 'HA'/'HP'/
# 'HQ' explain each one, matching the h<key> convention used elsewhere
# (e.g. commands/prefs.py's prefs_menu()).
_TERMINAL_NEGOTIATION_HELP = {
    'A': (
        "ANSI color mode uses color and cursor formatting understood by "
        "most modern terminal emulators and telnet/SSH clients (PuTTY, "
        "iTerm2, Windows Terminal, the TADA prompt_toolkit client, etc). "
        "Pick this unless your screen fills with garbled text like "
        "'[33m' instead of actual color."
    ),
    'P': (
        "Plain text mode strips out all color and cursor formatting, "
        "showing only plain characters. Use this if ANSI mode showed "
        "garbled escape-code text, or if you're on a very old or basic "
        "terminal that doesn't understand ANSI codes."
    ),
    'Q': "Disconnects immediately without logging in.",
}

# Hidden exits (SPUR.MISC.S:419 "->"/"<-" markers): the marker itself only
# sets a boolean "exit exists" flag on the room, never a target, so the real
# destination has to be traced per-room against the SPUR source. Room.
# hidden_exit_east/west (base_classes.py) hold the *confirmed* destination
# once that tracing has been done. All 12 currently-known hidden-exit rooms
# are confirmed this way (see MECHANICS.md's Hidden exits entries) -- 10 via
# SPUR.MAIN.S:169-171's row arithmetic (cr +/-1, using each level's real row
# width from D.LEVEL{n}.TXT's header), one (level 1 room 89) via a hardcoded
# cross-level override, and one (level 5 room 140) kept as the well-evidenced
# cr+1 despite sitting on a row-arithmetic boundary -- see MECHANICS.md.
# _HIDDEN_EXIT_FLAGS/_HIDDEN_EXIT_DELTA and _hidden_exit_target() below
# remain only as a +/-1 guess fallback in case a new hidden-exit room turns
# up that hasn't been traced yet.
_HIDDEN_EXIT_FLAGS = {'e': 'hidden_exit_east', 'w': 'hidden_exit_west'}
_HIDDEN_EXIT_DELTA = {'e': 1, 'w': -1}

# Shown when an exit resolves to a room number with no actual data behind
# it (see Server._move()'s guard, and MECHANICS.md's "Flee / Travel" section
# for the level 3 rooms 39/86 rc/rt case this exists for) -- in-character
# flavor rather than a bare error, blaming SPUR's own legendary ineptitude
# as level architect rather than breaking immersion with a raw bug report.
_BLOCKED_ROOM_MESSAGES = [
    "A translucent hand reaches out of nowhere and gently pushes you back. "
    "\"Not that way just yet,\" booms a voice. \"One of my elves is still "
    "finishing the crayon work on that room.\" -- SPUR",
    "You feel a soft, ghostly resistance, like walking into a wall of "
    "pudding. \"Ah -- yes -- that passage,\" SPUR's voice mutters. \"We're "
    "aware of a 'computer programming bug,' whatever that is. The elves "
    "assure me it's nearly fixed.\"",
    "An invisible hand steadies you before you can wander off the edge of "
    "the known universe. \"Whoops!\" says SPUR. \"That room didn't survive "
    "the move to the new filing cabinet. Try the art gallery instead -- "
    "my crayon self-portrait is finally finished.\"",
]

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
        self.server         = None   # set in start(): the JSON asyncio.Server
        self.petscii_server = None   # set in start(): the PETSCII asyncio.Server

        self.server_init = Init()
        self._load_game_data()

    # -----------------------------------------------------------------------
    # Game data
    # -----------------------------------------------------------------------

    def _load_game_data(self):
        script_dir = Path(__file__).parent
        try:
            self.game_map = Map()
            for lvl in range(1, 8):
                level_file = script_dir / f'level_{lvl}.json'
                if level_file.exists():
                    self.game_map.read_map(str(level_file), level=lvl)
        except Exception:
            logging.exception('Failed to load map')
            self.game_map = None

        self._place_wild_horse()
        self._place_dwarf()

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
        try:
            self.monster_quotes = load_quotes(str(script_dir / 'monster_quotes.json'))
        except Exception as e:
            logging.warning("Could not load 'monster_quotes.json': %s", e)
            self.monster_quotes = {}
        try:
            self.messages = load_messages(str(script_dir / 'messages.json'))
        except Exception as e:
            logging.warning("Could not load 'messages.json': %s", e)
            self.messages = {}
        try:
            from books import load_books
            self.books = load_books(str(script_dir / 'books.json'))
        except Exception as e:
            logging.warning("Could not load 'books.json': %s", e)
            self.books = {}
        try:
            from banner import load_banner
            self.banner = load_banner(str(script_dir / 'graphics' / 'banner.ans'))
        except Exception as e:
            logging.warning("Could not load 'graphics/banner.ans': %s", e)
            self.banner = []
        # Items dropped by players during this session: room_number → list of InventoryEntry
        self.room_items: dict[int, list] = {}
        logging.info('Map: %d rooms | %d monsters | %d items | %d weapons',
                     len(self.game_map.rooms) if self.game_map else 0,
                     len(self.monsters), len(self.items), len(self.weapons))

    def _place_wild_horse(self) -> None:
        """Randomize which level-1 room holds the wild horse this session.

        Mutates the live Room object only -- never written back to
        level_1.json, so the location resets on every server restart.
        """
        if not self.game_map:
            return
        room_no = random.choice(_WILD_HORSE_ROOMS)
        room = self.game_map.rooms.get(room_no)
        if room:
            room.monster = _WILD_HORSE_MONSTER_NUMBER
            logging.info('Wild horse this session: room %d (%s)', room_no, room.name)

    def _place_dwarf(self) -> None:
        """Place the Dwarf in a random eligible level-1 room at server
        boot -- see encounters/dwarf.py for the full mechanic (theft,
        periodic relocation, combat encounter, hoard payout on death).

        Unlike the wild horse, his room persists in run/server/
        dwarf_state.json across restarts (relocate() only re-rolls once
        the configured interval has actually elapsed), so this is a no-op
        placement call -- maybe_relocate() (per-move) handles the real
        first-time placement/relocation logic.
        """
        if not self.game_map:
            return
        from encounters.dwarf import current_room, relocate
        if current_room() == 0:
            relocate(self.game_map)
        else:
            # Restore his monster slot on the room he was already in --
            # game_map is freshly loaded from disk every restart, so the
            # in-memory room.monster mutation from a prior session is gone.
            from encounters.dwarf import DWARF_LEVEL, MONSTER_NUMBER
            room = self.game_map.get_room(DWARF_LEVEL, current_room())
            if room is not None:
                room.monster = MONSTER_NUMBER

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
                '  C.  Not sure? Run a color test',
                '  Q.  Quit',
                '',
                "  Type 'H' followed by a letter (e.g. HA) for more info on an option.",
                '',
                '  On a real Commodore 64/128? Disconnect and reconnect on port '
                f'{PETSCII_PORT} instead -- this port is for ANSI/plain-text '
                'terminals only.',
                '',
            )
            while True:
                raw = await ctx.prompt('Terminal type [A/P/C/Q]')
                if raw is None:
                    logging.debug('EXIT False (disconnect)')
                    return False
                choice = raw.strip().upper()

                if len(choice) == 2 and choice[0] == 'H' and choice[1] in ('A', 'P', 'Q'):
                    await ctx.send(_TERMINAL_NEGOTIATION_HELP[choice[1]])
                    continue

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
                elif choice == 'C':
                    await ctx.send(
                        '',
                        '|red|This line should be RED.|reset|',
                        '|green|This line should be GREEN.|reset|',
                        '|blue|This line should be BLUE.|reset|',
                        '',
                    )
                    color_raw = await ctx.prompt('Did you see color above? (Y/N)')
                    if color_raw is None:
                        logging.debug('EXIT False (disconnect)')
                        return False
                    if color_raw.strip().lower().startswith('y'):
                        ctx.player.client_settings.translation = Translation.ANSI
                        await ctx.send('ANSI color mode set.')
                        logging.info('ANSI color mode set (via color test).')
                        break
                    else:
                        ctx.player.client_settings.translation = Translation.ASCII
                        await ctx.send('Plain text mode set.')
                        logging.info('Plain text mode set (via color test).')
                        break
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
        banner = getattr(self, 'banner', None)
        if banner:
            await ctx.send(banner)
        await ctx.send(
            '',
            "Type 'connect <username> <password>' to log in.",
            "Type 'connect guest' to look around as a guest.",
            "Type 'new' to create a new character.",
            "Type 'help' for help, 'help about' to learn what this is, or 'quit' to leave.",
            '',
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

        # A pending Blue Djinn hit contract (bar/blue_djinn.py's HIRE flow)
        # ambushes the target here, before the room is shown -- see
        # bar/thug_attack.py. Runs before _show_room() so combat happens
        # first, room description second (like waking up mid-fight).
        from bar.thug_attack import maybe_trigger_thug_attack
        await maybe_trigger_thug_attack(ctx)
        if getattr(ctx.player, 'hit_points', 1) <= 0:
            logging.debug('death triggered by thug ambush')
            await self._player_dies(ctx)

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
        player   = getattr(getattr(client, 'ctx', None), 'player', None)
        level    = int(getattr(player, 'map_level', 1) or 1)
        room     = (self.game_map.get_room(level, int(room_no))
                    if self.game_map else None)
        if not room:
            return ['You are nowhere (map not loaded).']

        from base_classes import RoomAlignment, strip_legacy_alignment_suffix
        from formatting import guild_sigil_for
        clean_name, is_hq = strip_legacy_alignment_suffix(room.name)
        client_ctx = getattr(client, 'ctx', None)
        sigil = guild_sigil_for(client_ctx, getattr(room, 'alignment', None)) if client_ctx else None
        if is_hq and client_ctx:
            hq_sigil = guild_sigil_for(client_ctx, RoomAlignment.HQ)
            sigil = f'{sigil} {hq_sigil}' if sigil else hq_sigil
        lines.append(f"{clean_name}{f'  {sigil}' if sigil else ''}")

        if getattr(room, 'desc', None):
            lines += ['', room.desc]

        seen = []

        # Items: skip listing it in room contents if the item is already in the player's inventory.
        # Historically, this was the way The Land of Spur did it. It it makes even more sense in a multiplayer
        # game: one player could hoard an item and others wouldn't be able to acquire it.

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
            mon_number = int(getattr(room, 'monster', 0) or 0)
            m = get_monster(self.monsters, mon_number) if mon_number else None
            if m is not None:
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
                elif mon_num == _DWARF_MONSTER_NUMBER:
                    # SPUR.MAIN.S: "A short bearded person is here, with a
                    # pile of gold!" -- own flavor line instead of the
                    # generic "There is DWARF here." (gold -> silver, this
                    # port's own wording convention).
                    lines += ['', 'A short bearded person is here, with a pile of silver!']
                else:
                    lines += ['', f"There is {f'{size} ' if size else ''}{name} here."]
        except Exception:
            pass

        if seen:
            lines += ['', f"You see {grammatical_list(seen)}."]

        # Other players in the room -- fighters get called out by name against
        # the monster they're fighting, rather than blending into the plain
        # "X is here" list, so someone walking in immediately sees a fight
        # already in progress.
        try:
            others = []
            for addr, c in self.clients.items():
                if c is client or getattr(c, 'room', None) != room_no:
                    continue
                if getattr(c, 'virtual_location', None):
                    continue
                # NOTE: named other_player, not player -- this used to
                # reassign the outer `player` (the viewer, set above at
                # this method's top) to whichever other client was seen
                # last in this loop, so anything read from `player` below
                # this block (e.g. the debug-mode flag check further
                # down) silently used a random *other* occupant's data
                # instead of the viewer's own, whenever the room wasn't
                # empty.
                other_player = getattr(getattr(c, 'ctx', None), 'player', None)
                name = getattr(other_player, 'name', None) or getattr(c, 'username', None) or 'someone'
                others.append((name, other_player))

            session = (getattr(self, 'active_combats', {}) or {}).get(room_no)
            fighting = set()
            if session and not session._done.is_set():
                for a_ctx in session.attackers:
                    a_name = getattr(getattr(a_ctx, 'player', None), 'name', None)
                    if a_name in (n for n, _ in others):
                        fighting.add(a_name)

            bystanders = [(n, p) for n, p in others if n not in fighting]
            if bystanders:
                lines += ['', list_players_in_room([n for n, _ in bystanders])]
                # Each bystander's personal quote (SPUR.MAIN.S:398's
                # gosub ply.loc7, shown right under "X is here" there);
                # "$" in it becomes the *viewer's* name, not the author's.
                for n, p in bystanders:
                    quote = format_quote(getattr(p, 'quote', None), player.name)
                    if quote:
                        lines.append(f'{n}: {quote}')
            if fighting:
                mname = session.monster.get('name', 'a monster')
                verb  = 'is' if len(fighting) == 1 else 'are'
                lines += ['', f'{oxford_comma_list(sorted(fighting))} {verb} fighting {mname} here!']
        except Exception:
            pass

        # Items: skip listing it in room contents if the item is already in the player's inventory.
        # Historically, this was the way The Land of Spur did it. It makes even more sense in a multiplayer
        # game: one player could hoard an item and others wouldn't be able to acquire it.

        try:
            debug = getattr(player, 'is_debug', False)
            exits_str = room.exits_txt(client_ctx)
            if exits_str:
                lines += ['', f"Ye may travel {exits_str}."]
            if debug:
                room_flags = getattr(room, 'flags', None) or []
                if room_flags:
                    lines.append(f"[DEBUG] Room flags: {', '.join(room_flags)}")
                for attr, label in (('hidden_exit_east', 'east'), ('hidden_exit_west', 'west')):
                    value = getattr(room, attr, None)
                    if value is not None:
                        lines.append(f"[DEBUG] Hidden exit {label} -> {value}")
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
        level   = int(getattr(ctx.player, 'map_level', 1) or 1)
        room    = (self.game_map.get_room(level, int(room_no))
                   if self.game_map else None)
        if not room:
            await ctx.send("Can't go there.")
            logging.debug('EXIT (no room) direction=%r', direction)
            return

        dest = room.get_exit(direction)
        target_level = level
        message_number = None
        if not dest:
            hidden = room.hidden_exit(direction, level)
            if hidden:
                target_level, dest, message_number = hidden.level, hidden.room, hidden.message_number
            else:
                dest = self._hidden_exit_target(room, direction, level)

        if not dest:
            # rc/rt transport system (see commands/movement.py's own rc/rt
            # comment): rc=1 -> Up, rc=2 -> Down, rt>0 -> real staircase to
            # that room number on the same level. rt==0 (shoppe elevator) is
            # intercepted before MoveCommand ever calls _move(), so only the
            # real-connection case reaches here.
            exits = getattr(room, 'exits', {})
            rc = int(exits.get('rc', 0) or 0)
            rt = int(exits.get('rt', 0) or 0)
            if rt and ((direction == 'u' and rc == 1) or (direction == 'd' and rc == 2)):
                dest = rt

        if not dest:
            await ctx.send(f"Can't go {compass_txts[direction].lower()}.")
            logging.debug('EXIT (no exit) direction=%r room=%r', direction, room_no)
            return

        if not self.game_map.get_room(target_level, int(dest)):
            # Exit data points at a room number with no actual data behind
            # it (see MECHANICS.md's "Flee / Travel" section -- e.g. level 3
            # rooms 39/86's rc/rt targets, lost or broken in SPUR's own
            # original data decades ago). Block the move instead of leaving
            # the player stranded on a "You are nowhere" room they can only
            # escape via teleport.
            logging.warning(
                'Blocked move into room with no data: level=%r room=%r '
                '(player=%r, direction=%r, from room=%r)',
                target_level, dest, getattr(ctx.player, 'name', '?'), direction, room_no,
            )
            await ctx.send(random.choice(_BLOCKED_ROOM_MESSAGES))
            logging.debug('EXIT (blocked, no room data) direction=%r dest=%r', direction, dest)
            return

        self._leave_combat_on_move(ctx, room_no)

        if target_level != level:
            await self._teleport_to(ctx, target_level, int(dest), message_number=message_number)
            return

        ctx.client.room = int(dest)
        ctx.player.map_room = int(dest)
        ctx.player.unsaved_changes = True
        logging.debug('EXIT moved to room=%r', dest)
        await self._show_room(ctx)
        from ally_events import try_ally_find_gold
        await try_ally_find_gold(ctx)
        from wild_horse_events import try_wandering_horse_encounter
        await try_wandering_horse_encounter(ctx)
        from encounters.dwarf import maybe_relocate, try_steal
        maybe_relocate(ctx)
        await try_steal(ctx)

    def _leave_combat_on_move(self, ctx: GameContext, room_no) -> None:
        """Drop *ctx* from an active fight's attacker list when they move
        away from the room it's in (bystanders only in practice -- the
        leader's connection is occupied by CombatSession._run_loop()'s
        own prompt for the fight's duration, so it can't normally reach
        _move() mid-fight). Without this, a bystander who joined then
        walked away stays in CombatSession.attackers -- e.g. still
        getting the "monster is slain!" notice, still eligible for a
        stray-round hit -- despite no longer being in the room.
        """
        active  = getattr(self, 'active_combats', {})
        session = active.get(room_no)
        if session and not session._done.is_set() and ctx in session.attackers:
            session._remove_attacker(ctx)

    def _hidden_exit_target(self, room, direction: str, level: int) -> int | None:
        """Guess a hidden_exit_east/west flag's target room via +/-1 adjacency.

        Fallback only, for rooms that carry the legacy hidden_exit_east/west
        flag string but have no confirmed Room.hidden_exit_east/west field
        yet (see base_classes.py). Unverified against the SPUR source -- see
        _HIDDEN_EXIT_FLAGS/_HIDDEN_EXIT_DELTA above. Confirms the candidate
        room actually exists before allowing the move (level 1's numbering
        has real gaps).
        """
        flag = _HIDDEN_EXIT_FLAGS.get(direction)
        room_flags = getattr(room, 'flags', None) or []
        if not flag or flag not in room_flags:
            return None

        candidate = int(room.number) + _HIDDEN_EXIT_DELTA[direction]
        target = self.game_map.get_room(level, candidate) if self.game_map else None
        if target:
            logging.debug('Hidden exit %r found in room %s (level %s) -> room %s (guessed)',
                          direction, room.number, level, candidate)
            return candidate

        logging.debug('Hidden exit %r found in room %s (level %s), but guessed '
                      'target room %s does not exist -- blocking the move',
                      direction, room.number, level, candidate)
        return None

    async def _teleport_to(self, ctx: GameContext, target_level: int, target_room: int,
                            *, message_number: int | None = None) -> None:
        """Move the player to a confirmed cross-level hidden-exit destination.

        Prints the room's own pre-move message (e.g. level 1 room 89's
        message #18, server/messages.json) if any, then the same "YOU HAVE
        ENTERED <level>!" banner SPUR's travel4 always shows on a level
        change (SPUR.MISC.S:457-464).
        """
        if message_number is not None:
            await send_message(ctx, message_number)
        ctx.player.map_level = target_level
        try:
            ctx.client.map_level = target_level
        except Exception:
            pass
        ctx.client.room = target_room
        ctx.player.map_room = target_room
        ctx.player.unsaved_changes = True
        from shoppe.elevator import level_name
        name = level_name(target_level)
        if name:
            await ctx.send(f'You have entered {name}!')
        logging.debug('Cross-level hidden exit -> level=%s room=%s', target_level, target_room)
        await self._show_room(ctx)
        from ally_events import try_ally_find_gold
        await try_ally_find_gold(ctx)
        from wild_horse_events import try_wandering_horse_encounter
        await try_wandering_horse_encounter(ctx)
        from encounters.dwarf import maybe_relocate, try_steal
        maybe_relocate(ctx)
        await try_steal(ctx)

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

        # Exposed so callers/tests can discover the bound port (self.port may
        # be 0 for an ephemeral port) via self.server.sockets[0].getsockname().
        self.server         = json_server
        self.petscii_server = petscii_server

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

    from config import config as server_config

    parser = argparse.ArgumentParser(description='TADA server')
    parser.add_argument('--host',         default='127.0.0.1')
    # Defaults come from server_config.json (config.py's ServerConfig,
    # editable via the in-game CONFIG command or setup/server_setup.py)
    # rather than the DEFAULT_PORT/PETSCII_PORT module constants directly,
    # so a sysop's saved ansi_port/petscii_port actually takes effect on
    # the next restart; --port/--petscii-port still override for one run.
    parser.add_argument('--port',         type=int, default=server_config.ansi_port)
    parser.add_argument('--petscii-port', type=int, default=server_config.petscii_port,
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
