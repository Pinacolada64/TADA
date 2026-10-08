"""commands/board/ — the threaded message board's command surface, split
into a package (Ryan's call for the sig-editor project -- see the
approved plan) instead of the old flat commands/board.py +
commands/board_edit.py + commands/board_reply.py trio, since Phase 2's
SIG/board editor and Phase 4's RA/SN commands are about to add several
more files to this same feature.

  board.py — BoardCommand (board/bb): listing, post, reply, delete, rn/ld
  edit.py  — 'board #edit' admin settings menu
  reply.py — the Prompt-Mode one-message-at-a-time interactive reader

Re-exports BoardCommand at the package level so `from commands.board
import BoardCommand` (existing call sites/tests) doesn't need touching.
CommandProcessor.discover() still finds BoardCommand itself inside
board.py, not here -- pkgutil.walk_packages() recurses into this
package's modules directly (see command_processor.py's own discover()),
and its "skip classes merely imported into this module" check means
this re-export doesn't cause double registration.
"""
from __future__ import annotations

from .board import BoardCommand  # noqa: F401

__all__ = ['BoardCommand']
