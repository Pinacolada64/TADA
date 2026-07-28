"""petscii_editor/store.py — persist named canvases to disk, and load
either format banner.py might encounter.

On-disk files carry an explicit first-line header tag rather than
relying on a filename/extension convention (Ryan's call: a `.bin` vs
`.txt` split would silently break the moment a file gets renamed or
copied) --

    [tokenized]      -- today's existing format: the rest of the file is
                        plain `|token|`/`{glyph}`-markup text lines, same
                        as banner.py.load_banner() has always read.
    [raw_petscii]     -- new: followed immediately by the 2000-byte
                        binary chars+colors payload (canvas.py's Canvas,
                        chars then colors, no wire framing -- that's
                        wire-format concern, not a file-format one).

A file with no recognised header tag is treated as legacy `[tokenized]`
content for backward compatibility with every banner file that predates
this module.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from petscii_editor.canvas import Canvas, WIDTH, HEIGHT
from text_editor import _sanitize_filename

log = logging.getLogger(__name__)

TAG_TOKENIZED = '[tokenized]'
TAG_RAW       = '[raw_petscii]'

CANVASES_DIR = Path(__file__).resolve().parent / 'canvases'


def path_for(name: str) -> Path:
    """Resolve a named banner/canvas to its on-disk path under
    petscii_editor/canvases/, sanitizing *name* the same way
    text_editor.py's user files do."""
    safe_name = _sanitize_filename(name)
    return CANVASES_DIR / f'{safe_name}.canvas'


def load(path: Union[str, Path]) -> Union[Canvas, list[str]]:
    """Return a Canvas for a `[raw_petscii]` file, or a list of text
    lines for a `[tokenized]` file (or one with no header tag at all --
    legacy content). [] if *path* doesn't exist."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    newline = data.find(b'\n')
    header = data if newline == -1 else data[:newline]
    header_str = header.decode('ascii', errors='replace').rstrip('\r')

    if header_str == TAG_RAW:
        body = data if newline == -1 else data[newline + 1:]
        cells = WIDTH * HEIGHT
        if len(body) != cells * 2:
            log.warning('%s: [raw_petscii] body is %d bytes, expected %d -- returning a blank canvas',
                        path, len(body), cells * 2)
            return Canvas()
        return Canvas(chars=bytearray(body[:cells]), colors=bytearray(body[cells:]))

    text = data.decode('utf-8', errors='replace')
    if header_str == TAG_TOKENIZED:
        text = text[newline + 1:] if newline != -1 else ''
    return text.splitlines()


def save(path: Union[str, Path], canvas: Canvas) -> None:
    """Write *canvas* to *path* as a `[raw_petscii]` file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = TAG_RAW.encode('ascii') + b'\n' + bytes(canvas.chars) + bytes(canvas.colors)
    path.write_bytes(body)


def save_tokenized(path: Union[str, Path], lines: list[str]) -> None:
    """Write *lines* to *path* as a `[tokenized]` file -- used for
    round-tripping today's plain-text banner format through the same
    header convention (not currently exercised by the editor itself,
    which only ever writes `[raw_petscii]`, but keeps the two writers
    symmetric with load())."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = TAG_TOKENIZED + '\n' + '\n'.join(lines)
    path.write_text(text, encoding='utf-8')
