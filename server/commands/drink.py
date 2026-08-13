"""commands/drink.py — Drink a drink item from inventory."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from survival import apply_poison, cure_poison, full_restore, ration_restore, restore_drink

# Fountain of Youth (SPUR.SUB.S 'fountain' label): level 5, room 105 -- same
# room commands/use.py's Galadriel's Vial fill logic already keys off (see
# _VIAL_FOUNTAIN_LEVEL/_VIAL_FOUNTAIN_ROOM there).
_FOUNTAIN_LEVEL = 5
_FOUNTAIN_ROOM  = 105

# Generic "POOL OF WATER" floor-drink (SPUR.SUB.S 'pool' label): any room
# whose food slot references rations.json #51, not tied to one room.
_POOL_OF_WATER_ID = 51


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

        # ---- Fountain of Youth: room feature, unconditional on args/thirst
        # (SPUR.SUB.S: checked before any drink-item handling at all). -----
        room_no  = getattr(ctx.client, 'room', None)
        level    = int(getattr(player, 'map_level', 1) or 1)
        game_map = getattr(ctx.server, 'game_map', None)

        if level == _FOUNTAIN_LEVEL and int(room_no or 0) == _FOUNTAIN_ROOM:
            await self._drink_fountain(ctx, player)
            return CommandResult.ok()

        # ---- Generic "POOL OF WATER" floor object: auto-quenches thirst
        # only, no full restore (SPUR.SUB.S 'pool' label). -----------------
        room = game_map.get_room(level, int(room_no)) if game_map and room_no else None
        if room is not None and getattr(room, 'food', 0) == _POOL_OF_WATER_ID:
            from config import config
            restore_drink(player, config.survival_max)
            await ctx.send('You kneel and drink your fill..')
            return CommandResult.ok()

        entries = _drink_entries(player)

        if not entries:
            await ctx.send('You have nothing to drink.')
            return CommandResult.ok()

        from config import config
        drink_max = config.survival_max
        drink_now = getattr(player, 'drink', drink_max)
        if drink_now >= drink_max:
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

        # POTION OF SKILL — +4 to-hit with the readied weapon until the
        # player next READYs a weapon (SPUR.SUB.S potion subroutine).
        if 'OF SKILL' in uname:
            weapon = getattr(player, 'readied_weapon', None)
            if weapon is None:
                await ctx.send([f'You drink the {name}.',
                                'You feel more skillful, but you have nothing readied!'])
                return CommandResult.ok()
            wname = getattr(weapon, 'name', '?')
            player.skill_potion_bonus = 4
            await ctx.send([f'You drink the {name}.',
                            f'You feel more skillful with the {wname}',
                            '(+4 skill until READY is executed again)'])
            return CommandResult.ok()

        # CHARM POTION — charms the monster in this room (SPUR.SUB.S "charm").
        if 'CHARM POTION' in uname:
            await ctx.send(f'You drink the {name}.')
            from spells.charm import try_charm_potion
            await try_charm_potion(ctx)
            return CommandResult.ok()

        gs     = ration_restore(item)
        amount = (random.randint(0, gs) % 6) + 1
        restore_drink(player, amount)
        new_drink = getattr(player, 'drink', drink_max)

        await ctx.send(f'You drink the {name}. You feel refreshed.')
        if new_drink > 14:
            await ctx.send('...burp...')

        return CommandResult.ok()

    async def _drink_fountain(self, ctx: GameContext, player) -> None:
        """SPUR.SUB.S 'fountain' label: free full restore (HP, poison,
        disease, and any Ring of Invisibility stat drain -- see
        survival.full_restore()) plus charging the Amulet of Life (#76)
        if carried and not already energized."""
        from items import ItemCategory

        await ctx.send([
            'You kneel at the sparkling fountain and drink deeply.',
            'A wave of vigor washes over you!',
        ])
        full_restore(player)

        from flags import PlayerFlags
        if (player.has_item(category=ItemCategory.ITEM, name='Amulet of Life')
                and not player.query_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED)):
            player.set_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED)
            player.unsaved_changes = True
            await ctx.send('The Amulet of Life glows brightly -- it is now ENERGIZED!')
