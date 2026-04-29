# context.py
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
