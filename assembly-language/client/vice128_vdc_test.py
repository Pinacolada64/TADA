#!/usr/bin/env python3
"""x128 (80-column) scenario for client-128.asm's VDC screen and scrollback.

No server involved -- this runs client-128.asm offline (RUN/STOP at "Connecting...") and drives
the local "fill" test command (60 numbered lines, yellow text + white
number) and CRSR keys, and checks VDC RAM directly through the remote
monitor's "bank vdc" (x128 screenshots don't capture the VDC window
reliably -- see the VICE testing notes):
  A  boot: editor on the VDC ($D7 bit 7), lowercase ALT attribute,
     banner with real capitals on row 0, reverse status row 23,
     hardware cursor off, empty history
  B  "fill": window shows lines 39-60 on rows 0-21 with their colors,
     43 rows went to history, and the ring (bank 0 RAM $6000/$9000)
     holds line 38 as its newest row (bank 0 RAM $6000/$9000)
  C  CRSR UP: one line back -- history row on top, live rows shifted
     down by block copy, status row shows the position
  D  three more CRSR UP: offset 4
  E  Page Up / Page Down (the keymap's defaults, ALT + the grey arrows):
     a page (20) back and forth. ALT and the grey key's matrix number
     are faked by patching editor_key_hook's and km_dispatch's "lda $d3"
     to "lda #8" and km_scan_macro's "cmp $d4" to "cmp #83/84" in
     memory, since a held key can't be poked into the keyboard buffer
  F  CRSR DOWN back to offset 0: live window restored exactly
  G  scrolled back, typing leaves scrollback and the echo lands live
  H  paging to the top reaches the oldest history row (banner line 1)
Keystrokes go in by poking the C128 KERNAL keyboard buffer (KEYD $034a,
count NDX $d0). The VICE window takes real keystrokes too, so leave it
alone while it runs.

Written 2026-09-29. Usage: python3 vice128_vdc_test.py
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'client-128.prg'
SYM = CLIENT / 'client-128_pp.sym'
MON = 6536
KEYD, NDX = 0x034a, 0xd0
CRSR_UP, CRSR_DOWN = 0x91, 0x11
ALT = 0x80
YELLOW, WHITE = 0x0d, 0x0f            # VDC RGBI (editor table $CE5C)


def symbols() -> dict:
    out = {}
    for line in SYM.read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


SYMS = symbols()


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


def _bank(bank: str, addr: int) -> str:
    """The client's own variables above $4000 (the built-in Keymap
    Editor moved there once SwiftLink grew the program) live in bank 0
    RAM, but "bank default" follows whatever MMU state the CPU stopped
    in -- often the KERNAL IRQ's $FF00 = $00, BASIC ROM over $4000-$BFFF
    -- so read and write those through "bank ram" instead."""
    return 'ram' if bank == 'default' and 0x4000 <= addr < 0xc000 else bank


def dump(bank: str, start: int, length: int) -> bytes:
    bank = _bank(bank, start)
    out = mon([f'bank {bank}', f'm ${start:04x} ${start + length - 1:04x}',
               'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def vdc_row(row: int) -> bytes:
    return dump('vdc', row * 80, 80)


def vdc_attrs(row: int) -> bytes:
    return dump('vdc', 0x0800 + row * 80, 80)


def byte_at(addr: int) -> int:
    return dump('default', addr, 1)[0]


def decode(row: bytes) -> str:
    """Screen codes (reverse bit stripped), lowercase charset."""
    out = ''
    for b in row:
        c = b & 0x7f
        if 1 <= c <= 26:
            out += chr(c + 96)
        elif 0x41 <= c <= 0x5a:
            out += chr(c)
        else:
            out += '@' if c == 0 else chr(c)
    return out.rstrip()


def keys(codes: bytes) -> None:
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        pokes = ' '.join(f'${b:02x}' for b in chunk)
        mon([f'> ${NDX:02x} $00', f'> ${KEYD:04x} {pokes}',
             f'> ${NDX:02x} ${len(chunk):02x}'])
        time.sleep(1.0)
    time.sleep(1.0)


def type_line(text: str) -> None:
    keys(bytes(ord(ch.upper()) | (0x80 if ch.isupper() else 0)
               for ch in text) + b'\r')


def fake_alt_key(key_num):
    """ALT held + matrix key key_num (83 grey up, 84 grey down), or None to
    undo: editor_key_hook's and km_dispatch's "lda $d3" -> "lda #8",
    km_scan_macro's "cmp $d4" -> "cmp #key_num"."""
    hook = SYMS['editor_hook_crsr']
    mods = SYMS['km_dispatch'] + 8          # after sta km_key / lda #0 /
                                            # sta km_paged
    sfdx = SYMS['km_scan_macro'] + 5
    if key_num is None:
        mon([f'> ${hook:04x} $a5 $d3', f'> ${mods:04x} $a5 $d3',
             f'> ${sfdx:04x} $c5 $d4'])
    else:
        mon([f'> ${hook:04x} $a9 $08', f'> ${mods:04x} $a9 $08',
             f'> ${sfdx:04x} $c9 ${key_num:02x}'])


def line_text(n: int) -> str:
    return f'Scrollback test line {n:03d}'


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


def line_colors_ok(attrs: bytes) -> bool:
    """fill line: 21 yellow text columns, then 3 white digits."""
    return (all(a == ALT | YELLOW for a in attrs[:21])
            and all(a == ALT | WHITE for a in attrs[21:24]))


