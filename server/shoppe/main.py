"""shoppe/main.py — Merchant Shoppe entry point (SPUR.SHOP.S port)."""
import json
import logging
import os

from network_context import GameContext
from presence import enter_area, leave_area, broadcast_open_room, others_present

log = logging.getLogger(__name__)

_AP = "'"

# Shoppe is closed on level 7 (matches SPUR.SHOP.S main1 level-gate)
_CLOSED_LEVELS = {7}

_WEAPON_MAX = 6      # SPUR xw<6 gate
_SPELL_MAX  = 10     # SPUR xs=10 gate
_SPELL_NON_ADEPT_MAX = 6  # SPUR if pc>2 then if xs>5 goto wiz2b


# ---------------------------------------------------------------------------
# Shared data helpers
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


# Hardcoded from SPUR-data/spells.txt (21 records; last is dummy sentinel).
# Fields: number, name, effect_type, effect_magnitude, cast_chance, price
# effect_type codes: S=Str W=Wis D=Dex C=Con E=Egy I=Int T=Transfer
#   P=Player-HP M=Monster L=LevelDown U=LevelUp R=Shop G=SPUR A=Aura
_SPELLS: list[dict] = [
    {'number':  1, 'name': 'ESP',                'effect': 'I', 'magnitude': 4, 'cast_chance': 70, 'price': 100},
    {'number':  2, 'name': 'WHEATIES',           'effect': 'S', 'magnitude': 6, 'cast_chance': 70, 'price': 150},
    {'number':  3, 'name': 'HAPPY FEET',         'effect': 'E', 'magnitude': 6, 'cast_chance': 50, 'price': 100},
    {'number':  4, 'name': 'KILL',               'effect': 'M', 'magnitude': 6, 'cast_chance': 60, 'price': 140},
    {'number':  5, 'name': 'ELEVATOR UP',        'effect': 'U', 'magnitude': 7, 'cast_chance': 70, 'price': 800},
    {'number':  6, 'name': 'KNOWLEDGE',          'effect': 'W', 'magnitude': 4, 'cast_chance': 70, 'price': 75},
    {'number':  7, 'name': 'DESTROYER',          'effect': 'M', 'magnitude': 8, 'cast_chance': 70, 'price': 250},
    {'number':  8, 'name': 'SLAUGHTER',          'effect': 'M', 'magnitude': 4, 'cast_chance': 90, 'price': 100},
    {'number':  9, 'name': 'DEPOSIT',            'effect': 'T', 'magnitude': 4, 'cast_chance': 80, 'price': 50},
    {'number': 10, 'name': 'WELL-BEING',         'effect': 'C', 'magnitude': 9, 'cast_chance': 70, 'price': 170},
    {'number': 11, 'name': 'BALANCE',            'effect': 'D', 'magnitude': 4, 'cast_chance': 60, 'price': 80},
    {'number': 12, 'name': 'ELEVATOR DOWN',      'effect': 'L', 'magnitude': 5, 'cast_chance': 80, 'price': 1000},
    {'number': 13, 'name': 'ENDURANCE',          'effect': 'P', 'magnitude': 8, 'cast_chance': 70, 'price': 140},
    {'number': 14, 'name': 'TRANSPORT TO SHOPPE','effect': 'R', 'magnitude': 8, 'cast_chance': 80, 'price': 250},
    {'number': 15, 'name': 'SUMMONS SPUR',       'effect': 'G', 'magnitude': 7, 'cast_chance': 90, 'price': 2000},
    {'number': 16, 'name': 'DISPELL POISON',     'effect': 'A', 'magnitude': 5, 'cast_chance': 90, 'price': 100},
    {'number': 17, 'name': 'APPLE A DAY',        'effect': 'A', 'magnitude': 7, 'cast_chance': 90, 'price': 100},
    {'number': 18, 'name': 'DRUID HEALTH',       'effect': 'A', 'magnitude': 9, 'cast_chance': 90, 'price': 200,  'druid_only': True},
    {'number': 19, 'name': "WIZARD'S GLOW",      'effect': 'A', 'magnitude': 9, 'cast_chance': 90, 'price': 200,  'wizard_only': True},
    {'number': 20, 'name': 'BOOTS OF SPEED',     'effect': 'A', 'magnitude': 9, 'cast_chance': 50, 'price': 2000},
]


# ---------------------------------------------------------------------------
# Armory
# ---------------------------------------------------------------------------

async def _armory(ctx: GameContext) -> None:
    """Buy and sell weapons. Max 6 per player. (SPUR.SHOP.S armory section)"""
    from base_classes import PlayerMoneyTypes, PlayerStat
    from items import Weapon, ItemCategory
    from inventory import PACK_FULL_MESSAGE

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
            await _protection(ctx)
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
            await _armory_buy(ctx, player, inv, all_weapons)
        elif cmd == 'S':
            await _armory_sell(ctx, player, inv, all_weapons)
        else:
            await ctx.send('Bye. Come again!')
            return


