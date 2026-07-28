#!/usr/bin/env python3
"""tools/sid_to_frames.py — Convert a .sid file into sid_engine frame
stream(s), the same byte format commands/play.py streams over
send_raw().

Runs the tune's init/play routines through sid_engine.sid_dump's 6502
emulator and writes the resulting encoded frame stream to a file, so it
can be inspected or fed to the server without needing a live playback
session. PSID only -- see sid_engine/sid_file.py and sid_engine/
sid_dump.py's module docstrings for why RSID (and PSID tunes with their
own self-installed IRQ handler) aren't supported yet.

Two modes:

  Single song (default) -- writes one .frames file:
    .venv/bin/python tools/sid_to_frames.py TUNE.sid [--song N]
        [--seconds N] [--out OUT.frames]

  --all-songs -- renders every subtune into sid_engine/tunes/ (or
  --out-dir) as <key>.song<N>.frames, plus <key>.frames (a copy of the
  start_song render, so plain `play <key>` keeps working) and a
  <key>.json metadata sidecar commands/play.py reads for the header line
  it shows before streaming (title/author/released/subtune name). PSID
  headers carry no per-subtune titles or lengths (that's what HVSC's
  separate STIL and Songlengths.md5 databases are for) -- pass any known
  ones by hand:
    .venv/bin/python tools/sid_to_frames.py TUNE.sid --all-songs
        --key ultima3 --source "HVSC /MUSICIANS/A/Arnold_Kenneth/..." \
        --stil-name 8="Rule Britannia (Thomas Arne, quoted)" \
        --song-seconds 1=128 --song-seconds 2=62
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sid_engine import frames, sid_dump, sid_file

DEFAULT_SECONDS = 30
DEFAULT_RATE_HZ = 50  # PAL VBI rate -- see sid_file.SidFile.speed for the
                       # per-song 50Hz-vs-CIA-60Hz bit this ignores for now

DEFAULT_TUNES_DIR = Path(__file__).resolve().parent.parent / 'sid_engine' / 'tunes'


def _normalize_key(text: str) -> str:
    """Same normalization commands/play.py's _find_tune() applies to a
    requested tune name, so a --key here always matches what `play` will
    actually look up."""
    return ''.join(text.split()).lower()


def _render(sid: sid_file.SidFile, *, song: int, seconds: float) -> bytes:
    num_frames = max(1, round(seconds * DEFAULT_RATE_HZ))
    tune_frames = list(sid_dump.convert(sid, song=song, num_frames=num_frames))
    # A fixed-duration render has no natural ending -- whatever note is
    # sustaining at the cutoff just hangs forever on real playback (no
    # more frames ever arrive to change it). Appending an explicit mute
    # makes every render end in silence instead of a stuck note.
    tune_frames.append({frames.MODE_VOL: 0})
    return frames.encode_stream(tune_frames)


def _parse_stil_name(spec: str) -> tuple[int, str]:
    num, _, text = spec.partition('=')
    return int(num), text


def _parse_song_seconds(spec: str) -> tuple[int, float]:
    num, _, secs = spec.partition('=')
    return int(num), float(secs)


def _cmd_single(args, sid: sid_file.SidFile) -> int:
    song = args.song if args.song is not None else sid.start_song
    print(f'"{sid.name}" by {sid.author} ({sid.released})')
    print(f'  load=${sid.load_address:04x} init=${sid.init_address:04x} '
          f'play=${sid.play_address:04x} songs={sid.num_songs}')
    print(f'  rendering song {song}, ~{args.seconds:.1f}s at {DEFAULT_RATE_HZ}Hz...')

    try:
        stream = _render(sid, song=song, seconds=args.seconds)
    except sid_dump.SidEmulationError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else Path(args.sid_path).with_suffix('.frames')
    out_path.write_bytes(stream)
    print(f'wrote {len(stream)} bytes to {out_path}')
    return 0


def _cmd_all_songs(args, sid: sid_file.SidFile) -> int:
    key = args.key if args.key else _normalize_key(Path(args.sid_path).stem)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_TUNES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    subtune_names = dict(_parse_stil_name(spec) for spec in (args.stil_name or []))
    subtune_seconds = dict(_parse_song_seconds(spec) for spec in (args.song_seconds or []))

    print(f'"{sid.name}" by {sid.author} ({sid.released}) -- {sid.num_songs} subtunes')
    start_song_stream = None
    for song in range(1, sid.num_songs + 1):
        label = subtune_names.get(song, '')
        seconds = subtune_seconds.get(song, args.seconds)
        print(f'  rendering subtune {song}/{sid.num_songs}'
              f'{f" ({label})" if label else ""}, ~{seconds:.1f}s...')
        try:
            stream = _render(sid, song=song, seconds=seconds)
        except sid_dump.SidEmulationError as exc:
            print(f'error on subtune {song}: {exc}', file=sys.stderr)
            return 1
        (out_dir / f'{key}.song{song}.frames').write_bytes(stream)
        if song == sid.start_song:
            start_song_stream = stream

    (out_dir / f'{key}.frames').write_bytes(start_song_stream)

    manifest = {
        'title':           sid.name,
        'author':          sid.author,
        'released':        sid.released,
        'num_songs':       sid.num_songs,
        'start_song':      sid.start_song,
        'source':          args.source or '',
        'subtune_names':   {str(k): v for k, v in subtune_names.items()},
        'subtune_seconds': {str(k): v for k, v in subtune_seconds.items()},
    }
    (out_dir / f'{key}.json').write_text(json.dumps(manifest, indent=2) + '\n')

    print(f'wrote {sid.num_songs} subtune(s) + {key}.frames + {key}.json to {out_dir}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('sid_path', help='Path to the .sid file to convert')
    parser.add_argument('--seconds', type=float, default=DEFAULT_SECONDS,
                         help=f'How much playback time to render per subtune (default: {DEFAULT_SECONDS}s)')

    # Single-song mode
    parser.add_argument('--song', type=int, default=None,
                         help='1-based subtune number (single-song mode; default: start_song)')
    parser.add_argument('--out', default=None,
                         help='Output path for single-song mode (default: <input>.frames)')

    # --all-songs mode
    parser.add_argument('--all-songs', action='store_true',
                         help='Render every subtune + write a library manifest, instead of one file')
    parser.add_argument('--key', default=None,
                         help='Tune library key (default: normalized input filename stem)')
    parser.add_argument('--out-dir', default=None,
                         help=f'Output directory for --all-songs mode (default: {DEFAULT_TUNES_DIR})')
    parser.add_argument('--source', default=None,
                         help='Human-readable provenance string for the manifest (e.g. an HVSC path)')
    parser.add_argument('--stil-name', action='append', metavar='N=TEXT',
                         help='Subtune title, e.g. --stil-name 8="Rule Britannia" (repeatable)')
    parser.add_argument('--song-seconds', action='append', metavar='N=SECONDS',
                         help='Per-subtune render length override, e.g. --song-seconds 1=128 '
                              '(repeatable; falls back to --seconds for any subtune not given). '
                              'HVSC\'s DOCUMENTS/Songlengths.md5 has community-verified loop '
                              'points for real tunes, keyed by the .sid file\'s MD5 -- use those '
                              'rather than guessing, most SID tunes never end on their own.')

    args = parser.parse_args()

    sid_path = Path(args.sid_path)
    try:
        sid = sid_file.load(sid_path)
    except sid_file.SidFileError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    if args.all_songs:
        return _cmd_all_songs(args, sid)
    return _cmd_single(args, sid)


if __name__ == '__main__':
    sys.exit(main())
