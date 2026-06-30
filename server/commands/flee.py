"""commands/flee.py — Flee from an active combat."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class FleeCommand(Command):
    name    = 'flee'
    aliases = ['run', 'escape']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Try to escape from a fight.',
        category = HelpCategory.GENERAL,
        usage    = [('flee', 'Attempt to flee the current battle.')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        room_no = getattr(ctx.client, 'room', None)
        active  = getattr(ctx.server, 'active_combats', {})
        session = active.get(room_no)

        if not session or session._done.is_set():
            await ctx.send("You're not in a fight.")
            return CommandResult.fail(error='no_combat')

        if ctx not in session.attackers:
            await ctx.send("You're not fighting anything.")
            return CommandResult.fail(error='not_participant')

        escaped = await session.flee(ctx)
        return CommandResult.ok() if escaped else CommandResult.fail(error='blocked')
