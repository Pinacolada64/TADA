#!/usr/bin/env python3
"""x128 scenario for the Keymap Editor built into client-128.asm.

Runs client-128.prg from a scratch .d64 on drive 8 (so KEYMAP.CFG really
goes through KERNAL SAVE/LOAD) and checks memory -- VDC RAM through the
monitor's "bank vdc", VIC screen/color RAM, the client's own variables --
rather than screenshots:
  A  boot (80 columns): $FF00 = $0e, F1-F8 reprogrammed to $85-$8c, the
     CTRL decode pointer ($0344) moved to the patched RAM copy, default
     keymap in keymap_table (no KEYMAP128.CFG yet), including Page Up/
     Page Down = ALT + grey CRSR (key numbers 83/84) in slots 15-16
  B  F7 (delivered the way the editor hands out an F-key string: $d1/$d2)
     opens the popup; the IRQ copies it onto the VDC at columns 20-59,
     dialogue greyed, status row blanked around it; the Keymap Editor
     page lists Page Up/Page Down with their "Alt+" combos
  C  CRSR DOWN moves the selection; VDC rows 2-23 stay in sync with the
     VIC screen the popup draws on
  D  RUN/STOP: dialogue and colors restored, 80-column status "Aborted."
  E  the next key clears the status message
  F  keymap nav in the input line: CTRL+CRSR-RIGHT word left, CLR/HOME,
     CTRL+CRSR-DOWN word right (CTRL faked by patching km_dispatch's
     "lda $d3" to "lda #4" -- a held modifier can't be poked)
  G  a macro slot (poked into keymap_table, trigger key number 10) types
     "look" and submits it via the back-arrow marker (the matrix match is
     faked by patching "cmp $d4" to "cmp #10")
  H  'S' in the popup saves KEYMAP128.CFG; a fresh boot LOADs it back
     (the macro slot survives), and the file is on the disk
  I  40 columns: same disk, F7 opens the popup on the real screen with
     the rest greyed, RUN/STOP puts screen and colors back
The VICE windows take real keystrokes too, so leave them alone while
this runs.

Written 2026-09-29. Usage: python3 vice128_keymap_test.py
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'client-128.prg'
SYM = CLIENT / 'client-128_pp.sym'
MON = 6541
KEYD, NDX = 0x034a, 0xd0
ALT, WHITE, CYAN = 0x80, 0x0f, 0x07
GREY_VDC = 0x01                         # VIC 12 via the editor's table


def symbols() -> dict:
    out = {}
    for line in SYM.read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


S = symbols()


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


def byte_at(addr: int) -> int:
    return dump('default', addr, 1)[0]


def poke(addr: int, *values: int) -> None:
    mon([f'bank {_bank("default", addr)}',
         f'> ${addr:04x} ' + ' '.join(f'${v:02x}' for v in values),
         'bank default'])


def vdc(row: int, col: int = 0, n: int = 80) -> bytes:
    return dump('vdc', row * 80 + col, n)


def vdc_attr(row: int, col: int = 0, n: int = 80) -> bytes:
    return dump('vdc', 0x0800 + row * 80 + col, n)


def vic(row: int) -> bytes:
    return dump('default', 0x0400 + row * 40, 40)


def vic_colors(row: int) -> bytes:
    return bytes(b & 0x0f for b in dump('default', 0xd800 + row * 40, 40))


def decode(row: bytes) -> str:
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


def keys(codes: bytes, settle: float = 1.0) -> None:
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        mon([f'> ${NDX:02x} $00',
             f'> ${KEYD:04x} ' + ' '.join(f'${b:02x}' for b in chunk),
             f'> ${NDX:02x} ${len(chunk):02x}'])
        time.sleep(settle)
    time.sleep(settle)


def type_text(text: str, enter: bool = False) -> None:
    keys(bytes(ord(ch.upper()) | (0x80 if ch.isupper() else 0)
               for ch in text) + (b'\r' if enter else b''))


def press_f7() -> None:
    """One F-key string character pending ($d1), at offset 6 ($d2) of the
    F-key buffer -- F7's, keys 1-6 having one byte each."""
    mon(['> $d2 $06', '> $d1 $01'])
    time.sleep(3)


