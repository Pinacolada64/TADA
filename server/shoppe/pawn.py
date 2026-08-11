"""shoppe/pawn.py — Ye Olde Pawn Shoppe (SPUR.SHOP.S pawn.shp section)."""
import logging

from debug_tools import debug_toggle_once_per_day
from network_context import GameContext

log = logging.getLogger(__name__)

_ONCE_PER_DAY_KEY = 'pawn'

# Item IDs the pawn merchant refuses to buy (SPUR: if (a=73) or (a=76))
# 73 = Crown of Midas, 76 = Amulet of Life — quest-tier treasures, no resale
_REFUSED_IDS = frozenset({73, 76})

# Oldest item evicted once the back-room shelf fills up (server.pawn_stock
# has no save/load path -- same session-only precedent as server.room_items --
# so this only bounds memory during a long-running session, not across restarts).
_STOCK_CAP = 30

# Buy-back markup: no SPUR precedent to port (the original pawn.shp routine
# was sell-only -- see SPUR-code/SPUR.SHOP.S on the 'skip' branch), so this
# just sits between the sell price (price*10) and armory's full-retail buy
# (price*100, shoppe/armory.py's protection()) -- discounted "as-is" stock,
# matching ship/salvage_bay.py's existing price*40 buy-back ratio for
# internal consistency.
_BUY_MARKUP = 40


def _resolve_price(server, item) -> int:
    """Look up *item*'s catalog price by id_number, across whichever of
    server.items/weapons/rations matches its category -- entry.item.price
    is 0 for anything that survived a save/load round trip (Inventory.
    from_json() rebuilds carried items "lightweight", see main()'s comment
    below), so a raw attribute read alone isn't reliable."""
    from items import ItemCategory
    iid = getattr(item, 'id_number', None) or getattr(item, 'number', None)
    cat = getattr(item, 'category', None)
    if cat == ItemCategory.WEAPON:
        table = getattr(server, 'weapons', None) or []
    elif cat in (ItemCategory.FOOD, ItemCategory.DRINK):
        table = getattr(server, 'rations', None) or []
    else:
        table = getattr(server, 'items', None) or []
    data = next((d for d in table if d.get('number') == iid), {})
    return data.get('price', getattr(item, 'price', 0) or 0)


def add_to_stock(server, entry) -> None:
    """Add *entry* to the pawn shop's buy-back stock (server.pawn_stock).

    Fed both by players selling here and by commands/drop.py's water-room
    sinks -- once an item is in the shop's back room, it doesn't matter
    where it came from. Evicts the oldest entry once _STOCK_CAP is hit."""
    stock = server.pawn_stock
    stock.append(entry)
    while len(stock) > _STOCK_CAP:
        stock.pop(0)


async def main(ctx: GameContext) -> None:
    """Ye Olde Pawn Shoppe — sell items for price*10 silver, or buy back
    whatever's currently in the back room. (SPUR.SHOP.S pawn.shp -- SPUR's
    original was sell-only; Buy is new in this port, Ryan's request.)"""
    from base_classes import PlayerMoneyTypes
    from inventory import PACK_FULL_MESSAGE
    from items import ItemCategory
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    # Debug hook: manually toggle the once-per-day flag (see debug_tools.py)
    await debug_toggle_once_per_day(ctx, _ONCE_PER_DAY_KEY, label='pawn shoppe')

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
        stock = ctx.server.pawn_stock

        raw = await ctx.prompt(f'[S]ell, [B]uy, [Q]uit{shop_menu_hint(player)}')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            await ctx.send('Ok-fine')
            return
        if cmd in ('I', 'T') and await handle_shop_key(ctx, cmd):
            continue

        if cmd == 'B':
            if not stock:
                await ctx.send("Nothing's turned up in the back room today.")
                continue

            lines = ['', 'In the back room:', '']
            for i, entry in enumerate(stock, 1):
                price = _resolve_price(ctx.server, entry.item) * _BUY_MARKUP
                lines.append(f"  {i:>3}. {entry.item.name:<22} {price:>6}s")
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt('Buy which item number? (Q to cancel)')
            if raw is None:
                return
            choice = raw.strip().upper()
            if not choice or choice == 'Q':
                continue

            try:
                idx = int(choice) - 1
                if not (0 <= idx < len(stock)):
                    raise ValueError
            except ValueError:
                await ctx.send("I don't have that.")
                continue

            entry = stock[idx]
            price = _resolve_price(ctx.server, entry.item) * _BUY_MARKUP

            if player.get_silver(PlayerMoneyTypes.IN_HAND) < price:
                await ctx.send("You don't have that much on ya.")
                continue

            await ctx.send(f"That'll be {price} silver for the {entry.item.name},")
            raw = await ctx.prompt('Hoky-doky? (Y/N)')
            if raw is None or raw.strip().upper() != 'Y':
                await ctx.send('Sniff..')
                continue

            if inv is None or not inv.add(entry.item, entry.quantity):
                await ctx.send(PACK_FULL_MESSAGE)
                continue

            player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
            stock.pop(idx)
            player.unsaved_changes = True
            await ctx.send('SOLD! Ya-betcha!')
            continue

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
        offer = _resolve_price(ctx.server, item) * 10

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
        add_to_stock(ctx.server, entry)
        await ctx.send('SOLD! Ya-betcha!')
