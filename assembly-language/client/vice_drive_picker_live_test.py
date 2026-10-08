#!/usr/bin/env python3
"""The drive picker (F5) end to end in the real C64 client under VICE.

Boots a copy of tada-client.d64 (make d64 first) on drive 8, with a
1571 on 9 and a 1581 on 10, all true drive emulation, no server:
  1. RUN/STOP at "Connecting..." -- offline
  2. F5: DRIVE.MNU loads; the list shows 8 1541 (current), 9 1571,
     10 1581, bar on 8 (no data drive saved yet)
  3. CRSR-DOWN, RETURN: "Data drive 9 saved." on the status row; the
     client's own drive ($ba) stays 8
  4. F7: the keymap editor's nav page lists "Drive Picker" on F5
  5. detach, check TADA64.CFG on the disk (2 + 440 bytes, data drive 9)
  6. fresh boot from that disk: init_keymap loads TADA64.CFG, so F5
     now shows "(current)" and the bar on 9
Saves screenshots next to this script (drive_picker_live_*.png).

Written 2026-10-01. Usage: make d64 && python3 vice_drive_picker_live_test.py
The VICE window takes real keystrokes, so leave it alone while this
runs.
"""
import re, shutil, subprocess, sys, time
from pathlib import Path

import vice_drive_id_test as vt          # mon(), dump(), MON

CLIENT = Path(__file__).parent
SCREEN = 0xc400                          # the client's SCREEN_BUF_A
STATUS_ROW = 23
CFG_SIZE = 440                           # constants.asm's CONFIG_FILE_SIZE


def syms() -> dict:
    out = {}
    for line in (CLIENT / 'tada-client_pp.sym').read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


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


def reversed_cells(row: int) -> int:
    return sum(1 for b in vt.dump(SCREEN + row * 40, 40) if b & 0x80)


def keys(*codes, settle=2.0):
    vt.mon(['> $c6 00', '> $0277 ' + ' '.join(f'{c:02x}' for c in codes),
            f'> $c6 {len(codes):02x}'])
    time.sleep(settle)


def boot(disk: Path) -> subprocess.Popen:
    p = subprocess.Popen(
        ['x64sc', '-drive8type', '1541', '-8', str(disk), '-drive9type', '1571',
         '-drive10type', '1581', '-drive11type', '0', '-drive8truedrive',
         '-drive9truedrive', '-drive10truedrive', '+virtualdev8', '+virtualdev9',
         '+virtualdev10', '+virtualdev11', '-autostart', str(disk),
         '-remotemonitor', '-remotemonitoraddress', f'127.0.0.1:{vt.MON}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(40)                       # autostart LOAD at 1541 speed
    keys(0x03, settle=4)                 # RUN/STOP: work offline
    return p


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def picker_rows() -> list[str]:
    # drive_menu.asm: box at row 4, list rows from 7
    return [r[5:35].rstrip() for r in screen_rows(7, 3)]


def main():
    S = syms()
    disk = CLIENT / 'drive_picker_live.d64'
    shutil.copy(CLIENT / 'tada-client.d64', disk)
    try:
        print('First boot (no TADA64.CFG yet):')
        p = boot(disk)
        try:
            keys(0x87, settle=12)            # F5: load DRIVE.MNU + scan
            rows = picker_rows()
            for r in screen_rows(4, 18):
                print('   |' + r + '|')
            check('F5 opens the picker: 8 1541 (current), 9 1571, 10 1581',
                  rows == ['    8   1541   (current)', '    9   1571', '   10   1581'], rows)
            check('bar on 8', reversed_cells(7) == 28 and reversed_cells(8) == 0,
                  (reversed_cells(7), reversed_cells(8)))
            vt.mon([f'screenshot "{CLIENT / "drive_picker_live_1.png"}" 2'])
            keys(0x11)                       # CRSR down
            check('CRSR-DOWN: bar on 9', reversed_cells(8) == 28, reversed_cells(8))
            keys(0x0d, settle=8)             # RETURN: SCRATCH + SAVE
            status = screen_rows(STATUS_ROW, 1)[0].rstrip()
            check('status "Data drive 9 saved."', status.startswith('Data drive 9 saved.'), status)
            fa = vt.dump(0xba, 1)[0]
            check("client's drive ($ba) still 8", fa == 8, fa)
            drive = vt.dump(S['config_settings'] + 1, 1)[0]
            check('config_settings data drive = 9', drive == 9, drive)

            keys(0x88, settle=12)            # F7: keymap editor
            page = screen_rows(2, 21)
            line = next((r for r in page if 'Drive Picker' in r), '')
            check('F7 editor lists "Drive Picker" on F5', 'F5' in line, line.strip())
            vt.mon([f'screenshot "{CLIENT / "drive_picker_live_2.png"}" 2'])
            keys(0x03, settle=3)             # RUN/STOP: cancel the editor
            vt.mon(['detach 8']); time.sleep(1)   # write the .d64 back
        finally:
            p.terminate(); p.wait(timeout=10); time.sleep(1)

        out = CLIENT / 'drive_picker_live_cfg.bin'
        subprocess.run(['c1541', str(disk), '-read', 'TADA64.CFG', str(out)],
                       capture_output=True)
        data = out.read_bytes() if out.exists() else b''
        out.unlink(missing_ok=True)
        check(f'TADA64.CFG on the disk: 2 + {CFG_SIZE} bytes', len(data) == 2 + CFG_SIZE, len(data))
        check('...with data drive 9 in the settings block',
              data[2 + 432:2 + 434] == bytes([1, 9]), data[2 + 432:2 + 440].hex())

        print('Second boot (TADA64.CFG from the first):')
        p = boot(disk)
        try:
            keys(0x87, settle=12)            # F5
            rows = picker_rows()
            check('F5: "(current)" on 9 now',
                  rows == ['    8   1541', '    9   1571   (current)', '   10   1581'], rows)
            check('bar starts on 9', reversed_cells(8) == 28, reversed_cells(8))
            vt.mon([f'screenshot "{CLIENT / "drive_picker_live_3.png"}" 2'])
            keys(0x03, settle=3)             # RUN/STOP
            status = screen_rows(STATUS_ROW, 1)[0].rstrip()
            check('RUN/STOP: "Data drive unchanged."', status.startswith('Data drive unchanged.'), status)
        finally:
            p.terminate(); p.wait(timeout=10)
    finally:
        disk.unlink(missing_ok=True)
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
