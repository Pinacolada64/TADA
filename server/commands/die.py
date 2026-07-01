"""commands/die.py — Voluntary suicide (SPUR.MAIN.S line 80-82).

In SPUR, typing DIE prompts "DIE! Ok? Y/N"; answering Y jumps to the
same dead: label that hp<1 uses.  This command mirrors that flow by
delegating to server._player_dies() after confirmation.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory


class DieCommand(Command):
    name    = 'die'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'End your life voluntarily.',
        category = HelpCategory.GENERAL,
        usage    = [('die', 'Commit suicide — prompts for confirmation.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        raw = await ctx.prompt('DIE! Ok? [Y/N]')
        if raw is None or raw.strip().upper() != 'Y':
            await ctx.send('(Thought better of it.)')
            return CommandResult.ok()

        await ctx.server._player_dies(ctx)
        return CommandResult.ok()
