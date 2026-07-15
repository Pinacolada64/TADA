"""shoppe/armory.py — Armory and Protection shop (SPUR.SHOP.S armory/protect sections)."""
import json
import logging
import os

from network_context import GameContext

log = logging.getLogger(__name__)

_WEAPON_MAX = 6  # SPUR xw<6 gate


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_weapons() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), '..', 'weapons.json')
    try:
        with open(os.path.normpath(path)) as fh:
            return json.load(fh)
    except Exception:
        log.error('Failed to load weapons.json')
        return []


def _load_objects() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), '..', 'objects.json')
    try:
        with open(os.path.normpath(path)) as fh:
            raw = json.load(fh)
        return raw['items'] if isinstance(raw, dict) and 'items' in raw else raw
    except Exception:
        log.error('Failed to load objects.json')
        return []


# ---------------------------------------------------------------------------
# Weaponry — buy
# ---------------------------------------------------------------------------

async def _buy(ctx: GameContext, player, inv, all_weapons) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Weapon
    from inventory import PACK_FULL_MESSAGE

    def _owned_ids() -> set[int]:
        if inv is None:
            return set()
        return {getattr(e.item, 'id_number', None) for e in inv.entries('Weapon')}

    def _owned_count() -> int:
        if inv is None:
            return 0
        return len(inv.entries('Weapon'))

    await ctx.send([
        '',
        "Excellent! Choose thee well!! From mine hands I have crafted this list of fine weapons!",
        '',
    ])

    while True:
        if _owned_count() >= _WEAPON_MAX:
            raw = await ctx.prompt(
                'I am sorry, but you have no room for more weapons.  '
                'Do you wish to sell a weapon?'
            )
            if raw and raw.strip().upper() == 'Y':
                await _sell(ctx, player, inv, all_weapons)
            return

        raw = await ctx.prompt('Your Choice (?=List, Q to leave)')
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            lines = ['', 'Available weapons:', '']
            for w in all_weapons:
                lines.append(f"  {w['number']:>3}. {w['name']:<22} {w['price']:>5}s")
            await ctx.send(lines)
            continue

        try:
            wnum = int(choice)
        except ValueError:
            await ctx.send('Enter a weapon number, ? to list, or Q to leave.')
            continue

        matched = next((w for w in all_weapons if w['number'] == wnum), None)
        if matched is None:
            await ctx.send('Weapon not available for sale!')
            continue

        if matched['number'] in _owned_ids():
            await ctx.send("I see that you already possess this weapon.  You may NOT buy another.")
            continue

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        price  = matched['price']
        await ctx.send(f"You choose the {matched['name']} for {price} silver,")

        raw = await ctx.prompt('Do you wish to try it out first?')
        if raw and raw.strip().upper() == 'Y':
            wc = matched.get('weapon_class', '')
            await ctx.send([
                '',
                f"You try out the {matched['name']}",
                f"Weapon class: {wc}",
                f"Base damage:  {matched.get('to_hit', '?')}",
                '',
            ])

        raw = await ctx.prompt('Buy it?')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        if silver < price:
            await ctx.send("Sorry to say, but you do not have enough gold at hand.")
            continue

        weapon = Weapon(
            id_number    = matched['number'],
            name         = matched['name'],
            location     = matched.get('location', 0),
            kind         = matched.get('kind'),
            sound_effect = tuple(matched.get('sound_effect', ('', ''))),
            stability    = matched.get('stability', 0),
            to_hit       = matched.get('to_hit', 0),
            price        = price,
            weapon_class = matched.get('weapon_class'),
        )
        if inv is None or not inv.add(weapon):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        player.unsaved_changes = True
        remaining = player.get_silver(PlayerMoneyTypes.IN_HAND)
        await ctx.send(f"DONE!  You now have {remaining} silver in hand.")

        if _owned_count() >= _WEAPON_MAX:
            await ctx.send('No more room for weapons!')


# ---------------------------------------------------------------------------
# Weaponry — sell
# ---------------------------------------------------------------------------

