"""shoppe/ollys.py — Olly's Ammo & Trap Shop (SPUR.MISC5.S ammo/booby sections)."""
import json
import logging
import os

from network_context import GameContext

log = logging.getLogger(__name__)

_BOOBY_TRAP_COST = 1000  # SPUR: if zt=1 it=1000
_BOOBY_CODES     = 'ABCDEFGHI'
# Item numbers in objects.json
_AMMO_RANGE      = range(98, 112)    # 98–111 inclusive
_CARRIER_RANGE   = range(147, 151)   # 147–150 inclusive
_BOOBY_BASE      = 152               # code A = 152, B = 153, …


def _load_objects() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), '..', 'objects.json')
    try:
        with open(os.path.normpath(path)) as fh:
            raw = json.load(fh)
        return raw['items'] if isinstance(raw, dict) and 'items' in raw else raw
    except Exception:
        log.error('Failed to load objects.json')
        return []


def _ammo_line(it: dict) -> str:
    """Format one ammo item for the shop listing."""
    flags    = it.get('flags', {})
    rounds   = flags.get('rounds', '?')
    damage   = flags.get('damage', '?')
    used_with = flags.get('used_with', '').strip()
    cost     = it['price'] * 10  # SPUR: it=it*10
    name     = it['name']
    return (
        f"  {it['number']:>3}: {name:<16} "
        f"{rounds:>3}rnd  dmg:{damage}  [{used_with}]  {cost}s"
    )


# ---------------------------------------------------------------------------
# Ammo listing and purchase
# ---------------------------------------------------------------------------

async def _ammo_section(ctx: GameContext, player, inv, objects_by_num: dict) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    ammo_items    = [objects_by_num[n] for n in _AMMO_RANGE    if n in objects_by_num]
    carrier_items = [objects_by_num[n] for n in _CARRIER_RANGE if n in objects_by_num]

    while True:
        lines = [
            '',
            '[]=-=-=-=-=-=-=-=[OLLY]=-=-=-=-=-=-=-=[]',
            '   #  Name             Rnds  Dmg  Weapon          Cost',
            '',
        ]
        for it in ammo_items:
            lines.append(_ammo_line(it))
        lines += ['', '  [ Ammo Carriers ]', '']
        for it in carrier_items:
            lines.append(_ammo_line(it))
        lines += ['', 'Enter item number, ? to re-list, or Q to leave.', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Your Choice')
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            continue

        try:
            num = int(choice)
        except ValueError:
            await ctx.send('Enter a number, ? to list, or Q to leave.')
            continue

        it = objects_by_num.get(num)
        if it is None or (num not in _AMMO_RANGE and num not in _CARRIER_RANGE):
            await ctx.send(f'Enter {_AMMO_RANGE.start}-{_AMMO_RANGE.stop - 1}, '
                           f'{_CARRIER_RANGE.start}-{_CARRIER_RANGE.stop - 1}, or Q.')
            continue

        if inv is not None and inv.is_full():
            await ctx.send('You have no room in your pack!')
            continue

        cost = it['price'] * 10
        name = it['name']

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < cost:
            await ctx.send('You do not have enough gold.')
            continue

        await ctx.send(f"You choose {name} for {cost} gold?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        item = Item(
            id_number = it['number'],
            name      = name,
            category  = ItemCategory.ITEM,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
        player.unsaved_changes = True
        await ctx.send('Done!')

        if num in _CARRIER_RANGE:
            await ctx.send(
                f'(Appropriate ammo will automatically be placed in the {name} '
                'when it is purchased. Buying more than one will do no good.)'
            )


# ---------------------------------------------------------------------------
# Booby trap purchase
# ---------------------------------------------------------------------------

async def _booby_section(ctx: GameContext, player, inv, objects_by_num: dict) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    await ctx.send([
        '',
        'You go to the Booby Trap display...',
        '"Ahh, note this selection of the finest traps!" beams Olly..',
        '"For you, only 1000 gold a piece!  Each with its secret disarm code!',
        ' Bury one of these babies with the DIG command and it will discourage',
        ' people from digging up your gold!"',
        '',
    ])

    while True:
        await ctx.send(f'Cost=1000.  Purchase Booby Trap.')
        raw = await ctx.prompt(f'Disarm code [{_BOOBY_CODES}] or Q to leave')
        if raw is None:
            return
        choice = raw.strip().upper()[:1]
        if not choice or choice == 'Q':
            await ctx.send('You leave the booby trap display.')
            return

        if choice not in _BOOBY_CODES:
            await ctx.send("Olly pretends not to notice you fumbling at the keyboard.")
            continue

        if inv is not None and inv.is_full():
            await ctx.send('You have no room in your pack!')
            return

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < _BOOBY_TRAP_COST:
            await ctx.send('You do not have enough gold.')
            continue

        num  = _BOOBY_BASE + _BOOBY_CODES.index(choice)
        it   = objects_by_num.get(num, {})
        name = it.get('name', f'booby trap (code {choice})')

        await ctx.send(f"You choose {name} for {_BOOBY_TRAP_COST} gold?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        item = Item(
            id_number = num,
            name      = name,
            category  = ItemCategory.ITEM,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, _BOOBY_TRAP_COST)
        player.unsaved_changes = True
        await ctx.send('Done!')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Olly's Ammo & Trap Shop. (SPUR.MISC5.S ammo/booby sections)"""
    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    all_objects  = _load_objects()
    objects_by_num = {o['number']: o for o in all_objects}

    await ctx.send(
        f"Olly greets you, 'Welcome, {player.name}!! Choose from this "
        "fine list of ammunition and stuff.'"
    )

    while True:
        raw = await ctx.prompt('[A]mmo, [B]ooby traps, or Q to leave')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return
        if cmd == 'A':
            await _ammo_section(ctx, player, inv, objects_by_num)
        elif cmd == 'B':
            await _booby_section(ctx, player, inv, objects_by_num)
        else:
            await ctx.send('A)mmo, B)ooby traps, or Q to leave.')
