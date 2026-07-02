"""commands/take.py — Take an item from a party ally.

Mirrors SPUR.MISC.S TAKE: lists what the ally is carrying, player picks
one item to transfer back to their own inventory.

Syntax:
  take                         list all items across all servants
  take from <ally>             list items that specific ally carries
  take <item> from <ally>      take a specific item directly
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from bar.ally_data import AllyStatus
from bar.allies import purchased_allies
from network_context import GameContext


class TakeCommand(Command):
    name    = 'take'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Take an item back from a party ally.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('take',                   'List everything your servants carry'),
            ('take from <ally>',       'List items that ally carries'),
            ('take <item> from <ally>', 'Take a specific item from a named ally'),
        ],
        examples = [
            ('take from batman',       'See what Batman is holding'),
            ('take sword from batman', 'Retrieve the sword from Batman'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        allies = purchased_allies(player)
        active = [a for a in allies if a.status == AllyStatus.SERVANT]

        if not active:
            await ctx.send('You have no servants to take from.')
            return CommandResult.ok()

        # Parse "take <item> from <ally>" or "take from <ally>" or "take"
        arg_list   = list(args)
        item_words = []
        from_words = []
        if 'from' in arg_list:
            fi         = arg_list.index('from')
            item_words = arg_list[:fi]
            from_words = arg_list[fi + 1:]
        else:
            item_words = arg_list

        # Resolve ally subset
        if from_words:
            target = ' '.join(from_words).lower()
            ally_matches = [a for a in active if target in a.name.lower()]
            if not ally_matches:
                await ctx.send(
                    f'No servant named "{" ".join(from_words)}" in your party.')
                return CommandResult.ok()
            selected = ally_matches
        else:
            selected = active

        # Collect (ally, entry) pool
        pool: list[tuple] = []
        for a in selected:
            for e in (getattr(a, 'items', None) or []):
                pool.append((a, e))

        if not pool:
            if from_words:
                await ctx.send(f'{selected[0].name} is not carrying anything.')
            else:
                await ctx.send('Your servants are not carrying anything.')
            return CommandResult.ok()

        # Resolve item
        if item_words:
            pattern = ' '.join(item_words).lower()
            matches = [(a, e) for a, e in pool
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                pat_str = ' '.join(item_words)
                await ctx.send(
                    f'None of your servants are carrying anything matching "{pat_str}".')
                return CommandResult.ok()
            chosen_ally, chosen_entry = matches[0]
        else:
            lines = ['', 'Your servants carry:']
            for i, (a, e) in enumerate(pool, 1):
                iname = getattr(e.item, 'name', '?')
                lines.append(f'  {i:>2}. {iname:<24}  (carried by {a.name})')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Take which item (1-{len(pool)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                idx = int(raw.strip()) - 1
                if not (0 <= idx < len(pool)):
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid selection.')
                return CommandResult.ok()
            chosen_ally, chosen_entry = pool[idx]

        if inventory and inventory.is_full():
            await ctx.send('You cannot carry any more.')
            return CommandResult.ok()

        iname = getattr(chosen_entry.item, 'name', 'it')
        chosen_ally.items.remove(chosen_entry)
        if inventory:
            inventory.add(chosen_entry.item,
                          quantity=getattr(chosen_entry, 'quantity', 1),
                          charges=chosen_entry.charges)
        await ctx.send(f'{chosen_ally.name} hands you the {iname}.')
        return CommandResult.ok()
