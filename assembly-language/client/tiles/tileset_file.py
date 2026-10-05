#!/usr/bin/env python3
"""Pack/unpack tile_editor.asm's TILESET files.

Format (2310 bytes; on disk it's a PRG, so KERNAL SAVE puts a 2-byte load
address in front -- the editor LOADs relocated, so its value doesn't
matter):

  0     'T', 'S', 1        magic + format version
  3     2048 bytes         charset: tile t = chars 4t..4t+3 (TL, TR, BL, BR)
  2051  256 bytes          color RAM value per char (8 | color 0-7)
  2307  bg, mc1, mc2       $d021, $d022, $d023

  pack    tile_convert.py tileset output dir (charset.bin, colors.bin,
          tiles.json) -> TILESET file (.prg with load address, or raw .bin
          with --raw, which is what tile_editor.asm embeds as its default)
  unpack  TILESET file -> charset.bin, colors.bin, tileset.json, preview.png
          (e.g. after `c1541 disk.d64 -read tileset`, to bring touched-up
          tiles back to the PC)

Run with server/.venv's python (unpack's preview needs Pillow).
"""
import argparse
import json
import sys
from pathlib import Path

MAGIC = b'TS\x01'
SIZE = 2310
LOAD_ADDR = 0x4000          # written into .prg files; ignored by the editor


def pack(src_dir, out, raw):
    src = Path(src_dir)
    charset = (src / 'charset.bin').read_bytes()
    colors = (src / 'colors.bin').read_bytes()
    meta = json.loads((src / 'tiles.json').read_text())
    if len(charset) != 2048 or len(colors) != 256:
        sys.exit('charset.bin must be 2048 bytes and colors.bin 256')
    data = MAGIC + charset + colors + bytes([meta['bg'], meta['mc1'], meta['mc2']])
    assert len(data) == SIZE
    if not raw:
        data = bytes([LOAD_ADDR & 0xff, LOAD_ADDR >> 8]) + data
    Path(out).write_bytes(data)
    print(f'wrote {out} ({len(data)} bytes)')


def read_tileset(path):
    data = Path(path).read_bytes()
    if data[:3] != MAGIC and data[2:5] == MAGIC:
        data = data[2:]                       # skip a PRG load address
    if data[:3] != MAGIC or len(data) != SIZE:
        sys.exit(f'{path}: not a TILESET file (magic {data[:3]!r}, {len(data)} bytes)')
    return data[3:2051], data[2051:2307], data[2307], data[2308], data[2309]


def unpack(path, out_dir, scale):
    from PIL import Image
    from tile_convert import NAMES, PALETTE

    charset, colors, bg, mc1, mc2 = read_tileset(path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'charset.bin').write_bytes(charset)
    (out / 'colors.bin').write_bytes(colors)
    (out / 'tileset.json').write_text(json.dumps(
        {'bg': bg, 'mc1': mc1, 'mc2': mc2,
         'palette_names': {'bg': NAMES[bg], 'mc1': NAMES[mc1], 'mc2': NAMES[mc2]}},
        indent=1))
    # Preview: 16 tiles per row, fat pixels 2x wide, like tile_convert's.
    img = Image.new('RGB', (32 * 8, 8 * 8))
    px = img.load()
    regs = (bg, mc1, mc2)
    for ch in range(256):
        t, q = divmod(ch, 4)
        cx, cy = (t % 16) * 2 + q % 2, (t // 16) * 2 + q // 2
        for y in range(8):
            byte = charset[ch * 8 + y]
            for fx in range(4):
                bits = (byte >> (6 - 2 * fx)) & 3
                rgb = PALETTE[regs[bits] if bits < 3 else colors[ch] & 7]
                px[cx * 8 + fx * 2, cy * 8 + y] = rgb
                px[cx * 8 + fx * 2 + 1, cy * 8 + y] = rgb
    img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(out / 'preview.png')
    print(f'wrote {out}/charset.bin, colors.bin, tileset.json, preview.png '
          f'(bg={NAMES[bg]} mc1={NAMES[mc1]} mc2={NAMES[mc2]})')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('pack', help='tile_convert.py tileset dir -> TILESET file')
    p.add_argument('src_dir')
    p.add_argument('-o', '--out', default='tileset.prg')
    p.add_argument('--raw', action='store_true', help='no load address (for embedding)')
    u = sub.add_parser('unpack', help='TILESET file -> charset/colors/json/preview')
    u.add_argument('path')
    u.add_argument('-o', '--out-dir', default='tileset_out')
    u.add_argument('--scale', type=int, default=3)
    args = ap.parse_args()
    if args.cmd == 'pack':
        pack(args.src_dir, args.out, args.raw)
    else:
        unpack(args.path, args.out_dir, args.scale)


if __name__ == '__main__':
    main()
