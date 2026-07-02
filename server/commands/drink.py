"""commands/drink.py — Drink a drink item from inventory."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from survival import apply_poison, cure_poison, ration_restore, restore_drink

_DRINK_MAX = 20


def _drink_entries(player):
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    return [e for e in inv.entries() if getattr(e.item, 'kind', '') == 'drink']


class DrinkCommand(Command):
    name    = 'drink'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Drink something from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('drink',         'List carried drinks and choose one'),
            ('drink <name>',  'Drink the item matching name'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player
        entries = _drink_entries(player)

        if not entries:
            await ctx.send('You have nothing to drink.')
            return CommandResult.ok()

        drink_now = getattr(player, 'drink', _DRINK_MAX)
        if drink_now >= _DRINK_MAX:
            await ctx.send("You're not thirsty.")
            return CommandResult.ok()

        if args:
            pattern = ' '.join(args).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying any drink matching "{" ".join(args)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['Drinks you carry:', '']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Drink which item (1-{len(entries)}, Enter to cancel)')
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
        if await try_hungry_ally(ctx, item, 'THIRSTY'):
            return CommandResult.ok()

        inv = getattr(player, 'inventory', None)
        if inv is not None:
            inv.remove(item)

        # GREEN MOONSHINE — causes poison (SPUR.SUB.S moonshin subroutine).
        if 'MOONSHINE' in uname:
            apply_poison(player)
            await ctx.send([f'You drink the {name}.', 'BAD STUFF! Now you are poisoned!'])
            return CommandResult.ok()

        # RED SERUM — cures poison (SPUR.SUB.S serum subroutine).
        if 'SERUM' in uname:
            cure_poison(player)
            await ctx.send([f'You drink the {name}.', 'Yuk, it tastes awful!',
                            'Poison - gone!' if not getattr(player, 'poisoned', True)
                            else '(You were not poisoned.)'])
            return CommandResult.ok()

        gs     = ration_restore(item)
        amount = (random.randint(0, gs) % 6) + 1
        restore_drink(player, amount)
        new_drink = getattr(player, 'drink', _DRINK_MAX)

        await ctx.send(f'You drink the {name}. You feel refreshed.')
        if new_drink > 14:
            await ctx.send('...burp...')

        return CommandResult.ok()
