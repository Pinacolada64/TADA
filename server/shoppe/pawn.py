"""shoppe/pawn.py — Ye Olde Pawn Shoppe (SPUR.SHOP.S pawn.shp section)."""
import logging

from network_context import GameContext

log = logging.getLogger(__name__)

_ONCE_PER_DAY_KEY = 'pawn'

# Item IDs the pawn merchant refuses to buy (SPUR: if (a=73) or (a=76))
# 73 = Crown of Midas, 76 = Amulet of Life — quest-tier treasures, no resale
_REFUSED_IDS = frozenset({73, 76})


async def main(ctx: GameContext) -> None:
    """Ye Olde Pawn Shoppe — sell items for price*10 silver. (SPUR.SHOP.S pawn.shp)"""
    from base_classes import PlayerMoneyTypes
    from items import ItemCategory

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    # Once-per-day limit (SPUR ys$ "*PS" flag)
    if _ONCE_PER_DAY_KEY in player.once_per_day:
        await ctx.send('Pawn shoppe closed for today!')
        return
    player.once_per_day.append(_ONCE_PER_DAY_KEY)

    await ctx.send(['', 'Ye Olde Pawn Shoppe', ''])

    while True:
        item_entries = [
            e for e in (inv.entries(ItemCategory.ITEM) if inv else [])
        ]

        raw = await ctx.prompt('[S]ell, [Q]uit')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            await ctx.send('Ok-fine')
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

        raw = await ctx.prompt('Sell which item number? (Q to cancel)')
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

        # Refuse specific items (SPUR: if (a=73) or (a=76) print "I don't want it!")
        if iid in _REFUSED_IDS:
            await ctx.send("I don't want it!")
            continue

        # Price formula: item price * 10 (SPUR: g2=g2*10)
        base_price = getattr(item, 'price', 0) or 0
        offer      = base_price * 10

        if offer <= 0:
            await ctx.send(f"I'll give ya nothing for the {item.name}.")
            continue

        await ctx.send(f"I'll give ya {offer} silver for the {item.name},")
        raw = await ctx.prompt('Hoky-doky? (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            await ctx.send('Sniff..')
            continue

        if inv is None or not inv.remove(item):
            await ctx.send('Something went wrong removing the item.')
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, -offer)  # negative = add silver
        player.unsaved_changes = True
        await ctx.send('SOLD! Ya-betcha!')
