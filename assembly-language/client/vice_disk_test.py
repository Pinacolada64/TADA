#!/usr/bin/env python3
"""disk.asm under VICE true drive emulation (x64sc and x128).

Assembles disk_test.asm (C64 and 128 builds), boots it with a given set
of drives on the serial bus, and reads the harness's result bytes over
the remote monitor. Per scenario:
  - probe_device on 8-11 matches which drives are really attached --
    including an absent 9 while 8 IS there (the case a plain LISTEN/
    SECOND/UNLSN probe gets wrong)
  - a provoked DOS error on drive 8 (rename of a missing file) reads
    back as 62 -- read_error_channel doesn't probe the drive
    select_drive just found, which would reset the status to 00 -- and
    a second read gives 00 (reading clears it, error LED off)
  - read_error_channel on an absent drive returns $ff/carry set instead
    of hanging (the old version hung there)
  - scan_serial_bus lists exactly the attached drives
  - select_drive with FA = 9 (absent) falls back to the lowest drive, or
    reports carry set when there's none
Scenarios: stock KERNAL + 1541 on 8 and 1581 on 10; JiffyDOS KERNAL +
JiffyDOS 1541; no drives at all; the same three shapes on the 128.

Written 2026-09-30. Usage: python3 vice_disk_test.py
The VICE windows take real keystrokes, so leave them alone while this
runs.
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
C64LIST = ['wine', str(Path.home() / 'bin/C64List4.06/c64List.exe')]
MON = 6543
JIFFY = Path.home() / 'Documents/c64/JiffyDOS'
VICE_C64 = Path.home() / '.local/share/vice/C64'
DOS_NO_DEVICE = 0xff


def build(machine: str) -> tuple[Path, dict]:
    """disk_test.asm -> disk_test[128].prg; returns (prg, symbols).
    c64list names the .sym after its input file, so the 128 build
    assembles a copy under its own name."""
    src = CLIENT / ('disk_test.asm' if machine == 'c64' else 'disk_test128.asm')
    if machine == 'c128':
        src.write_text((CLIENT / 'disk_test.asm').read_text())
    args = C64LIST + [src.name, f'-prg:{src.stem}', '-sym', '-ovr']
    if machine == 'c128':
        args.append('-def:c128')
    out = subprocess.run(args, cwd=CLIENT, capture_output=True, text=True).stdout
    if '0 Errors' not in out:
        sys.exit(f'{src.name} failed to assemble:\n{out}')
    syms = {}
    for line in (CLIENT / f'{src.stem}.sym').read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            syms[m.group(1).lower()] = int(m.group(2), 16)
    return CLIENT / f'{src.stem}.prg', syms


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


def dump(start: int, length: int) -> bytes:
    # "bank ram": the harness lives in RAM below $4000 on both machines,
    # but the 128's default bank follows whatever MMU state it stopped in
    out = mon(['bank ram', f'm ${start:04x} ${start + length - 1:04x}',
               'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def run(machine: str, prg: Path, drive_args: list, wait: float,
        syms: dict) -> subprocess.Popen:
    """Boot to READY, then LOAD the harness and jump to it through the
    monitor. x128's -autostart sometimes never typed its RUN (seen
    here 2026-09-30, and with the .d64 in vice128_keymap_test.py) --
    and connecting the monitor while it's typing seems to derail it."""
    emu = 'x64sc' if machine == 'c64' else 'x128'
    extra = ['-40col'] if machine == 'c128' else []
    p = subprocess.Popen(
        [emu, *extra, *drive_args, '-remotemonitor',
         '-remotemonitoraddress', f'127.0.0.1:{MON}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # READY takes a while: a 1571/1581 under true drive emulation plus
    # the 128's own boot-disk check
    time.sleep(10 if machine == 'c64' else 20)
    mon(['bank ram', f'l "{prg}" 0', f'r pc = ${syms["start"]:04x}'])
    deadline = time.time() + wait
    while time.time() < deadline and dump(syms['t_progress'], 1)[:1] != b'\xff':
        time.sleep(3)
    return p


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def scenario(name, machine, prg, syms, drive_args, present, wait=None):
    wait = wait or 60
    print(f'{name}:')
    p = run(machine, prg, drive_args, wait, syms)
    try:
        s = syms
        progress = dump(s['t_progress'], 1)[0]
        pc = re.search(r'\.;([0-9a-f]{4})', mon(['r']))
        check('ran to the end (no hang)', progress == 0xff,
              f'stuck in step {progress}, PC ${pc.group(1) if pc else "?"}')
        probe = dump(s['t_probe'], 4)
        want = bytes(0 if d in present else 1 for d in range(8, 12))
        check(f'probe_device 8-11 = {list(want)} (1 = absent)', probe == want, list(probe))
        rec8, rec8b, rec9, rec9_c, count, sel_x, sel_c, sel_fa = dump(s['t_rec8'], 8)
        text = dump(s['t_rec8_buf'], 48).split(b'\0')[0].decode('latin-1')
        if 8 in present:
            check('drive 8 error survives to be read: 62, FILE NOT FOUND',
                  rec8 == 62 and text.startswith('62,'), f'{rec8} "{text}"')
            check('second read gives 00', rec8b == 0, rec8b)
        else:
            check('read_error_channel on absent 8 -> $ff', rec8 == DOS_NO_DEVICE, rec8)
        check('read_error_channel on absent 9 -> $ff, carry set',
              rec9 == DOS_NO_DEVICE and rec9_c == 1, (rec9, rec9_c))
        drives = list(dump(s['drive_list'], count)) if count else []
        check(f'scan_serial_bus finds {sorted(present)}', drives == sorted(present), drives)
        if present:
            first = min(present)
            check(f'select_drive (FA=9) -> {first}',
                  sel_c == 0 and sel_x == first and sel_fa == first, (sel_c, sel_x, sel_fa))
        else:
            check('select_drive with no drives -> carry set', sel_c == 1, sel_c)
        if 8 in present:
            print(f'        drive 8 said: "{text}"')
    finally:
        p.terminate(); p.wait(timeout=10)
        time.sleep(1)


def main():
    blank = CLIENT / 'disk_test_blank.d64'
    subprocess.run(['c1541', '-format', 'disktest,00', 'd64', str(blank)],
                   check=True, capture_output=True)
    c64, s64 = build('c64')
    c128, s128 = build('c128')
    true_drives = ['-drive8truedrive', '-drive10truedrive',
                   '+virtualdev8', '+virtualdev9', '+virtualdev10', '+virtualdev11']
    two = ['-drive8type', '1541', '-8', str(blank), '-drive9type', '0',
           '-drive10type', '1581', '-drive11type', '0', *true_drives]
    none = ['-drive8type', '0', '-drive9type', '0', '-drive10type', '0',
            '-drive11type', '0', '+virtualdev8', '+virtualdev9',
            '+virtualdev10', '+virtualdev11']
    scenario('C64, stock KERNAL, 1541 on 8 + 1581 on 10', 'c64', c64, s64,
             ['-kernal', str(VICE_C64 / 'kernal-901227-03.bin'), *two], {8, 10})
    scenario('C64, JiffyDOS KERNAL + JiffyDOS 1541 on 8', 'c64', c64, s64,
             ['-kernal', str(JIFFY / 'Jiffydos-Kernal.rom'),
              '-dos1541', str(JIFFY / 'JiffyC1541.ROM'),
              '-drive8type', '1541', '-8', str(blank), '-drive9type', '0',
              '-drive10type', '0', '-drive11type', '0', *true_drives], {8})
    scenario('C64, no drives', 'c64', c64, s64, none, set())
    scenario('C128, 1571 on 8 + 1581 on 10', 'c128', c128, s128,
             ['-drive8type', '1571', '-8', str(blank), '-drive9type', '0',
              '-drive10type', '1581', '-drive11type', '0', *true_drives], {8, 10})
    scenario('C128, no drives', 'c128', c128, s128, none, set())
    blank.unlink(missing_ok=True)
    (CLIENT / 'disk_test128.asm').unlink(missing_ok=True)   # build()'s copy
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
