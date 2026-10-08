#!/usr/bin/env python3
"""Regression test for the C64 client's dialogue scroll ("lost lines" bug).

Boots tada-client.prg in its own headless-ish x64sc (injected straight into
RAM via -autostartprgmode 1 -- no disk load), points its SwiftLink at a tiny
in-process fake server that sends 30 numbered lines (every third one 60
chars long, so it wraps), then dumps whichever screen buffer is front via
the remote monitor and checks every line arrived, in order.

The bug this guards against (fixed 2026-09-28 in term_scroll_advance): the
raw dialogue-window shift left KERNAL's LDTB1 line-link bits stale, so after
a line wrapped from row 22 the next CR skipped to PROMPT_ROW and the
following line was lost/overwritten.

Uses its own ports (fake server 34099, monitor 6531) so it never touches the
live server (34064) or a dev VICE session (6510/6511/6512).

Usage: python3 vice_scroll_test.py [path/to/tada-client.prg]
"""
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
PRG = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'tada-client.prg'
LABELS = HERE / 'tada-client-vice-labels'
SERVER_PORT = 34099
MONITOR_PORT = 6531
JIFFY = Path.home() / 'Documents/c64/JiffyDOS'
VICE_ROMS = Path.home() / '.local/share/vice/C64'
SEND_DELAY = 8      # seconds after a connection opens before sending
SETTLE = 45         # seconds after launch before dumping the screen --
                    # each scroll waits ~5 frames of vblank, so 30+ lines
                    # of output need several real seconds to finish

LINES = [(f'LONG {n:02d} ' + 'X' * 44 + f' END{n:02d}') if n % 3 == 0
         else f'SHORT {n:02d}' for n in range(1, 31)]
PAYLOAD = b''.join(line.encode() + b'\r' for line in LINES)


def fake_server():
    # VICE opens (and drops) more than one connection while the ACIA
    # initializes, so keep accepting and only send on one that stays open.
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', SERVER_PORT))
    srv.listen(4)

    def handle(conn):
        alive = [True]

        def drain():
            while True:
                try:
                    data = conn.recv(1024)
                except OSError:
                    data = b''
                if not data:
                    alive[0] = False
                    return
        threading.Thread(target=drain, daemon=True).start()
        time.sleep(SEND_DELAY)
        if alive[0]:
            for i in range(0, len(PAYLOAD), 16):
                conn.sendall(PAYLOAD[i:i + 16])
                time.sleep(0.01)

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


def monitor(cmds):
    # One connection per batch -- the CPU stays paused while connected.
    s = socket.create_connection(('127.0.0.1', MONITOR_PORT))
    s.settimeout(3)
    buf = b''
    for cmd in cmds:
        s.sendall(cmd.encode() + b'\n')
        time.sleep(0.6)
        try:
            while True:
                data = s.recv(65536)
                if not data:
                    break
                buf += data
        except socket.timeout:
            pass
    s.close()
    return buf.decode('latin1')


def screen_code_to_char(b):
    b &= 0x7f
    if b == 0:
        return '@'
    if 1 <= b <= 26:
        return chr(ord('a') + b - 1)
    if 0x20 <= b <= 0x3f or 0x41 <= b <= 0x5a:
        return chr(b)
    return '.'


def main():
    front_hi_addr = int(re.search(r'al \$?([0-9a-f]+) \.front_hi$',
                                  LABELS.read_text(), re.M).group(1), 16)
    threading.Thread(target=fake_server, daemon=True).start()
    time.sleep(0.5)
    vice = subprocess.Popen(
        ['x64sc',
         '-kernal', str(JIFFY / 'Jiffydos-Kernal.rom'),
         '-basic', str(VICE_ROMS / 'basic-901226-01.bin'),
         '-chargen', str(VICE_ROMS / 'chargen-901225-01.bin'),
         '-acia1', '-rsdev3', f'127.0.0.1:{SERVER_PORT}',
         '-rsdev3baud', '38400', '-rsuserdev', '2', '-myaciadev', '2',
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{MONITOR_PORT}',
         '-autostartprgmode', '1', '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        time.sleep(SETTLE)
        out = monitor([f'm {front_hi_addr:04x} {front_hi_addr:04x}'])
        front_hi = int(re.search(r'>C:[0-9a-f]{4}\s+([0-9a-f]{2})', out).group(1), 16)
        out = monitor([f'm {front_hi:02x}00 {front_hi + 3:02x}e7', 'x'])
    finally:
        vice.kill()

    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(x, 16) for x in m.group(1).split()]
    rows = [''.join(screen_code_to_char(b) for b in data[r * 40:r * 40 + 40])
            for r in range(25)]
    for r, text in enumerate(rows):
        print(f'{r:2d}|{text}|')

    # Rejoin wrapped rows (a full 40-col row continues onto the next) and
    # check the visible tail of LINES appears contiguously, ending at 30.
    shown, pending = [], ''
    for text in rows[:23]:
        pending += text
        if len(text.rstrip()) < 40:
            if pending.strip():
                shown.append(pending.rstrip())
            pending = ''
    expected = [line.lower() for line in LINES]
    tail = expected[-len(shown):] if shown else []
    # The top-most visible row may be the cut-off second half of a line.
    if shown and shown[0] != tail[0] and tail[0].endswith(shown[0]):
        shown[0] = tail[0]
    if len(shown) < 10 or shown != tail:
        print(f'FAIL: expected the last {len(shown)} lines to be\n  '
              + '\n  '.join(tail) + '\ngot\n  ' + '\n  '.join(shown))
        sys.exit(1)
    print(f'PASS: last {len(shown)} lines present and in order')


if __name__ == '__main__':
    main()
