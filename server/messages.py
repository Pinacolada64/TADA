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
    """Return message `number`'s paragraphs from ctx.server.messages, or None.

    Nested getattr(): a ctx without a .server at all (e.g. a lightweight
    test fixture) would otherwise raise on the plain `ctx.server` access
    before the outer getattr's default could ever help -- see
    editplayer.py's identical pattern.
    """
    messages = getattr(getattr(ctx, 'server', None), 'messages', None) or {}
    return messages.get(number)


async def send_message(ctx: 'GameContext', number: int, **context) -> bool:
    """Print message `number` to ctx, if loaded. Returns whether it was sent.

    Some recovered messages reference a specific character's pronoun (e.g.
    #34's "leads {HORSE_OBJECTIVE} away", where the horse's own gender
    should decide the word, not a hardcoded "him"). Pass named placeholders
    as kwargs -- e.g. `send_message(ctx, 34, HORSE_OBJECTIVE=get_pronoun(mount,
    PronounType.OBJECTIVE))` -- and they're substituted via str.format().

    Deliberately NOT a mini-expression-language (no function calls embedded
    in the JSON text) -- the message data stays inert, plain text; only the
    caller decides what values to resolve and pass in. Messages that don't
    reference any placeholder are unaffected -- formatting is skipped
    entirely when no context is given, so a stray "{" in ordinary prose
    (there isn't one today, but nothing guarantees there won't be) can't
    raise on calls that don't opt into this.
    """
    paragraphs = get_message(ctx, number)
    if not paragraphs:
        logging.warning("send_message: message #%d not found or unloaded", number)
        return False
    if context:
        try:
            paragraphs = [p.format(**context) for p in paragraphs]
        except (KeyError, IndexError):
            logging.exception(
                "send_message: failed to format message #%d with %r", number, context)
    await ctx.send(paragraphs)
    return True