async def _sell(ctx: GameContext, player, inv, all_weapons) -> None:
    from base_classes import PlayerMoneyTypes, PlayerStat

    if inv is None:
        await ctx.send('No weapons.')
        return

    weapon_entries = inv.entries('Weapon')
    if not weapon_entries:
        await ctx.send('No weapons.')
        return

    weapon_map = {w['number']: w for w in all_weapons}

    while True:
        weapon_entries = inv.entries('Weapon')
        if not weapon_entries:
            await ctx.send('You have no more weapons to sell.')
            return

        lines = ['', 'Sell which weapon:', '']
        for i, entry in enumerate(weapon_entries, 1):
            lines.append(f"  {i}. {entry.item.name}")
        await ctx.send(lines)

        raw = await ctx.prompt('Which (Q to leave)')
        if raw is None or raw.strip().upper() == 'Q':
            return
        try:
            idx = int(raw.strip()) - 1
            if not (0 <= idx < len(weapon_entries)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            continue

        entry = weapon_entries[idx]
        wnum  = getattr(entry.item, 'id_number', 0)
        wdata = weapon_map.get(wnum, {})
        v     = wdata.get('price', getattr(entry.item, 'price', 0) if hasattr(entry.item, 'price') else 0)
        pi    = int((player.stats or {}).get(PlayerStat.INT, 5) if hasattr(player, 'stats') and player.stats else 5)

        # Weapon #17 (Excalibur) is banned from sale (SPUR: if x=17 print "Hah! Shame on you")
        if wnum == 17:
            await ctx.send([
                "Hah! Shame on you, I will not buy this weapon!!",
                "King Arthur is VERY disappointed in you.",
            ])
            honor_loss = min(25, int(getattr(player, 'honor', 0) or 0))
            if honor_loss > 0:
                player.honor = int(getattr(player, 'honor', 0) or 0) - honor_loss
                player.unsaved_changes = True
                await ctx.send(f'(Honor reduced by {honor_loss}.)')
            continue

        # SPUR sell formula: a=v/16; l=a*pi; if l>=v then l=a*14; if pi=0 then l=a
        a = max(1, v // 16)
        if pi == 0:
            offer = a
        else:
            offer = a * pi
            if offer >= v:
                offer = a * 14

        await ctx.send(f"I will give you {offer} silver for the {entry.item.name}.")
        raw = await ctx.prompt("Doest thou accept MY offer?")
        if raw is None or raw.strip().upper() != 'Y':
            continue

        if inv.remove(entry.item):
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -offer)  # negative = add silver
            player.unsaved_changes = True
            await ctx.send('Good!')


# ---------------------------------------------------------------------------
# Protection (armor and shields)
# ---------------------------------------------------------------------------

async def protection(ctx: GameContext) -> None:
    """Buy armor and shields. (SPUR.SHOP.S protect section)"""
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    objects    = _load_objects()
    prot_items = [o for o in objects if o.get('type') in ('armor', 'shield')]

    await ctx.send([
        '',
        'The Weapons Master greets you and says:',
        '"Welcome, Adventurer!! Choose from this fine list of protection for your long journey!"',
        '',
    ])

    while True:
        lines = ['', 'Protection available:', '']
        for i, it in enumerate(prot_items, 1):
            kind  = it['type'].capitalize()
            price = it['price'] * 100  # SPUR: it=it*100
            lines.append(f"  {i:>3}. {it['name']:<22} ({kind})  {price:>6}s")
        lines += ['', 'Q to leave', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Your Choice (?=List)')
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            continue

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(prot_items)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            continue

        chosen = prot_items[idx]
        price  = chosen['price'] * 100

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send('You do not have enough gold.')
            continue

        await ctx.send(f"You choose {chosen['name']} for {price} silver?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        item = Item(
            id_number = chosen['number'],
            name      = chosen['name'],
            category  = ItemCategory.ARMOR,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)

        # Update player's numeric armor/shield rating (protection value = price * 4)
        if chosen['type'] == 'armor':
            player.armor = chosen['price'] * 4
        else:
            player.shield = chosen['price'] * 4
            # Links this purchase to shield_proficiency's per-item tracking
            # (player.py's gain_shield_proficiency()) -- a newly bought
            # shield replaces whichever one was backing the old rating.
            player.active_shield_id = chosen['number']

        player.unsaved_changes = True
        await ctx.send('Done!')


# ---------------------------------------------------------------------------
# Armory entry point (handles P/W routing)
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Armory entry point — routes to protection or weaponry. (SPUR.SHOP.S armory section)"""
    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    await ctx.send("The Weaponsmith's eyes glitter as you enter.")

    while True:
        raw = await ctx.prompt('Wouldst thou be interested in [P]rotection or [W]eaponry?')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return
        if cmd == 'P':
            await protection(ctx)
            return
        if cmd == 'W':
            break
        await ctx.send('Good journey to you!')
        return

    all_weapons = _load_weapons()

    while True:
        raw = await ctx.prompt('Wouldst thou [B]uy or [S]ell?')
        if raw is None or raw.strip().upper()[:1] in ('', 'Q'):
            return
        cmd = raw.strip().upper()[:1]
        if cmd == 'B':
            await _buy(ctx, player, inv, all_weapons)
        elif cmd == 'S':
            await _sell(ctx, player, inv, all_weapons)
        else:
            await ctx.send('Bye. Come again!')
            return
