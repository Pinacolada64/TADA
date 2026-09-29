#!/usr/bin/env python3
"""Fail the build if the resident client has grown into OVERLAY_BUF.

BACKUP_COLORS (1000 bytes) is the last floating label before the overlay
area; see tada-client.asm's OVERLAY_BUF comment for why this collision
keeps recurring as the resident program grows.
"""
import re
import sys
from pathlib import Path

sym_file = Path(sys.argv[1] if len(sys.argv) > 1 else 'tada-client_pp.sym')
syms = {m.group(1): int(m.group(2), 16)
        for m in re.finditer(r'(\S+)\s+=\s+\$([0-9a-f]+)', sym_file.read_text())}
end = syms['backup_colors'] + 1000
overlay_buf = syms['overlay_buf']
print(f'resident end ${end:04x}, OVERLAY_BUF ${overlay_buf:04x}, '
      f'margin {overlay_buf - end} bytes')
if end > overlay_buf:
    sys.exit('ERROR: BACKUP_COLORS overlaps OVERLAY_BUF -- raise OVERLAY_BUF '
             'and every overlay module\'s orig to match')