def boot(mode: str, disk: Path) -> subprocess.Popen:
    # The .prg is injected (like the other 128 tests); autostarting the
    # .d64 itself sometimes never typed its LOAD at all. The disk stays on
    # drive 8 for KEYMAP.CFG -- the client falls back to device 8 when $ba
    # isn't a disk drive.
    p = subprocess.Popen(
        ['x128', mode, '-VDC16KB', '-8', str(disk), '-remotemonitor',
         '-remotemonitoraddress', f'127.0.0.1:{MON}', '-autostartprgmode', '1',
         '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(16)
    # RUN/STOP at "Connecting...": no SwiftLink here, so go offline into
    # the local demo this test drives (client-128.asm's go_offline).
    mon([f'> ${KEYD:04x} $03', f'> ${NDX:02x} $01'])
    time.sleep(3)
    return p


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}'
          + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


def presented_in_sync() -> bool:
    for row in (2, 5, 8, 23):
        if vdc(row, 20, 40) != vic(row):
            return False
    return True


disk = Path(__file__).parent / 'vice128_keymap_test.d64'
disk.unlink(missing_ok=True)
subprocess.run(['c1541', '-format', 'kmtest,01', 'd64', str(disk), '-write',
                str(PRG), 'client-128'], check=True, capture_output=True)

vice = boot('-80col', disk)
try:
    # A
    table = dump('default', S['keymap_table'], 27 * 6)
    ctrl = dump('default', 0x0344, 2)
    check('A boot: MMU $0e, F-keys, CTRL table, default keymap',
          byte_at(0xff00) == 0x0e
          and dump('default', 0x1000, 8) == bytes([1] * 8)
          and dump('default', 0x100a, 8) == bytes([0x85, 0x89, 0x86, 0x8a,
                                                   0x87, 0x8b, 0x88, 0x8c])
          and (ctrl[0] | ctrl[1] << 8) == S['km_ctrl_table']
          and dump('default', S['km_ctrl_table'] + 2, 6)[0] == 0x1d
          and table[0:3] == bytes([4, 0x1d, 1]) and table[135:138] == bytes([0, 0x88, 5])
          and dump('default', S['keymap_table'] + 27 * 15, 3) == bytes([8, 83, 6])
          and dump('default', S['keymap_table'] + 27 * 16, 3) == bytes([8, 84, 7]))

    # B
    press_f7()
    listed = [decode(vic(r)) for r in range(5, 16)]
    page_rows = [t for t in listed if 'Page' in t]
    check('B F7 opens the popup, presented at VDC columns 20-59, rest grey',
          byte_at(S['km_present_on']) == 1
          and decode(vdc(5, 20, 40)).strip().startswith(']')
          and vdc(2, 20, 40) == vic(2)
          and all(a == ALT | WHITE for a in vdc_attr(2, 20, 40))
          and all(a == ALT | GREY_VDC for a in vdc_attr(0))
          and all(c == 0xa0 for c in vdc(23, 0, 20))
          and len(page_rows) == 2
          and all('Alt+' in t for t in page_rows),
          f'{page_rows}')

    # C
    keys(bytes([0x11]), settle=1.5)
    check('C CRSR DOWN: selection 1, VDC in sync with the popup',
          byte_at(S['selected_row']) == 1 and presented_in_sync())

    # D
    keys(bytes([0x03]), settle=1.5)
    status = decode(vdc(23))
    check('D RUN/STOP: dialogue + colors back, "Aborted." on the status row',
          byte_at(S['km_present_on']) == 0 and byte_at(S['scr_cols']) == 80
          and decode(vdc(0)) == '80-column mode (VDC) detected.'
          and all(a == ALT | CYAN for a in vdc_attr(0))
          and status.startswith('Aborted.'), f'|{status}|')

    # E
    type_text('x')
    keys(bytes([0x14]))                 # DEL it again
    check('E next key clears the status message',
          decode(vdc(23)).startswith('TADA'))

    # F
    type_text('one two')
    at = S['km_dispatch'] + 8           # lda $d3 (a5 d3), after sta km_key/
                                        # lda #0/sta km_paged
    orig = dump('default', at, 2)
    poke(at, 0xa9, 0x04)                # lda #4: CTRL held
    keys(bytes([0x1d]))                 # CTRL+CRSR-RIGHT: word left
    word_left = byte_at(S['cpos'])
    poke(at, *orig)
    keys(bytes([0x13]))                 # CLR/HOME
    home = byte_at(S['cpos'])
    # CRSR DOWN also passes editor_key_hook's own CTRL test (in 80
    # columns plain CRSR DOWN is scrollback's), so fake CTRL there too.
    hook = S['editor_hook_crsr']        # lda $d3 (a5 d3)
    hook_orig = dump('default', hook, 2)
    poke(at, 0xa9, 0x04)
    poke(hook, 0xa9, 0x04)
    keys(bytes([0x11]))                 # CTRL+CRSR-DOWN: word right
    word_right = byte_at(S['cpos'])
    poke(at, *orig)
    poke(hook, *hook_orig)
    keys(b'\r')
    check('F word left / home / word right through the keymap',
          (word_left, home, word_right) == (4, 0, 4)
          and orig == bytes([0xa5, 0xd3]) and hook_orig == orig,
          f'cpos {word_left}, {home}, {word_right}')

    # G
    slot6 = S['keymap_table'] + 27 * 6
    poke(slot6, 0, 10, 0xff, *b'LOOK', 0x5f, 0)
    at = S['km_scan_macro'] + 5         # cmp $d4 (c5 d4)
    orig = dump('default', at, 2)
    poke(at, 0xc9, 10)
    keys(b'A', settle=2)
    poke(at, *orig)
    echoed = [decode(vdc(r)) for r in range(0, 23)]
    check('G macro types "look" and submits it',
          orig == bytes([0xc5, 0xd4]) and 'You typed: look' in echoed,
          f'{[e for e in echoed if e]}')

    # H
    press_f7()
    keys(b'S')
    for _ in range(30):                 # SCRATCH + SAVE through the drive
        saved_status = decode(vdc(23))
        if saved_status.startswith('Saved keymap'):
            break
        time.sleep(1)
    time.sleep(2)
    vice.terminate(); time.sleep(2)
    listing = subprocess.run(['c1541', str(disk), '-list'],
                             capture_output=True, text=True).stdout
    vice = boot('-80col', disk)
    reloaded = dump('default', slot6, 9)
    check('H save, then a fresh boot LOADs the macro back from KEYMAP128.CFG',
          saved_status.startswith('Saved keymap')
          and 'keymap128.cfg' in listing.lower()
          and reloaded == bytes([0, 10, 0xff, *b'LOOK', 0x5f, 0]),
          f'|{saved_status}| {reloaded.hex()}')
    vice.terminate(); time.sleep(2)

    # I
    vice = boot('-40col', disk)
    before_chars, before_colors = vic(0), vic_colors(0)
    press_f7()
    opened = (byte_at(S['km_present_on']) == 0 and vic(2)[4] == 0x70  # box corner
              and all(c == 12 for c in vic_colors(0))
              and all(c == 1 for c in vic_colors(3)))
    keys(bytes([0x03]), settle=1.5)
    check('I 40 columns: popup on the real screen, grey around it; '
          'RUN/STOP restores',
          opened and vic(0) == before_chars and vic_colors(0) == before_colors,
          f'|{decode(before_chars)}|')
finally:
    vice.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
