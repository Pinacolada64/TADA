#!/usr/bin/env python3
"""x128 scenario for client-128.asm's SwiftLink connection, against a
real server.

Starts its own server (server/simple_server.py, PETSCII port PETSCII,
JSON port JSON -- distinct from the live server's defaults) and boots
x128 with an emulated SwiftLink (ACIA at $DE00, SwiftLink mode, NMI,
bridged over IP232 to that port -- the same cartridge as `make
vice128`). 80 columns first, reading VDC RAM through the remote monitor
(and the scrollback ring in bank 0 RAM for anything scrolled off):
  A  connect: the 40/80 menu answered "8" (history reads "[4/8] > 8"),
     connected status message, the login prompt moved to the input row
  B  "connect guest": echoed after the prompt, welcome text, "main >"
     on the input row, the Hourglass clock stream on the status row
  C  mid-line: with "loo" typed, a second guest (a JSON bot) says
     something -- it lands in the dialogue on its own line and the
     input row still reads "main > loo"
  D  "k" + RETURN: history reads "main > look", room text follows
  E  "keys" (Help popup stream): skipped with the client's note, the
     prompt comes back
  F  prefs -> t -> v (Video Settings stream): the client's cancel reply
     unblocks the server ("Video settings unchanged.")
Then 40 columns (SCREEN_RAM):
  G  menu answered "4", login prompt on the input row, status row intact
  H  "connect guest" + "look": echo and room text in the rows 0-22
     window, status row and input row untouched
Keystrokes go in through the C128 KERNAL keyboard buffer (KEYD $034a,
NDX $d0), as in the other vice128_*.py tests. The VICE window takes real
keystrokes too, so leave it alone while it runs.

Written 2026-09-29. Usage: ../../server/.venv/bin/python3 vice128_swiftlink_test.py
(from the main checkout; any .venv python with the server's packages works)
"""
import asyncio, re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
SERVER = CLIENT.parent.parent / 'server'
PRG = CLIENT / 'client-128.prg'
MON = 6542
PETSCII, JSON = 35165, 35164
KEYD, NDX = 0x034a, 0xd0
HIST_CHARS, HIST_BYTES = 0x6000, 150 * 80   # vdc_screen.asm's history ring


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


def decode(row: bytes) -> str:
    """Screen codes (reverse bit stripped), lowercase charset."""
    out = ''
    for b in row:
        c = b & 0x7f
        if 1 <= c <= 26:
            out += chr(c + 96)
        elif 0x41 <= c <= 0x5a:
            out += chr(c)
        elif c in (0x1b, 0x1d):          # screen codes for [ and ]
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


def history() -> list:
    d = dump('ram', HIST_CHARS, HIST_BYTES)
    return [decode(d[r * 80:(r + 1) * 80]) for r in range(150)]


def keys(codes: bytes) -> None:
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        pokes = ' '.join(f'${b:02x}' for b in chunk)
        mon([f'> ${NDX:02x} $00', f'> ${KEYD:04x} {pokes}',
             f'> ${NDX:02x} ${len(chunk):02x}'])
        time.sleep(1.0)
    time.sleep(1.0)


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
    # Boot + connect + banner takes ~20 s, more on a loaded machine --
    # wait for the login prompt on the input row instead of a fixed
    # sleep (keys typed before the editor runs are lost).
    cols = 80 if mode == '-80col' else 40
    time.sleep(12)
    for _ in range(48):
        try:
            if screen(cols)[24] == 'login >':
                break
        except OSError:
            pass                         # monitor not listening yet
        time.sleep(1)
    time.sleep(1)
    return vice


def bot_say(text: str) -> None:
    """A second guest on the JSON port says *text* in the lobby, then quits."""
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
        await _send(writer, {'lines': [f'say {text}'], 'mode': 'game'})
        await _recv_all(reader, timeout=2.0)
        await _send(writer, {'lines': ['quit'], 'mode': 'game'})
        await asyncio.sleep(1)
        writer.close()
    asyncio.run(run())


