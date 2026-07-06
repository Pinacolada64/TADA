"""messages.py — SPUR message-file emulation (server/messages.json).

The original SPUR source keeps a numbered "messages" data file and prints
from it via `a=N:gosub messages` (see MECHANICS.md's "Recovered SPUR
Messages" section for the full number -> subroutine -> feature
cross-reference). `server/messages.json` recovers 54 of those numbered
entries from `SPUR-data/SPUR Messages.txt`; this module loads that file
and prints from it the same way, by number, instead of features embedding
duplicate copies of the flavor text.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from network_context import GameContext


def load_messages(path: str) -> dict[int, list[str]]:
    """Load messages.json into {number: [paragraph, ...]}."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d messages from '%s'", len(data), path)
        return {int(k): v for k, v in data.items()}
    except FileNotFoundError:
        logging.warning("'%s' not found, messages unavailable.", path)
        return {}


def get_message(ctx: 'GameContext', number: int) -> Optional[list[str]]:
    """Return message `number`'s paragraphs from ctx.server.messages, or None."""
    messages = getattr(ctx.server, 'messages', None) or {}
    return messages.get(number)


async def send_message(ctx: 'GameContext', number: int) -> bool:
    """Print message `number` to ctx, if loaded. Returns whether it was sent."""
    paragraphs = get_message(ctx, number)
    if not paragraphs:
        logging.warning("send_message: message #%d not found or unloaded", number)
        return False
    await ctx.send(paragraphs)
    return True
