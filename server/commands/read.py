"""commands/read.py — READ: read a book-type item from inventory.

Mirrors SPUR.MISC2.S's `read` subroutine (line ~285) and, for item #69
specifically, the `elev` subroutine (line ~296-352).

Intelligence gate: SPUR's `read` subroutine opens with
`if pi<6 print "Not smart enough to read!":goto advent` -- too low
Intelligence blocks the command entirely, before even listing books.

Special case — item #69 "scrap of paper": READing it the first time asks
two flavor Y/N prompts ("Art thou true of heart?", "Good or Evil?" —
answering Evil costs 2 honor if honor > 2), then generates and displays a
random elevator combination. Deliberately deviates from SPUR here: the
paper is NOT consumed and the combination is NOT rerolled on subsequent
reads, so forgetting it isn't a dead end (see MECHANICS.md's "Elevator
Combination" section for the reasoning).

Special case — item #164 "brass claim tag" (shoppe/locker.py): READing it
displays the player's own LOCKER combination, engraved on the tag by the
locker attendant when it was handed over. Simpler than the scrap of paper:
no flavor prompts, since the combination already exists by the time the
tag does (see shoppe/locker.py's `_first_visit()`).

Other books have no flavor text in the data model yet, so READing them
just acknowledges the attempt.
"""
from __future__ import annotations

from base_classes import Combination, CombinationTypes, PlayerStat
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import ItemType
from network_context import GameContext

_SCRAP_OF_PAPER_ID = 69
_CLAIM_TAG_ID      = 164  # objects.json "brass claim tag" -- shoppe/locker.py
_MIN_INTELLIGENCE  = 6   # SPUR.MISC2.S read: `if pi<6 ... "Not smart enough to read!"`

_AP = "'"

# Special-cased by id rather than a shared `type`/`category` field: items
# picked up via commands/get.py or handed over directly (items.Item, e.g. the
# claim tag) only set `.category` (ItemCategory), never `.type` (ItemType) --
# so the ItemType.BOOK check below never actually matches a real in-play
# scrap of paper, only ones constructed directly in tests. Listing known
# readable ids here sidesteps that mismatch rather than fixing the deeper
# two-Item-class split (a bigger, separate cleanup).
_READABLE_IDS = {_SCRAP_OF_PAPER_ID, _CLAIM_TAG_ID}


def _item_number(item):
    """Return the item's catalog number, whichever attribute it's stored under.

    item_system.Item (load_items()) uses `.number`; items.Item
    (commands/get.py, shoppe/locker.py, etc.) uses `.id_number`.
    """
    number = getattr(item, 'number', None)
    return number if number is not None else getattr(item, 'id_number', None)


def _book_entries(player):
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    return [e for e in inv.entries()
            if getattr(e.item, 'type', None) == ItemType.BOOK
            or _item_number(e.item) in _READABLE_IDS]


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


async def _read_claim_tag(ctx: GameContext, player) -> None:
    combos = getattr(player, 'combinations', None) or {}
    combo  = combos.get(CombinationTypes.LOCKER)
    if combo is None:
        # Shouldn't normally happen -- the tag is only ever handed over
        # alongside the combination -- but don't crash if a save somehow
        # has one without the other.
        await ctx.send("The engraving has worn smooth -- you can't quite make it out.")
        return
    digits = '-'.join(f'{n:02}' for n in combo.combination)
    await ctx.send(f'Engraved on the tag: your Locker combination is {digits}.')


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

        stats = getattr(player, 'stats', None) or {}
        intelligence = int(stats.get(PlayerStat.INT, 10) or 0)
        if intelligence < _MIN_INTELLIGENCE:
            await ctx.send('Not smart enough to read!')
            return CommandResult.ok()

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

        item   = entry.item
        number = _item_number(item)
        if number == _SCRAP_OF_PAPER_ID:
            await _read_scrap_of_paper(ctx, player)
            return CommandResult.ok()
        if number == _CLAIM_TAG_ID:
            await _read_claim_tag(ctx, player)
            return CommandResult.ok()

        await ctx.send(f'You read the {item.name}, but there{_AP}s nothing more to learn from it.')
        return CommandResult.ok()
