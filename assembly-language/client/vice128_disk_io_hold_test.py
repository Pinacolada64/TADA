#!/usr/bin/env python3
"""x128 stress test: disk I/O while the server keeps talking.

KERNAL serial-bus I/O with SwiftLink receive NMIs live hangs the 128
for good -- stuck at $E3A4-$E3AC, the serial routine's untimed wait on
the bus CLK line (see swiftlink.asm's sl_hold). The Keymap Editor's
save, the drive picker's bus scan and save, and Video Settings' save
hold the line around their I/O (sl_hold/sl_release). This drives the
first two with traffic arriving the whole time:

  - its own server (simple_server.py, ports of its own) and x128 in 80
    columns with a SwiftLink and a blank .d64 in a true-drive 1571 as
    device 8, so the saves really write;
  - a second guest on the JSON port saying something every ~0.2 s, in
    the same room, so text keeps streaming in;
  - ROUNDS rounds alternating F7 -> S (Keymap Editor, Save) and F5 ->
    RETURN (drive picker: scan, choose, save), each pair typed at once:
    with a popup open nothing drains the receive buffer, so after a
    second or two RTS flow control stops the traffic anyway -- it's a
    save right after opening that does its I/O with NMIs arriving. Each round must put its
    status message up ("Saved keymap." / "Data drive ..."); one that
    doesn't within ROUND_TIMEOUT seconds is a hang, reported with the
    CPU's PC.
At the end TADA128.CFG must be in the image's directory.

What reproduces the hang (2026-10-05): EMPTY_DRIVE=1 BURST=1. A build
from before sl_hold hung in round 2 (drive picker, PC=$E3B1 -- the same
serial routine's $DD00 reads); the build with it passed 24 rounds of
the same. The defaults (a disk in the drive, a trickle of traffic)
passed on both builds -- they check that saves still really write, not
the hang.

Written 2026-10-05. Usage, from this directory:
  ../../server/.venv/bin/python3 vice128_disk_io_hold_test.py
PRG=path tests another build (e.g. one from before sl_hold, to see the
hang); ROUNDS=n changes the round count (default 8). EMPTY_DRIVE=1 leaves
device 8 with no disk in it (saves fail through the error path -- the
case Video Settings first hung on); BURST=1 makes the other guest send
five long lines at a time, back to back, instead of one short one every
0.2 s.
"""
import asyncio, os, re, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

CLIENT = Path(__file__).parent
SERVER = CLIENT.parent.parent / 'server'
PRG = Path(os.environ.get('PRG', CLIENT / 'client-128.prg'))
ROUNDS = int(os.environ.get('ROUNDS', '8'))
ROUND_TIMEOUT = 40
EMPTY_DRIVE = bool(os.environ.get('EMPTY_DRIVE'))
BURST = bool(os.environ.get('BURST'))
LONG = 'The quick brown fox jumps over the lazy dog, again and again and again'
MON = 6562
PETSCII, JSON = 35185, 35184
KEYD, NDX = 0x034a, 0xd0
F5, F7 = 0x87, 0x88               # km_init_keyboard's single-byte F-keys


def mon(cmds, wait=0.1, quiet=0.3):
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
    s.sendall(b'x\n'); time.sleep(0.1); s.close()
    return buf.decode('latin-1')


def vdc_rows(first: int, last: int) -> list:
    """VDC screen rows first..last, decoded (lowercase charset)."""
    out = mon(['bank vdc', f'm ${first * 80:04x} ${(last + 1) * 80 - 1:04x}',
               'bank default'], wait=0.4, quiet=1.0)
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    rows = []
    for r in range(last - first + 1):
        text = ''
        for b in data[r * 80:(r + 1) * 80]:
            c = b & 0x7f
            text += chr(c + 96) if 1 <= c <= 26 else chr(c) if 0x20 <= c < 0x60 else ' '
        rows.append(text.rstrip())
    return rows


def keys(codes: bytes) -> None:
    pokes = ' '.join(f'${b:02x}' for b in codes)
    mon([f'> ${NDX:02x} $00', f'> ${KEYD:04x} {pokes}', f'> ${NDX:02x} ${len(codes):02x}'])


def type_line(text: str, settle: float = 3.0) -> None:
    keys(bytes(ord(ch.upper()) for ch in text) + b'\r')
    time.sleep(settle)


def pc() -> str:
    m = re.search(r'\.;([0-9a-f]{4})', mon(['r'], wait=0.4, quiet=1.0))
    return f'${m.group(1)}' if m else '?'


