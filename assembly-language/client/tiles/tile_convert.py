#!/usr/bin/env python3
"""Convert 16x16 RPG tiles from a PNG sheet into C64 multicolor characters.

Design: assembly-language/client/TILESET_MEMORY_MAP.md. A tile is 2x2
multicolor chars, i.e. 8x16 double-wide pixels. Every char gets four
colors: three shared by the whole tileset (background $d021, $d022,
$d023) and one of its own from color RAM, limited to 0-7 (bit 3 of the
color RAM nibble is the per-cell multicolor flag).

Conversion:
  1. Each pair of source pixels becomes one fat pixel. Its color is the
     C64 color closest to BOTH source pixels (summed distance), not an
     RGB average -- averaging smears pixel-art outlines into in-between
     colors.
  2. One search picks the shared (bg, mc1, mc2) triple for the whole set,
     minimizing total error with every char also picking its best 0-7
     color.
  3. Fully transparent pixels always become the background (bit pair 00).

--remap FILE.json forces chosen source colors ("#rrggbb": C64 color
0-15) instead of nearest-match. Nearest-match can't know which tones
the art means to keep apart: in ArMM1998's pack the tree green
(#2eca5c) is closer to C64 green than light green, so trees vanish
into the grass. See overworld_remap.json.

Two modes:
  sheet   -- convert a whole sheet as if it were one big screen, and
             write a before/after preview PNG. For eyeballing how a pack
             survives the trip.
  tileset -- take 16x16 cells from a grid rectangle of the sheet, keep
             the non-empty, non-duplicate ones, and write a real charset:
             charset.bin (2048 bytes), colors.bin (256 color RAM values,
             one per char), tiles.json (palette + where each tile came
             from), and a preview PNG.

Run with server/.venv's python (Pillow is installed there).
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

from PIL import Image

# Pepto's PAL palette, the usual reference for VICE's default look.
PALETTE = [
    (0x00, 0x00, 0x00), (0xff, 0xff, 0xff), (0x68, 0x37, 0x2b), (0x70, 0xa4, 0xb2),
    (0x6f, 0x3d, 0x86), (0x58, 0x8d, 0x43), (0x35, 0x28, 0x79), (0xb8, 0xc7, 0x6f),
    (0x6f, 0x4f, 0x25), (0x43, 0x39, 0x00), (0x9a, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6c, 0x6c, 0x6c), (0x9a, 0xd2, 0x84), (0x6c, 0x5e, 0xb5), (0x95, 0x95, 0x95),
]
NAMES = ['black', 'white', 'red', 'cyan', 'purple', 'green', 'blue', 'yellow',
         'orange', 'brown', 'light red', 'dark grey', 'grey', 'light green',
         'light blue', 'light grey']

TRANSPARENT = None
TILE = 16
# Tile slots the doc reserves: 8 (chars $20-$23) stays blank so char $20
# reads as a space in both charsets; 63 (chars $fc-$ff) is the editor's
# cursor frame.
RESERVED_SLOTS = {8, 63}
TRIPLE_CANDIDATES = 10      # search triples among the N most-used colors


def redmean(a, b):
    """Perceptual-ish RGB distance (the 'redmean' approximation)."""
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db


def load(path):
    return Image.open(path).convert('RGBA')


def fat_pixels(im, x0, y0, w, h):
    """Source pixel pairs for a w x h (fat-pixel) block at source (x0, y0).

    Returns a list of rows of (rgb_a, rgb_b) pairs; a fully transparent
    pixel is TRANSPARENT, and a pair that is transparent on both sides is
    TRANSPARENT as a whole.
    """
    px = im.load()
    rows = []
    for y in range(y0, y0 + h):
        row = []
        for fx in range(w):
            pair = []
            for x in (x0 + 2 * fx, x0 + 2 * fx + 1):
                r, g, b, a = px[x, y]
                pair.append((r, g, b) if a >= 128 else TRANSPARENT)
            if pair[0] is TRANSPARENT and pair[1] is TRANSPARENT:
                row.append(TRANSPARENT)
            else:
                # one transparent half takes the other half's color
                a, b = pair
                row.append((a or b, b or a))
        rows.append(row)
    return rows


FORCED = 10 ** 9            # distance to every color but a remapped one's


def load_remap(path):
    """{'#rrggbb': c64 color} JSON -> {(r, g, b): c64 color}."""
    if not path:
        return {}
    raw = json.loads(Path(path).read_text())
    return {tuple(int(k[i:i + 2], 16) for i in (1, 3, 5)): v
            for k, v in raw.items() if k.startswith('#')}


class Converter:
    """Holds the pair -> palette distance cache shared by every char."""

    def __init__(self, remap=None):
        self.remap = remap or {}
        self.pair_ids = {}
        self.pair_dist = []     # pair id -> [distance to each palette color]

    def color_dist(self, rgb, idx):
        forced = self.remap.get(rgb)
        if forced is not None:
            return 0 if idx == forced else FORCED
        return redmean(rgb, PALETTE[idx])

    def pair_id(self, pair):
        pid = self.pair_ids.get(pair)
        if pid is None:
            pid = len(self.pair_dist)
            self.pair_ids[pair] = pid
            self.pair_dist.append([self.color_dist(pair[0], i) + self.color_dist(pair[1], i)
                                   for i in range(len(PALETTE))])
        return pid

    def char_hist(self, rows):
        """{pair id: count} for one 8x8 char's fat pixels (4 wide x 8 tall)."""
        hist = {}
        for row in rows:
            for pair in row:
                if pair is not TRANSPARENT:
                    pid = self.pair_id(pair)
                    hist[pid] = hist.get(pid, 0) + 1
        return hist

    def choose_triple(self, hists):
        """Pick (bg, mc1, mc2) minimizing total error over every char."""
        # Weight identical chars once per occurrence, but compute each once.
        uniq = {}
        for h in hists:
            key = tuple(sorted(h.items()))
            uniq[key] = uniq.get(key, 0) + 1
        votes = [0] * 16
        for key, n in uniq.items():
            for pid, cnt in key:
                d = self.pair_dist[pid]
                votes[d.index(min(d))] += cnt * n
        cands = sorted(range(16), key=lambda c: -votes[c])[:TRIPLE_CANDIDATES]
        best = None
        for triple in itertools.combinations(cands, 3):
            total = 0
            for key, n in uniq.items():
                total += n * self._char_error(key, triple)[0]
                if best and total >= best[0]:
                    break
            if best is None or total < best[0]:
                best = (total, triple)
        triple = best[1]
        # The most-used of the three becomes the background: it also shows
        # through every transparent pixel.
        bg = max(triple, key=lambda c: votes[c])
        mc1, mc2 = [c for c in triple if c != bg]
        return bg, mc1, mc2

    def _char_error(self, key, triple):
        best = None
        for k in range(8):
            err = 0
            for pid, cnt in key:
                d = self.pair_dist[pid]
                err += cnt * min(d[triple[0]], d[triple[1]], d[triple[2]], d[k])
            if best is None or err < best[0]:
                best = (err, k)
        return best

    def encode_char(self, rows, bg, mc1, mc2):
        """-> (8 bitmap bytes, char color 0-7, 8x4 grid of palette indices)."""
        hist = self.char_hist(rows)
        _, k = self._char_error(tuple(sorted(hist.items())), (bg, mc1, mc2))
        choices = ((0b00, bg), (0b01, mc1), (0b10, mc2), (0b11, k))
        data, grid = [], []
        for row in rows:
            byte, grow = 0, []
            for pair in row:
                if pair is TRANSPARENT:
                    bits, col = 0b00, bg
                else:
                    d = self.pair_dist[self.pair_id(pair)]
                    bits, col = min(choices, key=lambda bc: d[bc[1]])
                byte = (byte << 2) | bits
                grow.append(col)
            data.append(byte)
            grid.append(grow)
        return data, k, grid


