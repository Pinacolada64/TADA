"""commands/drop.py — Drop an item from inventory into the current room.

Water-room handling (SPUR room flag |@@):
  Items dropped in water either float or sink based on inferred buoyancy.
  Sinking items are lost (not placed in room_items).
  Floating items are placed in room_items as usual with a different message.

  The water flag is detected via room.flags ('water' entry), with a keyword
  fallback on room name/desc for maps whose JSON pre-dates flag parsing.

  Well rooms (names containing 'WELL') behave differently: everything dropped
  into a well sinks regardless — it's a vertical shaft, not a lake surface.

Sugar Cube handling (SPUR.MISC.S "d.sugar"):
  Dropping the Sugar Cube ration is a separate special case, handled by
  wild_horse_events.try_sugar_cube_drop() -- see that module for the
  'grassy'-room / wild-horse mechanic.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import InventoryEntry
from network_context import GameContext

# Keywords that indicate a water room in name/desc (fallback when flags absent).
# Primary detection is room.flags containing 'water'.
_WATER_NAME_KEYWORDS = (
    'LAKE', 'RIVER', 'OCEAN', 'SEA', 'STREAM', 'RAPIDS', 'POOL',
    'SWAMP', 'MOAT', 'FLOOD', 'WATERFALL',
)

# Item name keywords that imply the item is heavy enough to sink.
# Checked against the uppercased item name; anything not matching floats.
_SINK_KEYWORDS = (
    'SHIELD', 'ARMOR', 'ARMOUR', 'CHAIN MAIL', 'PLATE', 'GAUNTLET',
    'IRON', 'STEEL', 'CANNON', 'GRENADE',
    'GUN', 'PISTOL', 'RIFLE', 'MUSKET',
    'BULLET', 'STONE', 'COIN', 'GOLD',
    'ANCHOR',
)

# Weapon-name fragments that suggest wooden construction (floats despite WEAPON category).
_WOOD_WEAPON_KEYWORDS = ('BOW', 'STAFF', 'WOOD', 'CROSSBOW')

# "CUBE OF SUGAR" (rations.json) -- matches street/jakes.py's
# _SUGAR_CUBE_RATION_NUM. Dropping it is handled by wild_horse_events.py
# (SPUR.MISC.S "d.sugar") instead of the normal room-item placement below.
_SUGAR_CUBE_RATION_NUM = 16


def _is_sugar_cube(item) -> bool:
    from items import Rations
    return isinstance(item, Rations) and getattr(item, 'number', None) == _SUGAR_CUBE_RATION_NUM


def _is_water_room(room) -> bool:
    """Return True if *room* is a water room (requires boat to enter, blocks flee)."""
    flags = getattr(room, 'flags', None) or []
    if 'water' in flags:
        return True
    name = (getattr(room, 'name', '') or '').upper()
    desc = (getattr(room, 'desc', '') or '').upper()
    # 'WELL' rooms are handled separately — they're shafts, not open water
    return any(kw in name or kw in desc for kw in _WATER_NAME_KEYWORDS)


def _is_well_room(room) -> bool:
    """Well rooms are a special case: a vertical shaft, everything sinks."""
    name = (getattr(room, 'name', '') or '').upper()
    return 'WELL' in name


def _item_sinks(item) -> bool:
    """Infer whether *item* sinks in water (True) or floats (False).

    Without a per-item 'buoyant' flag in the data yet, this is purely
    name/category heuristics.  The bias is toward floating so players
    can recover most dropped items; only clearly-heavy things sink.
    """
    from items import ItemCategory
    cat  = str(getattr(item, 'category', '') or '').upper()
    name = (getattr(item, 'name', '') or '').upper()

    # Weapons: wooden types float, metal types sink
    if 'WEAPON' in cat:
        if any(kw in name for kw in _WOOD_WEAPON_KEYWORDS):
            return False
        return True

    # Named heavy materials / objects
    if any(kw in name for kw in _SINK_KEYWORDS):
        return True

    # Ammo: arrows and darts float (wood/feathers), bullets and stones sink
    if any(kw in name for kw in ('BULLET', 'STONE', 'ROUND')):
        return True
    if any(kw in name for kw in ('ARROW', 'DART', 'BOLT')):
        return False

    # Everything else (food, books, cloth, potions, compasses, torches…) floats
    return False


def _water_drop_messages(item, room) -> tuple[list[str], bool]:
    """Return (message_lines, item_is_lost) for dropping *item* in water."""
    name = getattr(item, 'name', 'it')

    if _is_well_room(room):
        return [
            f'You drop the {name} into the well..',
            'A distant splash echoes from below.',
            f'The {name} is gone.',
        ], True

    if _item_sinks(item):
        return [
            f'The {name} hits the water and sinks immediately!',
        ], True

    return [f'The {name} floats on the surface.'], False


class DropCommand(Command):
    name    = 'drop'
    aliases = ['discard']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Drop an item from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('drop',         'List inventory and choose an item to drop'),
            ('drop <name>',  'Drop item matching name (partial match)'),
        ],
        examples = [
            ('drop',         'Show inventory and pick what to drop'),
            ('drop guide',   'Drop the Adventurer\'s Guide'),
            ('drop sword',   'Drop anything with "sword" in the name'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        if inventory is None:
            await ctx.send('You are carrying nothing.')
            return CommandResult.ok()

        entries = inventory.entries()
        if not entries:
            await ctx.send('You are carrying nothing.')
            return CommandResult.ok()

        # Name/pattern given — find matching entries
        if args:
            pattern = ' '.join(args).lower()
            matches = [(i, e) for i, e in enumerate(entries)
                       if pattern in getattr(e.item, 'name', '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying anything matching "{" ".join(args)}".')
                return CommandResult.ok()
            if len(matches) == 1:
                choice = matches[0][0]
            else:
                # Ambiguous — show the matches and ask
                lines = ['Which one?', '']
                for i, (orig_idx, e) in enumerate(matches, 1):
                    name = getattr(e.item, 'name', '?')
                    qty  = f' x{e.quantity}' if e.quantity > 1 else ''
                    lines.append(f'  {i:>2}. {name}{qty}')
                lines.append('')
                await ctx.send(lines)
                raw = await ctx.prompt(f'Drop which (1-{len(matches)}, or Enter to cancel)')
                if not raw or not raw.strip():
                    return CommandResult.ok()
                try:
                    pick = int(raw.strip()) - 1
                    if not (0 <= pick < len(matches)):
                        raise ValueError
                except ValueError:
                    await ctx.send('Invalid selection.')
                    return CommandResult.ok()
                choice = matches[pick][0]

        else:
            # No args — show full inventory and prompt
            lines = ['You are carrying:', '']
            for i, entry in enumerate(entries, 1):
                name = getattr(entry.item, 'name', '?')
                qty  = f' x{entry.quantity}' if entry.quantity > 1 else ''
                lines.append(f'  {i:>2}. {name}{qty}')
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt(f'Drop which item (1-{len(entries)}, or Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                choice = int(raw.strip()) - 1
            except ValueError:
                await ctx.send('Invalid selection.')
                return CommandResult.ok()

        if not (0 <= choice < len(entries)):
            await ctx.send(f'You are not carrying item {choice + 1}.')
            return CommandResult.ok()

        entry = entries[choice]
        name  = getattr(entry.item, 'name', '?')

        inventory.remove(entry.item)

        # Check for water room
        room_no  = int(getattr(ctx.client, 'room', 0) or 0)
        level    = int(getattr(ctx.player, 'map_level', 1) or 1)
        game_map = getattr(ctx.server, 'game_map', None)
        room     = game_map.get_room(level, room_no) if game_map and room_no else None

        if _is_sugar_cube(entry.item):
            from wild_horse_events import try_sugar_cube_drop
            await try_sugar_cube_drop(ctx, room)
            return CommandResult.ok()

        if room and (_is_water_room(room) or _is_well_room(room)):
            msgs, lost = _water_drop_messages(entry.item, room)
            for msg in msgs:
                await ctx.send(msg)
            if not lost:
                # Float — place in room so it can be retrieved
                dropped = ctx.server.room_items.setdefault(room_no, [])
                dropped.append(InventoryEntry(
                    item     = entry.item,
                    quantity = entry.quantity,
                    charges  = entry.charges,
                ))
            return CommandResult.ok()

        # Dry room — normal drop
        if room_no:
            dropped = ctx.server.room_items.setdefault(room_no, [])
            dropped.append(InventoryEntry(
                item     = entry.item,
                quantity = entry.quantity,
                charges  = entry.charges,
            ))

        await ctx.send(f'You drop {name}.')
        return CommandResult.ok()
