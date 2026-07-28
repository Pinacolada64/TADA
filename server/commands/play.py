"""commands/play.py — PLAY <name> [<subtune>]: stream a SID tune to a C64
client.

Only PETSCIINetworkContext (real Commodore hardware, with a real SID chip)
can play anything; JSON/web clients get a plain refusal. `play #test` is
the escape hatch that streams sid_engine.stub_tune's canned arpeggio,
kept around deliberately as a standing way to prove the server ->
SwiftLink -> IRQ player pipe still works on its own, independent of
whatever's in the real tune library. `play #dir` lists everything in the
library; `play #about` lists the tools this whole pipeline is built on;
`play #stop` sends sid_engine.frames.STOP, a one-byte control signal
(not a stream) that silences the client's SID chip and resets its
playback state immediately -- for when a render goes wrong or the
player's just had enough.

The real library (TUNES_DIR) holds pre-rendered .frames files -- already
sid_engine.frames-encoded byte streams, produced offline by
tools/sid_to_frames.py from an actual .sid file -- so serving one is just
a file read, no per-request 6502 emulation. A tune with multiple subtunes
(tools/sid_to_frames.py --all-songs) gets one .frames file per subtune
(<key>.song<N>.frames) plus a <key>.json metadata sidecar (title/author/
released/subtune_names) this command displays before streaming. See that
tool's docstring for how to add a tune.

Subtune selection is a plain trailing number (`play ultima3 5`), not a
switch -- Command.parse_args()'s `#`-prefixed switches are bare flags by
design (#test, #about), with no value-parsing support, so a value-
carrying parameter doesn't fit that shape.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import PETSCIINetworkContext
from sid_engine import frames, stub_tune

TUNES_DIR = Path(__file__).resolve().parent.parent / 'sid_engine' / 'tunes'

_ABOUT_TEXT = [
    '|yellow|SID engine credits',
    '|white|6502 emulation: py65 (pure-Python 6502/65C02 emulator)',
    'Test fixture "vibratotest": ChiptuneSAK (MIT licensed)',
    'Real tunes: the High Voltage SID Collection (hvsc.c64.org)',
    'Pipeline design & implementation: Claude Sonnet 5 (Anthropic)',
]


def _normalize(name: str) -> str:
    return ''.join(name.split()).lower()


def _load_manifest(key: str) -> dict | None:
    manifest_path = TUNES_DIR / f'{key}.json'
    if not manifest_path.is_file():
        return None
    return json.loads(manifest_path.read_text())


def _find_tune(key: str, subtune: int | None) -> Path | None:
    """Look up a .frames file by library key, optionally a specific
    subtune (<key>.song<N>.frames); plain <key>.frames otherwise."""
    filename = f'{key}.song{subtune}.frames' if subtune is not None else f'{key}.frames'
    candidate = TUNES_DIR / filename
    return candidate if candidate.is_file() else None


def _split_trailing_subtune(positional: list[str]) -> tuple[list[str], int | None]:
    """If the last token is a bare integer, treat it as a subtune number
    and return the rest as the tune-name tokens."""
    if positional and positional[-1].isdigit():
        return positional[:-1], int(positional[-1])
    return positional, None


_SONG_SUFFIX_RE = re.compile(r'\.song\d+$')


def _list_tunes() -> list[str]:
    """Library keys with a base <key>.frames file, sorted -- excludes the
    per-subtune <key>.song<N>.frames files, which aren't tunes of their
    own."""
    if not TUNES_DIR.is_dir():
        return []
    return sorted(
        p.stem for p in TUNES_DIR.glob('*.frames')
        if not _SONG_SUFFIX_RE.search(p.stem)
    )


class PlayCommand(Command):
    name  = 'play'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'Play a SID tune on your Commodore 64.',
        category = HelpCategory.MISCELLANEOUS,
        usage    = [
            ('play <name>',           'Stream a tune from the library and play it.'),
            ('play <name> <subtune>', 'Play a specific subtune, e.g. "play ultima3 5".'),
            ('play #dir',             'List everything in the tune library.'),
            ('play #test',            'Stream the built-in test arpeggio, regardless of the library.'),
            ('play #about',           'Credits for the tools this pipeline is built on.'),
            ('play #stop',            'Silence your SID chip if playback misbehaves.'),
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not isinstance(ctx, PETSCIINetworkContext):
            await ctx.send("Your connection doesn't have a SID chip to play that on.")
            return CommandResult.fail('No SID chip available.', error='no_sid_chip')

        positional, switches = self.parse_args(*args)

        if '#stop' in switches:
            await ctx.send_raw(bytes([frames.STOP]))
            await ctx.send('Stopped.')
            return CommandResult.ok('Sent SID stop signal.')

        if '#about' in switches:
            await ctx.send(_ABOUT_TEXT)
            return CommandResult.ok('Displayed SID engine credits.')

        if '#dir' in switches:
            keys = _list_tunes()
            if not keys:
                await ctx.send('The tune library is empty.')
                return CommandResult.ok('Tune library is empty.')
            lines = ['|yellow|Tune library|white|']
            for key in keys:
                manifest = _load_manifest(key)
                if manifest is None:
                    lines.append(f'  {key}')
                    continue
                songs = f' ({manifest["num_songs"]} subtunes)' if manifest['num_songs'] > 1 else ''
                lines.append(f'  {key} -- "{manifest["title"]}" by {manifest["author"]}{songs}')
            await ctx.send(lines)
            return CommandResult.ok(f'Listed {len(keys)} tune(s).')

        if '#test' in switches:
            stream = frames.encode_stream(stub_tune.generate())
            await ctx.send(f'|cyan|[[c64]]|white| playing {len(stream)} bytes of SID music...')
            await ctx.send_raw(stream)
            return CommandResult.ok('Streamed the test arpeggio.')

        if not positional:
            await ctx.send('Play what? (try [play #test], or "help play" for the library)')
            return CommandResult.fail('No tune name given.')

        name_tokens, subtune = _split_trailing_subtune(positional)
        if not name_tokens:
            await ctx.send('Play what? (try [play #test], or "help play" for the library)')
            return CommandResult.fail('No tune name given.')

        name = ' '.join(name_tokens)
        key = _normalize(name)
        manifest = _load_manifest(key)

        if manifest is not None:
            if subtune is not None and not (1 <= subtune <= manifest['num_songs']):
                await ctx.send(f'"{name}" only has subtunes 1-{manifest["num_songs"]}.')
                return CommandResult.fail('Subtune out of range.', error='subtune_not_found')
            shown_subtune = subtune if subtune is not None else manifest['start_song']
            subtune_name = manifest['subtune_names'].get(str(shown_subtune))
            seconds = manifest.get('subtune_seconds', {}).get(str(shown_subtune))
            header = f'|yellow|{manifest["title"]}|white| by {manifest["author"]} ({manifest["released"]})'
            if manifest['num_songs'] > 1:
                header += f' -- subtune {shown_subtune}/{manifest["num_songs"]}'
                if subtune_name:
                    header += f': {subtune_name}'
            if seconds:
                header += f' ({int(seconds) // 60}:{int(seconds) % 60:02d})'
            await ctx.send(header)

        tune_path = _find_tune(key, subtune)
        if tune_path is None:
            await ctx.send(f'"{name}" isn\'t in the tune library -- try [play #test].')
            return CommandResult.fail('Tune not found.', error='tune_not_found')

        stream = tune_path.read_bytes()
        await ctx.send(f'|cyan|[[c64]]|white| playing {len(stream)} bytes of SID music...')
        await ctx.send_raw(stream)
        return CommandResult.ok(f'Streamed tune "{name}".')
