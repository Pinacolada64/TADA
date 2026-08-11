"""shoppe/ollys.py — Olly's Ammo & Trap Shop (SPUR.MISC5.S ammo/booby sections)."""
import json
import logging
import os

from network_context import GameContext
from presence import try_global_command
from tada_utilities import is_or_are, tip

log = logging.getLogger(__name__)

_BOOBY_TRAP_COST = 1000  # SPUR: if zt=1 it=1000
_BOOBY_CODES     = 'ABCDEFGHI'
# Item numbers in objects.json
_AMMO_RANGE      = range(98, 112)    # 98–111 inclusive
_CARRIER_RANGE   = range(147, 151)   # 147–150 inclusive
_BOOBY_BASE      = 152               # code A = 152, B = 153, …


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
# Ammo listing and purchase
# ---------------------------------------------------------------------------

def _matching_carrier(inv, used_with: str):
    """Find an already-owned carrier (a `capacity`-flagged item, see
    _ammo_section's purchase branch) matching *used_with*, or None."""
    used_with = (used_with or '').strip().lower()
    if not used_with or inv is None:
        return None
    for entry in inv:
        flags = getattr(entry.item, 'flags', None)
        if isinstance(flags, dict) and 'capacity' in flags:
            if (flags.get('used_with') or '').strip().lower() == used_with:
                return entry
    return None


