#!/usr/bin/env python3
"""x128 scenario for client-128.asm's Video Settings popup
(video_menu_128.asm), against a real server.

Starts its own server (server/simple_server.py on its own ports, distinct
from the live server's and from vice128_swiftlink_test.py's, so the two
can run side by side) and boots x128 with an emulated SwiftLink, as in
vice128_swiftlink_test.py. Each run: connect guest, then prefs -> t -> v.

80 columns (VDC registers through the monitor's `io d600`):
  A  the popup opens on the VDC: "80 columns" title, Background color,
     Cursor blink speed, Cursor (Soft/Block/Line), Flash -- and no
     Border color; VDC hardware cursor off (Soft)
  B  CRSR right on Background: R26's background nibble becomes the RGBI
     color for the next VIC-II color (dlg_vdc_colors) -- live preview
  C  Cursor -> Block: R10 = $60 (slow blink, scan line 0 -- the editor's
     own default), the VDC cursor on the demo cell (VDC $0302)
  D  Flash: Fast $40, Solid $00, back to Slow $60
  E  RETURN: the server saves ("Video settings saved"), the status row
     reports the TADA128.CFG save, the popup is gone, and the VDC cursor
     sits on the input row's cursor cell, right after the prompt
  F  open again: Block is still chosen (its bar reversed); change the
     background, RUN/STOP: "Video settings unchanged.", R26 back to the
     saved color, the VDC cursor back on the input row
  G  the input line still works afterwards: typing moves the VDC cursor
  J  Background never lands on the text's color (invisible text): sixteen
     CRSR rights skip whatever shows as the dialogue's or input line's
     color, then RUN/STOP
40 columns (VIC-II):
  H  the popup opens with Border color, Background color, Cursor blink
     speed, and no Cursor/Flash rows
  K  the same skip in 40 columns (Background is the second row there)
  I  CRSR right on Border: $D020 follows; RETURN saves it and it stays
     (reopening shows the server stored it)

Written 2026-10-05. Usage, from this directory:
  ../../server/.venv/bin/python3 vice128_video_settings_test.py
Takes about 15 minutes. ONLY40=1 runs just the 40-column half, DEBUG=1
prints what's on screen when the popup doesn't appear, SERVER_LOG=path
keeps the server's log.
(any .venv python with the server's packages works). Keystrokes go in
through the C128 KERNAL keyboard buffer; leave the VICE window alone
while it runs.
"""
import os, re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
SERVER = CLIENT.parent.parent / 'server'
PRG = CLIENT / 'client-128.prg'
MON = 6552
PETSCII, JSON = 35175, 35174
KEYD, NDX = 0x034a, 0xd0
POPUP_TOP = 6                     # video_menu_128.asm's VS_TOP_ROW
DEMO_VDC = 770                    # its VS_DEMO_VDC
INPUT_VDC = 1920                  # its VS_INPUT_VDC
# vdc_screen.asm's dlg_vdc_colors: VIC-II color -> VDC RGBI color
DLG_VDC_COLORS = [0x00, 0x0f, 0x08, 0x07, 0x0b, 0x04, 0x02, 0x0d,
                  0x0a, 0x0c, 0x09, 0x06, 0x01, 0x05, 0x03, 0x0e]
CRSR_UP, CRSR_DOWN, CRSR_LEFT, CRSR_RIGHT = 0x91, 0x11, 0x9d, 0x1d
RETURN, RUN_STOP = 0x0d, 0x03


def mon(cmds, wait=0.4, quiet=2.0):
    """quiet: how long the monitor must stay silent before the next
    command -- short for pokes, whose replies are tiny."""
    s = socket.create_connection(('127.0.0.1', MON)); s.settimeout(quiet); buf = b''
    for cmd in cmds:
        s.sendall(cmd.encode() + b'\n'); time.sleep(wait)
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


def vdc_regs() -> list:
    """The 8563's registers, from the monitor's VDC io dump."""
    out = mon(['io d600'], wait=1.0)
    regs = []
    for m in re.finditer(r'^([0-9a-f]{2}): ((?:[0-9a-f]{2}\s*)+)$', out, re.M):
        regs += [int(b, 16) for b in m.group(2).split()]
    return regs


def cursor_mode(regs) -> int:
    return regs[10] & 0x7f        # VICE shows R10's unused bit 7 as 1


