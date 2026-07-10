"""books.py — SPUR book-text emulation (server/books.json).

`SPUR-data/SPUR.BOOKS.TXT` is a GBBS Pro message-base file (see
`tools/gbbsmsgtool.py`) holding the flavor text shown when a player READs
a book item. SPUR's own `read` subroutine (SPUR.MISC2.S:285) looks this up
by message number, keyed to the book's own item number (`bk$=dx$+
"spur.books":gosub read.bk`, `input #msg(a),n$` where `a` is the item's
number). `tools/gbbsmsgtool.py extract --pretty` recovered all 23 active
messages; each maps 1:1, in order, to the 23 book-type entries in
objects.json (confirmed by matching each recovered message's subject line
against the book's name -- e.g. message "SCROLL OF ANTI-MAGIC" ->
objects.json #88 "Scroll of Anti-Magic"). `server/books.json` stores that
mapping directly by item number, same shape as `server/messages.json`
({"N": ["paragraph", ...], ...}); this module loads and serves it the
same way.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from network_context import GameContext


def load_books(path: str) -> dict[int, list[str]]:
    """Load books.json into {item_number: [paragraph, ...]}."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d books from '%s'", len(data), path)
        return {int(k): v for k, v in data.items()}
    except FileNotFoundError:
        logging.warning("'%s' not found, book text unavailable.", path)
        return {}


def get_book_text(ctx: 'GameContext', item_number: int) -> Optional[list[str]]:
    """Return item_number's recovered book text from ctx.server.books, or None."""
    books = getattr(ctx.server, 'books', None) or {}
    return books.get(item_number)