def underlay(im, ux, uy):
    """Composite ground tile cell (ux, uy) under every 16x16 cell of im.

    The art packs this is aimed at are layered: objects (logs, rocks,
    flowers) have transparent edges and sit over a separate ground tile.
    A character map has no layers, so the ground gets baked in. Cells
    that are fully transparent stay that way, so they're still skipped.
    """
    ground = im.crop((ux * TILE, uy * TILE, ux * TILE + TILE, uy * TILE + TILE))
    out = im.copy()
    for ty in range(im.height // TILE):
        for tx in range(im.width // TILE):
            box = (tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE)
            cell = im.crop(box)
            if cell.getextrema()[3][1] < 128:
                continue
            base = ground.copy()
            base.alpha_composite(cell)
            out.paste(base, box)
    return out


def pick_colors(args, conv, hists):
    """--colors bg,mc1,mc2 if given (artist's choice), else the search's."""
    if args.colors:
        return tuple(int(v) for v in args.colors.split(','))
    return conv.choose_triple(hists)


def char_rows(im, cx, cy):
    """Fat-pixel rows for the 8x8 char whose top-left source pixel is (cx, cy)."""
    return fat_pixels(im, cx, cy, 4, 8)


def render(grids_by_pos, w_chars, h_chars, scale):
    """Paint chars' palette grids into an image, fat pixels 2x wide."""
    out = Image.new('RGB', (w_chars * 8 * scale, h_chars * 8 * scale))
    px = out.load()
    for (cx, cy), grid in grids_by_pos.items():
        for y, row in enumerate(grid):
            for fx, col in enumerate(row):
                rgb = PALETTE[col]
                for sy in range(scale):
                    for sx in range(2 * scale):
                        px[(cx * 8 + fx * 2) * scale + sx, (cy * 8 + y) * scale + sy] = rgb
    return out


def side_by_side(src, conv, label_h=0):
    out = Image.new('RGB', (src.width + conv.width + 8, max(src.height, conv.height)), (32, 32, 32))
    flat = Image.new('RGB', src.size, PALETTE[0])
    flat.paste(src, mask=src.split()[3])
    out.paste(flat, (0, 0))
    out.paste(conv, (src.width + 8, 0))
    return out


def cmd_sheet(args):
    im = load(args.png)
    if args.under:
        im = underlay(im, *(int(v) for v in args.under.split(',')))
    if args.crop:
        x0, y0, tw, th = (int(v) for v in args.crop.split(','))
        im = im.crop((x0 * TILE, y0 * TILE, (x0 + tw) * TILE, (y0 + th) * TILE))
    w, h = im.width // 8, im.height // 8
    conv = Converter(load_remap(args.remap))
    rows = {(cx, cy): char_rows(im, cx * 8, cy * 8) for cy in range(h) for cx in range(w)}
    bg, mc1, mc2 = pick_colors(args, conv, [conv.char_hist(r) for r in rows.values()])
    grids = {pos: conv.encode_char(r, bg, mc1, mc2)[2] for pos, r in rows.items()}
    src = im.resize((im.width * args.scale, im.height * args.scale), Image.NEAREST)
    side_by_side(src, render(grids, w, h, args.scale)).save(args.out)
    print(f'bg={NAMES[bg]} ($d021={bg})  mc1={NAMES[mc1]} ($d022={mc1})  '
          f'mc2={NAMES[mc2]} ($d023={mc2})')
    print(f'wrote {args.out}')


def cmd_tileset(args):
    im = load(args.png)
    if args.under:
        im = underlay(im, *(int(v) for v in args.under.split(',')))
    # Collect non-empty, non-duplicate 16x16 cells in reading order,
    # rectangle by rectangle.
    tiles, seen = [], set()
    for rect in args.cells.split(';'):
        x0, y0, x1, y1 = (int(v) for v in rect.split(','))
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                box = im.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE))
                if box.getextrema()[3][1] < 128:
                    continue                    # fully transparent cell
                key = box.tobytes()
                if key in seen:
                    continue
                seen.add(key)
                tiles.append((tx, ty))
    slots = [s for s in range(64) if s not in RESERVED_SLOTS]
    if len(tiles) > len(slots):
        print(f'note: {len(tiles)} tiles found, keeping the first {len(slots)}',
              file=sys.stderr)
        tiles = tiles[:len(slots)]

    conv = Converter(load_remap(args.remap))
    # A tile's 4 chars in reading order: TL, TR, BL, BR.
    quads = [[char_rows(im, tx * TILE + dx, ty * TILE + dy)
              for dy in (0, 8) for dx in (0, 8)] for tx, ty in tiles]
    bg, mc1, mc2 = pick_colors(args, conv, [conv.char_hist(r) for q in quads for r in q])

    charset = bytearray(2048)
    colors = bytearray([8] * 256)             # MC flag set, color 0
    grids, uniq_chars = {}, set()
    for slot, quad in zip(slots, quads):
        for i, rows in enumerate(quad):
            data, k, grid = conv.encode_char(rows, bg, mc1, mc2)
            ch = 4 * slot + i
            charset[ch * 8:ch * 8 + 8] = bytes(data)
            colors[ch] = 8 | k
            uniq_chars.add((tuple(data), k))
            # preview: 16 tiles per row
            grids[((slot % 16) * 2 + i % 2, (slot // 16) * 2 + i // 2)] = grid

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'charset.bin').write_bytes(charset)
    (out / 'colors.bin').write_bytes(colors)
    meta = {
        'source': Path(args.png).name,
        'cells': args.cells,
        'bg': bg, 'mc1': mc1, 'mc2': mc2,
        'palette_names': {'bg': NAMES[bg], 'mc1': NAMES[mc1], 'mc2': NAMES[mc2]},
        'tiles': [{'slot': s, 'chars': [4 * s + i for i in range(4)],
                   'src_cell': [tx, ty]} for s, (tx, ty) in zip(slots, tiles)],
    }
    (out / 'tiles.json').write_text(json.dumps(meta, indent=1))
    render(grids, 32, 8, args.scale).save(out / 'preview.png')

    print(f'{len(tiles)} tiles -> {len(tiles) * 4} chars '
          f'({len(uniq_chars)} distinct char+color combos)')
    print(f'bg={NAMES[bg]} ($d021={bg})  mc1={NAMES[mc1]} ($d022={mc1})  '
          f'mc2={NAMES[mc2]} ($d023={mc2})')
    print(f'wrote {out}/charset.bin, colors.bin, tiles.json, preview.png')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sheet', help='convert a whole sheet for a before/after preview')
    s.add_argument('png')
    s.add_argument('-o', '--out', default='sheet_preview.png')
    s.add_argument('--scale', type=int, default=2)
    s.add_argument('--crop', help='x,y,w,h in 16-pixel tile units, e.g. 0,3,20,8 '
                   'for a 20x8-tile viewport (40x16 chars)')
    s.add_argument('--under', help='x,y tile cell to composite under transparent pixels')
    s.add_argument('--remap', help='JSON of "#rrggbb": C64 color overrides')
    s.add_argument('--colors', help='force the shared colors: bg,mc1,mc2 as C64 '
                   'color numbers 0-15 (default: searched)')
    s.set_defaults(func=cmd_sheet)
    t = sub.add_parser('tileset', help='build a 64-tile charset from a grid rectangle')
    t.add_argument('png')
    t.add_argument('--cells', required=True,
                   help='x0,y0,x1,y1 in 16-pixel tile units, inclusive; '
                   'several rectangles separated by ";"')
    t.add_argument('--under', help='x,y tile cell to composite under transparent pixels')
    t.add_argument('--remap', help='JSON of "#rrggbb": C64 color overrides')
    t.add_argument('--colors', help='force the shared colors: bg,mc1,mc2 as C64 '
                   'color numbers 0-15 (default: searched)')
    t.add_argument('-o', '--out-dir', default='tileset_out')
    t.add_argument('--scale', type=int, default=3)
    t.set_defaults(func=cmd_tileset)
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