def cursor_addr(regs) -> int:
    return regs[14] << 8 | regs[15]


def decode(row: bytes) -> str:
    """Screen codes (reverse bit stripped), lowercase charset."""
    out = ''
    for b in row:
        c = b & 0x7f
        if 1 <= c <= 26:
            out += chr(c + 96)
        elif 0x41 <= c <= 0x5a:
            out += chr(c)
        elif c in (0x1b, 0x1d):
            out += '[' if c == 0x1b else ']'
        else:
            out += '@' if c == 0 else chr(c)
    return out.rstrip()


def screen(cols: int) -> list:
    if cols == 80:
        d = dump('vdc', 0, 2000)
    else:
        d = dump('default', 0x0400, 1000)
    return [decode(d[r * cols:(r + 1) * cols]) for r in range(25)]


def vic_raw() -> bytes:
    """The VIC screen, where the popup draws in either mode."""
    return dump('default', 0x0400, 1000)


def keys(codes: bytes, settle: float = 1.0) -> None:
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        pokes = ' '.join(f'${b:02x}' for b in chunk)
        mon([f'> ${NDX:02x} $00', f'> ${KEYD:04x} {pokes}',
             f'> ${NDX:02x} ${len(chunk):02x}'], wait=0.1, quiet=0.3)
        time.sleep(settle)
    time.sleep(settle)


def type_line(text: str, settle: float = 3.0) -> None:
    keys(bytes(ord(ch.upper()) | (0x80 if ch.isupper() else 0)
               for ch in text) + b'\r')
    time.sleep(settle)


