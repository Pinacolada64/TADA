"""shoppe/main.py — Merchant Shoppe entry point (SPUR.SHOP.S port)."""
import json
import logging
import os

from network_context import GameContext
from presence import enter_area, leave_area, broadcast_open_room, others_present, try_global_command

log = logging.getLogger(__name__)

_AP = "'"

# Shoppe is closed on level 7 (matches SPUR.SHOP.S main1 level-gate)
_CLOSED_LEVELS = {7}

from shoppe.armory import main as _armory


def _load_store_rations(numbers: object = None) -> list[dict]:
    """Load rations.json entries whose number is in *numbers* (default:
    the first 10, all safe items, SPUR.SHOP.S's own `general` subroutine
    range). Pass a different container (e.g. ship/main.py's #70-75 sci-fi
    ration range, SPUR.SHIP.S's own `general` subroutine) to reuse this
    loader for a different rack."""
    path = os.path.join(os.path.dirname(__file__), '..', 'rations.json')
    try:
        with open(os.path.normpath(path)) as fh:
            data = json.load(fh)
        if numbers is None:
            return [r for r in data if r.get('number', 99) <= 10]
        return [r for r in data if r.get('number') in numbers]
    except Exception:
        log.error('Failed to load rations.json for general store')
        return []


async def _general_store(ctx: GameContext, *, numbers: object = None) -> None:
    """Buy food and drink supplies. Mirrors SPUR.SHOP.S `general` subroutine.

    Shows only items 1-10 from rations.json by default (guaranteed safe).
    Rations may be bought in any quantity -- SPUR's original "instr
    duplicate check" (one of each, ever) made it impossible to stock up
    before a trip, which made the hunger/thirst meter (survival.py)
    unforgivingly hard to keep ahead of; deliberately dropped, unlike most
    of this port's SPUR fidelity (2026-08-25). *numbers*, if given, is
    forwarded to _load_store_rations() to stock a different rack instead.
    """
    from base_classes import PlayerMoneyTypes
    from items import Rations

    player = ctx.player
    inv = getattr(player, 'inventory', None)

    store_items = _load_store_rations(numbers)
    if not store_items:
        await ctx.send('The shelves are bare. Come back later.')
        return

    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    while True:
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)

        # How many of each the player already carries, just for display --
        # no longer blocks a repurchase (see docstring above).
        carried_qty: dict = {}
        for e in (inv.entries() if inv else []):
            num = getattr(e.item, 'id_number', None)
            if num is not None:
                carried_qty[num] = carried_qty.get(num, 0) + getattr(e, 'quantity', 1)

        lines = ['Shelves of supplies stretch from floor to ceiling.', '',
                 f'Silver in hand: {silver}', '',
                 'Available items:', '']
        available = []
        for r in store_items:
            num  = r['number']
            name = r['name']
            kind = r['kind'].capitalize()
            price = r['price']
            available.append(r)
            have = carried_qty.get(num, 0)
            suffix = f'  (have {have})' if have else ''
            lines.append(f'  {len(available):>2}. {name:<20} {kind:<6}  {price:>4}s{suffix}')
        lines += ['', f'[{player.return_key}] to leave', '']
        await ctx.send(lines)

        raw = await ctx.prompt(
            'Item #',
            preamble_lines=[f'Buy which item (1-{len(available)}, {player.return_key} to leave{shop_menu_hint(player)})'])
        if not raw or not raw.strip():
            return

        if raw.strip().upper()[:1] in ('I', 'T') and await handle_shop_key(ctx, raw.strip().upper()[:1]):
            continue

        try:
            choice = int(raw.strip()) - 1
            if not (0 <= choice < len(available)):
                raise ValueError
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
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


def _bank(ctx: GameContext):
    from shoppe.bank import main as bank_main
    return bank_main(ctx)


def _wizard(ctx: GameContext):
    from shoppe.wizard import main as wizard_main
    return wizard_main(ctx)


def _clan(ctx: GameContext):
    from shoppe.clan import main as clan_main
    return clan_main(ctx)


async def _elevator(ctx: GameContext) -> None:
    """Ride the elevator to levels 1–5."""
    from shoppe.elevator import main as elevator_main
    await elevator_main(ctx)


async def _locker(ctx: GameContext) -> None:
    """Visit the Private Locker (SPUR.MISC6.S's `LOCKER` command)."""
    from shoppe.locker import main as locker_main
    await locker_main(ctx)


