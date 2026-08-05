"""ship/ammo_locker.py — the ship's ammo locker (SPUR.SHIP.S `ammo`/`ammo1`/`ammo2` section).

Sells energy-weapon ammo/power paks -- objects.json #118-121 (sabre power,
phaser pak, plasma power, plasma pak) -- at price*20 silver (SPUR: `it=it*20`).
Distinct from shoppe/ollys.py's Olly's Ammo & Traps, which covers a
different item range (98-111) and has no energy-weapon ammo at all.
"""
import json
import logging
import os

from network_context import GameContext
from table import Table, Column, Align

log = logging.getLogger(__name__)

# objects.json #118-121 inclusive (SPUR.SHIP.S ammo1: "x=118" ... "if x>121")
_AMMO_RANGE = range(118, 122)

# Same zebra-striping convention as shoppe/ollys.py's Olly's Ammo & Traps.
_ROW_COLORS = ['light_blue', 'cyan']


def _load_objects() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), '..', 'objects.json')
    try:
        with open(os.path.normpath(path)) as fh:
            raw = json.load(fh)
        return raw['items'] if isinstance(raw, dict) and 'items' in raw else raw
    except Exception:
        log.error('Failed to load objects.json for ship ammo locker')
        return []


def ammo_table(ammo_items: list, row_colors: list = None) -> Table:
    """Render the ammo listing, same style as shoppe/ollys.py's
    _ammo_table(). Unlike Olly's *carrier* items (which show remaining
    Capacity), every item here is straight ammo/power with its own
    rounds+damage -- so this borrows Olly's Rnds/Dmg ammo-table layout,
    not its Capacity carrier-table one.

    Two bugs fixed here from the first draft: `row_colors=list[ColorName]`/
    `ammo_items=list` as default *values* evaluate the type itself as the
    default, not an actual list/None -- and the call site was passing them
    in the wrong order, and never called .render() before sending the
    Table object as if it were already a list of lines.
    """
    if row_colors is None:
        row_colors = _ROW_COLORS
    t = Table(headers=[
        Column('#',         align=Align.RIGHT,  min_width=2),
        Column('Name',                          min_width=16),
        Column('Rnds',      align=Align.RIGHT,  min_width=4),
        Column('Dmg',       align=Align.RIGHT,  min_width=3),
        Column('Used With',                     min_width=12),
        Column('Cost',      align=Align.RIGHT,  min_width=4),
    ], border=False, text_color=row_colors)
    for j, it in enumerate(ammo_items, start=1):
        flags = it.get('flags', {})
        t.add_row([
            str(j),
            it['name'],
            str(flags.get('rounds', '?')),
            str(flags.get('damage', '?')),
            flags.get('used_with', '').strip(),
            f"{it['price'] * 20:,}s",  # SPUR: it=it*20 -- matches main()'s purchase price
        ])
    return t


async def main(ctx: GameContext) -> None:
    """Ship's ammo locker -- buy energy-weapon ammo for price*20 silver."""
    from base_classes import PlayerMoneyTypes
    from inventory import PACK_FULL_MESSAGE
    from items import Item, ItemCategory

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    objects_by_num = {o['number']: o for o in _load_objects()}
    ammo_items = [objects_by_num[n] for n in _AMMO_RANGE if n in objects_by_num]

    # Shop numbering is the table's own 1..N display index (matching the
    # "#" column and shoppe/ollys.py's own index_to_item convention), not
    # objects.json's raw #118-121 numbers -- easier to shop "1" than
    # remembering "phaser pak is #119".
    index_to_item = {i: it for i, it in enumerate(ammo_items, start=1)}

    await ctx.send("You enter the ship's ammo locker...")

    try:
        width = ctx.player.client_settings.screen_columns
    except AttributeError:
        width = 78

    while True:
        lines = ['', '<=-=-=-=-=-=-=[[AMMO LOCKER]]=-=-=-=-=-=-=-=>', '']
        lines += ammo_table(ammo_items).render(width=width)
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt('Your Choice (?=List, Q to leave)')
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
            await ctx.send(f'Enter 1-{len(ammo_items)} or Q')
            continue

        matched = index_to_item.get(num)
        if matched is None:
            await ctx.send(f'Enter 1-{len(ammo_items)} or Q')
            continue

        price = matched['price'] * 20
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send('You do not have enough silver.')
            continue

        await ctx.send(f"You choose {matched['name']} for {price} silver? ")
        raw = await ctx.prompt('AFFIRMATIVE? (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        item = Item(id_number=matched['number'], name=matched['name'],
                    category=ItemCategory.ITEM, flags=matched.get('flags', {}),
                    price=matched['price'])
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        player.unsaved_changes = True
        await ctx.send('You insert silver in the slot.')