async def _armory_buy(ctx, player, inv, all_weapons) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Weapon, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    def _owned_ids() -> set[int]:
        if inv is None:
            return set()
        return {getattr(e.item, 'id_number', None)
                for e in inv.entries('Weapon')}

    def _owned_count() -> int:
        if inv is None:
            return 0
        return len(inv.entries('Weapon'))

    await ctx.send(
        '',
        "Excellent! Choose thee well!! From mine hands I have crafted this list of fine weapons!",
        '',
    )

    while True:
        if _owned_count() >= _WEAPON_MAX:
            raw = await ctx.prompt(
                'I am sorry, but you have no room for more weapons.  '
                'Do you wish to sell a weapon?'
            )
            if raw and raw.strip().upper() == 'Y':
                await _armory_sell(ctx, player, inv, all_weapons)
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
            await ctx.send(
                f"I see that you already possess this weapon.  You may NOT buy another."
            )
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
            await ctx.send(
                "Sorry to say, but you do not have enough gold at hand."
            )
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


async def _armory_sell(ctx, player, inv, all_weapons) -> None:
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

        entry  = weapon_entries[idx]
        wnum   = getattr(entry.item, 'id_number', 0)
        wdata  = weapon_map.get(wnum, {})
        v      = wdata.get('price', getattr(entry.item, 'price', 0) if hasattr(entry.item, 'price') else 0)
        pi     = int((player.stats or {}).get(PlayerStat.INT, 5) if hasattr(player, 'stats') and player.stats else 5)

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
# Protection
# ---------------------------------------------------------------------------

async def _protection(ctx: GameContext) -> None:
    """Buy armor and shields from objects.json items. (SPUR.SHOP.S protect section)"""
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    objects = _load_objects()
    # SPUR shows items 1-5 from items file; keep only armor and shields
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
            price = it['price'] * 100
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
        price  = chosen['price'] * 100  # SPUR: it=it*100

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

        player.unsaved_changes = True
        await ctx.send('Done!')


def _load_store_rations() -> list[dict]:
    """Load the first 10 rations from rations.json (all safe items, SPUR general subroutine)."""
    path = os.path.join(os.path.dirname(__file__), '..', 'rations.json')
    try:
        with open(os.path.normpath(path)) as fh:
            data = json.load(fh)
        return [r for r in data if r.get('number', 99) <= 10]
    except Exception:
        log.error('Failed to load rations.json for general store')
        return []


