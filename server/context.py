# context.py
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# TADA imports:
import net_common as nc
from net_client import Client
from simple_server import Server

if TYPE_CHECKING:
    from player import Player

@dataclass
class GameContext:
    """Everything a command needs to do its job."""
    player: 'Player'
    reader: object   # asyncio.StreamReader
    writer: object   # asyncio.StreamWriter
    server: Server   # the Server instance
    client: Client   # the Client object

    async def send(self, *lines: str):
        """
        Send text to this player only. Calling this Generates a Message object.
        """
        msg = nc.Message(lines=list(lines), type=nc.MessageType.REGULAR,
                         mode=nc.Mode.app, prompt="main> ")
        await self.server.send_message(self.writer, msg)

    async def send_room(self, *lines: str, exclude_self=False):
        """Send text to all players in the same room."""
        my_room = getattr(self.client, 'room', None)
        for addr, other_client in self.server.clients.items():
            if exclude_self and other_client is self.client:
                continue
            if getattr(other_client, 'room', None) == my_room:
                w = getattr(other_client, 'writer', None)
                if w:
                    msg = nc.Message(lines=list(lines), type=nc.MessageType.REGULAR,
                                     mode=nc.Mode.app, prompt="main> ")
                    await self.server.send_message(w, msg)

    async def prompt(self, prompt_text: str = '',
                     preamble_lines: list[str] | None = None) -> str:
        """
        Send optional preamble lines and a prompt to the client,
        then await a single-line response.
        Mirrors TerminalContext.prompt() so all ctx-aware code works identically.
        """
        from net_common import Message, from_jsonb
        if preamble_lines:
            await self.send(preamble_lines)
        if not self.writer or not self.reader:
            return ''
        try:
            msg = Message(lines=[], prompt=prompt_text or '> ')
            await self.server.send_message(self.writer, msg)
            raw = await self.reader.readline()
            if not raw:
                return ''
            from net_common import from_jsonb
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
