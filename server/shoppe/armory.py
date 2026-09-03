"""shoppe/armory.py — Armory and Protection shop (SPUR.SHOP.S armory/protect sections)."""
import json
import logging
import os

from network_context import GameContext
from presence import try_global_command

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
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

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
                'Sell one?',
                preamble_lines=[
                    'I am sorry, but you have no room for more weapons.  '
                    'Do you wish to sell a weapon?'
                ])
            if raw and raw.strip().upper() == 'Y':
                await _sell(ctx, player, inv, all_weapons)
            return

        raw = await ctx.prompt(
            'Your Choice',
            preamble_lines=[f'(?=List, Q to leave{shop_menu_hint(player)})'])
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
        if choice in ('I', 'T') and await handle_shop_key(ctx, choice):
            continue

        try:
            wnum = int(choice)
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
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

        raw = await ctx.prompt('Try it?', preamble_lines=['Do you wish to try it out first?'])
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
            await ctx.send("Sorry to say, but you do not have enough silver at hand.")
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
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    if inv is None:
        await ctx.send('No weapons.')
        return

    weapon_entries = inv.entries('Weapon')
    if not weapon_entries:
        await ctx.send('No weapons.')
        return

    # Inventory.from_json() now resolves weapon-category entries back to a
    # real Weapon (items.resolve_weapon()) when the login path supplies
    # weapons_data, so entry.item.price should already be correct here --
    # this lookup is defense-in-depth for any entry that isn't (e.g. one
    # reconstructed by a code path that predates/skips that resolution),
    # not evidence it's dead code.
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

        raw = await ctx.prompt(
            'Which',
            preamble_lines=[f'Which (Q to leave{shop_menu_hint(player)})'])
        if raw is None or raw.strip().upper() == 'Q':
            return
        choice = raw.strip().upper()
        if choice in ('I', 'T') and await handle_shop_key(ctx, choice):
            continue
        try:
            idx = int(raw.strip()) - 1
            if not (0 <= idx < len(weapon_entries)):
                raise ValueError
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
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
                player.adjust_honor(-honor_loss)
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
        raw = await ctx.prompt('Accept?', preamble_lines=["Doest thou accept MY offer?"])
        if raw is None or raw.strip().upper() != 'Y':
            continue

        if inv.remove(entry.item):
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -offer)  # negative = add silver
            player.unsaved_changes = True
            await ctx.send('Good!')


# ---------------------------------------------------------------------------
# Protection (armor and shields)
# ---------------------------------------------------------------------------

# Condition-tier labels, adapted from origin/skip's SPUR.ARMORY.S 'pr.2a'
# label (master has no armory repair feature at all -- skip's is a whole
# separate source file this port never had an equivalent for, until now).
# Skip's own thresholds are ratio-based (current/max, can exceed 100 via a
# separate enchant path) with an extra ENCHANTED tier above 125%; this
# port's item.condition is already a flat 0-100 value with no >100 case
# for a repairable item, so that top tier collapses into EXCELLENT at 100.
def _condition_label(condition: int) -> str:
    if condition >= 100:
        return 'EXCELLENT'
    if condition > 75:
        return 'GOOD'
    if condition > 50:
        return 'SERVICABLE'
    if condition > 25:
        return 'POOR'
    return 'TERRIBLE'


