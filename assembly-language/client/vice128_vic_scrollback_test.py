#!/usr/bin/env python3
"""x128 (40-column) scenario for client-128.asm's VIC-II dialogue output
and its scrollback history in VDC RAM (vic_screen.asm, 2026-10-01).

Runs the client offline (RUN/STOP at "Connecting..."), once per VDC RAM
size -- x128's -VDC64KB and -VDC16KB -- and checks:
  A  boot: editor on the VIC-II ($D7 bit 7 clear), vdc_detect_ram found
     the size VICE was started with, the ring is sized from it (614 or
     179 rows), the banner says so, empty history
  B  "fill": lines 39-60 on rows 0-21 in color (yellow text, white
     number), and the ring's newest row in VDC RAM is line 38 -- 40
     screen codes then 40 colors
  C  CRSR UP: one line back, line 38 on top, status row shows position
  D  Page Up / Page Down (ALT + grey arrows, faked as in
     vice128_vdc_test.py): a page (20) back and forth
  E  CRSR DOWN to offset 0: live window and colors restored exactly
  F  scrolled back, typing leaves scrollback and the echo lands live
  G  paging to the top reaches the oldest history row (banner line 1)
  H  16K only: three more "fill"s overrun the 179-row ring -- the
     count holds at 179, and the oldest row reachable is the right one

VICE 3.8 can't check the 16K *detection*: its x128 answers 64K to this
exact $4200/$4300 test whatever -VDC16KB says (VICE bug #1981, "x128
always reports 64k", fixed in r45100, April 2024 -- after 3.8). So the
16K run reports what detection said, and if that's 64K, puts the 16K
layout in place by hand (vsb_* sizing, vdc_ram_64k, R28 back to 16K
addressing) while the client waits at "Connecting...", before anything
has been pushed -- the layout and the ring overrun still get tested.
Keystrokes go in through the KERNAL keyboard buffer, as in
vice128_vdc_test.py; leave the VICE window alone while it runs.

Usage: python3 vice128_vic_scrollback_test.py [64|16]   (default: both)
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'client-128.prg'
SYM = CLIENT / 'client-128_pp.sym'
MON = 6537
KEYD, NDX = 0x034a, 0xd0
CRSR_UP, CRSR_DOWN = 0x91, 0x11
SCREEN, COLORS = 0x0400, 0xd800
YELLOW, WHITE = 7, 1                 # VIC-II colors
BANNER_TOP = '40-column mode (vic-ii) detected.'
SIZES = {64: dict(limit=614, hist=0x4000, flag='-VDC64KB'),
         16: dict(limit=179, hist=0x0800, flag='-VDC16KB')}


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


def dump(bank: str, start: int, length: int) -> bytes:
    out = mon([f'bank {bank}', f'm ${start:04x} ${start + length - 1:04x}',
               'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def ram(addr: int, length: int = 1) -> bytes:
    """Client variables (some above $4000) and the VIC screen: bank 0 RAM."""
    return dump('ram', addr, length)


def word(name: str) -> int:
    b = ram(SYMS[name], 2)
    return b[0] | b[1] << 8


def screen_row(row: int) -> bytes:
    return ram(SCREEN + row * 40, 40)


def color_row(row: int) -> bytes:
    return bytes(b & 0x0f for b in dump('io', COLORS + row * 40, 40))


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
    """Same patch as vice128_vdc_test.py's: ALT held + matrix key
    key_num (83 grey up, 84 grey down), or None to undo."""
    hook = SYMS['editor_hook_crsr']
    mods = SYMS['km_dispatch'] + 8
    sfdx = SYMS['km_scan_macro'] + 5
    patch = ([f'> ${hook:04x} $a5 $d3', f'> ${mods:04x} $a5 $d3',
              f'> ${sfdx:04x} $c5 $d4'] if key_num is None else
             [f'> ${hook:04x} $a9 $08', f'> ${mods:04x} $a9 $08',
              f'> ${sfdx:04x} $c9 ${key_num:02x}'])
    mon(['bank ram'] + patch + ['bank default'])


def line_text(n: int) -> str:
    return f'Scrollback test line {n:03d}'


def line_colors_ok(colors: bytes) -> bool:
    """fill line: 21 yellow text columns, then 3 white digits."""
    return (all(c == YELLOW for c in colors[:21])
            and all(c == WHITE for c in colors[21:24]))


def wait_count(target: int) -> int:
    n = -1
    for _ in range(60):
        n = word('vsb_count')
        if n == target:
            break
        time.sleep(1)
    time.sleep(1)
    return n


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


def run(size: int) -> None:
    cfg = SIZES[size]
    tag = f'[{size}K]'
    print(f'--- VDC RAM {size}K ---')
    vice = subprocess.Popen(
        ['x128', '-40col', cfg['flag'], '-remotemonitor',
         '-remotemonitoraddress', f'127.0.0.1:{MON}',
         '-autostartprgmode', '1', '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(16)
        detected = ram(SYMS['vdc_ram_64k'])[0]
        if size == 16 and detected:
            print('NOTE  [16K] detection said 64K -- VICE bug #1981 (fixed '
                  'after VICE 3.8); forcing the 16K layout')
            mon(['bank ram',
                 f'> ${SYMS["vsb_limit"]:04x} ${cfg["limit"]:02x} $00',
                 f'> ${SYMS["vsb_hist_hi"]:04x} $08',
                 f'> ${SYMS["vsb_save_hi"]:04x} $00',
                 f'> ${SYMS["vdc_ram_64k"]:04x} $00',
                 'bank io', '> $d600 $1c', '> $d601 $2f', 'bank default'])
        elif size == 16:
            print('NOTE  [16K] detection said 16K')
        mon([f'> ${KEYD:04x} $03', f'> ${NDX:02x} $01'])   # RUN/STOP
        time.sleep(3)

        # A -- boot
        cursor_row = ram(SYMS['vdlg_row'])[0]
        banner = [decode(screen_row(r)) for r in range(cursor_row)]
        status = screen_row(23)
        size_line = f'VDC RAM: {size}K -- {cfg["limit"]} lines of scrollback.'
        check(f'{tag} A boot: 40 columns, {size}K detected, ring of '
              f'{cfg["limit"]}, banner, reverse status row, no history',
              not ram(0xd7)[0] & 0x80
              and ram(SYMS['vdc_ram_64k'])[0] == (1 if size == 64 else 0)
              and word('vsb_limit') == cfg['limit']
              and banner[0] == BANNER_TOP
              and size_line in banner
              # the normal status text, or the build number, which
              # holds the row as a status_override until the first key
              # (client-128.asm's show_build_msg, from PR #62)
              and decode(status).startswith(('TADA -- Commodore 128', 'build '))
              and all(b & 0x80 for b in status)
              and word('vsb_count') == 0,
              f'banner {banner} limit {word("vsb_limit")} '
              f'status |{decode(status)}|')
        fill = [line_text(n) for n in range(1, 61)]
        output = banner + fill        # every dialogue row, in order

        # B -- fill: rows 0-21 hold lines 39-60, the rest went to history
        type_line('fill')
        expected = len(output) - 22   # the cursor ends on row 22
        count = wait_count(expected)
        slot = count - 1
        rec = dump('vdc', cfg['hist'] + slot * 80, 80)
        check(f'{tag} B fill: lines 39-60 on rows 0-21 in color, '
              f'{expected} rows of history, ring holds line 38 with its colors',
              decode(screen_row(0)) == line_text(39)
              and decode(screen_row(21)) == line_text(60)
              and decode(screen_row(22)) == ''
              and line_colors_ok(color_row(21))
              and count == expected
              and decode(rec[:40]) == line_text(38)
              and line_colors_ok(bytes(b & 0x0f for b in rec[40:])),
              f'row0 |{decode(screen_row(0))}| hist {count} '
              f'ring |{decode(rec[:40])}|')

        # C -- one line back
        keys(bytes([CRSR_UP]))
        status = decode(screen_row(23))
        check(f'{tag} C CRSR UP: line 38 on top in color, live rows below, '
              'status shows position',
              decode(screen_row(0)) == line_text(38)
              and line_colors_ok(color_row(0))
              and decode(screen_row(1)) == line_text(39)
              and decode(screen_row(22)) == line_text(60)
              and line_colors_ok(color_row(22))
              and status.startswith(f'Scrollback: 001 of {count:03d}')
              and word('vsb_offset') == 1,
              f'|{status}|')

        # D -- Page Up / Page Down through the keymap
        fake_alt_key(83)
        keys(bytes([CRSR_UP]))
        top_back, off_back = decode(screen_row(0)), word('vsb_offset')
        fake_alt_key(84)
        keys(bytes([CRSR_DOWN]))
        fake_alt_key(None)
        check(f'{tag} D Alt + grey CRSR: page back to offset 21 (line 18 '
              'on top), page forward to 1',
              off_back == 21 and top_back == line_text(18)
              and word('vsb_offset') == 1
              and decode(screen_row(0)) == line_text(38),
              f'back |{top_back}| offset {off_back}')

        # E -- back to live
        keys(bytes([CRSR_DOWN]))
        check(f'{tag} E CRSR DOWN to offset 0: live window, colors, status '
              'restored',
              word('vsb_offset') == 0
              and decode(screen_row(0)) == line_text(39)
              and decode(screen_row(21)) == line_text(60)
              and decode(screen_row(22)) == ''
              and line_colors_ok(color_row(21))
              and decode(screen_row(23)).startswith('TADA'))

        # F -- typing while scrolled back
        keys(bytes([CRSR_UP] * 2))
        type_line('hi')
        check(f'{tag} F typing leaves scrollback; echo lands live',
              word('vsb_offset') == 0
              and decode(screen_row(21)) == 'You typed: hi'
              and decode(screen_row(20)) == line_text(60)
              and word('vsb_count') == count + 1,
              f'row21 |{decode(screen_row(21))}|')
        count += 1
        output.append('You typed: hi')

        # G -- page to the very top: oldest history row = banner line 1
        fake_alt_key(83)
        keys(bytes([CRSR_UP] * ((count + 19) // 20)))
        fake_alt_key(None)
        check(f'{tag} G paging to the top: offset {count}, banner line 1 '
              'on top',
              word('vsb_offset') == count
              and decode(screen_row(0)) == BANNER_TOP,
              f'offset {word("vsb_offset")} |{decode(screen_row(0))}|')
        keys(bytes([ord('X'), 0x14]))            # any key: back to live

        if size == 16:
            # H -- overrun the ring: three more fills. Every row is pushed
            # once, in output order, so the ring keeps the newest 179 of
            # everything but the 22 rows still on screen.
            for _ in range(3):
                type_line('fill')
                output += fill
                wait_count(min(len(output) - 22, cfg['limit']))
            oldest = output[:-22][-cfg['limit']:][0]
            final = word('vsb_count')
            fake_alt_key(83)
            keys(bytes([CRSR_UP] * 10))
            fake_alt_key(None)
            top = decode(screen_row(0))
            check(f'{tag} H ring overrun: count holds at {cfg["limit"]}, '
                  f'paging to the top stops at the oldest row kept ({oldest})',
                  final == cfg['limit']
                  and word('vsb_offset') == cfg['limit']
                  and top == oldest,
                  f'count {final} offset {word("vsb_offset")} top |{top}| '
                  f'head {word("vsb_head")}')
            keys(bytes([ord('X'), 0x14]))
    finally:
        vice.terminate()
        vice.wait()


for size in ([int(a) for a in sys.argv[1:]] or [64, 16]):
    run(size)

print('\nall passed' if not failures else f'\n{len(failures)} failed: {failures}')
sys.exit(1 if failures else 0)
