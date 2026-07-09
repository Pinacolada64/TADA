"""shoppe/locker.py — Private Locker (SPUR.MISC6.S "locker" subroutine).

Reached from the Merchant Shoppe by typing LOCKER (SPUR.MISC6.S:13's
`if i$="LOCKER" goto locker`, a free-text command word rather than one of
the Shoppe's lettered menu options), and returns to the Shoppe afterwards
(SPUR's `lnk.shop` link back into `spur.shop`, `"main1"`).

SPUR's own `locker` subroutine (SPUR.MISC6.S:276-345) has no access check at
all -- every player's locker record already exists (cleared at character
creation by SPUR.LOGON.S's `i$="locker":x=84:gosub wr.clr`), and P)ut/T)ake/
L)ook just read and write it directly by player number.

This port adds a combination-lock security layer on top (matching the
Elevator's guard-and-combination pattern in shoppe/elevator.py) as a
deliberate homebrew addition, not a port of original SPUR behaviour. A new
character has no LOCKER combination yet (see player.set_up_combinations());
the *first* visit to the locker is instead met by an attendant who assigns
one and hands over a brass claim tag engraved with it -- a distinct keepsake
from the Elevator's scrap of paper, so the two don't get confused.
Subsequent visits must enter the combination, like the Elevator guard.
"""
import logging

from base_classes import Combination, CombinationTypes
from inventory import Inventory, LOCKER_CAPACITY
from items import Item, ItemCategory
from network_context import GameContext

log = logging.getLogger(__name__)

_AP = "'"
_CLAIM_TAG_ID = 164  # objects.json: "brass claim tag"


def _find_combination(player, kind: CombinationTypes):
    """Return the Combination of the given type from the player's list, or None."""
    combos = getattr(player, 'combinations', None)
    if not combos:
        return None
    if isinstance(combos, dict):
        return combos.get(kind)
    return next((c for c in combos if c.name == kind), None)


# ---------------------------------------------------------------------------
# First visit — attendant assigns a locker and combination
# ---------------------------------------------------------------------------

async def _first_visit(ctx: GameContext, player) -> None:
    combo = Combination(CombinationTypes.LOCKER)
    combos = getattr(player, 'combinations', None)
    if not isinstance(combos, dict):
        combos = {}
    combos[CombinationTypes.LOCKER] = combo
    player.combinations = combos

    digits = '-'.join(f'{n:02}' for n in combo.combination)
    tag = Item(id_number=_CLAIM_TAG_ID, name='brass claim tag', category=ItemCategory.ITEM)
    inv = getattr(player, 'inventory', None)
    given = bool(inv) and inv.add(tag)

    lines = [
        '',
        'A locker attendant looks up as you approach the bank of lockers.',
        f'"First time here? Let me get you set up with a private locker."',
        f'"Your combination is {digits} -- don{_AP}t lose it!"',
    ]
    if given:
        lines.append('The attendant hands you a brass claim tag, engraved with the numbers, as a keepsake.')
    else:
        lines.append(f'"Hm, your pack looks full -- I can{_AP}t give you the tag, but I{_AP}ve made a note of your combination."')
    lines.append('')
    await ctx.send(lines)
    player.unsaved_changes = True


# ---------------------------------------------------------------------------
# Combination check — mirrors shoppe/elevator.py's get_combination()
# ---------------------------------------------------------------------------

async def _get_combination(ctx: GameContext, combo: Combination) -> bool:
    max_tries = 5
    for attempt in range(1, max_tries + 1):
        raw = await ctx.prompt(f'Locker combination [attempt {attempt}/{max_tries}]')
        if raw is None:
            return False
        ans = raw.strip()
        if not ans:
            await ctx.send("You need to enter your combination.")
            continue
        entered = Combination.from_string(ans)
        if entered and entered.combination == combo.combination:
            return True
        await ctx.send("That's not the right combination.")
    await ctx.send('Out of attempts.')
    return False


# ---------------------------------------------------------------------------
# P)ut / T)ake / L)ook  (SPUR.MISC6.S put.loc / tak.loc / look)
# ---------------------------------------------------------------------------

def _list_lines(label: str, entries) -> list[str]:
    lines = [f'{label}:', '']
    if entries:
        for i, e in enumerate(entries, 1):
            lines.append(f'  {i:>3}. {e.item.name}')
    else:
        lines.append('  Nothing..')
    return lines


async def _put(ctx: GameContext, player) -> None:
    inv, locker = player.inventory, player.locker
    if locker.is_full():
        await ctx.send('The locker is full!')
        return
    entries = list(inv.entries())
    if not entries:
        await ctx.send('No Items!')
        return

    await ctx.send([''] + _list_lines('You are carrying', entries) + [''])
    raw = await ctx.prompt('Put which item? (Enter to cancel)')
    if not raw or not raw.strip():
        return
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send("You're NOT carrying that!!")
        return

    item = entries[idx].item
    if inv.remove(item):
        locker.add(item)
        player.unsaved_changes = True
        await ctx.send('Ok, it is in the locker.')
    else:
        await ctx.send("You're NOT carrying that!!")


async def _take(ctx: GameContext, player) -> None:
    inv, locker = player.inventory, player.locker
    if inv.is_full():
        await ctx.send('You can carry no more Items.')
        return
    entries = list(locker.entries())
    if not entries:
        await ctx.send('The locker is empty!')
        return

    await ctx.send([''] + _list_lines('The locker contains', entries) + [''])
    raw = await ctx.prompt('Take which item? (Enter to cancel)')
    if not raw or not raw.strip():
        return
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send("That's not in the locker!")
        return

    item = entries[idx].item
    if locker.remove(item):
        if inv.add(item):
            player.unsaved_changes = True
            await ctx.send('Got it!')
        else:
            locker.add(item)
            await ctx.send('Your pack is full.')
    else:
        await ctx.send("That's not in the locker!")


async def _look(ctx: GameContext, player) -> None:
    lines = ['']
    lines += _list_lines('The locker contains', list(player.locker.entries()))
    lines += ['']
    lines += _list_lines('And you are carrying', list(player.inventory.entries()))
    lines += ['']
    await ctx.send(lines)


async def _locker_session(ctx: GameContext, player) -> None:
    await ctx.send(['', 'PRIVATE LOCKER', ''])
    while True:
        raw = await ctx.prompt('P)ut, T)ake, L)ook, Q)uit')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            await ctx.send('You close the locker.')
            return
        if cmd == 'P':
            await _put(ctx, player)
        elif cmd == 'T':
            await _take(ctx, player)
        elif cmd == 'L':
            await _look(ctx, player)
        else:
            await ctx.send('P)ut, T)ake, L)ook, Q)uit')


# ---------------------------------------------------------------------------
# Main entry point — called from shoppe/main.py
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Run the Private Locker interaction loop."""
    player = ctx.player
    if not isinstance(getattr(player, 'locker', None), Inventory):
        player.locker = Inventory(capacity=LOCKER_CAPACITY)

    combo = _find_combination(player, CombinationTypes.LOCKER)
    if combo is None:
        await _first_visit(ctx, player)
    else:
        ok = await _get_combination(ctx, combo)
        if not ok:
            return

    await _locker_session(ctx, player)


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    from player import Player

    ctx = MagicMock()
    ctx.player = Player(name='Rulan')
    ctx.send = AsyncMock()

    answers = iter(['q'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone locker test complete.')
