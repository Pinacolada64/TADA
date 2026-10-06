#!/usr/bin/env python3
"""Interactive VICE scenario for the client's own screen output.

Companion to vice_scroll_test.py (same ports, same fake-server approach,
prg injected straight into RAM). Drives a whole prompt cycle and checks
the screen through the remote monitor at each step:
  A  negotiation, colored/reverse text, then a prompt pinned to row 24
     (its inline copy erased from the dialogue)
  B  a typed line long enough to wrap off row 24: the status bar moves
     up to row 22 and the input area becomes rows 23-24
  C  cursor-left/right across the two input rows
  D  an async server page arriving mid-typing: lands in the dialogue,
     the input area is redrawn unchanged
  E  more typing + DEL + RETURN: the server receives the edited line,
     "prompt + line" goes into the history once, the status bar returns
     to row 23 and the next prompt lands on row 24
Keystrokes go in by poking the KERNAL keyboard buffer ($0277/$c6). The
VICE window it opens takes real keystrokes too, so leave it alone while
it runs.

Written 2026-09-28 for screen-output.asm (KERNAL-free output).
Usage: python3 vice_prompt_test.py
"""
import re, socket, subprocess, sys, threading, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'tada-client.prg'
LABELS = CLIENT / 'tada-client-vice-labels'
SERVER_PORT, MON = 34099, 6531
JIFFY = Path.home() / 'Documents/c64/JiffyDOS'
ROMS = Path.home() / '.local/share/vice/C64'

lab = {m.group(2): int(m.group(1), 16)
       for m in re.finditer(r'al \$?([0-9a-f]+) \.(\S+)', LABELS.read_text())}

got = bytearray()
events = {k: threading.Event() for k in ('neg', 'page', 'line')}
conn_holder = []


def serve():
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', SERVER_PORT)); srv.listen(4)

    def handle(c):
        alive = [True]
        def rd():
            while True:
                try: d = c.recv(1024)
                except OSError: d = b''
                if not d: alive[0] = False; return
                got.extend(d)
                if b'4\r' in got: events['neg'].set()
                if got.count(b'\r') >= 2: events['line'].set()
        threading.Thread(target=rd, daemon=True).start()
        time.sleep(6)
        if not alive[0]: return
        conn_holder.append(c)
        c.sendall(b'WELCOME TO THE TEST SERVER\rTERMINAL TYPE: ')
        events['neg'].wait()
        time.sleep(0.5)
        c.sendall(b'\x1cRED LINE\x05\r\x12REVERSE\x92 NORMAL\rMAIN > ')
        events['page'].wait()
        c.sendall(b'GUEST PAGES YOU\r')
        events['line'].wait()
        time.sleep(0.5)
        c.sendall(b'OK\rMAIN > ')
        time.sleep(600)

    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


def mon(cmds):
    s = socket.create_connection(('127.0.0.1', MON)); s.settimeout(2); buf = b''
    for cmd in cmds:
        s.sendall(cmd.encode() + b'\n'); time.sleep(0.4)
        try:
            while True:
                d = s.recv(65536)
                if not d: break
                buf += d
        except socket.timeout: pass
    s.close(); return buf.decode('latin1')


def membytes(out):
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(x, 16) for x in m.group(1).split()]
    return data


def ch(b):
    b &= 0x7f
    if 1 <= b <= 26: return chr(ord('a') + b - 1)
    if 0x20 <= b <= 0x3f or 0x41 <= b <= 0x5a: return chr(b)
    return '@' if b == 0 else '.'


def snapshot(title):
    fh_addr = lab['front_hi']
    out = mon([f'm {fh_addr:04x} {fh_addr:04x}',
               f"m {lab['crsr_row']:04x} {lab['crsr_col']:04x}", 'x'])
    vals = membytes(out)
    fh, row, col = vals[0], vals[1], vals[2]
    out = mon([f'm {fh:02x}00 {fh+3:02x}e7', 'm d800 dbe7', 'x'])
    data = membytes(out)
    scr, colr = data[:1000], data[1000:2000]
    print(f'--- {title}: cursor row {row} col {col}')
    rows = []
    for r in range(25):
        t = ''.join(ch(b) for b in scr[r*40:r*40+40])
        rv = ''.join('^' if b & 0x80 else ' ' for b in scr[r*40:r*40+40])
        rows.append((t, rv, [c & 15 for c in colr[r*40:r*40+40]]))
        print(f'{r:2d}|{t}|' + ('  rvs:' + rv.rstrip() if rv.strip() else ''))
    return row, col, rows


