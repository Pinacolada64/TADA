#!/usr/bin/env python3
"""Video Settings' Border style (CONFIG.MNU) end to end under VICE.

Boots a copy of tada-client.d64 (make d64 first) in x64sc with a
SwiftLink bridged over IP232 to a fake server in this script -- no real
TADA server needed. The fake server answers the negotiation, then sends
the display-settings stream that opens CONFIG.MNU, the same bytes
commands/c64_display.py sends.
  1. first open: the Gothic box glyphs get backed up to BORDER_BACKUP
     (constants.asm), BORDER_SIG set, style Single, bar on "Single"
  2. CRSR-DOWN x3: marker on the Border style row, its help text and
     the "Choose style" CRSR hint shown
  3. CRSR-RIGHT: the charset's 11 box glyphs become config_menu.asm's
     double_glyphs, bar on "Double"; CRSR-LEFT puts Gothic back
  4. while toggling, the server sends a burst of text -- run_under_io
     holds the receive NMI off around each glyph copy, so after RETURN
     (Save) every line must still print intact
  5. RETURN sends the usual 3-byte save; Double stays in the charset
  6. second open: bar starts on "Double", the backup is still Gothic;
     CRSR-LEFT then RUN/STOP (Cancel) reverts the charset to Double
Saves a screenshot next to this script (border_style_live.png).

Written 2026-10-02. Usage:
    make d64 && ../../server/.venv/bin/python3 vice_border_style_test.py
The VICE window takes real keystrokes, so leave it alone while this
runs.
"""
import re, shutil, socket, subprocess, sys, threading, time
from pathlib import Path

import vice_drive_id_test as vt          # mon(), dump(), MON

CLIENT = Path(__file__).parent
SCREEN = 0xc400                          # the client's SCREEN_BUF_A
CHARGEN = 0xd000                         # constants.asm's POPUP_CHARGEN
BORDER_SIG = 0x9000                      # constants.asm's BORDER_STATE
BORDER_CUR_STYLE = 0x9002
BORDER_BACKUP = 0x9008
GLYPH_CODES = [0x40, 0x5b, 0x5d, 0x6b, 0x6d, 0x6e, 0x70, 0x71, 0x72, 0x73, 0x7d]
STYLE_ROW = 11                           # config_menu.asm: BOX_TOP_ROW+5
HELP_ROW = 13                            # BOX_TOP_ROW+7
PORT = 34099
OPEN_STREAM = bytes([0x01, 0x06, 0x03, 0x00, 14, 6, 2])   # border 14, bg 6, blink 2


def bits_glyphs(path: Path, start_label: str, count: int) -> bytes:
    """The first `count` 8-row `bits` glyphs after `start_label:`."""
    lines = path.read_text().splitlines()
    i = lines.index(f'{start_label}:')
    rows = [re.match(r'\s+bits ([.*]{8})', l) for l in lines[i + 1:]]
    rows = [m.group(1) for m in rows if m][:count * 8]
    return bytes(int(r.replace('.', '0').replace('*', '1'), 2) for r in rows)


GOTHIC_ALL = bits_glyphs(CLIENT / 'gothic-charset.asm', 'gothic_charset', 128)
GOTHIC = b''.join(GOTHIC_ALL[c * 8:c * 8 + 8] for c in GLYPH_CODES)
DOUBLE = bits_glyphs(CLIENT / 'config_menu.asm', 'double_glyphs', len(GLYPH_CODES))


def petscii_encode(text: str) -> bytes:
    """Quick-n-dirty ASCII -> PETSCII: just swap the case. In the client's
    lowercase charset PETSCII $41-$5a are lowercase and $c1-$da
    uppercase, so an ASCII lowercase byte ($61-$7a) shows up as
    uppercase -- swapcase() fixes letters; digits, space, punctuation
    and CR are the same in both. Not for anything outside plain ASCII."""
    return text.swapcase().encode('ascii')


