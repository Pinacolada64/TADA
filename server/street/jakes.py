"""street/jakes.py — Jake's Stable: mount supplies and horse training.

Ported from the skip branch's SPUR.MISC8.S (jakes/jakes1/item/food/train/tips).

SPUR notes:
  - Oats (ration #25 "WILD OATS" in this port's rations.json -- SPUR's own
    numbering doesn't survive re-indexing) and Sugar Cube (#16 "CUBE OF
    SUGAR", numbers match exactly) are bought like any general-store ration
    (mirrors shoppe/main.py's _general_store).
  - Lasso (#161), Saddle (#162), Horse Armor (#163) already exist in
    objects.json, priced at SPUR's raw value x100 gold (mirrors
    shoppe/ollys.py's item-purchase pattern).
  - Saddle/Horse Armor are not "worn" here at the shop -- USE them on a
    mount ally afterwards (commands/use.py, SPUR.USE.S eq.horse).
  - Train Horse: 2,000 gold. Requires an owned MOUNT ally that is already
    SADDLED and ARMORED; applies AllyFlags.ELITE ("!" sigil -- SPUR reuses
    the same "trained" flag allies get from Discipline training).
  - Train Horse's flavor text and the Tips menu option both print
    server/messages.json entries #34/#35 (SPUR.MISC8.S: `a=34:gosub
    messages`/`a=35:gosub messages`) via messages.send_message(), rather
    than reproducing the text inline -- see MECHANICS.md's "Recovered SPUR
    Messages" table. The final "prances proudly" line after #34 is this
    port's own addition, naming the specific mount.
"""
import logging

from bar.ally_data import AllyFlags
from bar.allies import owned_allies
from base_classes import PlayerMoneyTypes
from network_context import GameContext

log = logging.getLogger(__name__)

_NPC = 'Jake'

_OATS_RATION_NUM        = 25   # "WILD OATS" (rations.json)
_SUGAR_CUBE_RATION_NUM  = 16   # "CUBE OF SUGAR" (rations.json)

_LASSO_ITEM_NUM       = 161
_SADDLE_ITEM_NUM      = 162
_HORSE_ARMOR_ITEM_NUM = 163

_TRAIN_COST = 2000

# server/messages.json entries (SPUR.MISC8.S: `train` -> a=34, `tips` -> a=35).
_TRAIN_MESSAGE_NUM = 34
_TIPS_MESSAGE_NUM  = 35


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_rations() -> list[dict]:
    import json
    from pathlib import Path
    path = Path(__file__).parent / '..' / 'rations.json'
    try:
        with path.resolve().open() as fh:
            return json.load(fh)
    except Exception:
        log.error('Failed to load rations.json for Jake\'s Stable')
        return []


def _load_objects() -> list[dict]:
    import json
    from pathlib import Path
    path = Path(__file__).parent / '..' / 'objects.json'
    try:
        with path.resolve().open() as fh:
            raw = json.load(fh)
        return raw['items'] if isinstance(raw, dict) and 'items' in raw else raw
    except Exception:
        log.error('Failed to load objects.json for Jake\'s Stable')
        return []


def _find_mount(player):
    """Return the player's MOUNT-flagged ally, or None."""
    for ally in owned_allies(player):
        if AllyFlags.MOUNT in (ally.flags or []):
            return ally
    return None


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------

async def _buy_ration(ctx: GameContext, ration_num: int) -> None:
    from inventory import PACK_FULL_MESSAGE
    from items import Rations

    player = ctx.player
    rations = _load_rations()
    chosen = next((r for r in rations if r['number'] == ration_num), None)
    if chosen is None:
        await ctx.send('Unavailable!')
        return

    price = chosen['price']
    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
    if silver < price:
        await ctx.send('You do not have enough gold.')
        return

    raw = await ctx.prompt(f"You choose {chosen['name']} for {price} gold? (Y/N)")
    if not raw or raw.strip().upper() != 'Y':
        return

    inv = getattr(player, 'inventory', None)
    item = Rations(number=chosen['number'], name=chosen['name'],
                    kind=chosen['kind'], price=price)
    if inv is None or not inv.add(item):
        await ctx.send(PACK_FULL_MESSAGE)
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
    player.unsaved_changes = True
    await ctx.send('Done!')


