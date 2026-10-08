#!/usr/bin/env python3
"""drive_menu.prg (the Select Drive popup) under VICE, without the client.

drive_menu_test.prg stands in for the resident client (stub jump table
at $c000, a stand-in keymap_table + config_settings for TADA64.CFG);
this loads it and drive_menu.prg, boots with a 1541/1571/1581 on drives
8/9/10 (true drive emulation, a blank disk in 8), then:
  - reads the popup's list rows off SCREEN_RAM: each drive's number and
    model, "(current)" and the highlight bar on 8 (no data drive chosen
    yet, so the client's own drive)
  - types CRSR-DOWN: the bar moves to 9
  - types RETURN: CFG_DATA_DRIVE becomes 9 while the client's drive
    ($ba) stays 8, "Data drive 9 saved." comes back as the status
    message, and TADA64.CFG -- the whole 440 bytes, data drive 9 --
    is on drive 8's disk
  - reopens the popup: "(current)" and the bar are on 9 now
Then boots again with no drives at all: "No drives found.", no bar,
CRSR keys and R (rescan) don't break it, RETURN closes it with
"Data drive unchanged." and the setting left alone.
Also saves a screenshot of the open popup next to this script
(drive_menu_test.png).

Written 2026-10-01. Usage: python3 vice_drive_menu_test.py
The VICE window takes real keystrokes, so leave it alone while this
runs.
"""
import re, subprocess, sys, time
from pathlib import Path

import vice_drive_id_test as vt   # build-free helpers: mon(), dump(), MON

CLIENT = Path(__file__).parent
SCREEN = 0xc400                        # POPUP_SCREEN (constants.asm)
TOP, LIST_TOP, ROWS = 4, 7, 18


def build(name: str) -> dict:
    subprocess.run(['python3', './macro_preprocessor.py', f'{name}.asm'],
                   cwd=CLIENT, check=True, capture_output=True)
    out = subprocess.run(vt.C64LIST + [f'{name}_pp.asm', f'-prg:{name}', '-sym', '-ovr'],
                         cwd=CLIENT, capture_output=True, text=True).stdout
    if '0 Errors' not in out:
        sys.exit(f'{name} failed to assemble:\n{out}')
    syms = {}
    for line in (CLIENT / f'{name}_pp.sym').read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            syms[m.group(1).lower()] = int(m.group(2), 16)
    return syms


def decode(row: bytes) -> tuple[str, str]:
    """Screen codes (lowercase charset) -> (text, mask of reversed cells)."""
    text, rev = '', ''
    for b in row:
        rev += '#' if b & 0x80 else '.'
        b &= 0x7f
        if 1 <= b <= 26:
            text += chr(b + 96)
        elif 0x41 <= b <= 0x5a:
            text += chr(b)
        elif 0x20 <= b <= 0x3f:
            text += chr(b)
        else:
            text += '+'
    return text, rev


def list_rows() -> list[tuple[str, str]]:
    data = vt.dump(SCREEN + LIST_TOP * 40, 3 * 40)
    return [decode(data[i * 40 + 5:i * 40 + 35]) for i in range(3)]


