"""tips.py — "Tip of the day" storage and per-player cycling.

tips.json is a flat list of strings, converted once from SPUR-data/
tips.txt (SPUR's own login/shoppe tip screen). Each entry there started
with '>' and wrapped across several column-padded PRINT lines; the
conversion collapsed each into a single sentence-flow string.

Loaded fresh on every call (like commands/ban.py's load_bans()) rather
than cached, so an admin editing tips.json takes effect immediately.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

TIPS_FILE = Path(__file__).resolve().parent / 'tips.json'


def load_tips(path: Optional[Path] = None) -> list[str]:
    """Return the list of tip strings, in file order. [] if missing."""
    path = path or TIPS_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load tips file %s', path)
    return []


def next_tip(player) -> Optional[str]:
    """Advance player.command_settings.tips.tip_number to the next tip
    (1-based, wrapping back to 1 past the last one) and return its text,
    or None if tips.json has no tips.

    Shared by commands/tips.py's bare 'tips' command and the login-time
    display (commands/connect.py) -- both should advance the same
    counter, so a session's login tip and a manually-requested 'tips'
    right after don't repeat the same one.
    """
    tips = load_tips()
    if not tips:
        return None

    settings = player.command_settings
    next_number = settings.tips.tip_number + 1
    if next_number > len(tips):
        next_number = 1
    settings.tips.tip_number = next_number
    player.unsaved_changes = True

    return tips[next_number - 1]


def format_tip_box(ctx, tip: str, tip_number: int, total: int, width: int = 60) -> list[str]:
    """Wrap *tip* in a bordered box titled "Tip #x / y", matching the
    player's own border-style/terminal-codec preferences (same helpers
    commands/prefs.py uses for its own boxes)."""
    from formatting import titled_box

    return titled_box(
        ctx, f'Tip #{tip_number} / {total}', tip, width=width,
        frame_color='green',
        text_color='white',
        # magenta -- green's complement on the color wheel, so the
        # "Tip #x / y" heading pops against the green frame instead of
        # blending into it.
        title_color='magenta',
    )
