#!/usr/bin/env python3
"""drive_id.asm's identify_drive under VICE true drive emulation.

Assembles drive_id_test.asm (C64 and 128 builds), boots it with a mix
of drive models on the serial bus, and checks each device 8-11 reads
back as the right model number ("1541", "1571", "1581") -- or as
absent/unrecognized (carry set, empty text).

Same approach as vice_disk_test.py (load + jump through the remote
monitor rather than -autostart), on its own monitor port so the two
can run side by side. Written 2026-10-01.
Usage: python3 vice_drive_id_test.py
The VICE windows take real keystrokes, so leave them alone while this
runs.
"""
import re, socket, subprocess, sys, time
from pathlib import Path

CLIENT = Path(__file__).parent
C64LIST = ['wine', str(Path.home() / 'bin/C64List4.06/c64List.exe')]
MON = 6544
JIFFY = Path.home() / 'Documents/c64/JiffyDOS'
VICE_C64 = Path.home() / '.local/share/vice/C64'


def build(machine: str) -> tuple[Path, dict]:
    """drive_id_test.asm -> drive_id_test[128].prg; returns (prg,
    symbols). c64list names the .sym after its input file, so the 128
    build assembles a copy under its own name."""
    src = CLIENT / ('drive_id_test.asm' if machine == 'c64' else 'drive_id_test128.asm')
    if machine == 'c128':
        src.write_text((CLIENT / 'drive_id_test.asm').read_text())
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
    s = socket.create_connection(('127.0.0.1', MON), timeout=10); s.settimeout(2); buf = b''
    for cmd in cmds:
        s.sendall(cmd.encode() + b'\n'); time.sleep(0.4)
        try:
            while True:
                d = s.recv(65536)
                if not d: break
                buf += d
        except socket.timeout:
            pass
    # A trailing `g` already resumed the CPU; an `x` sent after it sits
    # unread in VICE's socket and the remote monitor stops answering
    # new connections (seen 2026-10-01, x64sc 3.10).
    if not cmds or not cmds[-1].startswith('g '):
        s.sendall(b'x\n')
    time.sleep(0.2); s.close()
    return buf.decode('latin-1')


def dump(start: int, length: int) -> bytes:
    out = mon(['bank ram', f'm ${start:04x} ${start + length - 1:04x}',
               'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


failures = []


def check(label, cond, detail=''):
    print(f'  {"PASS" if cond else "FAIL"}  {label}' + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(label)


def scenario(name, machine, prg, syms, drive_args, want):
    """want: {device: "1541"/... or None for absent/unrecognized}"""
    print(f'{name}:')
    emu = 'x64sc' if machine == 'c64' else 'x128'
    extra = ['-40col'] if machine == 'c128' else []
    p = subprocess.Popen(
        [emu, *extra, *drive_args, '-remotemonitor',
         '-remotemonitoraddress', f'127.0.0.1:{MON}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(10 if machine == 'c64' else 20)
        mon(['bank ram', f'l "{prg}" 0', f'g ${syms["start"]:04x}'])
        deadline = time.time() + 60
        while time.time() < deadline and dump(syms['t_progress'], 1)[:1] != b'\xff':
            time.sleep(3)
        progress = dump(syms['t_progress'], 1)[0]
        check('ran to the end (no hang)', progress == 0xff, f'stuck on device {progress}')
        fa = dump(syms['t_fa'], 1)[0]
        check("client's drive (FA) still 8 after identifying 8-11", fa == 8, fa)
        carry = dump(syms['t_carry'], 4)
        models = dump(syms['t_models'], 20)
        for i, dev in enumerate(range(8, 12)):
            text = models[i * 5:i * 5 + 5].split(b'\0')[0].decode('latin-1')
            exp = want.get(dev)
            if exp:
                check(f'device {dev} = {exp}', carry[i] == 0 and text == exp, (carry[i], text))
            else:
                check(f'device {dev} absent/unknown (carry set, "")',
                      carry[i] == 1 and text == '', (carry[i], text))
    finally:
        p.terminate(); p.wait(timeout=10)
        time.sleep(1)


def main():
    blank = CLIENT / 'drive_id_test_blank.d64'
    subprocess.run(['c1541', '-format', 'driveid,00', 'd64', str(blank)],
                   check=True, capture_output=True)
    c64, s64 = build('c64')
    c128, s128 = build('c128')
    true_drives = ['-drive8truedrive', '-drive9truedrive', '-drive10truedrive',
                   '+virtualdev8', '+virtualdev9', '+virtualdev10', '+virtualdev11']
    three = ['-drive8type', '1541', '-8', str(blank), '-drive9type', '1571',
             '-drive10type', '1581', '-drive11type', '0', *true_drives]
    scenario('C64, stock KERNAL, 1541/1571/1581 on 8/9/10', 'c64', c64, s64,
             ['-kernal', str(VICE_C64 / 'kernal-901227-03.bin'), *three],
             {8: '1541', 9: '1571', 10: '1581'})
    scenario('C64, JiffyDOS KERNAL + JiffyDOS 1541/1581 on 8/10', 'c64', c64, s64,
             ['-kernal', str(JIFFY / 'Jiffydos-Kernal.rom'),
              '-dos1541', str(JIFFY / 'JiffyC1541.ROM'),
              '-dos1581', str(JIFFY / 'Jiffy1581.rom'),
              '-drive8type', '1541', '-8', str(blank), '-drive9type', '0',
              '-drive10type', '1581', '-drive11type', '0', *true_drives],
             {8: '1541', 10: '1581'})
    scenario('C128, 1571 on 8 + 1581 on 10', 'c128', c128, s128,
             ['-drive8type', '1571', '-8', str(blank), '-drive9type', '0',
              '-drive10type', '1581', '-drive11type', '0', *true_drives],
             {8: '1571', 10: '1581'})
    blank.unlink(missing_ok=True)
    print(f'\n{"ALL PASS" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
