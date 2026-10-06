#!/usr/bin/env python3
"""Flag 6502 relative branches whose target isn't a label.

c64list assembles an out-of-range bxx without an error -- it silently
wraps to some address nearby -- so a clean "0 Errors" proves nothing
about branch range. This disassembles the whole .prg from its load
address and lists every branch whose target isn't in the .sym file,
along with the label it sits under. Hits inside data (message text,
tables) are expected noise; a hit under a CODE label is a real bug.
Found one on its first run (2026-09-29): vdc_screen.asm's `beq dlg_cr`
needed +143 bytes and came out as a branch to the next byte.

Usage: check_branch_targets.py client-128.prg client-128_pp.sym
(run with the server's .venv python -- needs py65)
"""
import re, sys
from py65.devices.mpu6502 import MPU
from py65.disassembler import Disassembler

prg = open(sys.argv[1], 'rb').read()
load, body = prg[0] | prg[1] << 8, prg[2:]
labels = {}
for line in open(sys.argv[2]):
    m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
    if m:
        labels.setdefault(int(m.group(2), 16), m.group(1))
code_labels = sorted(a for a in labels if load <= a < load + len(body))

mpu = MPU()
mpu.memory[load:load + len(body)] = list(body)
dis = Disassembler(mpu)
addr, hits = load, 0
while addr < load + len(body):
    size, text = dis.instruction_at(addr)
    m = re.match(r'(BCC|BCS|BEQ|BNE|BMI|BPL|BVC|BVS) \$([0-9a-f]{4})', text)
    if m and int(m.group(2), 16) not in labels:
        owner = max((a for a in code_labels if a <= addr), default=None)
        print(f'{addr:04x}  {text:12} under {labels.get(owner, "?")}')
        hits += 1
    addr += size
print(f'{hits} branch(es) to non-label addresses')