async def _general_store(ctx: GameContext) -> None:
    """Buy food and drink supplies. Mirrors SPUR.SHOP.S `general` subroutine.

    Shows only items 1-10 from rations.json (guaranteed safe).  Each item may
    be purchased at most once per player (SPUR: instr duplicate check).
    """
    from base_classes import PlayerMoneyTypes
    from items import Rations

    player = ctx.player
    inv = getattr(player, 'inventory', None)

    store_items = _load_store_rations()
    if not store_items:
        await ctx.send('The shelves are bare. Come back later.')
        return

    while True:
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)

        # Build list of items player does not already own (SPUR duplicate check).
        carried_ids = {
            getattr(e.item, 'id_number', None)
            for e in (inv.entries() if inv else [])
        }

        lines = ['Shelves of supplies stretch from floor to ceiling.', '',
                 f'Silver in hand: {silver}', '',
                 'Available items:', '']
        available = []
        for r in store_items:
            num  = r['number']
            name = r['name']
            kind = r['kind'].capitalize()
            price = r['price']
            if num in carried_ids:
                lines.append(f'  {"":>2}  {name:<20} {kind:<6}  {price:>4}s  (you have one)')
            else:
                available.append(r)
                lines.append(f'  {len(available):>2}. {name:<20} {kind:<6}  {price:>4}s')
        lines += ['', '[Enter] to leave', '']
        await ctx.send(lines)

        if not available:
            await ctx.send('You already carry everything the store sells.')
            return

        raw = await ctx.prompt(f'Buy which item (1-{len(available)}, Enter to leave)')
        if not raw or not raw.strip():
            return

        try:
            choice = int(raw.strip()) - 1
            if not (0 <= choice < len(available)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            continue

        chosen = available[choice]
        price  = chosen['price']

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send(f"You can't afford that. (Need {price}s, have {silver}s.)")
            continue

        from inventory import PACK_FULL_MESSAGE
        item = Rations(
            number=chosen['number'],
            name=chosen['name'],
            kind=chosen['kind'],
            price=chosen['price'],
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        player.unsaved_changes = True
        await ctx.send(f"You buy the {chosen['name']} for {price}s.")


async def _bank(ctx: GameContext) -> None:
    """Deposit, withdraw, or transfer gold between players (level 2+ for transfers)."""
    await ctx.send(
        'You approach the Bank of SPUR.  A teller looks up with a practiced smile.',
        '',
        '(Banking not yet available.)',
    )


async def _wizard(ctx: GameContext) -> None:
    """Learn spells. Wizards pay half price, Druids two-thirds. Max 10 spells."""
    await ctx.send(
        'The wizened wizard studies you carefully.',
        '',
        '(Wizard not yet available.)',
    )


async def _clan(ctx: GameContext) -> None:
    """Change guild affiliation (Claw, Sword, Fist, Civilian, Outlaw). Costs gold and honor."""
    await ctx.send(
        'A stern-faced registrar eyes you from behind a heavy desk.',
        '',
        '(Clan/Guild office not yet available.)',
    )


async def _elevator(ctx: GameContext) -> None:
    """Ride the elevator to levels 1–5."""
    from shoppe.elevator import main as elevator_main
    await elevator_main(ctx)


async def _pawn_shop(ctx: GameContext) -> None:
    """Sell (not buy) items to the pawn merchant."""
    await ctx.send(
        'A wiry merchant peers at you over a pile of odds and ends.',
        '',
        '(Pawn shop not yet available.)',
    )


async def _player_list(ctx: GameContext) -> None:
    """Browse online and offline players, optionally filtered by a wildcard pattern.

    * matches any string; ? matches one character.
    Examples:  *  lists everyone;  r*  lists players starting with R.
    """
    from commands.messaging import prompt_player_choice

    await ctx.send([
        'Player List',
        '',
        '* matches any string, ? matches one character.',
        'Examples:  *  (everyone),  r*  (names starting with R).',
        '',
    ])
    raw = await ctx.prompt('Search pattern (or * for all)')
    if raw is None:
        return
    pattern = raw.strip() or '*'

    chosen = await prompt_player_choice(ctx, pattern, prompt_text='Select player')
    if chosen:
        await ctx.send(f'Selected: {chosen}')


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

_MENU = (
    ('A', 'Armory',          _armory),
    ('P', 'Protection',      _protection),
    ('G', 'General Store',   _general_store),
    ('B', 'Bank of SPUR',    _bank),
    ('W', 'Wizard',          _wizard),
    ('C', 'Clan / Guild',    _clan),
    ('E', 'Elevator',        _elevator),
    ('V', 'Pawn Shop',       _pawn_shop),
    ('L', 'Player List',     _player_list),
)


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', 'Merchant Shoppe:', '']
    other_names = others_present(ctx, 'shoppe')
    if other_names:
        lines.append(f'  Also here: {", ".join(other_names)}')
        lines.append('')
    for key, label, _ in _MENU:
        lines.append(f'  [{key}] {label}')
    lines += ['  [X] Leave the Shoppe', '']
    await ctx.send(lines)


# ---------------------------------------------------------------------------
# Main entry point — called from commands/movement.py _enter_shoppe()
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Run the Merchant Shoppe interaction loop."""
    player = ctx.player

    level = getattr(player, 'map_level', 1) or 1
    if level in _CLOSED_LEVELS:
        await ctx.send(
            'Shoppe closed due to lack of interest on this level. '
            'Look for our stores in levels 1-5!!!'
        )
        return

    await ctx.send(
        f'You follow the sloping passageway downward into the merchant{_AP}s annex.',
        '',
        'Torchlight flickers across rows of stalls lining the walls.  The smell '
        'of old parchment and coin mingles in the cool underground air.',
    )
    await broadcast_open_room(
        ctx, f'{player.name} follows the sloping passageway downward into the merchant{_AP}s annex.',
    )

    await enter_area(ctx, 'shoppe')
    try:
        await _shoppe_session(ctx, player)
    finally:
        await leave_area(ctx, 'shoppe')


async def _shoppe_session(ctx: GameContext, player) -> None:
    """Inner shoppe loop, called after presence is established."""
    while True:
        if not player.is_expert:
            await _show_menu(ctx)

        raw = await ctx.prompt('Shoppe')
        if raw is None:
            break
        cmd = raw.strip().lower()[:1]

        if not cmd:
            continue

        if cmd == 'x':
            await ctx.send(f'You climb back up the passageway into the daylight.')
            break

        matched = next((fn for key, _, fn in _MENU if key.lower() == cmd), None)
        if matched:
            await matched(ctx)
        else:
            keys = '/'.join(k for k, _, _ in _MENU)
            await ctx.send(f'"{raw.strip()}"? ({keys}/X to choose)')


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.name = 'Rulan'
    ctx.player.map_level = 1
    ctx.player.is_expert = True
    ctx.send = AsyncMock()

    answers = iter(['a', 'p', 'g', 'b', 'w', 'c', 'v', 'l', 'x'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone shoppe test complete.')
