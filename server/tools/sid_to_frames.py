#!/usr/bin/env python3
"""tools/sid_to_frames.py — Convert a .sid file into a sid_engine frame
stream, the same byte format commands/play.py streams over send_raw().

Runs the tune's init/play routines through sid_engine.sid_dump's 6502
emulator and writes the resulting encoded frame stream to a file, so it
can be inspected or fed to the server without needing a live playback
session. PSID only -- see sid_engine/sid_file.py and sid_engine/
sid_dump.py's module docstrings for why RSID (and PSID tunes with their
own self-installed IRQ handler) aren't supported yet.

Usage:
    .venv/bin/python tools/sid_to_frames.py TUNE.sid [--song N]
        [--seconds N] [--out OUT.frames]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sid_engine import frames, sid_dump, sid_file

DEFAULT_SECONDS = 30
DEFAULT_RATE_HZ = 50  # PAL VBI rate -- see sid_file.SidFile.speed for the
                       # per-song 50Hz-vs-CIA-60Hz bit this ignores for now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sid_path', help='Path to the .sid file to convert')
    parser.add_argument('--song', type=int, default=None,
                         help='1-based subtune number (default: the file\'s start_song)')
    parser.add_argument('--seconds', type=float, default=DEFAULT_SECONDS,
                         help=f'How much playback time to render (default: {DEFAULT_SECONDS}s)')
    parser.add_argument('--out', default=None,
                         help='Output path (default: <input>.frames)')
    args = parser.parse_args()

    sid_path = Path(args.sid_path)
    try:
        sid = sid_file.load(sid_path)
    except sid_file.SidFileError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    song = args.song if args.song is not None else sid.start_song
    num_frames = max(1, round(args.seconds * DEFAULT_RATE_HZ))

    print(f'"{sid.name}" by {sid.author} ({sid.released})')
    print(f'  load=${sid.load_address:04x} init=${sid.init_address:04x} '
          f'play=${sid.play_address:04x} songs={sid.num_songs}')
    print(f'  rendering song {song}, {num_frames} frames (~{args.seconds:.1f}s at {DEFAULT_RATE_HZ}Hz)...')

    try:
        tune_frames = list(sid_dump.convert(sid, song=song, num_frames=num_frames))
    except sid_dump.SidEmulationError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    stream = frames.encode_stream(tune_frames)

    out_path = Path(args.out) if args.out else sid_path.with_suffix('.frames')
    out_path.write_bytes(stream)
    print(f'wrote {len(stream)} bytes ({num_frames} frames) to {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
