#!/usr/bin/env python3
"""x128 scenario for client-128.asm's Hourglass clock on the status row.

No server involved -- client-128.asm has no SwiftLink yet, so this drives
its local "clock <text>" test command (clock_test_command) from the
input row and checks STATUS_ROW (23) straight out of SCREEN_RAM through
the remote monitor (a direct dump, not a screenshot -- see the VICE
testing notes on stale screenshots):
  A  boot: lowercase charset selected and SHIFT+C= locked (LOCKS $f7 =
     $80), status message only, capped at 39 columns, no clock
  B  "clock 12:34 PM" ("PM" shifted, as the server's lc codec sends it,
     so it must show as capitals): clock right-aligned in cols 32-39, message cut at
     col 30 with a blank gap column before the clock
  C  a 16-character clock: truncated to CLOCK_MAX (12)
  D  bare "clock": clock hidden, message back to 39 columns
Keystrokes go in by poking the C128 KERNAL keyboard buffer (KEYD $034a,
count NDX $d0 -- not the C64's $0277/$c6). The VICE window it opens
takes real keystrokes too, so leave it alone while it runs.

Written 2026-09-29. Usage: python3 vice128_clock_test.py
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'client-128.prg'
MON = 6533
STATUS = 0x0400 + 23 * 40
KEYD, NDX = 0x034a, 0xd0


def mon(cmds):
    s = socket.create_connection(('127.0.0.1', MON)); s.settimeout(2); buf = b''
    for cmd in cmds:
        s.sendall(cmd.encode() + b'\n'); time.sleep(0.4)
        try:
            while True:
                d = s.recv(65536)
                if not d: break
                buf += d
        except socket.timeout:
            pass
    s.sendall(b'x\n'); time.sleep(0.2); s.close()
    return buf.decode('latin-1')


def status_row() -> bytes:
    out = mon([f'm ${STATUS:04x} ${STATUS + 39:04x}'])
    data = []
    # ">C:0798  d4 c1 c4 c1  a0 ad ..." -- the first line also carries the
    # monitor's "(C:$xxxx) " prompt in front, so search, don't anchor
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:40])


def decode(row: bytes) -> str:
    """Screen codes (reverse bit stripped) -> text, lowercase charset
    (the client selects it at boot with CHR$(14))."""
    out = ''
    for b in row:
        c = b & 0x7f
        if 1 <= c <= 26:
            out += chr(c + 96)             # a-z
        elif 0x41 <= c <= 0x5a:
            out += chr(c)                  # A-Z
        else:
            out += '@' if c == 0 else chr(c)
    return out


def type_line(text: str) -> None:
    """Type *text* as the server's petscii_c64en_lc codec would encode
    it: lowercase -> unshifted $41-$5a, uppercase -> shifted $c1-$da."""
    keys = bytes(ord(ch.upper()) | (0x80 if ch.isupper() else 0)
                 for ch in text) + b'\r'
    for i in range(0, len(keys), 10):
        chunk = keys[i:i + 10]
        pokes = ' '.join(f'${b:02x}' for b in chunk)
        mon([f'> ${NDX:02x} $00', f'> ${KEYD:04x} {pokes}',
             f'> ${NDX:02x} ${len(chunk):02x}'])
        time.sleep(1.0)
    time.sleep(1.0)


failures = []


def check(label, cond, row):
    print(f'{"PASS" if cond else "FAIL"}  {label}\n      |{decode(row)}|')
    if not cond:
        failures.append(label)


vice = subprocess.Popen(
    ['x128', '-40col', '-remotemonitor', '-remotemonitoraddress',
     f'127.0.0.1:{MON}', '-autostartprgmode', '1', '-autostart', str(PRG)],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(15)

    row = status_row()
    msg = decode(row)
    d018 = re.search(r'>C:d018\s+([0-9a-f]{2})', mon(['m $d018 $d018']))
    locks = re.search(r'>C:00f7\s+([0-9a-f]{2})', mon(['m $f7 $f7']))
    check('A boot: lowercase charset locked, all reverse, message capped, '
          'col 39 blank, no clock',
          d018 is not None and int(d018.group(1), 16) & 0x02
          and locks is not None and int(locks.group(1), 16) == 0x80
          and len(row) == 40 and all(b & 0x80 for b in row)
          and msg.startswith('TADA -- Commodore') and row[39] == 0xa0, row)

    type_line('clock 12:34 PM')
    row = status_row(); text = decode(row)
    check('B clock right-aligned, gap col 31, message cut at col 30',
          text[32:] == '12:34 PM' and row[31] == 0xa0
          and all(b & 0x80 for b in row), row)

    type_line('clock 1234567890abcdef')
    row = status_row(); text = decode(row)
    check('C 16-char clock truncated to 12', text[28:] == '1234567890ab'
          and row[27] == 0xa0, row)

    type_line('clock')
    row = status_row(); text = decode(row)
    check('D bare "clock" hides it', text.startswith('TADA')
          and '1234' not in text and row[39] == 0xa0, row)
finally:
    vice.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
