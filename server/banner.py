"""banner.py — login banner display.

server/graphics/banner.ans holds the login-screen ANSI art (sword, rose,
and "TADA" lettering) as plain lines with |token| color markup, same
convention as everything else that goes through formatting.py's
ansi_encode()/petscii_encode(). This module just loads and returns those
lines; the actual color/terminal rendering happens downstream in
ctx.send(), same as any other game text.

server/graphics/banner-petscii.txt holds a 40-column PETSCII-friendly
version of the banner for Commodore clients.

Loading actually goes through petscii_editor.store.load(), which also
understands the `[raw_petscii]` binary canvas format the in-game PETSCII
editor (commands/banner_edit.py) produces -- see that package's
docstring. A canvas gets rendered into the same `{glyph}`/`|token|` text
lines a hand-authored banner file would already contain, so ctx.send()
stays the single display path for both.
"""
from __future__ import annotations

import logging
from network_context import GameContext
from petscii_editor import store as canvas_store
from petscii_editor.canvas import Canvas, render_lines
from terminal import Translation


def load_banner(path: str) -> list[str]:
    """Load the banner file into a list of lines. Returns [] if missing."""
    result = canvas_store.load(path)
    if isinstance(result, Canvas):
        lines = render_lines(result)
    else:
        lines = result
    if lines:
        logging.info("Loaded %d-line banner from '%s'", len(lines), path)
    else:
        logging.warning("'%s' not found, login banner unavailable.", path)
    return lines


def load_banner_for(ctx: GameContext,
                    ansi_path: str,
                    petscii_path: str) -> list[str]:
    """
    Load the appropriate banner based on the client's terminal type.
    Falls back to the ANSI banner if the PETSCII banner is missing.
    """
    translation = ctx.player.client_settings.translation
    if translation == Translation.PETSCII:
        lines = load_banner(petscii_path)
        if lines:
            return lines
        logging.warning("PETSCII banner missing, falling back to ANSI banner.")
    return load_banner(ansi_path)