def talker(stop: threading.Event) -> None:
    """A second guest saying something every ~0.2 s until stop is set."""
    sys.path.insert(0, str(SERVER))
    from bot_client import _recv_all, _send

    async def run():
        reader, writer = await asyncio.open_connection('127.0.0.1', JSON)
        init = await _recv_all(reader, timeout=5.0)
        if init:
            await _send(writer, {'server_id': init[0].get('server_id', 'test_server'),
                                 'server_key': init[0].get('server_key', 'test_key')})
        while True:
            batch = await _recv_all(reader, timeout=3.0)
            if not batch:
                break
            p = next((m.get('prompt', '') for m in reversed(batch) if m.get('prompt')), '')
            if 'login' in p.lower():
                break
            if 'terminal type' in p.lower():
                await _send(writer, {'lines': ['A'], 'mode': 'login'})
            elif 'more' in p.lower():
                await _send(writer, {'lines': ['q'], 'mode': 'login'})
        await _send(writer, {'lines': ['connect guest'], 'mode': 'login'})
        await _recv_all(reader, timeout=3.0)
        n = 0
        while not stop.is_set():
            for _ in range(5 if BURST else 1):
                n += 1
                text = f'Traffic {n}. {LONG}' if BURST else f'Traffic {n}.'
                await _send(writer, {'lines': [f'say {text}'], 'mode': 'game'})
            await _recv_all(reader, timeout=0.05 if BURST else 0.2)
        await _send(writer, {'lines': ['quit'], 'mode': 'game'})
        writer.close()
    asyncio.run(run())


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


tmp = Path(tempfile.mkdtemp(prefix='tada128io-'))
disk = tmp / 'data.d64'
subprocess.run(['c1541', '-format', 'tada,01', 'd64', str(disk)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
server = subprocess.Popen(
    [sys.executable, 'simple_server.py', '--host', '127.0.0.1', '--port', str(JSON),
     '--petscii-port', str(PETSCII)],
    cwd=SERVER, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
vice = None
stop = threading.Event()
try:
    time.sleep(6)
    vice = subprocess.Popen(
        ['x128', '-80col', '-VDC16KB', '-drive8type', '1571']
        + ([] if EMPTY_DRIVE else ['-8', str(disk)])
        + ['-drive8truedrive', '+virtualdev8',
         '-acia1', '-acia1base', '0xDE00', '-acia1mode', '1', '-acia1irq', '1',
         '-myaciadev', '0', '-rsdev1', f'127.0.0.1:{PETSCII}', '-rsdev1ip232',
         '-rsdev1baud', '38400',
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{MON}',
         '-autostartprgmode', '1', '-autostart', str(PRG)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(12)
    for _ in range(60):
        try:
            if vdc_rows(24, 24)[0] == 'login >':
                break
        except OSError:
            pass
        time.sleep(1)
    type_line('connect guest', 5)
    threading.Thread(target=talker, args=(stop,), daemon=True).start()
    time.sleep(6)
    rows = vdc_rows(0, 22)
    check('traffic is arriving (the other guest\'s lines in the dialogue)',
          any('Traffic' in r for r in rows), str(rows[-3:]))

    print(f'testing {PRG}' + (' (empty drive)' if EMPTY_DRIVE else '')
          + (' (bursts)' if BURST else ''))
    hung = False
    for n in range(ROUNDS):
        keymap = n % 2 == 0
        # Open and save in one keyboard-buffer poke: while a popup is open
        # nothing drains rx_buf, so within a second or two it fills and
        # nmi_handler turns RTS off -- a save made after that sees no
        # traffic at all. Saving at once is the case with NMIs arriving.
        keys(bytes([F7, ord('S')]) if keymap else bytes([F5, 0x0d]))
        want = ('keymap' if keymap else 'data drive')
        status = ''
        end = time.time() + ROUND_TIMEOUT
        while time.time() < end:
            status = vdc_rows(23, 23)[0]
            if want in status.lower():
                break
            time.sleep(1)
        ok = want in status.lower()
        check(f'round {n + 1}: {"Keymap Editor save" if keymap else "drive picker scan + save"} '
              'comes back', ok, f'|{status}|' + ('' if ok else f' PC={pc()}'))
        if not ok:
            hung = True
            break
        time.sleep(2)

    stop.set()
    time.sleep(2)
    vice.terminate(); vice.wait(); vice = None
    if not hung and not EMPTY_DRIVE:
        listing = subprocess.run(['c1541', str(disk), '-dir'], capture_output=True,
                                 text=True).stdout
        check('TADA128.CFG written to the disk', 'tada128.cfg' in listing.lower(),
              listing.strip().splitlines()[-2:])
finally:
    stop.set()
    if vice:
        vice.terminate()
    server.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
