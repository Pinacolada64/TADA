"""commands/page.py — Page a private message to any online player.

Syntax:  page <name>=<message>
Example: page Alice=Are you there?

Unlike whisper, the target does not need to be in the same room.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class PageCommand(Command):
    name    = 'page'
    aliases = ['tell', 'msg', 'p']
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Send a private message to any online player.",
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('page <name>=<message>', 'Send a private page to <name>'),
        ],
        examples = [
            ('page Alice=Are you there?', 'Alice receives your page from anywhere'),
            ('p Bob=Meet me at the inn',  'Alias p works the same way'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)

        if not args:
            await ctx.send('Page whom?  Usage: page <name>=<message>')
            return CommandResult.fail('No arguments.')

        raw = ' '.join(args)

        if '=' not in raw:
            await ctx.send('Usage: page <name>=<message>')
            return CommandResult.fail('Missing =.')

        target_name, _, message = raw.partition('=')
        target_name = target_name.strip()
        message     = message.strip()

        if not target_name:
            await ctx.send('Page whom?  Usage: page <name>=<message>')
            return CommandResult.fail('Missing target name.')

        if not message:
            await ctx.send('Page what?  Usage: page <name>=<message>')
            return CommandResult.fail('Missing message.')

        my_name = ctx.player.name
        if target_name.lower() == my_name.lower():
            await ctx.send('You cannot page yourself.')
            return CommandResult.ok()

        target_ctx = None
        for other_client in ctx.server.clients.values():
            if other_client is ctx.client:
                continue
            other_ctx = getattr(other_client, 'ctx', None)
            if other_ctx is None:
                continue
            other_name = getattr(getattr(other_ctx, 'player', None), 'name', '')
            if other_name.lower() == target_name.lower():
                target_ctx = other_ctx
                break

        if target_ctx is None:
            await ctx.send(f'{target_name} is not online.')
            return CommandResult.fail('Target not online.')

        real_name = target_ctx.player.name
        await ctx.send(f'You page {real_name}, "{message}"')
        await target_ctx.send(f'{my_name} pages you, "{message}"')
        return CommandResult.ok()
