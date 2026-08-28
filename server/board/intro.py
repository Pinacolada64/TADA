"""board/intro.py — SIG/board intro-screen storage paths.

An intro screen is an optional PETSCII/ANSI screen shown once a player
enters a SIG or a board (see commands/board/board.py's pick_board(),
which already sends a _welcome_lines() greeting at both of those same
two points -- this is the graphical/flavor-text companion to that
greeting, skipped for PlayerFlags.EXPERT_MODE players).

Deliberately *not* a new field in board_meta.json/board_sigs.json:
whether a SIG/board has an intro screen is just "does its file exist",
keyed off the SIG/board id via a fixed naming scheme -- one less piece
of metadata to keep in sync (create a screen, delete a screen, nothing
else to update). Reuses petscii_editor/store.py's existing
`[tokenized]`/`[raw_petscii]` file format as-is; only the directory and
naming convention are new.
"""
from __future__ import annotations

from pathlib import Path

INTROS_DIR = Path('run') / 'server' / 'board_intros'


def sig_intro_path(sig_id: int) -> Path:
    """On-disk path for SIG *sig_id*'s intro screen (shown once on
    entering the SIG, before any board within it is picked)."""
    return INTROS_DIR / f'sig-{sig_id}.canvas'


def board_intro_path(board_id: int) -> Path:
    """On-disk path for board *board_id*'s intro screen (shown once on
    entering that board, after any SIG-level intro screen)."""
    return INTROS_DIR / f'board-{board_id}.canvas'
