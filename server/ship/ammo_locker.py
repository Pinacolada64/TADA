"""ship/ammo_locker.py — the ship's ammo locker (SPUR.SHIP.S `ammo`/`ammo1`/`ammo2` section).

Sells energy-weapon ammo/power paks -- objects.json #118-121 (sabre power,
phaser pak, plasma power, plasma pak) -- at price*20 gold (SPUR: `it=it*20`).
Distinct from shoppe/ollys.py's Olly's Ammo & Traps, which covers a
different item range (98-111) and has no energy-weapon ammo at all.
"""
import json
import logging
import os

from network_context import GameContext

log = logging.getLogger(__name__)

# objects.json #118-121 inclusive (SPUR.SHIP.S ammo1: "x=118" ... "if x>121")
_AMMO_RANGE = range(118, 122)


def _load_objects() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), '..', 'objects.json')
    try:
        with open(os.path.normpath(path)) as fh:
            raw = json.load(fh)
        return raw['items'] if isinstance(raw, dict) and 'items' in raw else raw
    except Exception:
        log.error('Failed to load objects.json for ship ammo locker')
        return []


async def main(ctx: GameContext) -> None:
    """Ship's ammo locker -- buy energy-weapon ammo for price*20 gold."""
    from base_classes import PlayerMoneyTypes
    from inventory import PACK_FULL_MESSAGE
    from items import Item, ItemCategory

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    objects_by_num = {o['number']: o for o in _load_objects()}
    ammo_items = [objects_by_num[n] for n in _AMMO_RANGE if n in objects_by_num]

    await ctx.send("You enter the ship's ammo locker..")

    while True:
        lines = ['', '  #  Name           Rnds Dmg Weapon              Cost', '']
        for it in ammo_items:
            flags = it.get('flags', {}) or {}
            lines.append(
                f"  {it['number']:>3}: {it['name']:<14} "
                f"{flags.get('rounds', 0):>4} {flags.get('damage', 0):>3} "
                f"{flags.get('used_with', ''):<18} {it['price'] * 20:>5}"
            )
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
            await ctx.send(f'Enter {_AMMO_RANGE.start} - {_AMMO_RANGE.stop - 1} or Q')
            continue

        matched = objects_by_num.get(num) if num in _AMMO_RANGE else None
        if matched is None:
            await ctx.send(f'Enter {_AMMO_RANGE.start} - {_AMMO_RANGE.stop - 1} or Q')
            continue

        price = matched['price'] * 20
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send('You do not have enough gold.')
            continue

        await ctx.send(f"You choose {matched['name']} for {price} gold? ")
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
        await ctx.send('You insert gold in the slot.')
