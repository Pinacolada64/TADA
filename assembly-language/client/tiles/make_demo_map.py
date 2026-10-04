#!/usr/bin/env python3
"""Build tile_demo.asm's data: a scrollable char map cut from a tile sheet.

Converts a rectangle of a sheet (see tile_convert.py for how) into:
  demo_charset.bin  2048 bytes, the multicolor charset (VIC bank 3, $e000)
  demo_map.bin      map_w * map_h char codes, row-major
  demo_colors.bin   map_w * map_h color RAM values, same layout
  tile_demo_data.asm  constants (map size, shared colors) + embeds

Identical 8x8 bitmaps share one char code, whatever their color -- color
RAM is per cell, so the color lives in demo_colors.bin, not the charset.
That's the "tile table with shared chars" idea from TILESET_MEMORY_MAP.md
taken all the way down to single chars.

Char DIVIDER_CHAR ($a0) is reserved as a solid block ($ff in every
byte). The ROM lowercase set's $a0 (reverse space) is solid too, so with
color RAM 0 a row of it is solid black in either charset, multicolor or
not: that's the split's divider row, which hides exactly when the
raster IRQ switches charsets.

A raw crop of a tile sheet is far too dense for one charset (every crop
of Overworld.png needs 500-1000 unique chars; the budget is 255) -- a
sheet isn't a map. --layout instead composes a map the way a real one
looks: a ground tile everywhere, a few random ground variants for
texture, and objects stamped in from the sheet. See demo_map.json.

Run with server/.venv's python. --scan prints the unique-char count for
several crops instead of writing anything.
"""
import argparse
import json
import random
import sys
from pathlib import Path

from PIL import Image

from tile_convert import (NAMES, TILE, Converter, char_rows, load, load_remap, pick_colors,
                          underlay)

DIVIDER_CHAR = 0xa0
VIEW_COLS, VIEW_ROWS = 40, 23           # tile_demo.asm's map window


def convert(im, x0, y0, tw, th, args):
    im = im.crop((x0 * TILE, y0 * TILE, (x0 + tw) * TILE, (y0 + th) * TILE))
    w, h = im.width // 8, im.height // 8
    conv = Converter(load_remap(args.remap))
    rows = [[char_rows(im, cx * 8, cy * 8) for cx in range(w)] for cy in range(h)]
    bg, mc1, mc2 = pick_colors(args, conv, [conv.char_hist(r) for row in rows for r in row])
    cells = [[conv.encode_char(r, bg, mc1, mc2)[:2] for r in row] for row in rows]
    return w, h, (bg, mc1, mc2), cells


