"""commands/wear.py — WEAR: equip armor, or toggle the ring of invisibility.

Mirrors SPUR.SUB.S's `wear` label, plus the ring toggle -- moved here from
USE (SPUR.USE.S's `use4`, item #67) per Ryan's explicit call: SPUR itself
toggles the ring via USE, not WEAR, but "wear a ring" reads better than
"use a ring" for this port, so WEAR is the ring's only toggle command here.

Supported items:
  armor (objects.json type == 'armor', excluding #113/#115 below) —
    equips the item (non-consuming, since 2026-08-08's per-item durability
    redesign -- see player.py's equipped_entry()/refresh_equipped_rating()).
    player.armor becomes the item's own condition (0-100, degrades from
    combat hits -- combat/engine.py/combat/duel.py), capped by class/race
    (SPUR.SUB.S:33-35): Pixie/Hobbit/Gnome 50%, Assassin/Elf 60%, everyone
    else 100%. Wearing a different piece swaps it in; the old one stays in
    your pack at whatever condition it was last at. See commands/unwear.py
    to take it back off.
  battle armor (#113) — flat 125% armor rating.
  power armor (#115) — flat 150% armor rating. SPUR's "protects from
    nuclear back-blast this session" flavor line is kept, but the
    back-blast event itself isn't built in this port yet -- flavor only.
    Both special IDs are still non-consuming, but keep their flat rating
    regardless of item.condition -- they're a SPUR flavor exception (the
    only two ratings that exceed the normal 0-100 range), not a normal
    degrade-with-use piece.
  ring of invisibility (#67) — toggles PlayerFlags.RING_WORN (same flag
    encounters/little_girl.py and commands/stats.py already read). On:
    "hard to see" + an immediate one-time Constitution -2 (floor 5) -- see
    survival.py's survival_tick() for the ongoing per-move drain while
    worn, and encounters/ringwraith.py for the Ringwraith tie-in.

Not ported (SPUR.SUB.S x=68 "gauntlets"/SPUR.COMBAT.S's `gauntlet`
label): a separate hit-absorption mechanic entirely (the gauntlets block
one combat hit per fight, then can be destroyed on a bad roll) -- no
combat/engine.py hook for it exists yet, out of scope here.

Every armor-equip path here sets player.active_armor_id to the item's
objects.json number (mirroring active_shield_id, see player.py), so STAT
and the login banner can name the actual piece worn -- and, since
2026-08-08, so player.refresh_equipped_rating('armor') knows which item's
.condition to mirror into player.armor.
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
    from items import ItemCategory
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    out = []
    for e in inv.entries():
        item     = e.item
        item_no  = getattr(item, 'number', None) or getattr(item, 'id_number', None)
        item_cat = getattr(item, 'category', None)
        # id_number is only unique within its own category (weapons/items/
        # rations each number independently -- items.py:364); without this
        # guard a ration sharing #67 with the ring (DEAD BUG) showed up as
        # wearable and could toggle RING_WORN.
        is_ring = item_cat == ItemCategory.ITEM and item_no == _RING_ID
        if getattr(item, 'type', None) == ItemType.ARMOR or is_ring:
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

        # ---- Battle armor (#113) / Power armor (#115): flat ratings -------
        # Non-consuming like generic armor below, but exempt from the
        # condition-derived rating -- these are a fixed SPUR flavor bonus
        # (125%/150%, both above the normal 0-100 range), not a piece that
        # degrades with use.
        if item_no == _BATTLE_ARMOR_ID:
            player.armor = 125
            player.active_armor_id = item_no
            player.unsaved_changes = True
            await ctx.send('BATTLE ARMOR WORN.')
            await ctx.send('New armor rating=125%')
            return CommandResult.ok()

        if item_no == _POWER_ARMOR_ID:
            player.armor = 150
            player.active_armor_id = item_no
            player.unsaved_changes = True
            await ctx.send('POWER ARMOR ENERGIZED!')
            await ctx.send('Protects from nuclear back-blast for this play session!')
            await ctx.send('New armor rating=150%')
            return CommandResult.ok()

        # ---- Generic armor (SPUR.SUB.S "wear") -----------------------------
        if getattr(item, 'type', None) != ItemType.ARMOR:
            await ctx.send('This is not armor!')
            return CommandResult.ok()

        # Equip: non-consuming (2026-08-08 durability redesign). Wearing a
        # different piece just swaps which id is active -- the old one
        # (if any) stays in the pack at whatever condition it was at.
        from player import refresh_equipped_rating
        player.active_armor_id = item_no
        new_armor = refresh_equipped_rating(player, 'armor')
        player.unsaved_changes = True
        await ctx.send(f'(New armor rating: {new_armor}%)')
        await ctx.send(f'{name} worn.')
        return CommandResult.ok()
