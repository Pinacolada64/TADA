#!/usr/bin/env python3
"""tile_editor.prg under VICE: draws right, edits, undoes, saves, loads.

Boots tile_editor.d64 (the editor + a TILESET file, `make tile_editor.d64`)
in x64sc and checks, against the tileset decoded here in Python:
  - boot: palette rows 0-7 (chars + color RAM), divider row, zoomed grid
    colors, the VIC's copy at $e000 = the working copy
  - CRSR moves the cursor; pen 2 + SPACE sets that pixel's bit pair in
    the working copy and at $e000; U undoes it, U again redoes it
  - F7 bumps the char color under the cursor (working copy + palette
    color RAM); + selects tile 1 (preview, divider bar, panel number);
    F1 bumps the background
  - tile 8 (reserved) refuses SPACE; C on tile 9, V on tile 10 copies it
  - S saves (drive status "00, ok"); after more edits, L loads it back
  - Q restores the stock IRQ; afterwards the TILESET file on the disk
    image matches what was in memory, and tileset_file.py unpacks it
Saves samples/tile_editor.png (a screenshot after the edits).

Written 2026-10-03. Usage (from tiles/): python3 vice_tile_editor_test.py
The VICE window takes real keystrokes, so leave it alone while this runs.
"""
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import vice_drive_id_test as vt     # noqa: E402 -- mon(), dump(), check()

vt.MON = 6547
SCREEN, COLOR_RAM, TILE_CHARS = 0xc400, 0xd800, 0xe000
OFS_CHARS, OFS_COLORS, OFS_BG, WS_SIZE = 3, 2051, 2307, 2310
GRID_ROW, MSG_ROW, PANEL_COL = 9, 24, 18
KEYS = {'right': 0x1d, 'down': 0x11, 'space': 0x20, '2': 0x32, 'f1': 0x85, 'f7': 0x88,
        '+': 0x2b, '-': 0x2d, 'u': 0x55, 's': 0x53, 'l': 0x4c, 'c': 0x43, 'v': 0x56,
        'q': 0x51}


def syms():
    out = {}
    for line in (HERE / 'tile_editor.sym').read_text().splitlines():
        m = re.match(r'(\w+)\s+=\s+\$([0-9a-f]+)', line.strip(), re.I)
        if m:
            out[m.group(1).lower()] = int(m.group(2), 16)
    return out


def dump_io(start, length):
    out = vt.mon(['bank io', f'm ${start:04x} ${start + length - 1:04x}', 'bank default'])
    data = []
    for m in re.finditer(r'>C:[0-9a-f]{4}((?:\s+[0-9a-f]{2}){1,16})', out):
        data += [int(b, 16) for b in m.group(1).split()]
    return bytes(data[:length])


def press(*keys, wait=1.0):
    codes = [KEYS[k] for k in keys]
    for i in range(0, len(codes), 10):
        chunk = codes[i:i + 10]
        vt.mon(['> $c6 00', '> $0277 ' + ' '.join(f'{c:02x}' for c in chunk),
                f'> $c6 {len(chunk):02x}'])
        time.sleep(wait)


def msg():
    row = vt.dump(SCREEN + MSG_ROW * 40 + PANEL_COL, 22)
    return ''.join(chr(b + 96) if 1 <= b <= 26 else chr(b) for b in row).rstrip()


