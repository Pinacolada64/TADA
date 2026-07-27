"""commands/play.py — PLAY <name>: stream a SID tune to a C64 client.

Only PETSCIINetworkContext (real Commodore hardware, with a real SID chip)
can play anything; JSON/web clients get a plain refusal. There's no real
tune library yet, so a plain `play <name>` just says so -- `play #test`
is the escape hatch that streams sid_engine.stub_tune's canned arpeggio,
kept around deliberately as a standing way to prove the server ->
SwiftLink -> IRQ player pipe still works, even once a real library lookup
exists for plain names.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import PETSCIINetworkContext
from sid_engine import frames, stub_tune


class PlayCommand(Command):
    name  = 'play'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'Play a SID tune on your Commodore 64.',
        category = HelpCategory.MISCELLANEOUS,
        usage    = [
            ('play <name>', 'Stream a tune to your machine and play it.'),
            ('play #test',  'Stream the built-in test arpeggio (no tune library yet).'),
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
            # await ctx.send('Playing the test arpeggio in the C64 client...')
            return CommandResult.ok('Streamed the test arpeggio.')

        if not positional:
            await ctx.send('Play what? (there is no tune library yet -- try [play #test])')
            return CommandResult.fail('No tune name given.')

        name = ' '.join(positional)
        await ctx.send(f'"{name}" isn\'t in the tune library yet -- try [play #test].')
        return CommandResult.fail('No tune library yet.', error='no_tune_library')
