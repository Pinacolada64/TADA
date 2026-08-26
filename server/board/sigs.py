"""board/sigs.py — SIG (Special Interest Group) list storage for the
message board -- see board/__init__.py's module docstring for why this
got split out of the old top-level board.py.

One flat JSON file (run/server/board_sigs.json). List order *is*
persisted display order -- reordering a SIG, or the boards within one,
is just a list splice, no separate 'position' field:

    {
      "sigs": [
        {"id": 1, "name": "General", "board_ids": [1]}
      ]
    }

A board_id can appear in more than one SIG's board_ids list -- that's
"share between SIGs" (Ryan's call): one board object, referenced from
multiple SIGs, not copied/duplicated.

Not yet read by any command this phase (Phase 1: one default SIG holds
the one default board, but there's no SIG/board picker UI until Phase 2
-- see commands/board/board.py) -- exists now so migration.py has
somewhere to write the default SIG this pass, rather than adding this
file in a later phase and migrating a second time.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SIGS_FILE = Path('run') / 'server' / 'board_sigs.json'

# Phase 1: only one SIG exists, holding the one default board.
DEFAULT_SIG_ID = 1


def load_sigs(path: Optional[Path] = None) -> dict:
    """Return {'sigs': [...]}. {'sigs': []} if missing.

    path defaults to the module-level SIGS_FILE, looked up at call time
    (not bound at import) so tests can patch sigs.SIGS_FILE directly."""
    path = path or SIGS_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text())
            data.setdefault('sigs', [])
            return data
    except Exception:
        log.exception('Failed to load board sigs file %s', path)
    return {'sigs': []}


def save_sigs(sigs: dict, path: Optional[Path] = None) -> None:
    path = path or SIGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sigs, indent=2))
