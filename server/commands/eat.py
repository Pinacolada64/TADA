"""commands/eat.py — Eat a food item from inventory."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from survival import ration_restore, restore_food

_FOOD_MAX = 20


def _food_entries(player):
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    return [e for e in inv.entries() if getattr(e.item, 'kind', '') == 'food']


class EatCommand(Command):
    name    = 'eat'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Eat a food item from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('eat',         'List carried food and choose one'),
            ('eat <name>',  'Eat the food matching name'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player
        entries = _food_entries(player)

        if not entries:
            await ctx.send('You have no food to eat.')
            return CommandResult.ok()

        food_now = getattr(player, 'food', _FOOD_MAX)
        if food_now >= _FOOD_MAX:
            await ctx.send("You're not hungry.")
            return CommandResult.ok()

        if args:
            pattern = ' '.join(args).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying any food matching "{" ".join(args)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['Food you carry:', '']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Eat which item (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                choice = int(raw.strip()) - 1
                if not (0 <= choice < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid selection.')
                return CommandResult.ok()
            entry = entries[choice]

        item   = entry.item
        name   = getattr(item, 'name', '?')
        gs     = ration_restore(item)
        amount = (random.randint(0, gs) % 8) + 1
        restore_food(player, amount)
        new_food = getattr(player, 'food', _FOOD_MAX)

        inv = getattr(player, 'inventory', None)
        if inv is not None:
            inv.remove(item)

        if new_food >= 15:
            await ctx.send([f'You eat the {name}.', 'Your appetite is satisfied.'])
        else:
            await ctx.send([f'You eat the {name}.', 'Your hunger lessens.'])

        return CommandResult.ok()
