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

Scrolls: SPUR.MISC2.S's `scroll`/`scroll.b` subroutines dispatch purely on
a substring match against the item's *name* (not its item number) --
"ANTI-MAGIC", "ENDURANCE", "DOORWAYS". Any book whose name contains
"SCROLL" is always consumed on read (SPUR: "The scroll catches fire and
burns.."), regardless of which effect (if any) matched:
  - ANTI-MAGIC: wipes every spell the player is carrying (SPUR: `xs=0:
    xs$=""` -- spells live in `player.inventory` in this port, not a
    separate list, so this removes every ItemCategory.SPELL entry).
  - ENDURANCE: sets HP to 30 + character level, +2 more for Ogres (SPUR:
    `hp=30+xp:if pr=2 hp=hp+2` -- pr=2 is Ogre in SPUR's own race
    numbering, 1=Human/2=Ogre/3=Pixie/4=Elf/..., not Elf).
  - DOORWAYS: NOT implemented. SPUR's `scroll.a` unconditionally sets that
    room's n/s/e/w exit-availability flags to 1 for a chosen direction,
    the same variables SPUR.MAIN.S's own room-exit-computation code reads
    -- i.e. it lets the player walk through a wall that has no real exit,
    via the level's row-width grid arithmetic. This port's Room.exits is a
    static per-room dict with no equivalent "temporarily passable, gets
    computed live" concept, so there's no clean way to port this without
    a wider movement-system change. See TODO.md.

There just happen to be two separate objects.json entries both named
"Scroll of Endurance" (#89 price 6, #92 price 5) -- confirmed this is a
genuine duplicate already present in the original SPUR objects.txt data
(not a conversion artifact), and since SPUR dispatches by name, not
number, both behave identically. Left as-is, faithfully.

Other books (not a scroll, and not one of the two special-cased ids
above): `books.json` (recovered via `tools/gbbsmsgtool.py` from
`SPUR-data/SPUR.BOOKS.TXT`, a GBBS Pro message-base file -- see books.py's
docstring) has flavor text for every book-type item in objects.json,
keyed by item number. READing one displays it; a book with no matching
entry (or if books.json failed to load) just acknowledges the attempt.

Wisdom bonus: SPUR.MISC2.S:316 (`scroll.b`) grants +1 Wisdom (capped at
25) with "(You feel wiser..)" on *every* consumed book, scroll or not --
both the scroll path and the plain "vanishes in a cloud of smoke!" path
fall through into the same `scroll.b` code. Deliberate deviation here:
since this port keeps non-scroll books re-readable instead of consuming
them, the bonus is tracked per item number in `player.read_books` so it
only fires the first time a given book is read, rather than being
farmable by re-reading the same reference book forever (`
_grant_reading_wisdom()`). Scrolls are consumed either way, so a re-read
isn't possible there regardless -- the tracking is really only load-
bearing for the reference/guide books.
"""
from __future__ import annotations

from base_classes import Combination, CombinationTypes, PlayerRace, PlayerStat
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
    # SPUR.MISC2.S's `read`: `if a=69 gosub elev:goto scroll.b` -- reading
    # the scrap of paper reaches scroll.b's Wisdom bonus too, same as any
    # other book. Grant it here since this special case returns before
    # execute()'s own generic-book fallback would otherwise do so.
    if _grant_reading_wisdom(player, _SCRAP_OF_PAPER_ID):
        await ctx.send('(You feel wiser..)')

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


_SCROLL_ENDURANCE_BONUS_RACE = PlayerRace.OGRE  # SPUR: `if pr=2` -- pr=2 is Ogre, not Elf
_MAX_WIS_FOR_READING_BONUS   = 25  # SPUR.MISC2.S:316: `if pw<25 pw=pw+1`


def _grant_reading_wisdom(player, number) -> bool:
    """SPUR.MISC2.S:316's `if pw<25 pw=pw+1:print "(You feel wiser..)"` --
    fires once per book read there, scroll or not (every consumed book
    falls through into scroll.b). This port keeps non-scroll books
    re-readable instead of consuming them (see module docstring), so the
    bonus is tracked per item number in player.read_books to stop it being
    farmed by re-reading the same reference book -- scrolls are consumed
    either way, so a re-read isn't possible there regardless.

    Returns True if Wisdom actually increased (caller prints the flavor
    line only then) -- False if already read before, or WIS is already at
    the cap.
    """
    if number is None or number in player.read_books:
        return False
    player.read_books.append(number)
    player.unsaved_changes = True
    stats = getattr(player, 'stats', None) or {}
    wis = int(stats.get(PlayerStat.WIS, 0) or 0)
    if wis >= _MAX_WIS_FOR_READING_BONUS:
        return False
    stats[PlayerStat.WIS] = wis + 1
    player.stats = stats
    return True


async def _read_scroll(ctx: GameContext, player, entry) -> None:
    """SPUR.MISC2.S's `scroll`/`scroll.b`: dispatch by substring on the
    item's name, then always consume it. See module docstring.

    Flavor text is the item's own recovered book entry (books.json, via
    books.get_book_text()) when available -- e.g. item #89's own text for
    reading it, not a generic hardcoded line -- falling back to a plain
    mechanical description if books.json didn't load or has no entry for
    this item number.
    """
    from books import get_book_text
    item = entry.item
    name_upper = (getattr(item, 'name', '') or '').upper()
    number = _item_number(item)
    flavor = get_book_text(ctx, number) if number is not None else None

    if 'ANTI-MAGIC' in name_upper:
        from items import ItemCategory
        inv = getattr(player, 'inventory', None)
        if inv is not None:
            for spell_entry in list(inv.entries(category=str(ItemCategory.SPELL))):
                inv.remove(spell_entry.item, quantity=spell_entry.quantity)
            player.unsaved_changes = True
        await ctx.send(flavor or ['Your spells fade from memory!'])

    elif 'ENDURANCE' in name_upper:
        xp_level = int(getattr(player, 'xp_level', 1) or 1)
        bonus = 2 if getattr(player, 'char_race', None) == _SCROLL_ENDURANCE_BONUS_RACE else 0
        player.hit_points = 30 + xp_level + bonus
        player.unsaved_changes = True
        await ctx.send(flavor or ['You feel invigorated!'])

    elif 'DOORWAYS' in name_upper:
        await ctx.send(flavor or [
            "The scroll's magic strains against the walls of this place, "
            "but fizzles -- this power isn't available yet."
        ])

    await ctx.send('The scroll catches fire and burns..')
    if _grant_reading_wisdom(player, number):
        await ctx.send('(You feel wiser..)')

    inv = getattr(player, 'inventory', None)
    if inv is not None:
        inv.remove(item)
        player.unsaved_changes = True


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

        # Statue's plaque (Ryan's request): not a real book/inventory item,
        # so it can never reach the normal entries-search below -- checked
        # first and reuses commands/look.py's exact flavor text (the same
        # "small brass plaque" message 'look statue'/'examine statue' show)
        # rather than duplicating it here.
        if args:
            target = ' '.join(args).lower()
            if 'statue' in target:
                from commands.get import _room_available_items
                from commands.look import _examine_item
                for name, entry, _remove_fn in _room_available_items(ctx):
                    if getattr(entry.item, 'is_statue', False) and target in name.lower():
                        await ctx.send(_examine_item(ctx, name, entry.item))
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

        if 'SCROLL' in (getattr(item, 'name', '') or '').upper():
            await _read_scroll(ctx, player, entry)
            return CommandResult.ok()

        from books import get_book_text
        flavor = get_book_text(ctx, number) if number is not None else None
        if flavor:
            await ctx.send(flavor)
        else:
            await ctx.send(f'You read the {item.name}, but there{_AP}s nothing more to learn from it.')

        # Deliberate deviation from SPUR: reference books stay in inventory
        # (re-readable) instead of being consumed -- see module docstring --
        # but still grant their one-time Wisdom bonus, same as scrolls.
        if _grant_reading_wisdom(player, number):
            await ctx.send('(You feel wiser..)')
        return CommandResult.ok()
