"""board/ — Threaded message board storage and rendering.

Split into a package (Ryan's call this pass) from the old flat
board.py, since the sig-editor project (multiple SIGs, each holding
multiple independently-configurable boards -- see MECHANICS.md and the
approved sig-editor plan) needs SIG/board metadata storage alongside
thread storage, not just the one board.json this used to be:

  sigs.py      -- SIG list storage (board_sigs.json)
  meta.py      -- per-board settings storage (board_meta.json) -- name,
                  anonymous-posting mode, access gating (Phase 3+),
                  admin list (Phase 2+) -- plus load_config()/
                  save_config() back-compat shims for the single
                  default board (id 1) that exists until Phase 2's
                  SIG/board editor lands
  threads.py   -- thread storage (board_threads.json, was board.json),
                  same shape as before plus a 'board_id' key per thread
  listing.py   -- MessageHeader and the thread/reply rendering helpers,
                  unchanged from the old board.py
  migration.py -- one-time, explicitly-invoked migration from the old
                  board.json/board_config.json into the files above
  intro.py     -- SIG/board intro-screen on-disk path helpers (Phase 4+)

Re-exports the same public API the old flat board.py module had, so
existing `import board` / `from board import X` call sites don't need
touching. Submodules are also exposed as attributes (board.threads,
board.meta, board.sigs) so tests can patch e.g. board.threads.BOARD_FILE
directly, the same way they used to patch board.BOARD_FILE.
"""
from __future__ import annotations

from . import meta, sigs, threads, migration, intro  # noqa: F401 -- exposed as attributes for direct/test access
from .listing import (
    MessageHeader,
    _HEADER_COLORS_BY_POSITION,
    _HEADER_FALLBACK_COLOR,
    build_quote_preamble,
    display_author,
    format_thread,
    format_thread_listing,
    format_thread_summary,
    render_message_lines,
)
from .meta import load_config, save_config
from .threads import is_new_since, load_board, new_status, next_id, save_board
from .access import is_board_admin, player_can_access, accessible_board_ids, visible_sigs
from .intro import sig_intro_path, board_intro_path

__all__ = [
    'meta', 'sigs', 'threads', 'migration', 'intro',
    'MessageHeader', 'build_quote_preamble', 'display_author', 'format_thread',
    'format_thread_listing', 'format_thread_summary', 'render_message_lines',
    'load_config', 'save_config', 'is_new_since', 'new_status', 'load_board', 'next_id', 'save_board',
    'is_board_admin', 'player_can_access', 'accessible_board_ids', 'visible_sigs',
    'sig_intro_path', 'board_intro_path',
]
