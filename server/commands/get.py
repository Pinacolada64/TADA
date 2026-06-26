"""commands/get.py — Pick up an item from the current room."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import InventoryEntry
from items import Item, ItemCategory, Rations, Weapon
from network_context import GameContext


def _room_available_items(ctx: GameContext) -> list[tuple]:
    """Return a list of (display_name, InventoryEntry, remove_fn) for everything
    the player can pick up in the current room.

    remove_fn() is called after the item is successfully added to inventory.
    """
    server  = ctx.server
    room_no = getattr(ctx.client, 'room', None)
    room    = (server.game_map.rooms.get(int(room_no))
               if server.game_map and room_no else None)
    if not room:
        return []

    available = []

    # Static room items from the map (item / weapon / food fields are 1-based indices)
    for attr, collection, category in (
        ('item',   server.items,   ItemCategory.ITEM),
        ('weapon', server.weapons, ItemCategory.WEAPON),
        ('food',   server.rations, ItemCategory.FOOD),
    ):
        idx = int(getattr(room, attr, 0) or 0) - 1
        if 0 <= idx < len(collection):
            raw = collection[idx]
            name = (raw.get('name') if isinstance(raw, dict)
                    else getattr(raw, 'name', None))
            if not name:
                continue
            item_id = (raw.get('id_number', idx + 1) if isinstance(raw, dict)
                       else getattr(raw, 'id_number', idx + 1))

            item = Item(id_number=item_id, name=name, category=category)
            entry = InventoryEntry(item=item)

            captured_room  = room
            captured_attr  = attr
            def _remove(r=captured_room, a=captured_attr):
                setattr(r, a, 0)

            available.append((name, entry, _remove))

    # Items dropped by players this session
    dropped = server.room_items.get(int(room_no) if room_no else -1, [])
    for i, entry in enumerate(dropped):
        name = getattr(entry.item, 'name', '?')
        captured_i = i
        captured_room_no = int(room_no)
        def _remove_dropped(ri=captured_i, rn=captured_room_no):
            lst = server.room_items.get(rn, [])
            if ri < len(lst):
                lst.pop(ri)
        available.append((name, entry, _remove_dropped))

    return available


class GetCommand(Command):
    name    = 'get'
    aliases = ['g', 'take', 'pick']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Pick up an item from the room.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('get',        'List items in the room'),
            ('get <name>', 'Pick up a specific item by name'),
        ],
        examples = [
            ('get',        'Show what is on the ground'),
            ('get sword',  'Pick up the sword'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        available = _room_available_items(ctx)

        if not available:
            await ctx.send('There is nothing here to pick up.')
            return CommandResult.ok()

        # If a name was given, try to match directly
        if args:
            target = ' '.join(args).lower()
            matches = [(name, entry, rm) for name, entry, rm in available
                       if target in name.lower()]
            if not matches:
                await ctx.send(f'You do not see any "{" ".join(args)}" here.')
                return CommandResult.ok()
            if len(matches) == 1:
                return await self._pick_up(ctx, inventory, *matches[0])
            # Multiple matches — fall through to numbered list
            available = matches

        # Show numbered list and prompt
        lines = ['You see:', '']
        for i, (name, entry, _) in enumerate(available, 1):
            lines.append(f'  {i:>2}. {name}')
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt(f'Get which item (1-{len(available)}, or Enter to cancel)')
        if not raw or not raw.strip():
            return CommandResult.ok()

        try:
            choice = int(raw.strip()) - 1
            if not (0 <= choice < len(available)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            return CommandResult.ok()

        return await self._pick_up(ctx, inventory, *available[choice])

    async def _pick_up(self, ctx: GameContext, inventory,
                       name: str, entry: InventoryEntry, remove_fn) -> CommandResult:
        player  = ctx.player
        item_id = getattr(entry.item, 'id_number', None)

        # Anti-hoarding: refuse if player already carries this item
        if item_id and inventory is not None and inventory.find(item_id=item_id):
            await ctx.send(f'You already have {name}.')
            return CommandResult.ok()

        # Capacity check
        if inventory is not None and inventory.is_full():
            await ctx.send('You can carry no more.')
            return CommandResult.ok()

        if inventory is not None:
            inventory.add(entry.item,
                          quantity=getattr(entry, 'quantity', 1),
                          charges=entry.charges)

        remove_fn()
        await ctx.send(f'You pick up {name}.')
        return CommandResult.ok()
