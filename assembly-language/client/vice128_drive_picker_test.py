#!/usr/bin/env python3
"""The drive picker (F5) built into client-128.asm, under x128.

Boots client-128.prg (injected, like vice128_keymap_test.py) with a
scratch .d64 in a 1571 on drive 8, a 1541 on 9 and a 1581 on 10, all
true drive emulation, no server (RUN/STOP at "Connecting..."):
  80 columns:
    A  F5 opens the picker: the VIC screen (where drive_menu_body.asm
       draws) lists 8 1571 (current), 9 1541, 10 1581, bar on 8, and
       keymap_host_128.asm presents it on the VDC at columns 20-59
    B  CRSR-DOWN, RETURN: "Data drive 9 saved." on the status row,
       config_settings' data drive = 9, the client's drive ($ba) still 8
    C  TADA128.CFG on the disk: 2 + 494 bytes, data drive 9
  40 columns, booted again from that disk:
    D  init_keymap loaded TADA128.CFG: F5 shows "(current)" and the bar
       on 9; RUN/STOP says "Data drive unchanged."

Written 2026-10-01. Usage: make client-128.prg && python3
vice128_drive_picker_test.py -- leave the VICE window alone meanwhile.
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
PRG = CLIENT / 'client-128.prg'
SYM = CLIENT / 'client-128_pp.sym'
MON = 6545
KEYD, NDX = 0x034a, 0xd0
CFG_SIZE = 494                          # keymap_menu_128.asm's CONFIG_FILE_SIZE
TABLE_SIZE = 486


def symbols() -> dict:
    out = {}
    for line in SYM.read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


S = symbols()


# mon/_bank/dump/vdc/vic/decode/keys: as in vice128_keymap_test.py
def mon(cmds):
    s = socket.create_connection(('127.0.0.1', MON), timeout=10)
    s.settimeout(2); buf = b''
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
    return 'ram' if bank == 'default' and 0x4000 <= addr < 0xc000 else bank


def dump(bank: str, start: int, length: int) -> bytes:
    bank = _bank(bank, start)
    out = mon([f'bank {bank}', f'm ${start:04x} ${start + length - 1:04x}',
               'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def vdc(row: int, col: int = 0, n: int = 80) -> bytes:
    return dump('vdc', row * 80 + col, n)


def vic(row: int) -> bytes:
    return dump('default', 0x0400 + row * 40, 40)


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
    mon([f'> ${NDX:02x} $00',
         f'> ${KEYD:04x} ' + ' '.join(f'${b:02x}' for b in codes),
         f'> ${NDX:02x} ${len(codes):02x}'])
    time.sleep(settle)


def press_f5(settle: float = 10.0) -> None:
    """One F-key string character pending ($d1) at offset 4 ($d2) of the
    F-key buffer -- F5's (keys 1-8 one byte each, F1 F2 F3 F4 F5 ...)."""
    mon(['> $d2 $04', '> $d1 $01'])
    time.sleep(settle)                  # scan + M-R on three drives


def boot(mode: str, disk: Path) -> subprocess.Popen:
    """Boot to READY, LOAD client-128.prg through the monitor and type
    RUN -- not -autostart: with three true-emulated drives, autostart's
    injection never typed its RUN here, and a monitor connection while it
    was typing hung (2026-10-01)."""
    p = subprocess.Popen(
        ['x128', mode, '-VDC16KB', '-drive8type', '1571', '-8', str(disk),
         '-drive9type', '1541', '-drive10type', '1581', '-drive11type', '0',
         '-drive8truedrive', '-drive9truedrive', '-drive10truedrive',
         '+virtualdev8', '+virtualdev9', '+virtualdev10', '+virtualdev11',
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{MON}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(25)                      # READY, after the 1571's boot check
    mon(['bank ram', f'l "{PRG}" 0', 'bank default'])
    keys(b'RUN\r', settle=12)          # TADA128.CFG LOAD on a 1571
    mon([f'> ${KEYD:04x} $03', f'> ${NDX:02x} $01'])   # RUN/STOP: offline
    time.sleep(3)
    return p


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def list_rows() -> list[tuple[str, int]]:
    """drive_menu_body.asm's list rows 7-9 on the VIC screen: (text of
    the interior, how many cells are reversed)."""
    out = []
    for r in range(7, 10):
        row = vic(r)
        out.append((decode(row[5:35]), sum(1 for b in row if b & 0x80)))
    return out


def main():
    disk = CLIENT / 'vice128_drive_picker_test.d64'
    disk.unlink(missing_ok=True)
    subprocess.run(['c1541', '-format', 'dptest,01', 'd64', str(disk), '-write',
                    str(PRG), 'client-128'], check=True, capture_output=True)
    try:
        print('80 columns, no TADA128.CFG yet:')
        p = boot('-80col', disk)
        try:
            press_f5()
            rows = list_rows()
            check('A F5: 8 1571 (current), 9 1541, 10 1581',
                  [t for t, _ in rows] == ['    8   1571   (current)', '    9   1541', '   10   1581'],
                  [t for t, _ in rows])
            check('A bar on 8', [n for _, n in rows] == [28, 0, 0], [n for _, n in rows])
            time.sleep(2)                       # a full presentation pass
            check('A presented on the VDC at columns 20-59',
                  vdc(7, 20, 40) == vic(7) and vdc(8, 20, 40) == vic(8),
                  (decode(vdc(7, 20, 40)), decode(vic(7))))
            keys(b'\x11', settle=2)             # CRSR down
            check('B CRSR-DOWN: bar on 9', [n for _, n in list_rows()] == [0, 28, 0])
            keys(b'\r', settle=10)              # RETURN: SCRATCH + SAVE
            status = decode(vdc(23))
            check('B status "Data drive 9 saved."', status.startswith('Data drive 9 saved.'), status)
            drive = dump('default', S['config_settings'] + 1, 1)[0]
            check('B config_settings data drive = 9', drive == 9, drive)
            fa = dump('default', 0xba, 1)[0]
            check("B client's drive ($ba) still 8", fa == 8, fa)
            mon(['detach 8']); time.sleep(1)    # write the .d64 back
        finally:
            p.terminate(); p.wait(timeout=10); time.sleep(1)

        out = CLIENT / 'vice128_drive_picker_cfg.bin'
        subprocess.run(['c1541', str(disk), '-read', 'TADA128.CFG', str(out)],
                       capture_output=True)
        data = out.read_bytes() if out.exists() else b''
        out.unlink(missing_ok=True)
        check(f'C TADA128.CFG: 2 + {CFG_SIZE} bytes', len(data) == 2 + CFG_SIZE, len(data))
        check('C ...data drive 9 in the settings block',
              data[2 + TABLE_SIZE:2 + TABLE_SIZE + 2] == bytes([1, 9]),
              data[2 + TABLE_SIZE:2 + CFG_SIZE].hex())

        print('40 columns, booted again from that disk:')
        p = boot('-40col', disk)
        try:
            press_f5()
            rows = list_rows()
            check('D F5: "(current)" on 9 now',
                  [t for t, _ in rows] == ['    8   1571', '    9   1541   (current)', '   10   1581'],
                  [t for t, _ in rows])
            check('D bar starts on 9', [n for _, n in rows] == [0, 28, 0], [n for _, n in rows])
            keys(b'\x03', settle=3)             # RUN/STOP
            status = decode(vic(23))
            check('D RUN/STOP: "Data drive unchanged."',
                  status.startswith('Data drive unchanged.'), status)
        finally:
            p.terminate(); p.wait(timeout=10)
    finally:
        disk.unlink(missing_ok=True)
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