vice = subprocess.Popen(
    ['x128', '-80col', '-VDC16KB', '-remotemonitor', '-remotemonitoraddress',
     f'127.0.0.1:{MON}', '-autostartprgmode', '1', '-autostart', str(PRG)],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(16)
    # RUN/STOP at "Connecting...": no SwiftLink here, so go offline into
    # the local demo this test drives (client-128.asm's go_offline).
    mon([f'> ${KEYD:04x} $03', f'> ${NDX:02x} $01'])
    time.sleep(3)

    # A -- boot
    row0, status = vdc_row(0), vdc_row(23)
    regs = mon(['io d600'])
    r10 = re.search(r'00:(?:\s+[0-9a-f]{2}){10}\s+([0-9a-f]{2})', regs)
    check('A boot: 80-column editor, banner, reverse status row, '
          'cursor off, no history',
          byte_at(0xd7) & 0x80
          and decode(row0) == '80-column mode (VDC) detected.'
          and all(a == ALT | 0x07 for a in vdc_attrs(0))
          and decode(status).startswith('TADA -- Commodore 128')
          and all(b & 0x80 for b in status)
          and r10 is not None and (int(r10.group(1), 16) & 0x60) == 0x20
          and byte_at(SYMS['hist_count']) == 0,
          f'|{decode(row0)}| |{decode(status)}|')

    # B -- fill: 5 banner rows + 60 lines -> cursor on logical row 65,
    # 65 - 22 = 43 rows scrolled into history; window row r = line 39 + r
    type_line('fill')
    for _ in range(30):                  # output takes a few seconds
        if byte_at(SYMS['hist_count']) == 43:
            break
        time.sleep(1)
    time.sleep(1)
    rows = {r: vdc_row(r) for r in (0, 21, 22)}
    hist_count = byte_at(SYMS['hist_count'])
    slot = 42                            # newest pushed row = 43rd push
    ring_chr = dump('ram', 0x6000 + slot * 80, 80)   # vdc_screen.asm's
    ring_attr = dump('ram', 0x9000 + slot * 80, 80)  # HIST_CHARS_HI/ATTR
    check('B fill: lines 39-60 on rows 0-21 in color, 43 rows of history, '
          'ring holds line 38 with its colors',
          decode(rows[0]) == line_text(39)
          and decode(rows[21]) == line_text(60)
          and decode(rows[22]) == ''
          and line_colors_ok(vdc_attrs(21))
          and hist_count == 43
          and decode(ring_chr) == line_text(38)
          and line_colors_ok(ring_attr),
          f'row0 |{decode(rows[0])}| row21 |{decode(rows[21])}| '
          f'hist {hist_count} ring |{decode(ring_chr)}|')

    # C -- one line back
    keys(bytes([CRSR_UP]))
    status = decode(vdc_row(23))
    check('C CRSR UP: history line 38 on top in color, live rows shifted, '
          'status shows position',
          decode(vdc_row(0)) == line_text(38)
          and line_colors_ok(vdc_attrs(0))
          and decode(vdc_row(1)) == line_text(39)
          and decode(vdc_row(22)) == line_text(60)
          and line_colors_ok(vdc_attrs(22))
          and status.startswith('Scrollback: 001 of 043')
          and byte_at(SYMS['sb_offset']) == 1,
          f'|{status}|')

    # D -- three more
    keys(bytes([CRSR_UP] * 3))
    check('D 3x CRSR UP: offset 4, line 35 on top',
          decode(vdc_row(0)) == line_text(35)
          and decode(vdc_row(4)) == line_text(39)
          and byte_at(SYMS['sb_offset']) == 4)

    # E -- Page Up / Page Down through the keymap
    fake_alt_key(83)
    keys(bytes([CRSR_UP]))
    top_back = decode(vdc_row(0))
    off_back = byte_at(SYMS['sb_offset'])
    fake_alt_key(84)
    keys(bytes([CRSR_DOWN]))
    fake_alt_key(None)
    check('E Alt + grey CRSR: page back to offset 24 (line 15 on top), '
          'page forward to 4',
          off_back == 24 and top_back == line_text(15)
          and byte_at(SYMS['sb_offset']) == 4
          and decode(vdc_row(0)) == line_text(35),
          f'back |{top_back}| offset {off_back}')

    # F -- back to live
    keys(bytes([CRSR_DOWN] * 4))
    check('F CRSR DOWN to offset 0: live window and status restored',
          byte_at(SYMS['sb_offset']) == 0
          and decode(vdc_row(0)) == line_text(39)
          and decode(vdc_row(21)) == line_text(60)
          and decode(vdc_row(22)) == ''
          and line_colors_ok(vdc_attrs(21))
          and decode(vdc_row(23)).startswith('TADA'))

    # G -- typing while scrolled back
    keys(bytes([CRSR_UP] * 2))
    type_line('hi')
    check('G typing leaves scrollback; echo lands live',
          byte_at(SYMS['sb_offset']) == 0
          and decode(vdc_row(21)) == 'You typed: hi'
          and decode(vdc_row(20)) == line_text(60)
          and byte_at(SYMS['hist_count']) == 44,
          f'row21 |{decode(vdc_row(21))}|')

    # H -- page to the very top: oldest history row = banner line 1
    fake_alt_key(83)
    keys(bytes([CRSR_UP] * 3))
    fake_alt_key(None)
    check('H paging to the top: offset 44, banner line 1 on top',
          byte_at(SYMS['sb_offset']) == 44
          and decode(vdc_row(0)) == '80-column mode (VDC) detected.',
          f'|{decode(vdc_row(0))}|')
finally:
    vice.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