def type_keys(petscii):
    for i in range(0, len(petscii), 10):
        chunk = petscii[i:i+10]
        mon(['> c6 00', '> 0277 ' + ' '.join(f'{b:02x}' for b in chunk),
             f'> c6 {len(chunk):02x}', 'x'])
        time.sleep(1.0)


def main():
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(0.5)
    vice = subprocess.Popen(['x64sc', '-kernal', str(JIFFY/'Jiffydos-Kernal.rom'),
        '-basic', str(ROMS/'basic-901226-01.bin'), '-chargen', str(ROMS/'chargen-901225-01.bin'),
        '-acia1', '-rsdev3', f'127.0.0.1:{SERVER_PORT}', '-rsdev3baud', '38400',
        '-rsuserdev', '2', '-myaciadev', '2',
        '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{MON}',
        '-autostartprgmode', '1', '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    results = []
    def check(name, cond):
        results.append((name, cond)); print(('PASS ' if cond else 'FAIL ') + name)
    try:
        time.sleep(22)
        snapshot('A0: settle probe')
        time.sleep(3)
        row, col, rows = snapshot('A: prompt relocated')
        text = [r[0].rstrip() for r in rows]
        def is_bar(r): return all(c == '^' for c in rows[r][1])
        check('A prompt on row 24', text[24] == 'main >' and (row, col) == (24, 7))
        check('A inline prompt copy erased', 'main >' not in text[:23])
        red = [(r, r[0].index('red line')) for r in rows if 'red line' in r[0]]
        check('A red line color', bool(red) and red[0][0][2][red[0][1]] == 2)
        rv = [r for r in rows if r[0].startswith('reverse normal')]
        check('A reverse word', bool(rv) and rv[0][1].startswith('^^^^^^^ '))
        check('A status bar on row 23', is_bar(23) and not is_bar(22))

        typed = b'ABCDEFGHIJ' * 4 + b'KLMNO'          # 45 chars, wraps on row 24
        full = 'main > ' + 'abcdefghij' * 4 + 'klmno'
        type_keys(typed)
        time.sleep(1)
        row, col, rows = snapshot('B: long line typed')
        text = [r[0].rstrip() for r in rows]
        check('B status bar moved up to row 22', is_bar(22) and not is_bar(23))
        check('B input on rows 23-24', text[23] == full[:40] and text[24] == full[40:] and (row, col) == (24, 12))

        type_keys(bytes([0x9d] * 10))
        type_keys(bytes([0x9d] * 3))
        time.sleep(0.5)
        row, col, rows = snapshot('C: 13x cursor left')
        check('C cursor walked back to row 23 col 39', (row, col) == (23, 39))
        type_keys(bytes([0x1d]))
        time.sleep(0.5)
        row, col, _ = snapshot('C2: 1x cursor right')
        check('C2 cursor forward to row 24 col 0', (row, col) == (24, 0))
        type_keys(bytes([0x1d] * 12))

        events['page'].set()
        time.sleep(4)
        row, col, rows = snapshot('D: async page while typing')
        text = [r[0].rstrip() for r in rows]
        check('D page shown in the dialogue', 'guest pages you' in text[:22])
        check('D input area untouched', is_bar(22) and text[23] == full[:40] and text[24] == full[40:] and (row, col) == (24, 12))
        check('D no stray reverse cells in dialogue', not any('^' in r[1] for r in rows[:22] if not r[0].startswith('reverse normal')))

        type_keys(b'XYZ' + bytes([0x14]))
        type_keys(b'\r')
        time.sleep(4)
        row, col, rows = snapshot('E: after RETURN and server reply')
        text = [r[0].rstrip() for r in rows]
        sent = bytes(got).split(b'\r')[1]
        print('server received:', sent)
        check('E server got the edited line', sent == typed + b'XY')
        sub = full + 'xy'
        i = text.index(sub[:40]) if sub[:40] in text else -1
        check('E submitted line in history once, then the reply',
              i >= 0 and text[i+1] == sub[40:] and text[i+2] == 'ok' and text[:23].count('main >') == 0)
        check('E page still above it', 'guest pages you' in text[:i] if i >= 0 else False)
        check('E layout back to one input row', is_bar(23) and not is_bar(22))
        check('E new prompt pinned to row 24', text[24] == 'main >' and (row, col) == (24, 7))
    finally:
        vice.kill()
    passed = sum(c for _, c in results)
    print(f"\n{passed}/{len(results)} checks passed")
    sys.exit(0 if passed == len(results) else 1)


main()
