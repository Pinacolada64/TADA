#!/usr/bin/env python3
"""Fail the build if the resident client has grown into OVERLAY_BUF.

BACKUP_CHARS is the last floating label before the overlay area: the
2048 bytes of gothic_charset's glyph data, which double as the 2000-byte
BACKUP_CHARS/BACKUP_COLORS screen backup once the boot copy is done (see
tada-client.asm's BACKUP_CHARS comment). See tada-client.asm's
OVERLAY_BUF comment for why this collision keeps recurring as the
resident program grows.
"""
import re
import sys
from pathlib import Path

sym_file = Path(sys.argv[1] if len(sys.argv) > 1 else 'tada-client_pp.sym')
syms = {m.group(1): int(m.group(2), 16)
        for m in re.finditer(r'(\S+)\s+=\s+\$([0-9a-f]+)', sym_file.read_text())}
end = syms['backup_chars'] + 2048          # gothic_charset's full size
if syms['gothic_charset'] != syms['backup_chars']:
    sys.exit('ERROR: gothic_charset must start at BACKUP_CHARS -- see '
             "tada-client.asm's BACKUP_CHARS comment")
overlay_buf = syms['overlay_buf']
print(f'resident end ${end:04x}, OVERLAY_BUF ${overlay_buf:04x}, '
      f'margin {overlay_buf - end} bytes')
if end > overlay_buf:
    sys.exit('ERROR: BACKUP_CHARS/gothic_charset overlaps OVERLAY_BUF -- raise OVERLAY_BUF '
             'and every overlay module\'s orig to match')