class FakeServer:
    """One IP232 connection: collects what the client sends (escapes
    stripped -- nothing here sends or expects a real $ff byte)."""
    def __init__(self):
        self.lsock = socket.create_server(('127.0.0.1', PORT))
        self.conn = None
        self.rx = bytearray()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.conn, _ = self.lsock.accept()
        pending = b''
        while True:
            d = self.conn.recv(4096)
            if not d:
                return
            d = pending + d
            pending = b''
            i = 0
            while i < len(d):
                if d[i] == 0xff:
                    if i + 1 == len(d):
                        pending = d[i:]
                        break
                    if d[i + 1] == 0xff:
                        self.rx.append(0xff)
                    i += 2             # ip232 control (DTR etc) or escaped $ff
                else:
                    self.rx.append(d[i])
                    i += 1

    def send(self, data: bytes | str):
        """bytes go out as-is (protocol streams); str is player-visible
        text, run through petscii_encode first."""
        if isinstance(data, str):
            data = petscii_encode(data)
        self.conn.sendall(data)

    def wait_rx(self, want: bytes, timeout: float) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if want in self.rx:
                return True
            time.sleep(0.25)
        return False


def decode(row: bytes) -> str:
    text = ''
    for b in row:
        b &= 0x7f
        if 1 <= b <= 26:
            text += chr(b + 96)
        elif 0x41 <= b <= 0x5a or 0x20 <= b <= 0x3f:
            text += chr(b)
        else:
            text += '+'
    return text


def screen_rows(first: int, count: int) -> list[str]:
    data = vt.dump(SCREEN + first * 40, count * 40)
    return [decode(data[i * 40:i * 40 + 40]) for i in range(count)]


def reversed_cols(row: int) -> list[int]:
    return [i for i, b in enumerate(vt.dump(SCREEN + row * 40, 40)) if b & 0x80]


def charset_glyphs() -> bytes:
    return b''.join(vt.dump(CHARGEN + c * 8, 8) for c in GLYPH_CODES)


def keys(*codes, settle=1.5):
    vt.mon(['> $c6 00', '> $0277 ' + ' '.join(f'{c:02x}' for c in codes),
            f'> $c6 {len(codes):02x}'])
    time.sleep(settle)


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def open_popup(srv: FakeServer):
    srv.send(OPEN_STREAM)
    for _ in range(40):                  # CONFIG.MNU LOAD at 1541 speed
        time.sleep(1)
        try:
            if 'Border style' in screen_rows(STYLE_ROW, 1)[0]:
                break
        except OSError:
            pass
    time.sleep(1)