failures = []


def check(label, cond, detail=''):
    print(f'{"PASS" if cond else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not cond:
        failures.append(label)


def has(lines: list, text: str) -> bool:
    return any(text in l for l in lines)


# The server runs under this script's own interpreter -- run it with the
# repo's .venv python (server/CLAUDE.md), which has the server's packages.
server = subprocess.Popen(
    [sys.executable, 'simple_server.py', '--host', '127.0.0.1', '--port', str(JSON),
     '--petscii-port', str(PETSCII)],
    cwd=SERVER, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
vice = None
try:
    time.sleep(6)

    # --- 80 columns ---
    vice = boot('-80col')
    s = screen(80)
    h = history()
    check('A 80 columns: menu answered 8, connected, login prompt on the input row',
          has(s + h, '[4/8] > 8') and has(s + h, '80 column mode set.')
          and s[23].startswith('TADA -- Commodore 128 client')
          and '(offline)' not in s[23]
          and s[24] == 'login >' and has(s, "Type 'connect guest'"),
          f'|{s[23]}| |{s[24]}|')

    type_line('connect guest', 4)
    s = screen(80)
    check('B connect guest: echoed after the prompt, "main >" on the input '
          'row, clock on the status row',
          has(s, 'login > connect guest') and has(s, 'Welcome, Guest')
          and s[24] == 'main >' and re.search(r'\d\d:\d\d$', s[23]) is not None,
          f'|{s[23]}| |{s[24]}|')

    keys(b'LOO')
    bot_say('Mid-line test.')
    time.sleep(2)
    s = screen(80)
    said = [l for l in s if 'says, "Mid-line test."' in l]
    check('C mid-line: the other guest\'s line lands in the dialogue, '
          'input row keeps "main > loo"',
          len(said) == 1 and said[0].startswith('Guest') and s[24] == 'main > loo',
          f'{said} |{s[24]}|')

    keys(b'K\r')
    time.sleep(3)
    s = screen(80)
    check('D RETURN: history reads "main > look", room text follows',
          has(s, 'main > look') and has(s, 'MERCHANT LOBBY') and s[24] == 'main >')

    type_line('keys', 4)
    s = screen(80)
    check('E Help popup stream: skipped with a note, prompt back',
          has(s, 'main > keys') and has(s, '(Popup not on the 128 client yet.)')
          and s[24] == 'main >')

    type_line('prefs', 4)
    type_line('t', 4)
    type_line('v', 5)
    s = screen(80)
    check('F Video Settings stream: cancel reply, server carries on',
          has(s + history(), 'Video settings unchanged.')
          and s[24] == 'terminal settings >',
          f'|{s[24]}|')
    vice.terminate(); vice.wait(); vice = None
    time.sleep(2)

    # --- 40 columns ---
    vice = boot('-40col')
    s = screen(40)
    check('G 40 columns: menu answered 4, login prompt on the input row',
          s[23].startswith('TADA -- Commodore 128 client')
          and s[24] == 'login >' and has(s, "'connect guest'"),
          f'|{s[23]}| |{s[24]}|')

    type_line('connect guest', 5)
    type_line('look', 4)
    s = screen(40)
    look = [i for i, l in enumerate(s) if l == 'main > look']
    check('H connect + look: echo and room text inside rows 0-22, status and '
          'input rows intact',
          len(look) == 1 and look[0] <= 22 and has(s[look[0]:23], 'MERCHANT LOBBY')
          and s[23].startswith('TADA -- Commodore 128 client')
          and s[24] == 'main >',
          f'look at {look} |{s[23]}| |{s[24]}|')
finally:
    if vice:
        vice.terminate()
    server.terminate()

print('\nall passed' if not failures else f'\n{len(failures)} failed')
sys.exit(1 if failures else 0)