async def _buy_item(ctx: GameContext, item_num: int) -> None:
    from inventory import PACK_FULL_MESSAGE
    from items import Item, ItemCategory

    player = ctx.player
    objects_by_num = {o['number']: o for o in _load_objects()}
    chosen = objects_by_num.get(item_num)
    if chosen is None:
        await ctx.send('Unavailable!')
        return

    price = chosen['price'] * 100   # SPUR "item" subroutine: it=it*100
    name  = chosen['name']
    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
    if silver < price:
        await ctx.send('You do not have enough gold.')
        return

    raw = await ctx.prompt(f'You choose {name} for {price} gold? (Y/N)')
    if not raw or raw.strip().upper() != 'Y':
        return

    inv = getattr(player, 'inventory', None)
    item = Item(id_number=chosen['number'], name=name, category=ItemCategory.ITEM)
    if inv is None or not inv.add(item):
        await ctx.send(PACK_FULL_MESSAGE)
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
    player.unsaved_changes = True
    await ctx.send('Done!')


# ---------------------------------------------------------------------------
# Train Horse
# ---------------------------------------------------------------------------

async def _train_horse(ctx: GameContext) -> None:
    player = ctx.player
    mount = _find_mount(player)
    if mount is None:
        await ctx.send("Ye don't have a mount!")
        return
    if AllyFlags.SADDLED not in (mount.flags or []):
        await ctx.send('Ye horse must have a saddle first.')
        return
    if AllyFlags.ARMORED not in (mount.flags or []):
        await ctx.send('Ye horse must have armor first.')
        return
    if AllyFlags.ELITE in (mount.flags or []):
        await ctx.send('Thy mount already IS trained!')
        return

    raw = await ctx.prompt(f'Ye want me to train yer horse for {_TRAIN_COST} gold? (Y/N)')
    if not raw or raw.strip().upper() != 'Y':
        return
    if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, _TRAIN_COST):
        await ctx.send('Ye do not have enough gold.')
        return

    player.unsaved_changes = True
    mount.flags.append(AllyFlags.ELITE)

    from messages import send_message
    if not await send_message(ctx, _TRAIN_MESSAGE_NUM):
        await ctx.send("Jake leads your horse into the back room, and returns some time later.")
    await ctx.send(f'{mount.name} prances proudly -- fully trained and ready to ride!')


# ---------------------------------------------------------------------------
# Tips
# ---------------------------------------------------------------------------

async def _tips(ctx: GameContext) -> None:
    from messages import send_message
    if not await send_message(ctx, _TIPS_MESSAGE_NUM):
        await ctx.send(
            f'{_NPC} leans on the fence post. '
            '"A good mount needs a saddle AND armor before I can train it up proper."'
        )


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

_MENU = [
    ('1', lambda ctx: _buy_ration(ctx, _OATS_RATION_NUM)),
    ('2', lambda ctx: _buy_item(ctx, _LASSO_ITEM_NUM)),
    ('3', lambda ctx: _buy_item(ctx, _SADDLE_ITEM_NUM)),
    ('4', lambda ctx: _buy_item(ctx, _HORSE_ARMOR_ITEM_NUM)),
    ('5', lambda ctx: _buy_ration(ctx, _SUGAR_CUBE_RATION_NUM)),
    ('6', _train_horse),
    ('7', _tips),
]


async def main(ctx: GameContext, bar=None) -> None:
    from presence import enter_area, leave_area, broadcast_open_room

    player = ctx.player
    await ctx.send([
        'You stand inside a dimly lit stable.  A fat little man peers at you',
        'over grimey lenses, perched on an enormous mustache.',
        f'"Welcome to {_NPC}\'s Stable!"',
    ])
    await broadcast_open_room(ctx, f'{player.name} wanders into the stable.')

    await enter_area(ctx, 'JakesStable')
    try:
        await _stable_session(ctx)
    finally:
        await leave_area(ctx, 'JakesStable')


async def _stable_session(ctx: GameContext) -> None:
    while True:
        await ctx.send([
            '',
            '"What kin ey git fer ye?"',
            ' 1) Oats         5) Sugar Cube',
            ' 2) Lasso        6) Train Horse',
            ' 3) Saddle       7) Tips',
            ' 4) Horse Armor',
            '',
        ])
        raw = await ctx.prompt(f'{_NPC}: "->"')
        if not raw or not raw.strip() or raw.strip().upper() == 'Q':
            return

        match = next((fn for key, fn in _MENU if key == raw.strip()), None)
        if match is None:
            await ctx.send("'Beg yer pardin?'")
            continue
        await match(ctx)