def type_keys(*codes):
    """Keyboard buffer poke -- one connection, ending in x (see the
    VICE monitor notes in project memory)."""
    vt.mon(['> $c6 00', '> $0277 ' + ' '.join(f'{c:02x}' for c in codes),
            f'> $c6 {len(codes):02x}'])
    time.sleep(2)


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def boot(stub: dict, drive_args: list) -> subprocess.Popen:
    """Boot x64sc with drive_args, load the stub + overlay, start it."""
    p = subprocess.Popen(
        ['x64sc', *drive_args, '-remotemonitor',
         '-remotemonitoraddress', f'127.0.0.1:{vt.MON}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(10)
    vt.mon([f'l "{CLIENT / "drive_menu.prg"}" 0',
            f'l "{CLIENT / "drive_menu_test.prg"}" 0',
            f'g ${stub["start"]:04x}'])
    time.sleep(6)
    return p


def scenario_three_drives(stub, drive_args):
    p = boot(stub, drive_args)
    try:
        print('Select Drive popup, 1541/1571/1581 on 8/9/10:')
        box = vt.dump(SCREEN + TOP * 40, ROWS * 40)
        for i in range(ROWS):
            print('   |' + decode(box[i * 40:i * 40 + 40])[0] + '|')
        rows = list_rows()
        texts = [t.rstrip() for t, _ in rows]
        check('row 1: drive 8, 1541, (current)', texts[0] == '    8   1541   (current)', texts[0])
        check('row 2: drive 9, 1571', texts[1] == '    9   1571', texts[1])
        check('row 3: drive 10, 1581', texts[2] == '   10   1581', texts[2])
        bar = '.' + '#' * 28 + '.'
        check('bar on drive 8', [r for _, r in rows] == [bar, '.' * 30, '.' * 30],
              [r for _, r in rows])
        vt.mon([f'screenshot "{CLIENT / "drive_menu_test.png"}" 2'])

        type_keys(0x11)                        # CRSR down
        rows = list_rows()
        check('CRSR-DOWN moves the bar to drive 9',
              [r for _, r in rows] == ['.' * 30, bar, '.' * 30], [r for _, r in rows])

        type_keys(0x0d)                        # RETURN
        time.sleep(6)                          # SCRATCH + SAVE on a 1541
        done = vt.dump(stub['t_done'], 3)
        check('RETURN hands back (JT_RESUME_LOCAL)', done[0] == 0xff, done[0])
        cfg = stub['t_config']
        drive = vt.dump(cfg + 432 + 1, 1)[0]
        check('data drive (CFG_DATA_DRIVE) is now 9', drive == 9, drive)
        fa = vt.dump(0xba, 1)[0]
        check("client's drive ($ba) still 8", fa == 8, fa)
        msg = vt.dump(done[1] | done[2] << 8, 40).split(b'\0')[0]
        text = decode(msg)[0]
        check('status message "Data drive 9 saved."', text == 'Data drive 9 saved.', text)

        vt.mon([f'g ${stub["start"]:04x}'])    # reopen
        time.sleep(6)
        rows = list_rows()
        texts = [t.rstrip() for t, _ in rows]
        check('reopened: "(current)" on 9', texts[0] == '    8   1541' and
              texts[1] == '    9   1571   (current)', texts[:2])
        check('reopened: bar on 9', [r for _, r in rows] == ['.' * 30, bar, '.' * 30],
              [r for _, r in rows])
        type_keys(0x03)                        # STOP
        # VICE keeps true-drive-emulated tracks in memory and writes them
        # back on detach; a plain terminate left TADA64.CFG as an
        # unclosed *PRG with no data (2026-10-01)
        vt.mon(['detach 8']); time.sleep(1)
    finally:
        p.terminate(); p.wait(timeout=10)
        time.sleep(1)


def scenario_no_drives(stub, drive_args):
    """Nothing on the bus: "No drives found.", no bar, CRSR keys do
    nothing, R rescans without hanging, RETURN leaves the drive alone."""
    p = boot(stub, drive_args)
    try:
        print('Select Drive popup, no drives on the bus:')
        rows = list_rows()
        texts = [t.rstrip() for t, _ in rows]
        check('row 1 says "No drives found."', texts[0] == '   No drives found.', texts[0])
        check('rows 2-3 blank', texts[1:] == ['', ''], texts[1:])
        check('no highlight bar', all(r == '.' * 30 for _, r in rows),
              [r for _, r in rows])
        type_keys(0x11, 0x91)                  # CRSR down, CRSR up
        check('CRSR keys change nothing', list_rows() == rows, list_rows())
        type_keys(0x52)                        # R -- rescan
        check('R rescans and still says "No drives found."',
              list_rows()[0][0].rstrip() == '   No drives found.', list_rows()[0])
        check('still open after rescan', vt.dump(stub['t_done'], 1)[0] == 0)
        type_keys(0x0d)                        # RETURN
        done = vt.dump(stub['t_done'], 3)
        check('RETURN hands back', done[0] == 0xff, done[0])
        drive = vt.dump(stub['t_config'] + 432 + 1, 1)[0]
        check('data drive left at 0 (none chosen)', drive == 0, drive)
        msg = vt.dump(done[1] | done[2] << 8, 40).split(b'\0')[0]
        text = decode(msg)[0]
        check('status message "Data drive unchanged."', text == 'Data drive unchanged.', text)
    finally:
        p.terminate(); p.wait(timeout=10)
        time.sleep(1)


def main():
    stub = build('drive_menu_test')
    build('drive_menu')
    blank = CLIENT / 'drive_menu_test_blank.d64'
    subprocess.run(['c1541', '-format', 'drivemenu,00', 'd64', str(blank)],
                   check=True, capture_output=True)
    three = ['-drive8type', '1541', '-8', str(blank), '-drive9type', '1571',
             '-drive10type', '1581', '-drive11type', '0', '-drive8truedrive',
             '-drive9truedrive', '-drive10truedrive', '+virtualdev8', '+virtualdev9',
             '+virtualdev10', '+virtualdev11']
    none = ['-drive8type', '0', '-drive9type', '0', '-drive10type', '0',
            '-drive11type', '0', '+virtualdev8', '+virtualdev9',
            '+virtualdev10', '+virtualdev11']
    try:
        scenario_three_drives(stub, three)
        # VICE has written the disk image back by now (it exited)
        out = CLIENT / 'drive_menu_test_cfg.bin'
        # Uppercase: c1541 maps it to $C1-$DA, which is what the client's
        # {alpha:alt} filename wrote (see the Makefile's .d64 comment)
        subprocess.run(['c1541', str(blank), '-read', 'TADA64.CFG', str(out)],
                       capture_output=True)
        data = out.read_bytes() if out.exists() else b''
        out.unlink(missing_ok=True)
        if len(data) != 442:
            print(subprocess.run(['c1541', str(blank), '-list'],
                                 capture_output=True, text=True).stdout)
        check('TADA64.CFG on drive 8: 2-byte header + 440 bytes',
              len(data) == 442, len(data))
        check('...holding the table and data drive 9',
              data[2:434] == b'\x5a' * 432 and data[2 + 432 + 1:2 + 432 + 2] == b'\x09',
              data[434:442].hex())
        scenario_no_drives(stub, none)
    finally:
        blank.unlink(missing_ok=True)
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