def compose(sheet, layout):
    """Build a map image from a layout dict (see demo_map.json).

    size     [w, h] in tiles
    ground   [x, y] sheet cell filling the whole map
    variants list of [x, y] cells sprinkled over the ground at
             variant_rate (0-1), seeded by seed
    stamps   list of [sx, sy, w, h, dx, dy]: copy sheet tiles
             (sx, sy)-(sx+w-1, sy+h-1) to map tile (dx, dy), composited
             over what's there so transparent edges show the ground
    """
    def cell(x, y, w=1, h=1):
        return sheet.crop((x * TILE, y * TILE, (x + w) * TILE, (y + h) * TILE))

    mw, mh = layout['size']
    out = Image.new('RGBA', (mw * TILE, mh * TILE))
    ground = cell(*layout['ground'])
    variants = [cell(*v) for v in layout.get('variants', [])]
    rng = random.Random(layout.get('seed', 1))
    for ty in range(mh):
        for tx in range(mw):
            tile = ground
            if variants and rng.random() < layout.get('variant_rate', 0):
                tile = rng.choice(variants)
            out.paste(tile, (tx * TILE, ty * TILE))
    for sx, sy, w, h, dx, dy in layout['stamps']:
        out.alpha_composite(cell(sx, sy, w, h), (dx * TILE, dy * TILE))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('png')
    ap.add_argument('--crop', default='0,4,30,16', help='x,y,w,h in 16-pixel tiles')
    ap.add_argument('--under', help='x,y ground tile cell (see tile_convert.py)')
    ap.add_argument('--colors', help='force bg,mc1,mc2 (see tile_convert.py)')
    ap.add_argument('--remap', help='"#rrggbb": C64 color overrides (see tile_convert.py)')
    ap.add_argument('--scan', action='store_true', help='report unique chars for a few crops')
    ap.add_argument('--layout', help='compose the map from this JSON instead of cropping')
    ap.add_argument('--preview', help='also write a PNG of the converted map here')
    ap.add_argument('-o', '--out-dir', default='.')
    args = ap.parse_args()

    im = load(args.png)
    if args.under:
        im = underlay(im, *(int(v) for v in args.under.split(',')))

    if args.scan:
        for crop in [(0, 4, 20, 12), (0, 4, 24, 14), (0, 4, 30, 16), (0, 4, 40, 16),
                     (0, 0, 30, 16), (0, 10, 30, 16), (0, 18, 30, 18), (0, 20, 40, 16)]:
            w, h, _, cells = convert(im, *crop, args)
            uniq = {bytes(d) for row in cells for d, _ in row}
            print(f'crop {crop}: {w}x{h} chars, {len(uniq)} unique bitmaps')
        return

    if args.layout:
        im = compose(load(args.png), json.loads(Path(args.layout).read_text()))
        x0, y0, tw, th = 0, 0, im.width // TILE, im.height // TILE
        source = f'layout {Path(args.layout).name}'
    else:
        x0, y0, tw, th = (int(v) for v in args.crop.split(','))
        source = f'crop {args.crop} (tiles), under {args.under}'
    w, h, (bg, mc1, mc2), cells = convert(im, x0, y0, tw, th, args)
    if w < VIEW_COLS or h < VIEW_ROWS:
        sys.exit(f'map {w}x{h} chars is smaller than the {VIEW_COLS}x{VIEW_ROWS} window')

    # Char codes in first-seen order, skipping the reserved divider.
    codes, charset = {}, bytearray(2048)
    charset[DIVIDER_CHAR * 8:DIVIDER_CHAR * 8 + 8] = b'\xff' * 8
    free = (c for c in range(256) if c != DIVIDER_CHAR)
    mapbytes, colbytes = bytearray(), bytearray()
    for row in cells:
        for data, k in row:
            key = bytes(data)
            if key not in codes:
                try:
                    codes[key] = next(free)
                except StopIteration:
                    sys.exit(f'more than 255 unique chars -- pick a smaller --crop '
                             f'(try --scan)')
                charset[codes[key] * 8:codes[key] * 8 + 8] = key
            mapbytes.append(codes[key])
            colbytes.append(8 | k)          # multicolor flag + the char's color

    out = Path(args.out_dir)
    (out / 'demo_charset.bin').write_bytes(charset)
    (out / 'demo_map.bin').write_bytes(mapbytes)
    (out / 'demo_colors.bin').write_bytes(colbytes)
    (out / 'tile_demo_data.asm').write_text(f"""\
; tile_demo_data.asm -- GENERATED by tiles/make_demo_map.py, don't edit.
; Source: {Path(args.png).name}, {source}
; Shared colors: bg {NAMES[bg]}, mc1 {NAMES[mc1]}, mc2 {NAMES[mc2]}
; {len(codes)} unique chars + the divider at ${DIVIDER_CHAR:02x}
MAP_W           = {w}
MAP_H           = {h}
MAP_BG          = {bg}
MAP_MC1         = {mc1}
MAP_MC2         = {mc2}
DIVIDER_CHAR    = ${DIVIDER_CHAR:02x}
""")
    if args.preview:
        from tile_convert import PALETTE
        prev = Image.new('RGB', (w * 8, h * 8))
        px = prev.load()
        regs = (bg, mc1, mc2)
        for i, (code, col) in enumerate(zip(mapbytes, colbytes)):
            cx, cy = i % w, i // w
            for y in range(8):
                byte = charset[code * 8 + y]
                for fx in range(4):
                    bits = (byte >> (6 - 2 * fx)) & 3
                    rgb = PALETTE[regs[bits] if bits < 3 else col & 7]
                    px[cx * 8 + fx * 2, cy * 8 + y] = rgb
                    px[cx * 8 + fx * 2 + 1, cy * 8 + y] = rgb
        prev.save(args.preview)
    print(f'{w}x{h} chars, {len(codes)} unique chars; bg={NAMES[bg]} '
          f'mc1={NAMES[mc1]} mc2={NAMES[mc2]}; wrote {out}/demo_*.bin, tile_demo_data.asm')


if __name__ == '__main__':
    main()
