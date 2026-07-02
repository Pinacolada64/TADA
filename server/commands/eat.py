"""commands/eat.py — Eat a food item from inventory."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from survival import apply_disease, cure_disease, ration_restore, restore_food

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
        uname  = name.upper()

        from ally_events import try_hungry_ally
        if await try_hungry_ally(ctx, item, 'HUNGRY'):
            return CommandResult.ok()

        inv = getattr(player, 'inventory', None)
        if inv is not None:
            inv.remove(item)

        # Monster meat — restores food; diseased monster's meat has 30% chance to infect
        # (SPUR.MISC3.S:369 fd=69 fd$=m$+" MEAT"; mon.des disease check).
        if uname.endswith(' MEAT'):
            if getattr(item, 'diseased_meat', False) and random.randint(1, 10) < 3:
                apply_disease(player)
                await ctx.send([f'You eat the {name}.', 'YUK!  YOU PICKED UP A DISEASE FROM THE THING!'])
            else:
                restore_food(player, random.randint(2, 6))
                await ctx.send(f'You eat the {name}.  (Tastes like chicken.)')
            return CommandResult.ok()

        # OLD HAMBURGER — causes disease (SPUR.SUB.S old subroutine).
        if 'OLD ' in uname:
            apply_disease(player)
            await ctx.send([f'You eat the {name}.', 'GROSS! Now you are diseased!!'])
            return CommandResult.ok()

        # BLUE PILL — cures disease (SPUR.SUB.S pill subroutine).
        if 'PILL' in uname:
            cure_disease(player)
            await ctx.send([f'You eat the {name}.', 'Yech, gross!',
                            'Disease - gone!' if not getattr(player, 'diseased', True)
                            else '(You were not diseased.)'])
            return CommandResult.ok()

        gs     = ration_restore(item)
        amount = (random.randint(0, gs) % 8) + 1
        restore_food(player, amount)
        new_food = getattr(player, 'food', _FOOD_MAX)

        if new_food >= 15:
            await ctx.send([f'You eat the {name}.', 'Your appetite is satisfied.'])
        else:
            await ctx.send([f'You eat the {name}.', 'Your hunger lessens.'])

        return CommandResult.ok()
