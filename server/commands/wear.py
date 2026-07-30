"""commands/wear.py — WEAR: equip armor, or toggle the ring of invisibility.

Mirrors SPUR.SUB.S's `wear` label, plus the ring toggle -- moved here from
USE (SPUR.USE.S's `use4`, item #67) per Ryan's explicit call: SPUR itself
toggles the ring via USE, not WEAR, but "wear a ring" reads better than
"use a ring" for this port, so WEAR is the ring's only toggle command here.

Supported items:
  armor (objects.json type == 'armor', excluding #113/#115 below) —
    adds a rating (price * 10, same price-as-rating-proxy convention
    combat/... USE's shield section uses) to player.armor, capped by
    class/race (SPUR.SUB.S:33-35): Pixie/Hobbit/Gnome 50%, Assassin/Elf
    60%, everyone else 100%. Item is consumed.
  battle armor (#113) — flat 125% armor rating, consumed.
  power armor (#115) — flat 150% armor rating, consumed. SPUR's "protects
    from nuclear back-blast this session" flavor line is kept, but the
    back-blast event itself isn't built in this port yet -- flavor only.
  ring of invisibility (#67) — toggles PlayerFlags.RING_WORN (same flag
    encounters/little_girl.py and commands/stats.py already read). On:
    "hard to see" + an immediate one-time Constitution -2 (floor 5) -- see
    survival.py's survival_tick() for the ongoing per-move drain while
    worn, and encounters/ringwraith.py for the Ringwraith tie-in.

Not ported (SPUR.SUB.S x=68 "gauntlets"/SPUR.COMBAT.S's `gauntlet`
label): a separate hit-absorption mechanic entirely (the gauntlets block
one combat hit per fight, then can be destroyed on a bad roll) -- no
combat/engine.py hook for it exists yet, out of scope here.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from item_system import ItemType
from network_context import GameContext

_RING_ID         = 67   # ring of invisibility (objects.json)
_BATTLE_ARMOR_ID = 113  # battle armor (objects.json) -- flat 125%
_POWER_ARMOR_ID  = 115  # power armor (objects.json) -- flat 150%

# SPUR.SUB.S:33-34 -- max armor rating by class/race.
_CAP_MID_RACE  = {'Pixie', 'Hobbit', 'Gnome'}   # 50%
_CAP_HIGH_CR   = {'Assassin', 'Elf'}            # 60% (class or race)


def _armor_cap(player) -> int:
    cls  = str(getattr(player, 'char_class', '') or '')
    race = str(getattr(player, 'char_race',  '') or '')
    if race in _CAP_MID_RACE:
        return 50
    if cls in _CAP_HIGH_CR or race in _CAP_HIGH_CR:
        return 60
    return 100


def _wearable_entries(player):
    """Armor-type items, plus the ring -- everything WEAR actually handles."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    out = []
    for e in inv.entries():
        item    = e.item
        item_no = getattr(item, 'number', None) or getattr(item, 'id_number', None)
        if getattr(item, 'type', None) == ItemType.ARMOR or item_no in (_RING_ID,):
            out.append(e)
    return out


class WearCommand(Command):
    name    = 'wear'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Wear a piece of armor, or toggle the ring of invisibility.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('wear',        'List wearable items and choose one'),
            ('wear <name>', 'Wear the item matching name'),
        ],
        examples = [
            ('wear',            'Pick from item list'),
            ('wear plate armor', 'Wear plate armor'),
            ('wear ring',        'Toggle the ring of invisibility'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player

        entries = _wearable_entries(player)
        if not entries:
            await ctx.send('You have nothing to wear.')
            return CommandResult.ok()

        if args:
            pattern = ' '.join(args).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying anything matching "{" ".join(args)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['', 'Items:']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Wear which item (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                idx = int(raw.strip()) - 1
                if not (0 <= idx < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send("You don't have that item.")
                return CommandResult.ok()
            entry = entries[idx]

        item    = entry.item
        item_no = getattr(item, 'number', None) or getattr(item, 'id_number', None)
        name    = getattr(item, 'name', 'it')

        # ---- Ring of invisibility (#67): toggle worn (SPUR.USE.S use4, ------
        # moved to WEAR -- see module docstring) --------------------------
        if item_no == _RING_ID:
            worn = player.query_flag(PlayerFlags.RING_WORN)
            if not worn:
                player.set_flag(PlayerFlags.RING_WORN)
                player.unsaved_changes = True
                lines = ['Ring worn!  You are hard to see!']
                if not player.is_expert:
                    lines.append('(WEAR again to remove)')
                lines.append('THE EVIL SENSES YOU MORE CLEARLY!')
                stats = getattr(player, 'stats', None) or {}
                pt = int(stats.get('Constitution', 10))
                if pt > 5:
                    stats['Constitution'] = pt - 2
                    player.stats = stats
                    lines.append('(You feel a bit less healthy!)')
                await ctx.send(lines)
            else:
                player.clear_flag(PlayerFlags.RING_WORN)
                player.unsaved_changes = True
                await ctx.send('Ring returned to your pack.')
            return CommandResult.ok()

        inv = getattr(player, 'inventory', None)

        # ---- Battle armor (#113) / Power armor (#115): flat ratings -------
        if item_no == _BATTLE_ARMOR_ID:
            player.armor = 125
            player.unsaved_changes = True
            if inv:
                inv.remove(item)
            await ctx.send('BATTLE ARMOR WORN.')
            await ctx.send('New armor rating=125%')
            return CommandResult.ok()

        if item_no == _POWER_ARMOR_ID:
            player.armor = 150
            player.unsaved_changes = True
            if inv:
                inv.remove(item)
            await ctx.send('POWER ARMOR ENERGIZED!')
            await ctx.send('Protects from nuclear back-blast for this play session!')
            await ctx.send('New armor rating=150%')
            return CommandResult.ok()

        # ---- Generic armor (SPUR.SUB.S "wear") -----------------------------
        if getattr(item, 'type', None) != ItemType.ARMOR:
            await ctx.send('This is not armor!')
            return CommandResult.ok()

        cap        = _armor_cap(player)
        current    = int(getattr(player, 'armor', 0) or 0)
        if current >= cap:
            await ctx.send(f'(Max armor rating for you is {cap}%)')
            return CommandResult.ok()

        rating_add = (getattr(item, 'price', 0) or 0) * 10
        new_armor  = min(cap, current + rating_add)
        player.armor = new_armor
        player.unsaved_changes = True
        if inv:
            inv.remove(item)
        await ctx.send(f'(New armor rating: {new_armor}%)')
        await ctx.send(f'{name} worn.')
        return CommandResult.ok()