async def _ammo_section(ctx: GameContext, player, inv, objects_by_num: dict) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from inventory import PACK_FULL_MESSAGE
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint
    from table import Align, Column, Table

    ammo_items    = [objects_by_num[n] for n in _AMMO_RANGE    if n in objects_by_num]
    carrier_items = [objects_by_num[n] for n in _CARRIER_RANGE if n in objects_by_num]

    # New in TADA: shop numbering is now the display's own 1..N sequence
    # rather than objects.json's raw item numbers -- easier to shop from
    # than remembering "arrows are #100". index_to_item maps the number the
    # player types back to the underlying object; Ryan's request.
    listing = ammo_items + carrier_items
    index_to_item = {i: it for i, it in enumerate(listing, start=1)}

    try:
        width = ctx.player.client_settings.screen_columns
    except AttributeError:
        width = 78

    # New in TADA: hand-rolled f-string columns (_ammo_line()/_carrier_line())
    # broke alignment on wide names like "Armor Piercing arrows" -- table.py's
    # Table(border=False) computes real column widths and wraps overflow
    # instead of letting it bleed into the next column. Ryan's request.
    # New in TADA: alternate row color (table.py's text_color) makes a long
    # list easier to scan at a glance -- Ryan's request. Used With cells no
    # longer wrap the weapon name in [brackets]: that syntax gets swapped
    # for a highlight color by formatting.highlight_brackets() downstream,
    # and its own reset would cut the row's color short partway through the
    # line; the 'Used With' header already labels the column, so the
    # brackets were redundant anyway (same reasoning that dropped 'rnd'/
    # 'dmg:'/'cap:' from these rows earlier).
    _ROW_COLORS = ['light_blue', 'cyan']

    def _ammo_table() -> Table:
        t = Table(headers=[
            Column('#',         align=Align.RIGHT, min_width=2),
            Column('Name',                          min_width=16),
            Column('Rnds',      align=Align.RIGHT,  min_width=4),
            Column('Dmg',       align=Align.RIGHT,  min_width=3),
            Column('Used With',                     min_width=12),
            Column('Cost',      align=Align.RIGHT,  min_width=4),
        ], border=False, text_color=_ROW_COLORS)
        for i, it in enumerate(ammo_items, start=1):
            flags = it.get('flags', {})
            t.add_row([
                str(i),
                it['name'],
                str(flags.get('rounds', '?')),
                str(flags.get('damage', '?')),
                flags.get('used_with', '').strip(),
                f"{it['price'] * 10:,}s",
            ])
        return t

    def _carrier_table() -> Table:
        t = Table(headers=[
            Column('#',         align=Align.RIGHT,  min_width=2),
            Column('Name',                          min_width=16),
            Column('Capacity',  align=Align.RIGHT,  min_width=8),
            Column('Used With',                     min_width=12),
            Column('Cost',      align=Align.RIGHT,  min_width=4),
        ], border=False, text_color=_ROW_COLORS)
        for j, it in enumerate(carrier_items, start=len(ammo_items) + 1):
            flags = it.get('flags', {})
            t.add_row([
                str(j),
                it['name'],
                str(flags.get('rounds', '?')),
                flags.get('used_with', '').strip(),
                f"{it['price'] * 10:,}s",
            ])
        return t

    while True:
        lines = [
            '',
            '<=-=-=-=-=-=-=-=[[OLLY]]=-=-=-=-=-=-=-=>',
            '',
        ]
        lines += _ammo_table().render(width=width)
        lines += ['', '  [[ Ammo Carriers ]]', '']
        lines += _carrier_table().render(width=width)
        lines += ['', f'Enter item number, ? to re-list{shop_menu_hint(player)}, or Q to leave.', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Your Choice')
        if raw is None:
            return
        choice = raw.strip().upper()
        if not choice or choice == 'Q':
            return
        if choice == '?':
            continue
        if choice in ('I', 'T') and await handle_shop_key(ctx, choice):
            # New in TADA: it's easy to lose track of what you're already
            # carrying (or want to offload to a mount) while browsing this
            # list -- let [I]/[T] work without leaving the shop. Ryan's
            # request. (Was a bare 'inventory' global-command dispatch;
            # upgraded to the shared pack-management tool so [T]ransfer
            # works here too, not just a read-only listing.)
            continue

        try:
            num = int(choice)
        except ValueError:
            if await try_global_command(ctx, raw):
                continue
            await ctx.send('Enter a number, ? to list, I)nventory, or Q to leave.')
            continue

        it = index_to_item.get(num)
        if it is None:
            await ctx.send(f'Enter 1-{len(listing)}, or Q.')
            continue

        is_carrier = it in carrier_items
        flags      = it.get('flags') or {}
        used_with  = (flags.get('used_with') or '').strip()
        existing_carrier = _matching_carrier(inv, used_with)

        # New in TADA: implements Olly's own listing text ("Appropriate
        # ammo will automatically be placed in the carrier when it is
        # purchased. Buying more than one will do no good.") -- previously
        # just flavor text with no code behind it.
        if is_carrier and existing_carrier is not None:
            await ctx.send(
                f'You already have a {existing_carrier.item.name} for that '
                '-- buying another would do no good.'
            )
            continue

        # Raw ammo matching a carrier already owned tops the carrier off
        # instead of taking its own pack slot.
        loads_into_carrier = (not is_carrier) and existing_carrier is not None
        if loads_into_carrier:
            carrier_flags = existing_carrier.item.flags
            capacity      = int(carrier_flags.get('capacity', 0))
            if int(carrier_flags.get('rounds', 0)) >= capacity:
                await ctx.send(f'Your {existing_carrier.item.name} is already full.')
                continue

        if not loads_into_carrier and inv is not None and inv.is_full():
            await ctx.send('You have no room in your pack!')
            continue

        cost = it['price'] * 10
        name = it['name']

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < cost:
            await ctx.send('You do not have enough gold.')
            continue

        await ctx.send(f"You choose {name} for {cost} gold?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        if loads_into_carrier:
            carrier_flags = existing_carrier.item.flags
            capacity      = int(carrier_flags.get('capacity', 0))
            carrier_flags['rounds'] = min(
                capacity, int(carrier_flags.get('rounds', 0)) + int(flags.get('rounds', 0))
            )
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
            player.unsaved_changes = True
            await ctx.send(
                f"Done! The {name} {is_or_are(name)} loaded straight into your "
                f"{existing_carrier.item.name}. "
                f"({carrier_flags['rounds']}/{capacity} rounds)"
            )
            continue

        item_flags = dict(flags)
        if is_carrier:
            # 'capacity' marks this item as a reusable carrier (arrives
            # full, refilled by matching ammo purchases, never consumed by
            # USE) rather than a single-use ammo box -- see commands/use.py's
            # _apply_item.
            item_flags['capacity'] = item_flags.get('rounds', 0)

        item = Item(
            id_number = it['number'],
            name      = name,
            category  = ItemCategory.ITEM,
            # rounds/damage/used_with (ammo) travels with the purchased
            # item so commands/use.py can actually load it later -- dropping
            # this left every shop-bought round of ammo permanently unusable
            # (see commands/use.py's _apply_item docstring).
            flags     = item_flags,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
        player.unsaved_changes = True
        await ctx.send('Done!')

        if is_carrier:
            await ctx.send(
                f'(The {name} comes loaded with {item_flags["rounds"]} rounds '
                'already -- ready to fire right away. You can buy more ammo '
                f'for it separately later to top it back off; a second {name} '
                'would just sit empty, so one per weapon is all you need.)'
            )


# ---------------------------------------------------------------------------
# Booby trap purchase
# ---------------------------------------------------------------------------

async def _booby_section(ctx: GameContext, player, inv, objects_by_num: dict) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Item, ItemCategory
    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint
    from inventory import PACK_FULL_MESSAGE

    await ctx.send([
        '',
        'You go to the Booby Trap display...',
        '"Ahh, note this selection of the finest traps!" beams Olly..',
        '"For you, only 1000 gold a piece!  Each with its secret disarm code!',
        ' Bury one of these babies with the DIG command and it will discourage',
        ' people from digging up your gold!"',
        '',
    ])

    while True:
        await ctx.send(f'Cost=1000.  Purchase Booby Trap.')
        raw = await ctx.prompt(f'Disarm code [{_BOOBY_CODES}] or Q to leave{shop_menu_hint(player)}')
        if raw is None:
            return
        stripped = raw.strip()
        choice = stripped.upper()[:1]
        if not choice or choice == 'Q':
            await ctx.send('You leave the booby trap display.')
            return
        if choice in ('I', 'T') and await handle_shop_key(ctx, choice):
            continue

        # A disarm code is always a single letter -- multi-character input
        # (e.g. 'help', 'help combination') can't be one, so try it as a
        # global command *before* truncating down to its first letter
        # below. Without this length check, 'help' would truncate to 'H'
        # -- itself a valid disarm code (_BOOBY_CODES spans A-I) -- and
        # get silently swallowed as if the player had picked code H.
        if len(stripped) > 1 and await try_global_command(ctx, raw):
            continue

        if choice not in _BOOBY_CODES:
            await ctx.send("Olly pretends not to notice you fumbling at the keyboard.")
            continue

        if inv is not None and inv.is_full():
            await ctx.send('You have no room in your pack!')
            return

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < _BOOBY_TRAP_COST:
            await ctx.send('You do not have enough gold.')
            continue

        num  = _BOOBY_BASE + _BOOBY_CODES.index(choice)
        it   = objects_by_num.get(num, {})
        name = it.get('name', f'booby trap (code {choice})')

        await ctx.send(f"You choose {name} for {_BOOBY_TRAP_COST} gold?")
        raw = await ctx.prompt('Confirm (Y/N)')
        if raw is None or raw.strip().upper() != 'Y':
            continue

        item = Item(
            id_number = num,
            name      = name,
            category  = ItemCategory.ITEM,
        )
        if inv is None or not inv.add(item):
            await ctx.send(PACK_FULL_MESSAGE)
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, _BOOBY_TRAP_COST)
        player.unsaved_changes = True
        await ctx.send('Done!')


# ---------------------------------------------------------------------------
# Help section
# ---------------------------------------------------------------------------

async def _help_section(ctx: GameContext) -> None:
    """Show the ammo/booby-trap help text.

    Booby-trap disarm codes (A-I) aren't stored separately anywhere -- each
    code is baked into which of the nine "booby trap (code X)" items
    (objects.json #152-160) the player bought, so the code travels with the
    item itself.

    DIG/bury are not implemented yet. SPUR's own data model (SPUR.MISC7.S
    dig.a / bury.add / wr.bury) is one "bury.<level>" file per dungeon level
    (1-5 only -- DIG refuses on level 6+), one record per room, with five
    slots per room (North, South, East, West, Center) each holding whatever
    is buried there (a gold amount or an item number) -- and, notably,
    *no* record of who buried it: anyone who digs in the right spot finds
    it, whoever they are.

    Deliberate TADA deviations planned for whenever DIG/BURY get built (none
    of this exists yet -- noted here so the eventual implementation builds
    it in from the start rather than bolting it on after):
      - Record the burying player alongside each slot (extending the record
        with an owner id/name) -- SPUR itself does not.
      - Give Olly a paid "recall" service -- he goes quiet for a moment as
        if lost in thought, then lists everywhere *you've* buried something
        (level, room, position, and its disarm code) in case you forget.
      - Give Thieves a chance to disarm someone else's booby trap outright
        (no code needed) when digging one up, playing to the class's
        stealth/lock-picking flavor (`base_classes.py`'s THIEF description).
        Not found in the SPUR source reviewed so far (`SPUR.MISC7.S`'s
        `disarm.a`/`disarm.b` timing-based key-press challenge applies to
        every class alike) -- this would be a new TADA class perk, not a
        restoration of existing SPUR behavior. Flagging the uncertainty
        rather than assuming; worth confirming against source before
        committing to the mechanic.
    """
    from formatting import underline

    await ctx.send([
        '',
        "<=-=-=-=-=-=-=[ Ammunition Guide ]=-=-=-=-=-=-=>",
        '',
        *underline('How Ammo Works', ctx),
        'Projectile and energy weapons require ammunition to fire. '
        'Purchase ammo here, then [USE] the ammo item to load it into '
        'your readied weapon.  Rounds are consumed one-per-shot in '
        'combat.  When you run out you cannot [ATTACK] until you reload.',
        '',
        'Storm weapons do not use physical ammo.',
        '',
        *underline('Ammo Carriers', ctx),
        'A carrier (cartridge box, bandolier, shell caisson) is a '
        'reusable alternative to buying loose ammo boxes.  It arrives '
        'full and [USE]s just like a box of ammo, but it stays in your '
        'pack afterward instead of being used up -- buy matching ammo '
        'here again later to top it back off.  You only need one per '
        'weapon; a second sits empty and does nothing.',
        '',
        *underline('Stray Rounds / Friendly Fire', ctx),
        'A missed ammo shot may go wide and hit a party member or '
        'another player in the same room.  The chance depends on your '
        'experience with that weapon:',
        '',
        '  |green|Green|reset|   (  0-39 exp)  1-in-3  chance of a stray round',
        '  |yellow|Veteran|reset| ( 40-98 exp)  1-in-6  chance of a stray round',
        '  |cyan|Elite|reset|   (99+    exp)  1-in-10 chance of a stray round',
        '',
        'Stray rounds deal 1-4 damage.  Train your weapon skill to '
        'reduce the risk to your allies.',
        '',
        *underline('Booby Traps', ctx),
        'Each trap you buy comes with its own disarm code (A-I) fixed '
        "at purchase -- pick carefully, it can't be changed later.",
        '',
        *tip(ctx,
             title='Note:',
             message="The DIG command needed to bury a trap (or anything "
                     'else) is not implemented yet -- buying one here is all you '
                     'can currently do with it. Once [DIG] exists, Olly is planned '
                     'to offer a paid memory-jogging service if you forget where '
                     'you buried something (or which code it needs).'),
    ])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Olly's Ammo & Trap Shop. (SPUR.MISC5.S ammo/booby sections)"""
    player = ctx.player
    inv    = getattr(player, 'inventory', None)

    all_objects  = _load_objects()
    objects_by_num = {o['number']: o for o in all_objects}

    await ctx.send(
        f"Olly greets you, 'Welcome, {player.name}!! Choose from this "
        "fine list of ammunition and stuff.'"
    )

    from shoppe.inventory_tools import handle_shop_key, shop_menu_hint

    while True:
        raw = await ctx.prompt(f'[A]mmo, [B]ooby traps, [H]elp, or Q to leave{shop_menu_hint(player)}')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return
        if cmd == 'A':
            await _ammo_section(ctx, player, inv, objects_by_num)
        elif cmd == 'B':
            await _booby_section(ctx, player, inv, objects_by_num)
        elif cmd == 'H':
            await _help_section(ctx)
        elif cmd in ('I', 'T') and await handle_shop_key(ctx, cmd):
            pass
        elif await try_global_command(ctx, raw):
            pass
        else:
            await ctx.send('A)mmo, B)ooby traps, H)elp, or Q to leave.')