def boot(mode: str) -> subprocess.Popen:
    vice = subprocess.Popen(
        ['x128', mode, '-VDC16KB', '-acia1', '-acia1base', '0xDE00',
         '-acia1mode', '1', '-acia1irq', '1', '-myaciadev', '0',
         '-rsdev1', f'127.0.0.1:{PETSCII}', '-rsdev1ip232', '-rsdev1baud', '38400',
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{MON}',
         '-autostartprgmode', '1', '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cols = 80 if mode == '-80col' else 40
    time.sleep(12)
    for _ in range(48):
        try:
            if screen(cols)[24] == 'login >':
                break
        except OSError:
            pass
        time.sleep(1)
    time.sleep(1)
    return vice


def wait_popup(timeout: float = 15) -> None:
    """Until the popup's title is on the VIC screen (it draws there in
    either mode)."""
    end = time.time() + timeout
    while time.time() < end:
        vic = vic_raw()
        if any('Video Settings:' in decode(vic[r * 40:(r + 1) * 40])
               for r in range(25)):
            return
        time.sleep(1)
    if os.environ.get('DEBUG'):
        print('      no popup:', screen(40))


def open_popup(cols: int) -> None:
    if cols == 40:
        type_line('mp', 3)               # More prompt off: 40 columns would
                                         # page the PREFS menu
    type_line('prefs', 4)
    type_line('t', 4)
    type_line('v', 3)
    wait_popup()


def value_at(vic: bytes, slot: int) -> int:
    """The two-digit value on a popup field row (columns 32-33)."""
    row = (POPUP_TOP + 2 + slot) * 40
    try:
        return int(bytes(vic[row + 32:row + 34]).decode())
    except ValueError:
        return -1                    # no popup there


def reversed_text(vic: bytes, slot: int) -> str:
    row = vic[(POPUP_TOP + 2 + slot) * 40:(POPUP_TOP + 3 + slot) * 40]
    return decode(bytes(b for b in row if b & 0x80)).strip()


def sym(name: str) -> int:
    for line in open(CLIENT / 'client-128_pp.sym'):
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m and m.group(1).lower() == name:
            return int(m.group(2), 16)
    raise KeyError(name)


def text_colors(cols: int) -> set:
    """The colors (VIC-II numbers in 40 columns, RGBI in 80) a background
    must not show as -- video_menu_128.asm's vs_bg_clash."""
    kernal_color = dump('default', 0xf1, 1)[0] & 0x0f
    if cols == 80:
        return {dump('default', sym('dlg_attr'), 1)[0] & 0x0f, kernal_color}
    return {dump('default', sym('vdlg_color'), 1)[0] & 0x0f, kernal_color}


def next_bg(v: int, texts: set, cols: int, steps: int = 1) -> int:
    """Where CRSR right takes Background from v, skipping text colors."""
    for _ in range(steps):
        v = (v + 1) % 16
        while (DLG_VDC_COLORS[v] if cols == 80 else v) in texts:
            v = (v + 1) % 16
    return v


def bg_cycle(cols: int, slot: int) -> tuple:
    """Select the Background row, press CRSR right 16 times; returns
    (values visited, the text colors)."""
    texts = text_colors(cols)
    keys(bytes([CRSR_DOWN] * slot))
    seen = []
    for _ in range(16):
        keys(bytes([CRSR_RIGHT]), settle=0.6)
        # just the two digits -- the server gives up on the popup after
        # UPLOAD_TIMEOUT_SECONDS (5 minutes), and a whole-screen dump per
        # step got this loop close enough to that to lose the cancel
        row = 0x0400 + (POPUP_TOP + 2 + slot) * 40 + 32
        seen.append(int(dump('default', row, 2).decode()))
    keys(bytes([RUN_STOP]), settle=2.0)
    time.sleep(2)
    if os.environ.get('DEBUG'):
        print('      after cancel:', screen(cols)[12:])
    return seen, texts


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


def has(lines: list, text: str) -> bool:
    return any(text in l for l in lines)


server = subprocess.Popen(
    [sys.executable, 'simple_server.py', '--host', '127.0.0.1', '--port', str(JSON),
     '--petscii-port', str(PETSCII)],
    cwd=SERVER, stdout=subprocess.DEVNULL,
    stderr=open(os.environ['SERVER_LOG'], 'w') if os.environ.get('SERVER_LOG')
    else subprocess.DEVNULL)
vice = None
try:
    time.sleep(6)

    # --- 80 columns --- (ONLY40=1 in the environment skips them)
    if not os.environ.get('ONLY40'):
        vice = boot('-80col')
        type_line('connect guest', 4)
        open_popup(80)
        s = screen(80)
        r = vdc_regs()
        check('A 80 columns: popup on the VDC with the VDC fields, VDC cursor off',
              has(s, 'Video Settings: 80 columns') and has(s, 'Background color:')
              and has(s, 'Cursor blink speed:') and has(s, 'Cursor:   Soft  Block  Line')
              and has(s, 'Flash:') and not has(s, 'Border color:')
              and cursor_mode(r) == 0x20,
              f'R10=${cursor_mode(r):02x} rows: {s[POPUP_TOP:POPUP_TOP + 13]}')

        bg0 = value_at(vic_raw(), 0)
        texts80 = text_colors(80)
        keys(bytes([CRSR_RIGHT]))
        r = vdc_regs()
        bg1 = value_at(vic_raw(), 0)
        check('B Background right: next color (past any text color), R26 '
              'previews its RGBI color',
              bg1 == next_bg(bg0, texts80, 80) and r[26] & 0x0f == DLG_VDC_COLORS[bg1],
              f'{bg0} -> {bg1}, R26=${r[26]:02x}')

        keys(bytes([CRSR_DOWN, CRSR_DOWN, CRSR_RIGHT]))
        r = vdc_regs()
        vic = vic_raw()
        check('C Cursor -> Block: R10 $60, VDC cursor on the demo cell',
              cursor_mode(r) == 0x60 and cursor_addr(r) == DEMO_VDC
              and reversed_text(vic, 2) == 'Block',
              f'R10=${cursor_mode(r):02x} addr={cursor_addr(r)} bar={reversed_text(vic, 2)!r}')

        keys(bytes([CRSR_DOWN, CRSR_RIGHT]))
        fast = cursor_mode(vdc_regs())
        keys(bytes([CRSR_RIGHT]))
        solid = cursor_mode(vdc_regs())
        keys(bytes([CRSR_RIGHT, CRSR_LEFT, CRSR_LEFT]))   # stays on Solid, then back
        slow = cursor_mode(vdc_regs())
        check('D Flash: Fast $40, Solid $00, back to Slow $60',
              (fast, solid, slow) == (0x40, 0x00, 0x60),
              f'${fast:02x} ${solid:02x} ${slow:02x}')

        keys(bytes([RETURN]), settle=2.0)
        time.sleep(3)
        s = screen(80)
        r = vdc_regs()
        check('E RETURN: saved, status row message, popup gone, VDC cursor on the '
              'input row after the prompt',
              has(s, 'Video settings saved') and 'VDC cursor' in s[23]
              and not has(s, 'Video Settings: 80 columns')
              and s[24] == 'terminal settings >'
              and cursor_mode(r) == 0x60
              and cursor_addr(r) == INPUT_VDC + len(s[24]) + 1
              and r[26] & 0x0f == DLG_VDC_COLORS[bg1],
              f'|{s[23]}| |{s[24]}| R10=${cursor_mode(r):02x} addr={cursor_addr(r)} '
              f'R26=${r[26]:02x}')

        type_line('v', 3)
        wait_popup()
        vic = vic_raw()
        keys(bytes([CRSR_RIGHT, CRSR_RIGHT]))
        mid = vdc_regs()[26] & 0x0f
        keys(bytes([RUN_STOP]), settle=2.0)
        time.sleep(3)
        s = screen(80)
        r = vdc_regs()
        check('F reopen: Block still chosen; RUN/STOP reverts the preview, server '
              'says unchanged, VDC cursor back on the input row',
              reversed_text(vic, 2) == 'Block'
              and mid == DLG_VDC_COLORS[next_bg(bg1, texts80, 80, 2)]
              and has(s, 'Video settings unchanged.')
              and r[26] & 0x0f == DLG_VDC_COLORS[bg1]
              and cursor_mode(r) == 0x60
              and cursor_addr(r) == INPUT_VDC + len(s[24]) + 1,
              f'bar={reversed_text(vic, 2)!r} mid=${mid:x} R26=${r[26]:02x} '
              f'R10=${cursor_mode(r):02x} addr={cursor_addr(r)} |{s[24]}|')

        before = cursor_addr(vdc_regs())
        keys(b'ABC')
        s = screen(80)
        after = cursor_addr(vdc_regs())
        check('G typing still works and moves the VDC cursor along',
              s[24] == 'terminal settings > abc' and after == before + 3,
              f'|{s[24]}| {before} -> {after}')

        keys(b'\r', settle=2.0)
        time.sleep(2)
        type_line('v', 3)
        wait_popup()
        seen, texts = bg_cycle(80, 0)
        shown = {DLG_VDC_COLORS[v] for v in seen}
        check('J 80 columns: Background skips colors that hide the text',
              not (shown & texts) and len(set(seen)) == 16 - len(texts),
              f'visited {seen}, text RGBI {sorted(texts)}')
        vice.terminate(); vice.wait(); vice = None
        time.sleep(2)

    # --- 40 columns ---
    vice = boot('-40col')
    type_line('connect guest', 5)
    open_popup(40)
    s = screen(40)
    check('H 40 columns: popup with Border/Background/blink, no VDC rows',
          has(s, 'Video Settings: 40 columns') and has(s, 'Border color:')
          and has(s, 'Background color:') and has(s, 'Cursor blink speed:')
          and not has(s, 'Cursor:   Soft') and not has(s, 'Flash:'),
          str(s[POPUP_TOP:POPUP_TOP + 12]))

    seen, texts = bg_cycle(40, 1)
    check('K 40 columns: Background skips colors that hide the text',
          not (set(seen) & texts) and len(set(seen)) == 16 - len(texts),
          f'visited {seen}, text colors {sorted(texts)}')
    type_line('v', 3)
    wait_popup()

    b0 = dump('default', 0xd020, 1)[0] & 0x0f
    keys(bytes([CRSR_RIGHT]))
    b1 = dump('default', 0xd020, 1)[0] & 0x0f
    keys(bytes([RETURN]), settle=2.0)
    time.sleep(3)
    s = screen(40)
    b2 = dump('default', 0xd020, 1)[0] & 0x0f
    # The redrawn PREFS menu scrolls the "saved" line off 40 columns, so
    # check the round trip instead: reopened, the server sends the new
    # border back.
    type_line('v', 3)
    wait_popup()
    reopened = value_at(vic_raw(), 0)
    keys(bytes([RUN_STOP]), settle=2.0)
    check('I Border right previews on $D020; RETURN saves it (the server '
          'sends it back on reopening) and it stays',
          b1 == (b0 + 1) % 16 and b2 == b1 and reopened == b1
          and not has(s, 'Video Settings: 40 columns')
          and s[24] == 'terminal settings >',
          f'{b0} -> {b1} -> {b2}, reopened {reopened} |{s[24]}|')
finally:
    if vice:
        vice.terminate()
    server.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
