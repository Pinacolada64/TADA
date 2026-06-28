"""commands/whisper.py — Whisper a private message to a player in the same room.

Syntax:  whisper <name>=<message>
Example: whisper Bob=Did you see that?

The '=' delimiter separates the target name from the message body so that
names or messages containing spaces work without quoting.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class WhisperCommand(Command):
    name    = 'whisper'
    # can't be 'w' — that's an alias for 'go west'
    aliases = ['wh']
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Whisper a private message to a player in your room.",
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('whisper <name>=<message>', 'Send a private whisper to <name>'),
        ],
        examples = [
            ('whisper Bob=Did you see that?', 'Only Bob hears your whisper'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)

        if not args:
            await ctx.send('Whisper to whom?  Usage: whisper <name>=<message>')
            return CommandResult.fail('No arguments.')

        raw = ' '.join(args)

        if '=' not in raw:
            await ctx.send('Usage: whisper <name>=<message>')
            return CommandResult.fail('Missing =.')

        target_name, _, message = raw.partition('=')
        target_name = target_name.strip()
        message     = message.strip()

        if not target_name:
            await ctx.send('Whisper to whom?  Usage: whisper <name>=<message>')
            return CommandResult.fail('Missing target name.')

        if not message:
            await ctx.send('Whisper what?  Usage: whisper <name>=<message>')
            return CommandResult.fail('Missing message.')

        my_name = ctx.player.name
        if target_name.lower() == my_name.lower():
            await ctx.send('You mutter to yourself, but no one notices.')
            return CommandResult.ok()

        my_room = getattr(ctx.client, 'room', None)

        target_ctx = None
        for other_client in ctx.server.clients.values():
            if other_client is ctx.client:
                continue
            if getattr(other_client, 'room', None) != my_room:
                continue
            other_ctx = getattr(other_client, 'ctx', None)
            if other_ctx is None:
                continue
            other_name = getattr(getattr(other_ctx, 'player', None), 'name', '')
            if other_name.lower() == target_name.lower():
                target_ctx = other_ctx
                break

        if target_ctx is None:
            await ctx.send(f'{target_name} is not here.')
            return CommandResult.fail('Target not in room.')

        real_name = target_ctx.player.name
        await ctx.send(f'You whisper to {real_name}, "{message}"')
        await target_ctx.send(f'{my_name} whispers to you, "{message}"')
        return CommandResult.ok()
