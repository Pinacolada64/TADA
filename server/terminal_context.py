#!/bin/env python3
"""
terminal_context.py

A GameContext-compatible object for local terminal use.
Satisfies the same interface as GameContext (send, send_room, reader, writer,
player, server, client) but uses print() and input() instead of asyncio
network streams.

Hierarchy:
    BaseContext          — interface only: send(), send_room(), prompt()
        TerminalContext  — local terminal (print/input), in terminal_context.py
        NetworkContext   — JSON wire protocol (Python client, web client)
            PETSCIINetworkContext  — raw bytes (Commodore 64/128 client)

    async def main():
        ctx = TerminalContext()
        await ctx.send("Hello from the terminal!")
        response = await ctx.prompt("What is your name?")
        await ctx.send(f"Hello, {response}!")

    asyncio.run(main())
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from formatting import (
    format_lines, codec_for_settings, flatten_send_args
    )

if TYPE_CHECKING:
    from simple_server import Server
    from net_client import Client
    from player import Player
    from terminal import Translation

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
        self.name       = 'Guest'
        self.flags      = {}
        self._flags_set = set()

        # Default settings — updated during terminal negotiation
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
    screen_columns: int   = 80
    screen_rows:    int   = 24
    return_key:     str   = 'Enter'
    translation:    object = None   # set during terminal negotiation

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
        raise NotImplementedError

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        raise NotImplementedError

    async def prompt(self,
                     prompt_text:    str       = '',
                     preamble_lines: list[str] | None = None) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# GameContext — server-side base (JSON wire protocol)
# ---------------------------------------------------------------------------

@dataclass
class GameContext(BaseContext):
    """
    Context for a connected player using the JSON wire protocol.
    Used by Python clients, web clients, and any ANSI terminal that
    speaks the TADA JSON Message format.

    Attributes:
        player:  Player object (or GuestPlayer before login)
        reader:  asyncio.StreamReader
        writer:  asyncio.StreamWriter
        server:  Server instance
        client:  Client object (holds addr, username, mode, etc.)
    """
    player: 'Player'
    reader: object          # asyncio.StreamReader
    writer: object          # asyncio.StreamWriter
    server: 'Server'
    client: 'Client'

    # Prompt text shown to the player; updated by menu/command code
    _prompt: str = field(default='> ', repr=False)

    # ---------------------------------------------------------------------------
    # Core I/O
    # ---------------------------------------------------------------------------

    async def send(self, *lines) -> None:
        """
        Format and send text to this player over the JSON wire.
        Lines are word-wrapped and bracket-highlighted for this player's
        terminal settings before being packed into a Message.

        Format and print lines to the terminal.
        Accepts the same calling styles as GameContext.send():
            await ctx.send("one line")
            await ctx.send("line one", "line two")
            await ctx.send(["line one", "line two"])   # list as first arg

        Lines are word-wrapped and bracket-highlighted according to the
        player's ClientSettings before printing.
        """
        # Flatten args into a single list of strings
        raw       = flatten_send_args(*lines)
        codec     = codec_for_settings(self.player.client_settings)
        formatted = format_lines(raw, self.player.client_settings, codec)
        msg = nc.Message(
            lines   = formatted,
            type    = nc.MessageType.REGULAR,
            mode    = nc.Mode.app,
            prompt  = self._prompt,
        )
        await self.server.send_message(self.writer, msg)

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        """Send text to all players in the same room as this player."""
        my_room = getattr(self.client, 'room', None)
        raw     = flatten_send_args(*lines)
        codec   = codec_for_settings(self.player.client_settings)

        for addr, other_client in self.server.clients.items():
            if exclude_self and other_client is self.client:
                continue
            if getattr(other_client, 'room', None) != my_room:
                continue
            w = getattr(other_client, 'writer', None)
            if not w:
                continue
            # Format for each recipient's own settings
            other_player   = getattr(other_client, 'player', self.player)
            other_codec    = codec_for_settings(other_player.client_settings)
            other_settings = other_player.client_settings
            formatted      = format_lines(raw, other_settings, other_codec)
            msg = nc.Message(lines=formatted, type=nc.MessageType.REGULAR,
                             mode=nc.Mode.app, prompt=self._prompt)
            await self.server.send_message(w, msg)

    async def prompt(self,
                     prompt_text:    str            = '',
                     preamble_lines: list[str] | None = None) -> str:
        """
        Send optional preamble lines and a prompt, then await a single-line
        response from the client. Returns the stripped response string.
        """
        from net_common import from_jsonb

        if preamble_lines:
            await self.send(preamble_lines)

        # Send the prompt as a Message with no lines, just a prompt field
        msg = nc.Message(lines=[], prompt=prompt_text or '> ')
        await self.server.send_message(self.writer, msg)

        try:
            raw = await self.reader.readline()
            if not raw:
                return ''
            obj = from_jsonb(raw)
            if isinstance(obj, dict):
                lines = obj.get('lines')
                if isinstance(lines, list) and lines:
                    return str(lines[0]).strip()
                return str(obj.get('text', '')).strip()
            return ''
        except Exception:
            logging.exception('GameContext.prompt: error reading response')
            return ''

    # ---------------------------------------------------------------------------
    # Convenience helpers
    # ---------------------------------------------------------------------------

    def set_prompt(self, text: str) -> None:
        """Update the prompt string shown after each send()."""
        self._prompt = text

    @classmethod
    def for_guest(cls, reader, writer, server, client) -> 'GameContext':
        """
        Create a GameContext with a GuestPlayer stub.
        Use this during the pre-login / terminal-negotiation phase.
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

    Instead of wrapping output in JSON Message objects, sends raw PETSCII
    bytes directly. |token| color sequences are spliced in as control bytes;
    text is encoded via cbmcodecs2.

    Terminal negotiation should set:
        ctx.player.client_settings.translation = Translation.PETSCII
        ctx.player.client_settings.screen_columns = 40  (or 80 for C128)
    """

    # Commodore line ending is CR (0x0D)
    LINE_ENDING: bytes = b'\r'

    # cbmcodecs2 codec name — override for uppercase/graphics mode
    CODEC_NAME: str = 'petscii_c64en_lc'

    async def send(self, *lines) -> None:
        """
        Format and send text as raw PETSCII bytes.
        No JSON envelope — bytes go straight to the Commodore client.
        """
        from formatting import PETSCIICodec
        raw       = flatten_send_args(*lines)
        codec     = PETSCIICodec()
        formatted = format_lines(raw, self.player.client_settings, codec)
        encoded   = petscii_encode_lines(
            formatted,
            codec_name   = self.CODEC_NAME,
            line_ending  = self.LINE_ENDING,
        )
        try:
            self.writer.write(encoded)
            await self.writer.drain()
        except Exception:
            logging.exception('PETSCIINetworkContext.send: write error')

    async def prompt(self,
                     prompt_text:    str            = '',
                     preamble_lines: list[str] | None = None) -> str:
        """
        Send preamble + prompt as raw PETSCII bytes, then read a CR-terminated
        line of raw bytes from the Commodore client and decode it.
        """
        from formatting import PETSCIICodec, petscii_encode
        if preamble_lines:
            await self.send(preamble_lines)

        if prompt_text:
            encoded = petscii_encode(prompt_text, self.CODEC_NAME)
            self.writer.write(encoded)
            await self.writer.drain()

        try:
            # Commodore sends CR-terminated lines
            raw = await self.reader.readuntil(b'\r')
            # Strip CR and any trailing nulls, decode as ASCII
            text = raw.rstrip(b'\r\x00').decode('ascii', errors='replace').strip()
            return text
        except asyncio.IncompleteReadError:
            return ''
        except Exception:
            logging.exception('PETSCIINetworkContext.prompt: read error')
            return ''

    async def send_room(self, *lines, exclude_self: bool = False) -> None:
        """
        Broadcast to other players in the same room.
        Each recipient gets output formatted for their own context type.
        """
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
    def for_guest(cls,
                  reader, writer, server, client,
                  screen_columns: int = 40) -> 'PETSCIINetworkContext':
        """
        Create a PETSCIINetworkContext with a GuestPlayer stub configured
        for a Commodore client (40 columns, PETSCII translation).
        """
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


def run_local(coro):
    """
    Run an async coroutine in a local terminal context.
    Convenience wrapper around asyncio.run() for editor entry points.

    Usage:
        from terminal_context import TerminalContext, run_local

        async def main():
            ctx = TerminalContext()
            # ... editor code ...

        if __name__ == '__main__':
            run_local(main())
    """
    asyncio.run(coro)