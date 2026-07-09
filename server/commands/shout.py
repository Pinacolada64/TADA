# commands/shout.py

# TADA imports
from commands.base_command import Command, CommandResult
from commands.help import Help, HelpCategory
from flags import PlayerFlags

class ShoutCommand(Command):
    """Send text to every connected player."""
    name    = 'shout'
    aliases = ['yell']

    help = Help(
        summary  = "Shout a message to every connected player.",
        category = HelpCategory.COMMUNICATION,
        usage    = [('shout <message>', 'Broadcast to all players on the server')],
    )
    async def execute(self, ctx, *args):
        if not args:
            await ctx.send("Shout what?")
            return CommandResult(success=False)

        text = ' '.join(args)
        name = ctx.player.name

        to_self = f'You shout, "{text}"'
        to_others = f'{name} shouts, "{text}"'

        is_dm = ctx.player.query_flag(PlayerFlags.DUNGEON_MASTER)
        await ctx.send(to_self)
        for other_client in ctx.server.clients.values():
            if other_client is ctx.client:
                continue
            # TODO: check whether shouts are ignored; override by DM/Wizard shout (non-negotiable)
            other_ctx = getattr(other_client, 'ctx', None)
            if other_ctx:
                await other_ctx.send(to_others)
        return CommandResult(success=True)
