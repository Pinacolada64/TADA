"""commands/more_prompt.py — quickly toggle PlayerFlags.MORE_PROMPT.

The same toggle is also reachable via 'prefs' (the 'M' key); this command
exists so it can be flipped mid-session without opening the full menu.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.prefs import toggle_more_prompt


class MorePromptCommand(Command):
    """Toggle whether output pauses between screenfuls."""

    name    = 'mp'
    aliases = ['moreprompt']
    modes   = {Mode.LOGIN, Mode.GAME}

    help = Help(
        summary     = 'Quickly toggle More Prompt on/off.',
        description = (
            "When More Prompt is on, output longer than a screenful pauses "
            "with a '-- More --' prompt between pages (Enter for next, "
            "B/- for back, Q to stop). When off, everything is sent at "
            "once regardless of length. Same setting as 'prefs' menu's "
            "'M' key -- this is just a shortcut."
        ),
        category = HelpCategory.GENERAL,
        usage    = [('mp', 'Toggle More Prompt on/off.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        await toggle_more_prompt(ctx)
        return CommandResult.ok('More Prompt toggled.')
