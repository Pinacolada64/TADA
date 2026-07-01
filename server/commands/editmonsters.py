"""commands/editmonsters.py — In-game monster editor (admin only)."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags


class EditMonstersCommand(Command):
    name    = 'editmonsters'
    aliases = ['em']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Open the monster editor (admin only).',
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [('editmonsters', 'Browse and edit monsters.json in-game.')],
        notes    = ['Requires the Administrator flag.'],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send("You don't have permission to use that command.")
            return CommandResult.fail(error='permission_denied')

        from monster_editor import main as monster_editor_main
        await monster_editor_main(ctx)
        return CommandResult.ok()
