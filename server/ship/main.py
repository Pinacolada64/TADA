"""ship/main.py — the Ship's Stores (SPUR.SHIP.S, level 6's own copy of the shop program).

Reuses the regular Merchant Shoppe's Bank/Player List modules directly --
SPUR.SHIP.S's own bank/plr.list labels are near-identical copies of
SPUR.SHOP.S's, and this port's shoppe/bank.py already sells from the same
level-agnostic catalog everywhere rather than SPUR's fixed per-location
item ranges, so there is nothing ship-specific to re-implement for those
two.

What actually differs here from shoppe/main.py:
  - Armory/Protection (ship/armory.py) is a thin wrapper around
    shoppe/armory.py restricted to a narrower rack -- SPUR.SHIP.S's own
    `weapons0`/`protect` sections only stock energy weapons (#58-60) and
    sci-fi armor (#113-116), unlike SPUR.SHOP.S's full catalog that this
    port's regular armory already generalized to.
  - General Store also reuses shoppe/main.py's `_general_store`, but
    restocked to rations.json #70-75 (SPUR.SHIP.S's own `general` item
    range -- sci-fi rations like FORMULAE H2O) instead of the regular
    shop's #1-10.
  - SALVAGE (ship/salvage_bay.py) and the ammo locker (ship/ammo_locker.py,
    energy-weapon ammo -- objects.json #118-121) exist only on the ship.
  - TR / the transporter (ship/transporter.py) beams the player down to
    another level's shop; unlike every other command here, a successful
    (or malfunctioning) trip ends the ship visit outright, matching
    SPUR's `link` semantics (the ship's own program is left behind, not
    returned to).
  - Wizard, Pawn Shop, and Clan/Guild are disabled here (SPUR.SHIP.S:
    `if i$="V" print "(No magic shop on the ship..)"`, `pawn.shp`,
    `clan` labels) -- refused with the same in-theme flavor text rather
    than silently omitted from the menu, so a player who reflexively
    types the regular shoppe's letters for them gets a reason, not a
    generic "Huh?".
"""
import logging

from network_context import GameContext
from presence import enter_area, leave_area, broadcast_open_room, others_present

log = logging.getLogger(__name__)


def _armory(ctx: GameContext):
    from ship.armory import main as armory_main
    return armory_main(ctx)


def _protection(ctx: GameContext):
    from ship.armory import protection as protection_main
    return protection_main(ctx)


# rations.json #70-75: GRUB #9277814, GRUB #983347, STANDARD RATIONS,
# FORMULAE H2O, ISSUE#92667 LIQUID, "RECYCLER WASTE" -- SPUR.SHIP.S's own
# `general` subroutine range (position #1,26,x for x=70..75), distinct
# from SPUR.SHOP.S's #1-10 that shoppe/main.py's General Store sells.
_RATION_IDS = range(70, 76)


def _general_store(ctx: GameContext):
    from shoppe.main import _general_store as general_store_impl
    return general_store_impl(ctx, numbers=_RATION_IDS)


def _bank(ctx: GameContext):
    from shoppe.bank import main as bank_main
    return bank_main(ctx)


def _player_list(ctx: GameContext):
    from shoppe.main import _player_list as player_list_impl
    return player_list_impl(ctx)


def _salvage_bay(ctx: GameContext):
    from ship.salvage_bay import main as salvage_bay_main
    return salvage_bay_main(ctx)


def _ammo_locker(ctx: GameContext):
    from ship.ammo_locker import main as ammo_locker_main
    return ammo_locker_main(ctx)


async def _wizard_disabled(ctx: GameContext) -> None:
    await ctx.send('(No magic shop on the ship..)')


async def _pawn_disabled(ctx: GameContext) -> None:
    await ctx.send('(Pawn shop not active here)')


async def _clan_disabled(ctx: GameContext) -> None:
    await ctx.send('(Join not active here)')


_MENU = (
    ('A', 'Armory',       _armory),
    ('P', 'Protection',   _protection),
    ('G', 'General Store', _general_store),
    ('M', 'Ammo Locker',  _ammo_locker),
    ('B', 'Bank of SPUR', _bank),
    ('W', 'Wizard',       _wizard_disabled),
    ('C', 'Clan / Guild', _clan_disabled),
    ('V', 'Pawn Shop',    _pawn_disabled),
    ('L', 'Player List',  _player_list),
)


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', "Ship's Stores:", '']
    other_names = others_present(ctx, 'ship')
    if other_names:
        lines.append(f'  Also here: {", ".join(other_names)}')
        lines.append('')
    for key, label, _ in _MENU:
        lines.append(f'  [{key}] {label}')
    lines += ['  [SALVAGE] Salvage Bay', '  [TR] Transporter',
              '  [X] Leave the Ship', '']
    await ctx.send(lines)


async def main(ctx: GameContext) -> None:
    """Run the Ship's Stores interaction loop (level 6, SPUR.SHIP.S)."""
    player = ctx.player

    await ctx.send(
        'You climb down through the manhole into the ship’s Stores area.',
        '',
        'Banks of humming consoles and metal shelving stretch into the gloom, '
        'lit by the cold glow of status lights.',
    )
    await broadcast_open_room(
        ctx, f'{player.name} climbs down through the manhole into the ship’s Stores area.',
    )

    await enter_area(ctx, 'Ship')
    try:
        await _ship_session(ctx, player)
    finally:
        await leave_area(ctx, 'Ship')


async def _ship_session(ctx: GameContext, player) -> None:
    while True:
        if not player.is_expert:
            await _show_menu(ctx)

        raw = await ctx.prompt('Ships Stores')
        if raw is None:
            break
        full = raw.strip().lower()

        if not full:
            continue

        # SALVAGE and TR are full-text commands (SPUR: `i$="SALVAGE"`,
        # `left$(i$,2)="TR"`), not lettered menu keys.
        if full == 'salvage':
            await _salvage_bay(ctx)
            continue
        if full.startswith('tr'):
            from ship.transporter import main as transporter_main
            left_ship = await transporter_main(ctx)
            if left_ship:
                return
            continue

        cmd = full[:1]

        if cmd == 'x':
            await ctx.send('You climb back up through the manhole.')
            break

        matched = next((fn for key, _, fn in _MENU if key.lower() == cmd), None)
        if matched:
            await matched(ctx)
        else:
            keys = '/'.join(k for k, _, _ in _MENU)
            await ctx.send(f'"{raw.strip()}"? ({keys}/SALVAGE/TR/X to choose)')
