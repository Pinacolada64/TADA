"""commands/drop.py — Drop an item from inventory into the current room."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import InventoryEntry
from network_context import GameContext


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

        # Place in room_items on the server
        room_no = int(getattr(ctx.client, 'room', 0) or 0)
        if room_no:
            dropped = ctx.server.room_items.setdefault(room_no, [])
            dropped.append(InventoryEntry(
                item     = entry.item,
                quantity = entry.quantity,
                charges  = entry.charges,
            ))

        await ctx.send(f'You drop {name}.')
        return CommandResult.ok()
