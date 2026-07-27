"""commands/play.py — PLAY <name>: stream a SID tune to a C64 client.

Only PETSCIINetworkContext (real Commodore hardware, with a real SID chip)
can play anything; JSON/web clients get a plain refusal. `play #test` is
the escape hatch that streams sid_engine.stub_tune's canned arpeggio,
kept around deliberately as a standing way to prove the server ->
SwiftLink -> IRQ player pipe still works on its own, independent of
whatever's in the real tune library.

The real library (TUNES_DIR) holds pre-rendered .frames files -- already
sid_engine.frames-encoded byte streams, produced offline by
tools/sid_to_frames.py from an actual .sid file -- so serving one is just
a file read, no per-request 6502 emulation. See that tool's docstring for
how to add a tune: render it once, drop the .frames file in TUNES_DIR.
"""
from __future__ import annotations

from pathlib import Path

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import PETSCIINetworkContext
from sid_engine import frames, stub_tune

TUNES_DIR = Path(__file__).resolve().parent.parent / 'sid_engine' / 'tunes'


def _find_tune(name: str) -> Path | None:
    """Case/whitespace-insensitive lookup by filename stem in TUNES_DIR
    (e.g. "Vibrato Test" and "vibratotest" both match vibratotest.frames)."""
    key = ''.join(name.split()).lower()
    candidate = TUNES_DIR / f'{key}.frames'
    return candidate if candidate.is_file() else None


class PlayCommand(Command):
    name  = 'play'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'Play a SID tune on your Commodore 64.',
        category = HelpCategory.MISCELLANEOUS,
        usage    = [
            ('play <name>', 'Stream a tune from the library to your machine and play it.'),
            ('play #test',  'Stream the built-in test arpeggio, regardless of the library.'),
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not isinstance(ctx, PETSCIINetworkContext):
            await ctx.send("Your connection doesn't have a SID chip to play that on.")
            return CommandResult.fail('No SID chip available.', error='no_sid_chip')

        positional, switches = self.parse_args(*args)

        if '#test' in switches:
            stream = frames.encode_stream(stub_tune.generate())
            await ctx.send(f'|yellow|[[sid]] |white|streaming {len(stream)} bytes to client')
            await ctx.send_raw(stream)
            return CommandResult.ok('Streamed the test arpeggio.')

        if not positional:
            await ctx.send('Play what? (try [play #test], or `help play` for the library)')
            return CommandResult.fail('No tune name given.')

        name = ' '.join(positional)
        tune_path = _find_tune(name)
        if tune_path is None:
            await ctx.send(f'"{name}" isn\'t in the tune library -- try [play #test].')
            return CommandResult.fail('Tune not found.', error='tune_not_found')

        stream = tune_path.read_bytes()
        await ctx.send(f'|yellow|[[sid]] |white|streaming {len(stream)} bytes to client')
        await ctx.send_raw(stream)
        return CommandResult.ok(f'Streamed tune "{name}".')
