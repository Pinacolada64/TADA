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

_SPELL_MAX  = 10     # SPUR xs=10 gate
_SPELL_NON_ADEPT_MAX = 6  # SPUR if pc>2 then if xs>5 goto wiz2b


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


from shoppe.armory import main as _armory, protection as _protection


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

def _ollys(ctx: GameContext):
    from shoppe.ollys import main as ollys_main
    return ollys_main(ctx)


_MENU = (
    ('A', 'Armory',              _armory),
    ('P', 'Protection',          _protection),
    ('G', 'General Store',       _general_store),
    ('O', "Olly's Ammo & Traps", _ollys),
    ('B', 'Bank of SPUR',        _bank),
    ('W', 'Wizard',              _wizard),
    ('C', 'Clan / Guild',        _clan),
    ('E', 'Elevator',            _elevator),
    ('V', 'Pawn Shop',           _pawn_shop),
    ('L', 'Player List',         _player_list),
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
