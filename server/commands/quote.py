"""commands/quote.py — SPUR.MISC2.S:488-503's QUOTE command.

Each player has a personal one-line quote (60 char max) shown to other
players who see them in a room (see simple_server.py's _describe_room(),
which shows each bystander's quote via tada_utilities.format_quote() --
mirrors SPUR.MAIN.S:398's gosub ply.loc7). A "$" in the quote is replaced
by the *reading* player's name, not the author's -- e.g. the author
writes "Hello $, welcome!" and each viewer sees their own name in place
of the $.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from tada_utilities import format_quote, input_yes_no

_MAX_QUOTE_LEN = 60


async def confirm_dollar_quote(ctx, text: str) -> bool | None:
    """If *text* contains a "$", show a rendered preview (substituted
    with the player's own name, as a stand-in reader) and ask for
    confirmation before it's used -- the $-placement is easy to get
    subtly wrong (e.g. no space after it running two words together).

    Returns True if there's nothing to preview (no "$") or the player
    accepted it, False if they rejected it (caller should let them
    re-enter the quote), or None if the connection dropped mid-prompt.

    Shared by QuoteCommand._write() (the in-game 'quote' command) and
    new_player.py's _choose_quote() (the character-creation step).
    """
    if '$' not in text:
        return True
    preview = format_quote(text, ctx.player.name)
    await ctx.send('That will look like:', preview)
    return await input_yes_no(ctx, 'Accept this?', default=True)


class QuoteCommand(Command):
    """View or change your personal quote."""

    name  = 'quote'
    modes = {Mode.GAME}

    help = Help(
        summary     = 'View or change your personal quote.',
        description = (
            "Your quote is a short line (60 characters max) other players "
            "see when they run into you. A '$' in it is replaced by "
            "*their* name, not yours -- e.g. write \"Hello $, welcome!\" "
            "and each viewer sees their own name where the $ was."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('quote', 'Open the View/Write/Quit menu.'),
        ],
        notes = [
            "V)iew previews how your quote reads to someone else.",
            "W)rite changes it; blank input leaves it unchanged.",
            "If your new quote contains a '$', you'll see a rendered "
            "preview and get to confirm it before it's saved.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        player = ctx.player

        while True:
            raw = await ctx.prompt('Quote: V)iew W)rite Q)uit')
            if raw is None:
                return CommandResult.ok()
            ans = raw.strip().lower()

            if ans == 'v':
                await ctx.send("VIEW: $ will be replaced by your handle.")
                preview = format_quote(player.quote, player.name)
                await ctx.send(preview if preview else f'{player.name} is silent..')
                continue

            if ans == 'w':
                await self._write(ctx)
                continue

            if not ans or ans == 'q':
                return CommandResult.ok()

    async def _write(self, ctx) -> None:
        player = ctx.player
        preamble = [
            '',
            f"Enter your quote now, {_MAX_QUOTE_LEN} char max. A $ in the quote "
            "will be replaced by the reading player's handle (leave a space, "
            "comma, etc, after the $).",
        ]
        while True:
            raw = await ctx.prompt('Enter quote now', preamble_lines=preamble)
            if raw is None:
                return
            text = raw.strip()
            if len(text) > _MAX_QUOTE_LEN:
                await ctx.send('TOO LONG!')
                continue
            if not text:
                await ctx.send('No change..')
                return

            satisfied = await confirm_dollar_quote(ctx, text)
            if satisfied is None:
                return
            if not satisfied:
                continue

            player.quote = text
            player.unsaved_changes = True
            await ctx.send('Quote set.')
            return