async def _repair(ctx: GameContext, player, inv) -> None:
    """Repair a carried armor/shield item's condition back to 100%, for
    silver scaled to how much is missing. Adapted from origin/skip's
    SPUR.ARMORY.S -- same "smithy" flavor text and condition-label
    listing, retargeted from skip's separate misc.data-backed intactness
    file onto this port's item.condition (2026-08-08 durability redesign).
    Not present on master at all before this.

    Cost: skip's formula (missing points, doubled on some difficulty
    flag never resolved in this port) has no direct equivalent silver
    scale here, since this port's economy already ties an item's price
    to its full-condition value (protection()'s `price * 100` to buy one
    fresh). Repairing 1 missing point of condition costs the same as
    1/100th of a fresh purchase -- i.e. `missing_points * price` silver
    -- so repairing something to full never costs more than just buying
    a brand new one would.
    """
    from base_classes import PlayerMoneyTypes
    from item_system import ItemType
    from player import equipped_entry, refresh_equipped_rating

    if inv is None:
        await ctx.send('You have nothing to repair.')
        return

    def _repairable():
        return [e for e in inv.entries()
                if getattr(e.item, 'type', None) in (ItemType.ARMOR, ItemType.SHIELD)]

    def _worn_tag(item) -> str:
        item_id = getattr(item, 'id_number', None)
        for slot in ('armor', 'shield'):
            entry = equipped_entry(player, slot)
            if entry is not None and getattr(entry.item, 'id_number', None) == item_id:
                return '  [worn]'
        return ''

    while True:
        entries = _repairable()
        if not entries:
            await ctx.send("You don't have any armor or shields!")
            return

        lines = ['', "'What kin eye fix fer ye?'", '']
        for i, e in enumerate(entries, 1):
            condition = int(getattr(e.item, 'condition', 100) or 0)
            label     = _condition_label(condition)
            lines.append(f'  {i:>3}. {e.item.name:<22} {condition:>3}%  '
                         f'IN {label} CONDITION{_worn_tag(e.item)}')
        lines += ['', 'Q to leave', '']
        await ctx.send(lines)

        raw = await ctx.prompt(
            'Item #',
            preamble_lines=['Repair which (?=List, Q to leave)'])
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            continue

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(entries)):
                raise ValueError
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
            await ctx.send('Invalid selection.')
            continue

        entry     = entries[idx]
        condition = int(getattr(entry.item, 'condition', 100) or 0)
        if condition >= 100:
            await ctx.send(f"'The {entry.item.name} is already in perfect condition!'")
            continue

        missing = 100 - condition
        price   = int(getattr(entry.item, 'price', 0) or 0)
        cost    = missing * max(price, 1)

        await ctx.send(f"'I will fix the {entry.item.name} for {cost} silver.'")
        raw = await ctx.prompt('Ok? (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < cost:
            await ctx.send('You do not have enough silver.')
            continue

        await ctx.send([
            f'The smithy grabs the {entry.item.name} and scuttles back into the smoke.',
            'Noises can soon be heard.',
            'BANG... CLANG... RATTLE... WHEEZE(?)... OOFF!',
            'Done!',
        ])
        player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
        entry.item.condition = 100
        # If this happens to be the currently-worn/readied piece, refresh
        # the live rating too -- same as SPUR.ARMORY.S's own worn/readied
        # check at the end of its repair loop.
        for slot in ('armor', 'shield'):
            eq = equipped_entry(player, slot)
            if eq is entry:
                refresh_equipped_rating(player, slot)
        player.unsaved_changes = True
        remaining = player.get_silver(PlayerMoneyTypes.IN_HAND)
        await ctx.send(f'You now have {remaining} silver in hand.')


async def protection(ctx: GameContext, *, item_ids: set[int] | None = None) -> None:
    """Buy, or repair, armor and shields. (SPUR.SHOP.S protect section +
    origin/skip's separate SPUR.ARMORY.S repair feature, see _repair())

    *item_ids*, if given, restricts the rack to just those objects.json
    numbers -- e.g. ship/armory.py's sci-fi armor rack (#113-116),
    matching SPUR.SHIP.S's own narrower `protect` item range vs.
    SPUR.SHOP.S's full catalog (this port's default, unfiltered).
    """
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    objects    = _load_objects()
    prot_items = [o for o in objects if o.get('type') in ('armor', 'shield')]
    if item_ids is not None:
        prot_items = [o for o in prot_items if o.get('number') in item_ids]

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
        lines += ['', '[R]epair', 'Q to leave', '']
        await ctx.send(lines)

        raw = await ctx.prompt(
            'Your Choice',
            preamble_lines=[f'Your Choice (?=List{shop_menu_hint(player)})'])
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            continue
        if choice == 'R':
            await _repair(ctx, player, inv)
            continue
        if choice in ('I', 'T') and await handle_shop_key(ctx, choice):
            continue

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(prot_items)):
                raise ValueError
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
            await ctx.send('Invalid selection.')
            continue

        chosen = prot_items[idx]
        price  = chosen['price'] * 100

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send('You do not have enough silver.')
            continue

        await ctx.send(f"You choose {chosen['name']} for {price} silver?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        # item.type ('armor'/'shield') and a fresh condition=100 are what
        # let commands/wear.py/use.py recognize and equip this once it's
        # bought -- 2026-08-08's per-item durability redesign made
        # equipping an explicit WEAR/USE step rather than an armory side
        # effect (see below), so without .type this item would otherwise
        # sit in the pack unequippable ("This is not armor!").
        from item_system import ItemType
        item = Item(
            id_number = chosen['number'],
            name      = chosen['name'],
            category  = ItemCategory.ARMOR,
            type      = ItemType(chosen['type']),
            condition = 100,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        player.unsaved_changes = True
        # Purchasing no longer auto-equips (2026-08-08) -- it used to set
        # player.armor/player.shield directly here, bypassing WEAR/USE
        # entirely and leaving armor purchases (unlike shield ones) never
        # setting active_armor_id at all. Buying now behaves like any
        # other shop item: it lands in the pack, and WEAR/USE puts it on.
        if not player.is_expert:
            verb = 'WEAR' if chosen['type'] == 'armor' else 'USE'
            await ctx.send(f'Done! ({verb} it to put it on.)')
        else:
            await ctx.send('Done!')


# ---------------------------------------------------------------------------
# Armory entry point (handles P/W routing)
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, *, item_ids: set[int] | None = None) -> None:
    """Armory entry point — routes to protection or weaponry. (SPUR.SHOP.S armory section)

    *item_ids*, if given, restricts weapon purchases to just those
    weapons.json numbers and is forwarded to protection() unchanged --
    see its own docstring. Used by ship/armory.py for the ship's
    energy-weapon rack (#58-60).
    """
    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    # Flavor line swapped 2026-08-08 for origin/skip's SPUR.ARMORY.S
    # entrance text ("a huge metal smith who eyes you through a yellow
    # grin"), to match _repair()'s smithy already pulled from that same
    # source -- Ryan's call, not a drive-by ALL-CAPS conversion (CLAUDE.md).
    await ctx.send('The weapons master eyes you, grinning with a mouthful of yellowed teeth.')

    while True:
        raw = await ctx.prompt(
            'Choice',
            preamble_lines=['Wouldst thou be interested in [P]rotection or [W]eaponry?'])
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return
        if cmd == 'P':
            await protection(ctx, item_ids=item_ids)
            return
        if cmd == 'W':
            break
        await ctx.send('Good journey to you!')
        return

    all_weapons = _load_weapons()
    if item_ids is not None:
        all_weapons = [w for w in all_weapons if w.get('number') in item_ids]

    while True:
        raw = await ctx.prompt('Choice', preamble_lines=['Wouldst thou [B]uy or [S]ell?'])
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
