#!/usr/bin/env python3
"""tile_demo.prg under VICE: boots, scrolls, clamps, quits.

  - after boot, screen rows 0-22 hold the map's top-left 40x23 window
    (demo_map.bin), color RAM the matching demo_colors.bin values, row 23
    the divider char and row 24 the status line ending "00,00"
  - 10 x CRSR RIGHT, 5 x CRSR DOWN: view_x/view_y = 10/5, the window and
    "10,05" follow
  - 12 x CRSR LEFT, 8 x CRSR UP: clamps at 0,0 (doesn't wrap to 255)
  - 45 x CRSR RIGHT, 30 x CRSR DOWN: clamps at MAP_W-40, MAP_H-23
  - Q: raster IRQ off, $0314 back to the stock $ea31
Saves tile_demo_boot.png and tile_demo_scrolled.png in samples/.

Written 2026-10-02. Usage (from tiles/): python3 vice_tile_demo_test.py
(builds first with `make`). The VICE window takes real keystrokes, so
leave it alone while this runs.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import vice_drive_id_test as vt     # noqa: E402 -- mon(), dump(), check()

vt.MON = 6546                       # away from the other tests' ports
SCREEN, COLOR_RAM = 0xc400, 0xd800
ROWS, KEYS = 23, {'right': 0x1d, 'left': 0x9d, 'down': 0x11, 'up': 0x91, 'q': 0x51}


def syms():
    out = {}
    for line in (HERE / 'tile_demo.sym').read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


def press(key, n):
    """n presses, 10 at a time (the KERNAL buffer's size)."""
    while n:
        k = min(n, 10)
        vt.mon(['> $c6 00', '> $0277 ' + ' '.join(f'{KEYS[key]:02x}' for _ in range(k)),
                f'> $c6 {k:02x}'])
        time.sleep(1.5)
        n -= k


def dump_io(start, length):
    """vt.dump reads `bank ram` -- at $d800 that's the RAM under I/O, not
    color RAM. This reads through the I/O view instead."""
    out = vt.mon(['bank io', f'm ${start:04x} ${start + length - 1:04x}', 'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def window_ok(label, vx, vy, mapb, colb, map_w):
    def want(src):
        return b''.join(src[(vy + r) * map_w + vx:(vy + r) * map_w + vx + 40]
                        for r in range(ROWS))
    scr = vt.dump(SCREEN, ROWS * 40)
    # color RAM is 4 bits wide; the high nibble reads back as noise
    col = bytes(c & 15 for c in dump_io(COLOR_RAM, ROWS * 40))
    vt.check(f'{label}: screen = map', scr == want(mapb),
             f'{sum(a != b for a, b in zip(scr, want(mapb)))} cells differ')
    vt.check(f'{label}: color RAM = map colors', col == want(colb),
             f'{sum(a != b for a, b in zip(col, want(colb)))} cells differ')


def status():
    row = vt.dump(SCREEN + 24 * 40, 40)
    return ''.join(chr(b + 96) if 1 <= b <= 26 else chr(b) for b in row)


def view(s):
    d = vt.dump(s['view_x'], 2)
    return d[0], d[1]


def main():
    subprocess.run(['make', 'tile_demo.prg'], cwd=HERE, check=True, capture_output=True)
    s = syms()
    data = (HERE / 'tile_demo_data.asm').read_text()
    map_w = int(re.search(r'MAP_W\s+=\s+(\d+)', data).group(1))
    map_h = int(re.search(r'MAP_H\s+=\s+(\d+)', data).group(1))
    mapb = (HERE / 'demo_map.bin').read_bytes()
    colb = (HERE / 'demo_colors.bin').read_bytes()
    shots = HERE / 'samples'

    vice = subprocess.Popen(['x64sc', '-remotemonitor', '-remotemonitoraddress',
                             f'127.0.0.1:{vt.MON}', '-autostartprgmode', '1',
                             '-autostart', str(HERE / 'tile_demo.prg')],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(6)
        print('boot:')
        vt.check('view at 0,0', view(s) == (0, 0), view(s))
        window_ok('window', 0, 0, mapb, colb, map_w)
        vt.check('divider row', vt.dump(SCREEN + 23 * 40, 40) == b'\xa0' * 40)
        vt.check('status line', status().endswith('00,00 '), status())
        vt.mon([f'screenshot "{shots / "tile_demo_boot.png"}" 2'])

        print('scroll right 10, down 5:')
        press('right', 10)
        press('down', 5)
        vt.check('view at 10,5', view(s) == (10, 5), view(s))
        window_ok('window', 10, 5, mapb, colb, map_w)
        vt.check('status says 10,05', status().endswith('10,05 '), status())
        vt.mon([f'screenshot "{shots / "tile_demo_scrolled.png"}" 2'])

        print('clamp at 0,0:')
        press('left', 12)
        press('up', 8)
        vt.check('view at 0,0', view(s) == (0, 0), view(s))

        print('clamp at the far corner:')
        press('right', map_w - 40 + 5)
        press('down', map_h - ROWS + 5)
        far = (map_w - 40, map_h - ROWS)
        vt.check(f'view at {far[0]},{far[1]}', view(s) == far, view(s))
        window_ok('window', *far, mapb, colb, map_w)

        print('quit:')
        press('q', 1)
        irq = vt.dump(0x0314, 2)
        vt.check('$0314 back to $ea31', irq == b'\x31\xea', irq.hex())
    finally:
        vice.terminate()
    if vt.failures:
        sys.exit(f'{len(vt.failures)} failure(s)')
    print('all passed')


if __name__ == '__main__':
    main()
