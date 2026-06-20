#!/bin/env python3
"""
network_context.py

Context objects passed to all commands and editor functions.

Hierarchy:
    BaseContext          — interface only: send(), send_room(), prompt()
        TerminalContext  — local terminal (print/input), in terminal_context.py
        NetworkContext   — JSON wire protocol (Python client, web client)
            PETSCIINetworkContext  — raw bytes (Commodore 64/128 client)

All subclasses satisfy the same interface so game code never needs to know
which transport it is talking to.

Import order (no circular imports):
    net_common           <- no TADA imports
    net_client           <- net_common only
    formatting           <- no TADA imports
    terminal             <- formatting
    terminal_context     <- formatting, terminal
    context              <- net_common, net_client, formatting, terminal
                           (TYPE_CHECKING only: simple_server)
    simple_server        <- context, net_common, net_client, terminal, ...
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import net_common as nc
from formatting import (
    format_lines, codec_for_settings, flatten_send_args,
    ansi_encode_lines, petscii_encode_lines, ANSICodec, PlainCodec,
)

if TYPE_CHECKING:
    # These are only needed for type annotations, never at runtime.
    # Keeping them here breaks the circular import:
    #   simple_server -> context -> simple_server
    from simple_server import Server
    from net_client import Client
    from player import Player


# ---------------------------------------------------------------------------
# GuestPlayer — pre-login stub
# ---------------------------------------------------------------------------

class GuestPlayer:
    """
    Minimal Player-compatible stub used before a user authenticates.

    Provides the attributes that ctx and formatting code need without
    loading or creating a real Player record. Replaced by a real Player
    object after successful login.
    """
    def __init__(self):
        self.name        = 'Guest'
        self.flags       = {}
        self._flags_set  = set()
        self.client_settings = _GuestSettings()

    def query_flag(self, flag) -> bool:
        return flag in self._flags_set

    def set_flag(self, flag):
        self._flags_set.add(flag)

    def clear_flag(self, flag):
        self._flags_set.discard(flag)

    def __str__(self):
        return f'{self.name} <Guest>'


@dataclass
class _GuestSettings:
    """ClientSettings-compatible stub for GuestPlayer."""
    screen_columns: int    = 80
    screen_rows:    int    = 24
    return_key:     str    = 'Enter'
    translation:    object = None

    def __post_init__(self):
        try:
            from terminal import Translation
            self.translation = Translation.ANSI
        except ImportError:
            self.translation = None


# ---------------------------------------------------------------------------
# BaseContext — shared interface
# ---------------------------------------------------------------------------

class BaseContext:
    """
    Abstract base defining the interface all context objects must provide.
    Game code should type-hint against BaseContext (or GameContext for
    server-side code that needs server/client access).
    """

    async def send(self, *lines) -> None:
        """Send lines to the player, paginating automatically if they exceed screen height."""
        raise NotImplementedError

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        raise NotImplementedError

    async def prompt(self,
                     prompt_text:    str            = '',
                     preamble_lines: list[str] | None = None) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# GameContext — JSON wire protocol
# ---------------------------------------------------------------------------

@dataclass
class GameContext(BaseContext):
    """
    Context for a connected player using the JSON wire protocol.
    Used by Python clients, web clients, and ANSI terminals that
    speak the TADA JSON Message format.

    Attributes:
        player:  Player object (or GuestPlayer before login)
        reader:  asyncio.StreamReader
        writer:  asyncio.StreamWriter
        server:  Server instance  (type-checked only, no runtime import)
        client:  Client object    (type-checked only, no runtime import)
    """
    player: 'Player | GuestPlayer'
    reader: object      # asyncio.StreamReader
    writer: object      # asyncio.StreamWriter
    server: 'Server'    # no runtime import — see TYPE_CHECKING above
    client: 'Client'    # no runtime import — see TYPE_CHECKING above

    _prompt: str = field(default='> ', repr=False)

    # -----------------------------------------------------------------------
    # Core I/O
    # -----------------------------------------------------------------------

    async def send(self, *lines) -> None:
        """
        Format and send text to this player over the JSON wire.
        Lines are word-wrapped and bracket-highlighted for this player's
        terminal settings before being packed into a Message.
        Automatically paginates when output exceeds the player's screen height.
        """
        from formatting import (
            format_lines, codec_for_settings, flatten_send_args,
            ansi_encode_lines, plain_encode_lines, petscii_encode_lines, ANSICodec, PlainCodec,
        )
        raw = flatten_send_args(*lines)
        codec = codec_for_settings(self.player.client_settings)
        formatted = format_lines(raw, self.player.client_settings, codec)
        if isinstance(codec, ANSICodec):
            formatted = ansi_encode_lines(formatted)
        elif isinstance(codec, PlainCodec):
            formatted = plain_encode_lines(formatted)

        page_size = max(1, self.player.client_settings.screen_rows - 1)
        if len(formatted) > page_size:
            await self._paginate(formatted, page_size)
        else:
            await self._send_formatted(formatted)

    async def _send_formatted(self, formatted: list[str]) -> None:
        """Send pre-formatted lines over the JSON wire without pagination."""
        msg = nc.Message(
            lines=formatted,
            type=nc.MessageType.REGULAR,
            mode=nc.Mode.app,
            prompt=self._prompt,
        )
        await self.server.send_message(self.writer, msg)

    async def _paginate(self, formatted: list[str], page_size: int) -> None:
        """Send formatted lines one screenful at a time with navigation.

        Enter / empty — next page
        B or -        — previous page
        Q             — stop reading early
        """
        total      = len(formatted)
        total_pgs  = max(1, (total + page_size - 1) // page_size)
        idx        = 0

        while True:
            page   = formatted[idx:idx + page_size]
            await self._send_formatted(page)

            at_end    = idx + len(page) >= total
            cur_pg    = (idx // page_size) + 1
            pg_info   = f'({cur_pg}/{total_pgs}) ' if total_pgs > 1 else ''
            status    = f'-- {"End" if at_end else "More"} {pg_info}--'

            opts: list[str] = []
            if not at_end:
                opts.append('Enter')
            if idx > 0:
                opts.append('B/-: back')
            opts.append('Q: quit')

            ui = await self.prompt(f'{status} {", ".join(opts)}')
            if ui is None:
                return
            ui = ui.lower().strip()

            if ui == 'q':
                return
            elif ui in ('b', '-') and idx > 0:
                idx = max(0, idx - page_size)
            elif at_end:
                return
            else:
                idx += page_size

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        """Send text to all players in the same room, formatted per recipient."""
        my_room = getattr(self.client, 'room', None)
        raw     = flatten_send_args(*lines)

        for addr, other_client in self.server.clients.items():
            if exclude_self and other_client is self.client:
                continue
            if getattr(other_client, 'room', None) != my_room:
                continue
            w = getattr(other_client, 'writer', None)
            if not w:
                continue
            other_player   = getattr(other_client, 'player', self.player)
            other_codec    = codec_for_settings(other_player.client_settings)
            formatted      = format_lines(raw, other_player.client_settings,
                                          other_codec)
            msg = nc.Message(lines=formatted, type=nc.MessageType.REGULAR,
                             mode=nc.Mode.app, prompt=self._prompt)
            await self.server.send_message(w, msg)

    async def prompt(self,
                     prompt_text:    str            = '',
                     preamble_lines: list[str] | None = None) -> str:
        """
        Send optional preamble + a prompt, then await a single-line
        JSON response. Returns the stripped response string.
        """
        from net_common import from_jsonb

        if preamble_lines:
            await self.send(preamble_lines)

        msg = nc.Message(lines=[], prompt=f"{prompt_text}> " or '> ')
        await self.server.send_message(self.writer, msg)

        try:
            raw = await self.reader.readline()
            if not raw:
                return None     # EOF — client disconnected cleanly
            obj = from_jsonb(raw)
            if isinstance(obj, dict):
                lines = obj.get('lines')
                if isinstance(lines, list) and lines:
                    return str(lines[0]).strip()
                return str(obj.get('text', '')).strip()
            return ''
        except asyncio.IncompleteReadError:
            return None         # EOF mid-stream — client dropped
        except Exception:
            logging.exception('GameContext.prompt: error reading response')
            return None         # treat unrecoverable errors as disconnect

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def set_prompt(self, text: str) -> None:
        """Update the prompt string appended to each send()."""
        self._prompt = text

    @classmethod
    def for_guest(cls, reader, writer, server, client) -> 'GameContext':
        """
        Create a GameContext with a GuestPlayer stub for the pre-login phase.
        Replace ctx.player with a real Player after authentication.
        """
        return cls(
            player = GuestPlayer(),
            reader = reader,
            writer = writer,
            server = server,
            client = client,
        )


# ---------------------------------------------------------------------------
# PETSCIINetworkContext — raw bytes for Commodore clients
# ---------------------------------------------------------------------------

class PETSCIINetworkContext(GameContext):
    """
    GameContext variant for Commodore 64/128 clients.

    Sends raw PETSCII bytes directly instead of JSON Message objects.
    |token| color sequences are spliced in as raw control bytes;
    text is encoded via cbmcodecs2.
    """

    LINE_ENDING: bytes = b'\r'          # Commodore CR
    CODEC_NAME:  str   = 'petscii_c64en_lc'

    async def send(self, *lines) -> None:
        """Encode and send as raw PETSCII bytes — no JSON envelope.
        Automatically paginates when output exceeds the player's screen height."""
        from formatting import PETSCIICodec
        raw       = flatten_send_args(*lines)
        codec     = PETSCIICodec()
        formatted = format_lines(raw, self.player.client_settings, codec)

        page_size = max(1, self.player.client_settings.screen_rows - 1)
        if len(formatted) > page_size:
            await self._paginate(formatted, page_size)
        else:
            await self._send_formatted(formatted)

    async def _send_formatted(self, formatted: list[str]) -> None:
        """Send pre-formatted lines as raw PETSCII bytes without pagination."""
        encoded = petscii_encode_lines(formatted,
                                       codec_name     = self.CODEC_NAME,
                                       line_ending    = self.LINE_ENDING,
                                       screen_columns = self.player.client_settings.screen_columns)
        try:
            self.writer.write(encoded)
            await self.writer.drain()
        except Exception:
            logging.exception('PETSCIINetworkContext._send_formatted: write error')

    async def prompt(self,
                     prompt_text:    str            = '',
                     preamble_lines: list[str] | None = None) -> str:
        """Send raw PETSCII prompt, read CR-terminated response."""
        from formatting import petscii_encode
        if preamble_lines:
            await self.send(preamble_lines)
        if prompt_text:
            # CR before prompt so it starts on a fresh line
            self.writer.write(self.LINE_ENDING + petscii_encode(prompt_text, self.CODEC_NAME))
            await self.writer.drain()
        try:
            raw = await self.reader.readuntil(b'\r')
            text = raw.rstrip(b'\r\x00').decode('ascii', errors='replace').strip()
            # Echo input back so the player sees what they typed, then CR to
            # advance the cursor before any response is sent.
            self.writer.write(text.encode('ascii', errors='replace') + self.LINE_ENDING)
            await self.writer.drain()
            return text
        except asyncio.IncompleteReadError:
            return None         # EOF — Commodore client disconnected
        except Exception:
            logging.exception('PETSCIINetworkContext.prompt: read error')
            return None

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        """Broadcast via each recipient's own ctx so encoding is correct."""
        my_room = getattr(self.client, 'room', None)
        for addr, other_client in self.server.clients.items():
            if exclude_self and other_client is self.client:
                continue
            if getattr(other_client, 'room', None) != my_room:
                continue
            other_ctx = getattr(other_client, 'ctx', None)
            if other_ctx:
                await other_ctx.send(*lines)

    @classmethod
    def for_guest(cls, reader, writer, server, client,
                  screen_columns: int = 40) -> 'PETSCIINetworkContext':
        """Create with a 40-col PETSCII GuestPlayer for a Commodore client."""
        from terminal import Translation
        guest = GuestPlayer()
        guest.client_settings.translation    = Translation.PETSCII
        guest.client_settings.screen_columns = screen_columns
        guest.client_settings.screen_rows    = 25
        guest.client_settings.return_key     = 'Return'
        return cls(
            player = guest,
            reader = reader,
            writer = writer,
            server = server,
            client = client,
        )
