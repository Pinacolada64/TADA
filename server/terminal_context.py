#!/bin/env python3
"""
terminal_context.py

A GameContext-compatible object for local terminal use.
Satisfies the same interface as GameContext (send, send_room, reader, writer,
player, server, client) but uses print() and input() instead of asyncio
network streams.

Usage:
    import asyncio
    from terminal_context import TerminalContext

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

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Minimal player/settings stubs for local terminal use
# ---------------------------------------------------------------------------

@dataclass
class TerminalSettings:
    """Mimics player.client_settings for local terminal use."""
    screen_columns: int = 80
    screen_rows:    int = 24
    return_key:     str = 'Enter'


class TerminalPlayer:
    """
    Minimal Player-compatible stub for local terminal use.
    Provides the attributes and methods that tada_utilities functions
    expect from a Player object.
    """
    def __init__(self, name: str = 'Sysop'):
        self.name            = name
        self.client_settings = TerminalSettings()
        self._flags          = set()

    def query_flag(self, flag) -> bool:
        """Return True if the flag is set. Expert mode is off by default."""
        return flag in self._flags

    def set_flag(self, flag):
        self._flags.add(flag)

    def clear_flag(self, flag):
        self._flags.discard(flag)


# ---------------------------------------------------------------------------
# Fake stream objects so menu_system.py can check ctx.reader / ctx.writer
# ---------------------------------------------------------------------------

class _TerminalReader:
    """Wraps input() as an asyncio-compatible readline()."""
    async def readline(self) -> bytes:
        try:
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(None, input)
            import json
            # Return in the same wire format the real client uses
            return (json.dumps({'lines': [line]}) + '\n').encode()
        except EOFError:
            return b''


class _TerminalWriter:
    """Absorbs write/drain calls — output goes through ctx.send() instead."""
    def write(self, data: bytes):
        pass

    async def drain(self):
        pass


# ---------------------------------------------------------------------------
# TerminalContext
# ---------------------------------------------------------------------------

class TerminalContext:
    """
    GameContext-compatible context for local terminal use.

    Provides the same interface as GameContext so that any function
    taking a ctx argument works identically whether running locally
    or wired into the network server.

    Attributes mirroring GameContext:
        player  -- TerminalPlayer stub
        reader  -- _TerminalReader (wraps input())
        writer  -- _TerminalWriter (no-op)
        server  -- None (not available locally)
        client  -- None (not available locally)
    """

    def __init__(self, player_name: str = 'Sysop'):
        self.player = TerminalPlayer(name=player_name)
        self.reader = _TerminalReader()
        self.writer = _TerminalWriter()
        self.server = None
        self.client = None

    async def send(self, *lines):
        """
        Print lines to the terminal.
        Accepts the same calling styles as GameContext.send():
            await ctx.send("one line")
            await ctx.send("line one", "line two")
            await ctx.send(["line one", "line two"])   # list as first arg
        """
        for item in lines:
            if isinstance(item, list):
                for line in item:
                    print(line)
            else:
                print(item)

    async def send_room(self, *lines, exclude_self: bool = False):
        """No-op for local terminal — no other players in the room."""
        pass

    async def prompt(self,
                     prompt_text: str = '',
                     preamble_lines: list[str] | None = None) -> str:
        """
        Display optional preamble lines, then prompt for input.
        Returns the stripped input string.

        This is the preferred way to get input through ctx — it works
        for both TerminalContext and (once added) GameContext.
        """
        if preamble_lines:
            await self.send(preamble_lines)
        try:
            loop = asyncio.get_event_loop()
            suffix = ': ' if prompt_text and not prompt_text.endswith(' ') else ''
            result = await loop.run_in_executor(None, input, f'{prompt_text}{suffix}')
            return result.strip()
        except EOFError:
            return ''


# ---------------------------------------------------------------------------
# Convenience entry point for running async editors locally
# ---------------------------------------------------------------------------

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
