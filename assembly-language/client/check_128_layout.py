#!/usr/bin/env python3
"""Fail the client-128 build if its memory layout breaks.

client-128.asm runs with $FF00 = $0e (RAM at $4000-$bfff), but the
KERNAL IRQ calls irq_handler with $FF00 = $00 -- BASIC ROM over
$4000-$bfff -- so everything an interrupt can reach must sit below
$4000. The file keeps all of that above `main_loop_sp` (the last label
before the Keymap Editor include); this checks that label is below
$4000. It also checks the program ends before the scrollback history
ring at $6000 (vdc_screen.asm's HIST_CHARS_HI).

Usage: check_128_layout.py client-128.prg client-128_pp.sym
"""
import re, sys

IRQ_LIMIT, HIST_START = 0x4000, 0x6000
prg = open(sys.argv[1], 'rb').read()
end = (prg[0] | prg[1] << 8) + len(prg) - 2
syms = {}
for line in open(sys.argv[2]):
    m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
    if m:
        syms[m.group(1).lower()] = int(m.group(2), 16)

errors = []
last_irq = syms.get('main_loop_sp')
if last_irq is None:
    errors.append('main_loop_sp not found in the symbol file')
elif last_irq >= IRQ_LIMIT:
    errors.append(f'interrupt-reachable code/data runs to ${last_irq:04x}, '
                  f'past ${IRQ_LIMIT:04x}')
if end > HIST_START:
    errors.append(f'program ends at ${end:04x}, into the history ring at '
                  f'${HIST_START:04x}')
for e in errors:
    print('check_128_layout: ' + e)
if errors:
    sys.exit(1)
print(f'check_128_layout: IRQ side ends ${last_irq:04x} (< ${IRQ_LIMIT:04x}), '
      f'program ends ${end:04x} (< ${HIST_START:04x})')