def main():
    assert len(DOUBLE) == 88, len(DOUBLE)
    disk = CLIENT / 'border_style_live.d64'
    shutil.copy(CLIENT / 'tada-client.d64', disk)
    srv = FakeServer()
    p = subprocess.Popen(
        ['x64sc', '-acia1', '-acia1base', '0xDE00', '-acia1mode', '1',
         '-acia1irq', '1', '-myaciadev', '0',
         '-rsdev1', f'127.0.0.1:{PORT}', '-rsdev1ip232', '-rsdev1baud', '38400',
         '-drive8type', '1541', '-8', str(disk),
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{vt.MON}',
         '-autostart', str(disk)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(90):               # autostart + connect
            if srv.conn:
                break
            time.sleep(1)
        time.sleep(3)
        srv.send('TADA border style test\r')
        check('client answers the negotiation with "4"', srv.wait_rx(b'4\r', 30), bytes(srv.rx))
        srv.rx.clear()
        srv.send('Ready\r')
        time.sleep(2)

        print('First open:')
        open_popup(srv)
        for r in screen_rows(6, 13):
            print('   |' + r + '|')
        check('BORDER_SIG set', vt.dump(BORDER_SIG, 2) == b'TB', vt.dump(BORDER_SIG, 2))
        check('BORDER_CUR_STYLE = Single', vt.dump(BORDER_CUR_STYLE, 1) == b'\0')
        check('backup holds the Gothic box glyphs', vt.dump(BORDER_BACKUP, 88) == GOTHIC)
        check('charset still Gothic', charset_glyphs() == GOTHIC)
        check('bar on Single (cols 20-27)', reversed_cols(STYLE_ROW) == list(range(20, 28)),
              reversed_cols(STYLE_ROW))

        keys(0x11, 0x11, 0x11)            # CRSR-DOWN x3
        row = screen_rows(STYLE_ROW, 1)[0]
        check('marker on the Border style row', row[5] == '>', row)
        help_row = screen_rows(HELP_ROW, 1)[0]
        check('Border style help text', 'Single or Double line borders' in help_row, help_row)
        hint = screen_rows(16, 1)[0]      # BOX_TOP_ROW+10
        check('CRSR hint says "Choose style"', 'Crsr Left/Right: Choose style' in hint, hint)

        keys(0x1d)                        # CRSR-RIGHT: Double
        check('CRSR-RIGHT: charset has the double glyphs', charset_glyphs() == DOUBLE)
        check('BORDER_CUR_STYLE = Double', vt.dump(BORDER_CUR_STYLE, 1) == b'\1')
        check('bar on Double (cols 27-34)', reversed_cols(STYLE_ROW) == list(range(27, 35)),
              reversed_cols(STYLE_ROW))
        vt.mon([f'screenshot "{CLIENT / "border_style_live.png"}" 2'])
        keys(0x9d)                        # CRSR-LEFT: Single
        check('CRSR-LEFT: charset back to Gothic', charset_glyphs() == GOTHIC)

        # Text arriving while glyphs are being copied -- see run_under_io.
        burst = ''.join(f'Burst {i:02d} 0123456789 abcdefghij\r' for i in range(8))
        def send_burst():
            for i in range(0, len(burst), 16):
                srv.send(burst[i:i + 16])
                time.sleep(0.05)
        t = threading.Thread(target=send_burst)
        t.start()
        for _ in range(4):
            keys(0x1d, settle=0.2)
            keys(0x9d, settle=0.2)
        t.join()
        keys(0x1d)                        # end on Double
        check('after toggling: Double', charset_glyphs() == DOUBLE)

        srv.rx.clear()
        keys(0x0d, settle=4)              # RETURN: save
        check('RETURN sends the 3-byte save', srv.wait_rx(bytes([1, 6, 3, 0, 14, 6, 2]), 5),
              bytes(srv.rx).hex())
        check('Double stays after Save', charset_glyphs() == DOUBLE)
        time.sleep(2)
        screen = '\n'.join(screen_rows(0, 23))
        got = [i for i in range(8) if f'Burst {i:02d} 0123456789 abcdefghij' in screen]
        check('the burst sent mid-swap printed intact', got == list(range(8)), got)
        if got != list(range(8)):
            print(screen)

        print('Second open:')
        open_popup(srv)
        check('bar starts on Double', reversed_cols(STYLE_ROW) == list(range(27, 35)),
              reversed_cols(STYLE_ROW))
        check('backup still Gothic', vt.dump(BORDER_BACKUP, 88) == GOTHIC)
        keys(0x11, 0x11, 0x11, 0x9d)      # to Border style, CRSR-LEFT
        check('CRSR-LEFT previews Gothic', charset_glyphs() == GOTHIC)
        srv.rx.clear()
        keys(0x03, settle=4)              # RUN/STOP: cancel
        check('RUN/STOP sends the cancel', srv.wait_rx(bytes([1, 0x58, 0, 0]), 5),
              bytes(srv.rx).hex())
        check('Cancel reverts the charset to Double', charset_glyphs() == DOUBLE)
    finally:
        p.terminate(); p.wait(timeout=10)
        disk.unlink(missing_ok=True)
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
