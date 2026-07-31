"""encounters/droid_salvage.py — Mechanical-monster kill: salvage parts
drop + energy-weapon power pak recharge.

SPUR.MISC.S:406-415 ("no.gold"/"no.salvg" labels, right after the gold
roll in source order)::

    if not instr(":",wy$) goto no.robot
    gosub rnd.10z:if z>5 print "No salvagable parts":goto no.salvg
    if i=0 i=146:it$="SALVAGE PARTS":i1$="T"
   no.salvg
    if wa<>10 goto no.robot
    gosub rnd.10z
    if z>4 print "The power pak on "m$" was destroyed..":goto no.robot
    print "The power pak on "m$" is still energized!""Recharge your "wr$;
    input @2"? [Y]/n:"i$
    if i$<>"N" gosub delay.a:print "ZZZZTTT":gosub delay.a:vn=vl
   no.robot

Gated on the monster's mechanical flag (SPUR's `instr(":",wy$)`):
  - 50% chance (rnd(10)<=5) to drop objects.json #146 "salvage parts",
    regardless of what the player is wielding.
  - if the player's readied weapon is energy-class (SPUR wa=10), a
    further 40% chance (rnd(10)<=4) the droid's power pak is still
    charged; prompts to recharge, refilling ammo_rounds to ammo_max.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from monsters import monster_display_name
from tada_utilities import input_yes_no

if TYPE_CHECKING:
    from terminal_context import GameContext


def _weapon_class_str(weapon) -> str:
    wc = getattr(weapon, 'weapon_class', None)
    if wc is None:
        return 'hack_slash_bash'
    return wc.value if hasattr(wc, 'value') else str(wc)


async def apply(ctx: 'GameContext', monster: dict) -> None:
    """Run the salvage-parts/power-pak-recharge roll for a slain *monster*."""
    if not (monster.get('flags', {}) or {}).get('mechanical'):
        return
    player = ctx.player
    mname = monster_display_name(monster)

    if random.randint(1, 10) <= 5:
        pool = getattr(ctx.server, 'items', None) or []
        raw = next((r for r in pool if r.get('number') == 146), None)
        if raw:
            from items import Item, ItemCategory
            salvage = Item(id_number=146, name=raw.get('name', 'salvage parts'),
                            category=ItemCategory.ITEM, price=raw.get('price', 0))
            player.inventory.add(salvage, quantity=1)
            player.unsaved_changes = True
            await ctx.send(f'You find some salvage parts on {mname}!')
    else:
        await ctx.send('No salvageable parts.')

    weapon = getattr(player, 'readied_weapon', None)
    if weapon is None or _weapon_class_str(weapon) != 'energy':
        return
    if random.randint(1, 10) <= 4:
        wname = getattr(weapon, 'name', '') or 'weapon'
        await ctx.send(f'The power pak on {mname} is still energized!')
        recharge = await input_yes_no(ctx, f'Recharge your {wname}?', default=True)
        if recharge:
            await ctx.send('ZZZZTTT')
            player.ammo_rounds = player.ammo_max
            player.unsaved_changes = True
    else:
        await ctx.send(f'The power pak on {mname} was destroyed.')
