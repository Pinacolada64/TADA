"""board/migration.py — One-time migration from the old single-board
storage (board.json/board_config.json) into the SIG/board-aware storage
this package now uses (board_sigs.json/board_meta.json/
board_threads.json).

migrate_if_needed() is idempotent and safe to call repeatedly: it's a
no-op once any of the new files already exist, and a no-op if there was
never a legacy board.json/board_config.json to begin with (a genuinely
fresh install just gets its defaults from meta.get_board()/
threads.load_board()'s own "missing file" fallbacks, same as before --
no need to force-create files nobody's written to yet).

Deliberately NOT auto-invoked from threads.load_board()/meta.load_meta()/
sigs.load_sigs() -- those need to stay safe to call under test with only
the *new* file paths patched, without also reaching past the patch to
read whatever legacy board.json happens to exist on the real filesystem.
A one-time call site (server startup) is Phase 2+ wiring, out of scope
here -- see the sig-editor project plan's Phase 1 scope.

Legacy files are left untouched (rollback insurance) -- migrating only
ever writes the three new files.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from . import meta, sigs, threads

log = logging.getLogger(__name__)

_LEGACY_BOARD_FILE = Path('run') / 'server' / 'board.json'
_LEGACY_CONFIG_FILE = Path('run') / 'server' / 'board_config.json'

# The one board/SIG every pre-existing thread lands in.
_MIGRATED_BOARD_ID = 1
_MIGRATED_SIG_ID = 1
_MIGRATED_NAME = 'General'


def migrate_if_needed(
    legacy_board_path: Optional[Path] = None,
    legacy_config_path: Optional[Path] = None,
    sigs_path: Optional[Path] = None,
    meta_path: Optional[Path] = None,
    threads_path: Optional[Path] = None,
) -> bool:
    """Returns True if migration actually ran (and wrote the three new
    files), False if it was a no-op."""
    legacy_board_path = legacy_board_path or _LEGACY_BOARD_FILE
    legacy_config_path = legacy_config_path or _LEGACY_CONFIG_FILE
    sigs_path = sigs_path or sigs.SIGS_FILE
    meta_path = meta_path or meta.META_FILE
    threads_path = threads_path or threads.BOARD_FILE

    if sigs_path.exists() or meta_path.exists() or threads_path.exists():
        return False  # already migrated

    if not legacy_board_path.exists() and not legacy_config_path.exists():
        return False  # fresh install -- nothing legacy to carry forward

    legacy_threads = []
    if legacy_board_path.exists():
        try:
            legacy_threads = json.loads(legacy_board_path.read_text())
        except Exception:
            log.exception('Failed to read legacy board file %s during migration', legacy_board_path)
            legacy_threads = []

    legacy_anonymous_mode = 'ask'
    if legacy_config_path.exists():
        try:
            legacy_config = json.loads(legacy_config_path.read_text())
            legacy_anonymous_mode = legacy_config.get('anonymous_mode', 'ask')
        except Exception:
            log.exception('Failed to read legacy board config file %s during migration', legacy_config_path)

    # Every field preserved verbatim -- only 'board_id' is new.
    new_threads = []
    for thread in legacy_threads:
        migrated = dict(thread)
        migrated['board_id'] = _MIGRATED_BOARD_ID
        new_threads.append(migrated)

    new_meta = {'boards': {str(_MIGRATED_BOARD_ID): {
        'id': _MIGRATED_BOARD_ID,
        'name': _MIGRATED_NAME,
        'anonymous_mode': legacy_anonymous_mode,
        'access': {'type': 'any'},
        'admins': [],
    }}}

    new_sigs = {'sigs': [{
        'id': _MIGRATED_SIG_ID,
        'name': _MIGRATED_NAME,
        'board_ids': [_MIGRATED_BOARD_ID],
    }]}

    threads.save_board(new_threads, threads_path)
    meta.save_meta(new_meta, meta_path)
    sigs.save_sigs(new_sigs, sigs_path)
    log.info('BOARD MIGRATION: migrated %d thread(s) from legacy storage into board id %d',
              len(new_threads), _MIGRATED_BOARD_ID)
    return True
