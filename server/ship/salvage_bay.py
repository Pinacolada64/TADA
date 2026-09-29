"""ship/salvage_bay.py — the Ship's Salvage Bay (SPUR.SHIP.S `salvage`/`sal.1`/`pwn.1` section).

Buys back salvage parts (objects.json #146 -- see encounters/droid_salvage.py
for how players acquire them) at price*40 gold, same currency pool as
shoppe/pawn.py's silver-in-hand sale. Any other item is refused
("NON-SALVAGE STATUS. DOES NOT COMPUTE").

Gated to once per session: SPUR's `ys$` "*SS" token
(`if instr("*SS",ys$) print "The salvage computer does not respond"`),
modeled here as player.once_per_day like every other once-per-session flag
in this port (see TODO.md's 7/15/26 once-per-session flag inventory).
"""
import logging

from debug_tools import debug_toggle_once_per_day
from network_context import GameContext

log = logging.getLogger(__name__)

_ONCE_PER_DAY_KEY = 'ship_salvage_bay'

# objects.json #146 -- the only item this bay will buy back.
_SALVAGE_ITEM_ID = 146


async def main(ctx: GameContext) -> None:
    """Ship's Salvage Bay -- sell salvage parts for price*40 gold. (SPUR.SHIP.S `salvage`)"""
    from base_classes import PlayerMoneyTypes
    from items import ItemCategory

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    items_map = {i['number']: i for i in (getattr(ctx.server, 'items', None) or [])}

    await ctx.send('You go to the ships Salvage Bay.')

    # Debug hook: manually toggle the once-per-session flag (see debug_tools.py)
    await debug_toggle_once_per_day(ctx, _ONCE_PER_DAY_KEY, label='ship salvage bay')

    if _ONCE_PER_DAY_KEY in player.once_per_day:
        await ctx.send('The salvage computer does not respond.')
        return
    player.once_per_day.append(_ONCE_PER_DAY_KEY)

    await ctx.send(['', 'Salvage Bay', ''])

    while True:
        item_entries = [
            e for e in (inv.entries(ItemCategory.ITEM) if inv else [])
        ]

        raw = await ctx.prompt('[S]ell, [Q]uit')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            await ctx.send('Affirmative, Dave.')
            return
        if cmd != 'S':
            continue

        if not item_entries:
            await ctx.send('No Items!!')
            return

        lines = ['', 'You are carrying:', '']
        for i, entry in enumerate(item_entries, 1):
            lines.append(f"  {i:>3}. {entry.item.name}")
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt(
            'Item #',
            preamble_lines=['Sell which item number? ([Q] Cancel)'])
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            continue

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(item_entries)):
                raise ValueError
        except ValueError:
            await ctx.send("You're NOT carrying that!!")
            continue

        entry = item_entries[idx]
        item  = entry.item
        iid   = getattr(item, 'id_number', 0)

        if iid != _SALVAGE_ITEM_ID:
            await ctx.send('NON-SALVAGE STATUS. DOES NOT COMPUTE.')
            continue

        # Price formula: item price * 40 (SPUR: g2=g2*40)
        idata      = items_map.get(iid, {})
        base_price = idata.get('price', getattr(item, 'price', 0) or 0)
        offer      = base_price * 40

        await ctx.send(f'SALVAGE VALUE {offer} GOLD FOR THE {item.name},')
        raw = await ctx.prompt('AFFIRMATIVE? (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            await ctx.send('bzzz..')
            continue

        if inv is None or not inv.remove(item):
            await ctx.send('Something went wrong removing the item.')
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, -offer)  # negative = add silver
        player.unsaved_changes = True
        await ctx.send('ACKNOWLEDGED.')
