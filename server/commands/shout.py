# commands/shout.py

# TADA imports
from commands.base_command import Command, CommandResult
from commands.command_types import command
from flags import PlayerFlags

@command(name='shout', aliases=['yell'], summary='Shout to the entire MUD')
class ShoutCommand(Command):
    """Send text to every connected player."""
    async def execute(self, ctx, *args):
        if not args:
            await ctx.send("Shout what?")
            return CommandResult(success=False)

        text = ' '.join(args)
        name = ctx.player.name

        to_self = f'You shout, "{text}"'
        to_others = f'{name} shouts, "{text}"'

        for addr, other_client in ctx.server.clients.items():
            w = getattr(other_client, 'writer', None)
            # TODO: check whether shouts are ignored; override by DM/Wizard shout (non-negotiable)
            if ctx.player.query_flag(PlayerFlags.DUNGEON_MASTER):
                # shouting player is a DM; players set to 'shout #ignore' cannot ignore these
                w = getattr(other_client, 'ignore_shout', False)
                if w:
                    await ctx.send(to_others)

        await ctx.send(to_self)
        await ctx.send_room(to_others)
        return CommandResult(success=True)