def wait_msg(want, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        m = msg()
        if want(m):
            return m
        time.sleep(2)
    return msg()


def pixel(block, tile, x, y):
    ch = tile * 4 + (y // 8) * 2 + x // 4
    byte = block[OFS_CHARS + ch * 8 + y % 8]
    return (byte >> (6 - 2 * (x % 4))) & 3, ch


def pixel_color(block, tile, x, y):
    bits, ch = pixel(block, tile, x, y)
    return block[OFS_BG + bits] if bits < 3 else block[OFS_COLORS + ch] & 7


def main():
    subprocess.run(['make', 'tile_editor.d64'], cwd=HERE, check=True, capture_output=True)
    s = syms()
    work = s['work']
    disk = HERE / 'tile_editor.d64'
    vice = subprocess.Popen(['x64sc', '-remotemonitor', '-remotemonitoraddress',
                             f'127.0.0.1:{vt.MON}', '-8', str(disk),
                             '-autostartprgmode', '1', '-autostart', str(HERE / 'tile_editor.prg')],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    saved = None
    try:
        time.sleep(7)
        block = vt.dump(work, WS_SIZE)

        print('boot:')
        vt.check('cursor starts at 0,0', vt.dump(s['cur_x'], 2) == b'\0\0',
                 vt.dump(s['cur_x'], 2).hex())
        vt.check('working copy = default tileset',
                 block == (HERE / 'default_tileset.bin').read_bytes())
        vt.check('$e000 = working charset', vt.dump(TILE_CHARS, 2048) == block[3:2051])
        scr, col = vt.dump(SCREEN, 8 * 40), dump_io(COLOR_RAM, 8 * 40)
        want_s = [(r >> 1) * 64 + (c >> 1) * 4 + (r & 1) * 2 + (c & 1)
                  for r in range(8) for c in range(32)]
        got_s = [scr[r * 40 + c] for r in range(8) for c in range(32)]
        got_c = [col[r * 40 + c] & 15 for r in range(8) for c in range(32)]
        vt.check('palette chars', got_s == want_s)
        vt.check('palette colors', got_c == [block[OFS_COLORS + ch] & 15 for ch in want_s])
        div_s, div_c = vt.dump(SCREEN + 8 * 40, 40), dump_io(COLOR_RAM + 8 * 40, 40)
        vt.check('divider row', div_s == b'\xa0' * 40 and
                 [c & 15 for c in div_c] == [1, 1] + [0] * 38)
        gcol = dump_io(COLOR_RAM + GRID_ROW * 40, 16 * 40)
        bad = [(x, y) for y in range(16) for x in range(8) if (x, y) != (0, 0) and
               gcol[y * 40 + 2 * x] & 15 != pixel_color(block, 0, x, y)]
        vt.check('zoomed grid colors', not bad, f'{len(bad)} wrong, e.g. {bad[:3]}')
        vt.check('ready message', msg() == 'Tile editor ready.', msg())

        print('cursor, pen, plot, undo:')
        press('right', 'right', 'down', 'down', 'down', '2')
        cur = vt.dump(s['cur_x'], 2)
        vt.check('cursor at 2,3', cur == bytes([2, 3]), cur.hex())
        vt.check('pen 2 = bits 01', vt.dump(s['pen'], 1)[0] == 1)
        before, ch = pixel(block, 0, 2, 3)
        want = 1 if before != 1 else 1        # pen 2 = %01
        press('space')
        after = vt.dump(work, WS_SIZE)
        vt.check('pixel 2,3 now %01', pixel(after, 0, 2, 3)[0] == want)
        off = OFS_CHARS + ch * 8 + 3
        vt.check('$e000 copy updated', vt.dump(TILE_CHARS + ch * 8 + 3, 1)[0] == after[off])
        press('u')
        vt.check('U undoes', pixel(vt.dump(work, WS_SIZE), 0, 2, 3)[0] == before)
        press('u')
        vt.check('U again redoes', pixel(vt.dump(work, WS_SIZE), 0, 2, 3)[0] == want)

        print('char color, tile select, shared color:')
        b0 = vt.dump(work, WS_SIZE)
        press('f7')
        b1 = vt.dump(work, WS_SIZE)
        vt.check('F7 bumps char color',
                 b1[OFS_COLORS + ch] == 8 | ((b0[OFS_COLORS + ch] + 1) & 7))
        pal_c = dump_io(COLOR_RAM, 40)[0] & 15    # palette cell (0,0) = char 0
        vt.check('palette shows it', pal_c == b1[OFS_COLORS + 0] & 15)
        press('+')
        vt.check('tile 1 selected', vt.dump(s['cur_tile'], 1)[0] == 1)
        pv = vt.dump(SCREEN + 34, 6)
        vt.check('preview = tile 1', pv == bytes([4, 5] * 3), pv.hex())
        vt.check('divider bar moved', [c & 15 for c in dump_io(COLOR_RAM + 8 * 40, 4)] == [0, 0, 1, 1])
        num = vt.dump(SCREEN + 9 * 40 + 24, 2)
        vt.check('panel says 01', num == b'01', num)
        press('f1')
        vt.check('F1 bumps bg', vt.dump(work + OFS_BG, 1)[0] == (b1[OFS_BG] + 1) & 15)

        print('reserved tile, copy/paste:')
        press(*['+'] * 7)                        # tile 8
        b2 = vt.dump(work, WS_SIZE)
        press('space')
        vt.check('tile 8 refuses edits', vt.dump(work, WS_SIZE) == b2 and
                 msg() == 'Tile reserved (split).', msg())
        press('+', 'c', '+', 'v')                # copy 9, paste into 10
        b3 = vt.dump(work, WS_SIZE)
        t9, t10 = OFS_CHARS + 9 * 32, OFS_CHARS + 10 * 32
        vt.check('tile 10 = tile 9', b3[t10:t10 + 32] == b3[t9:t9 + 32] and
                 b3[OFS_COLORS + 40:OFS_COLORS + 44] == b3[OFS_COLORS + 36:OFS_COLORS + 40])
        vt.check('$e000 tile 10 too', vt.dump(TILE_CHARS + 10 * 32, 32) == b3[t10:t10 + 32])
        vt.mon([f'screenshot "{HERE / "samples" / "tile_editor.png"}" 2'])

        print('save, edit, load:')
        saved = vt.dump(work, WS_SIZE)
        press('s', wait=2)
        m = wait_msg(lambda m: m.startswith('00,') or 'error' in m.lower() or 'drive' in m)
        vt.check('save: drive says 00, ok', m.startswith('00, ok'), m)
        press('-', 'space', 'f1')                # change something
        vt.check('edited after save', vt.dump(work, WS_SIZE) != saved)
        press('l', wait=2)
        m = wait_msg(lambda m: m in ('Loaded.', 'Not a TILESET file.') or 'drive' in m
                     or 'found' in m or 'error' in m.lower())
        vt.check('load: "Loaded."', m == 'Loaded.', m)
        vt.check('working copy = saved', vt.dump(work, WS_SIZE) == saved)
        vt.check('$e000 = saved charset', vt.dump(TILE_CHARS, 2048) == saved[3:2051])

        print('quit:')
        press('q')
        irq = vt.dump(0x0314, 2)
        vt.check('$0314 back to $ea31', irq == b'\x31\xea', irq.hex())
    finally:
        vice.terminate()
        vice.wait()

    if saved is not None:
        print('disk image:')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'tileset.prg'
            subprocess.run(['c1541', str(disk), '-read', 'tileset', str(out)],
                           check=True, capture_output=True)
            data = out.read_bytes()
            vt.check('TILESET on disk = memory', data[2:] == saved,
                     f'{len(data)} bytes')
            r = subprocess.run([sys.executable, '-B', 'tileset_file.py', 'unpack', str(out),
                                '-o', str(Path(tmp) / 'unpacked')],
                               cwd=HERE, capture_output=True, text=True)
            vt.check('tileset_file.py unpacks it', r.returncode == 0, r.stderr.strip())
    if vt.failures:
        sys.exit(f'{len(vt.failures)} failure(s)')
    print('all passed')


if __name__ == '__main__':
    main()
