"""commands/history.py — Show the player's recent command history."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from player import Player


class HistoryCommand(Command):
    name  = 'history'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'List your recently-typed commands.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('history', 'Show your last commands, most recent first.'),
            ('^1',      'Re-run the most recent command shown by "history".'),
            ('^3',      'Re-run the 3rd-most-recent command.'),
        ],
        notes = [
            f'Keeps your last {Player.COMMAND_HISTORY_CAP} commands.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        history = getattr(ctx.player, 'command_history', [])
        if not history:
            await ctx.send('No command history yet.')
            return CommandResult.ok()

        lines = ['', 'Command history:']
        for i, cmd_text in enumerate(reversed(history), 1):
            lines.append(f'{i:>2}. {cmd_text}')
        lines.append('')
        lines.append('Type ^N to re-run entry N (e.g. ^1 for the most recent).')
        await ctx.send(lines)
        return CommandResult.ok()