async def _school(ctx: GameContext) -> None:
    """Buy formal shield training (SPUR.MISC2.S's `SCHOOL` command)."""
    from shoppe.school import main as school_main
    await school_main(ctx)


def _pawn_shop(ctx: GameContext):
    from shoppe.pawn import main as pawn_main
    return pawn_main(ctx)


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
    raw = await ctx.prompt(
        'Pattern',
        preamble_lines=['Search pattern (or * for all)'])
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


def _inventory(ctx: GameContext):
    from shoppe.inventory_tools import inventory_main
    return inventory_main(ctx)


def _transfer(ctx: GameContext):
    from shoppe.inventory_tools import transfer_main
    return transfer_main(ctx)


_MENU = (
    ('A', 'Armory',              _armory),
    ('G', 'General Store',       _general_store),
    ('O', "Olly's Ammo & Traps", _ollys),
    ('B', 'Bank of SPUR',        _bank),
    ('W', 'Wizard',              _wizard),
    ('C', 'Clan / Guild',        _clan),
    ('E', 'Elevator',            _elevator),
    ('V', 'Pawn Shop',           _pawn_shop),
    ('L', 'Player List',         _player_list),
    ('I', 'Inventory',           _inventory),
)


def _menu_entries(ctx: GameContext) -> tuple:
    """_MENU plus [T]ransfer, shown only once there's somewhere to send an
    item -- a party ally or horse (shoppe/inventory_tools.has_transfer_targets()).
    Built per-call rather than baked into _MENU itself since eligibility can
    change mid-session (an ally dies, a horse is bought/sold) without the
    player leaving and re-entering the Shoppe.

    Sorted alphabetically by label (Ryan's request) rather than kept in
    _MENU's declaration order -- both the listing in _show_menu() and the
    key lookup in _shoppe_session() read this same sorted tuple, so the
    display order and any 'valid keys' error message stay in sync."""
    from shoppe.inventory_tools import has_transfer_targets

    entries = _MENU
    if has_transfer_targets(ctx.player):
        entries += (('T', 'Transfer to Party/Horse', _transfer),)
    return tuple(sorted(entries, key=lambda e: e[1].lower()))


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', 'Merchant Shoppe:', '']
    other_names = others_present(ctx, 'shoppe')
    if other_names:
        lines.append(f'  Also here: {", ".join(other_names)}')
        lines.append('')
    for key, label, _ in _menu_entries(ctx):
        lines.append(f'  [{key}] {label}')
    lines += ['  [LOCKER] Private Locker', '  [SCHOOL] Formal Shield Training',
              '  [X] Leave the Shoppe', '']
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

    await enter_area(ctx, 'Shoppe')
    try:
        await _shoppe_session(ctx, player)
    finally:
        await leave_area(ctx, 'Shoppe')


async def _shoppe_session(ctx: GameContext, player) -> None:
    """Inner shoppe loop, called after presence is established."""
    while True:
        if not player.is_expert:
            await _show_menu(ctx)

        raw = await ctx.prompt('Shoppe')
        if raw is None:
            break
        full = raw.strip().lower()

        if not full:
            continue

        # LOCKER is a free-text command word (SPUR.MISC6.S's `if i$="LOCKER"`),
        # not one of the Shoppe's lettered menu options, so check the full
        # word before truncating to a single character below.
        if full in ('locker', 'lock'):
            await _locker(ctx)
            continue

        # SCHOOL is likewise a free-text command word (SPUR.MISC2.S's
        # `if i$="SCHOOL"`), not a lettered menu option.
        if full == 'school':
            await _school(ctx)
            continue

        cmd = full[:1]

        if cmd == 'x':
            await ctx.send(f'You climb back up the passageway into the daylight.')
            break

        menu = _menu_entries(ctx)
        matched = next((fn for key, _, fn in menu if key.lower() == cmd), None)
        if matched:
            await matched(ctx)
        elif await try_global_command(ctx, raw):
            # 'help', 'help combination', 'whereat', etc. -- see
            # presence.try_global_command()'s own docstring. Checked
            # against the *full* input, not the single-char `cmd` this
            # menu dispatches on, so a multi-word command like
            # 'help combination' isn't truncated down to a bare 'h'
            # before it ever gets a chance to match. Ryan's report: a
            # player without a locker combination yet had no way to look
            # up 'help combination' while standing in the Shoppe.
            pass
        else:
            keys = '/'.join(k for k, _, _ in menu)
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
