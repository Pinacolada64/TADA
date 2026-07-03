"""commands/read.py — READ: read a book-type item from inventory.

Mirrors SPUR.MAIN.S's book-reading dispatch (`read.bk`) and, for item #69
specifically, SPUR.MISC2.S:296-352's `elev` subroutine.

Special case — item #69 "scrap of paper": READing it the first time asks
two flavor Y/N prompts ("Art thou true of heart?", "Good or Evil?" —
answering Evil costs 2 honor if honor > 2), then generates and displays a
random elevator combination. Deliberately deviates from SPUR here: the
paper is NOT consumed and the combination is NOT rerolled on subsequent
reads, so forgetting it isn't a dead end (see MECHANICS.md's "Elevator
Combination" section for the reasoning).

Other books have no flavor text in the data model yet, so READing them
just acknowledges the attempt.
"""
from __future__ import annotations

from base_classes import Combination, CombinationTypes
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import ItemType
from network_context import GameContext

_SCRAP_OF_PAPER_ID = 69

_AP = "'"


def _book_entries(player):
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    return [e for e in inv.entries() if getattr(e.item, 'type', None) == ItemType.BOOK]


async def _read_scrap_of_paper(ctx: GameContext, player) -> None:
    combos = getattr(player, 'combinations', None)
    if not isinstance(combos, dict):
        combos = {}
        player.combinations = combos

    existing = combos.get(CombinationTypes.ELEVATOR)
    if existing is None:
        raw = await ctx.prompt("A voice whispers, 'Art thou true of heart?' [Y/N]")
        # SPUR doesn't branch on the answer -- it's flavor only.
        _ = raw

        raw = await ctx.prompt("'Wilt thou use this information for Good or Evil?' [G/E]")
        if (raw or '').strip().upper().startswith('E'):
            honor = int(getattr(player, 'honor', 0) or 0)
            if honor > 2:
                player.honor = honor - 2
                player.unsaved_changes = True

        combo = Combination(CombinationTypes.ELEVATOR)
        combos[CombinationTypes.ELEVATOR] = combo
        player.unsaved_changes = True
        digits = '-'.join(f'{n:02}' for n in combo.combination)
        await ctx.send([
            "The voice dies away, 'read the paaaaper..'",
            f'It reads: Your personal combination to the Elevator is: {digits}',
        ])
    else:
        digits = '-'.join(f'{n:02}' for n in existing.combination)
        await ctx.send(f'It reads: Your personal combination to the Elevator is: {digits}')


class ReadCommand(Command):
    name    = 'read'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Read a book from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('read',        'List readable books and choose one'),
            ('read <name>', 'Read the book matching name'),
        ],
        examples = [
            ('read',                 'Pick from book list'),
            ('read scrap of paper',  'Read the scrap of paper'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player
        entries = _book_entries(player)

        if not entries:
            await ctx.send('You have no books!')
            return CommandResult.ok()

        if args:
            pattern = ' '.join(args).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying anything matching "{" ".join(args)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['', 'Books:']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Read which Book (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                idx = int(raw.strip()) - 1
                if not (0 <= idx < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send("You don't have that Book!")
                return CommandResult.ok()
            entry = entries[idx]

        item = entry.item
        if getattr(item, 'number', None) == _SCRAP_OF_PAPER_ID:
            await _read_scrap_of_paper(ctx, player)
            return CommandResult.ok()

        await ctx.send(f'You read the {item.name}, but there{_AP}s nothing more to learn from it.')
        return CommandResult.ok()
