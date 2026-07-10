"""banner.py — login banner display.

server/graphics/banner.ans holds the login-screen ANSI art (sword, rose,
and "TADA" lettering) as plain lines with |token| color markup, same
convention as everything else that goes through formatting.py's
ansi_encode()/petscii_encode(). This module just loads and returns those
lines; the actual color/terminal rendering happens downstream in
ctx.send(), same as any other game text.
"""
from __future__ import annotations

import logging


def load_banner(path: str) -> list[str]:
    """Load the banner file into a list of lines. Returns [] if missing."""
    try:
        with open(path) as f:
            lines = f.read().splitlines()
        logging.info("Loaded %d-line banner from '%s'", len(lines), path)
        return lines
    except FileNotFoundError:
        logging.warning("'%s' not found, login banner unavailable.", path)
        return []
