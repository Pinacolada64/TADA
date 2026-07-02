"""commands/use.py — USE: activate or apply an item from inventory.

Mirrors SPUR.USE.S. Supported item types:
  compass    — toggle compass on/off (session state)
  shield     — add to shield rating; class/race caps apply; item consumed
  ammunition — load rounds into readied weapon; item consumed
  power      — same as ammunition (energy-weapon charges)
  book       — redirect to READ
  (other)    — "You play with the <name>.."

Not yet implemented (deferred):
  grenade / rocket — single-use combat items; need active-combat context
  ring of invisibility — needs ring-worn state and alignment penalty
  security cards — level-6 items
  spacesuit assembly, communicator repair — level-6 crafting
  slippers of Galad / crystal vial / palintar — special room items
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import Item, ItemType
from items import ItemCategory
from network_context import GameContext

# SPUR.USE.S: max shield % by class/race (sh cap).
# cap_bonus is added for BATTLE SHIELD and LAZER SHIELD (a=20 in SPUR).
_CAP_LOW_CLASS  = {'Wizard'}               # 25 + bonus
_CAP_MID_CLASS  = {'Thief', 'Assassin'}    # 35 + bonus
_CAP_MID_RACE   = {'Pixie'}               # 35 + bonus
_CAP_HIGH_RACE  = {'Hobbit', 'Gnome'}     # 50 + bonus


def _shield_cap(player, cap_bonus: int) -> int:
    """Max shield rating for this player (SPUR.USE.S shield section)."""
    cls  = str(getattr(player, 'char_class', '') or '')
    race = str(getattr(player, 'char_race',  '') or '')
    if cls in _CAP_LOW_CLASS:
        return 25 + cap_bonus
    if cls in _CAP_MID_CLASS or race in _CAP_MID_RACE:
        return 35 + cap_bonus
    if race in _CAP_HIGH_RACE:
        return 50 + cap_bonus
    return 100 + cap_bonus


def _apply_item(item: Item, player) -> list[str]:
    """Apply item effect to player; return message lines. Removes item from inventory on use."""
    inv   = getattr(player, 'inventory', None)
    itype = item.type
    name  = item.name

    # ---- Compass -----------------------------------------------------------
    if itype == ItemType.COMPASS:
        active = not getattr(player, 'compass_active', False)
        player.compass_active = active
        if active:
            return ['Compass used.', '(USE again to return to pack)']
        return ['Compass placed in pack.']

    # ---- Shield ------------------------------------------------------------
    if itype == ItemType.SHIELD:
        name_upper = name.upper()
        cap_bonus  = 20 if ('BATTLE' in name_upper or 'LAZER' in name_upper) else 0
        rating_add = item.price * 10 or 20   # proxy: price maps to ~20-80% rating
        cap        = _shield_cap(player, cap_bonus)
        current    = int(getattr(player, 'shield', 0) or 0)
        if current >= cap:
            return [f'(Max shield rating for you is {cap}%)']
        new_shield     = min(cap, current + rating_add)
        player.shield  = new_shield
        player.unsaved_changes = True
        if inv:
            inv.remove(item)
        msgs = []
        if 'BATTLE' in name_upper:
            msgs.append('THE BATTLE SHIELD GLOWS!')
        msgs.append(f'(New shield rating: {new_shield}%)')
        msgs.append(f'{name} used.')
        return msgs

    # ---- Ammo / power pak --------------------------------------------------
    if item.is_ammo_carrier:
        weapon = getattr(player, 'readied_weapon', None)
        if weapon is None:
            return ['YOU MUST READY YOUR WEAPON FIRST!']
        wname_upper = (getattr(weapon, 'name', '') or '').upper()
        if 'STORM' in wname_upper:
            return [f'THE {wname_upper} DOES NOT USE PHYSICAL AMMO!']
        used_with = ((item.flags or {}).get('used_with') or '').strip().upper()
        if used_with and used_with not in wname_upper:
            return [f'THIS AMMO IS NOT FOR THE {wname_upper}!']
        rounds = int((item.flags or {}).get('rounds', 0))
        damage = int((item.flags or {}).get('damage', 0))
        player.ammo_rounds = rounds
        player.ammo_damage = damage
        player.unsaved_changes = True
        if inv:
            inv.remove(item)
        return [f'{rounds} ROUNDS NOW READY: +{damage} DAMAGE']

    # ---- Book --------------------------------------------------------------
    if itype == ItemType.BOOK:
        return [f'(Use the `read` command to read the {name}.)']

    # ---- Fallback ----------------------------------------------------------
    return [f'You play with the {name}..']


def _usable_entries(player):
    """Return inventory entries that are not weapons (weapons use `ready`)."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    weapon_cat = str(ItemCategory.WEAPON)
    return [e for e in inv.entries() if str(getattr(e.item, 'category', '')) != weapon_cat]


class UseCommand(Command):
    name    = 'use'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Use an item from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('use',          'List usable items and choose one'),
            ('use <name>',   'Use the item matching name'),
        ],
        examples = [
            ('use',          'Pick from item list'),
            ('use compass',  'Toggle compass'),
            ('use shield',   'Activate a shield'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player
        entries = _usable_entries(player)

        if not entries:
            await ctx.send('You have nothing to use.')
            return CommandResult.ok()

        # Resolve by name arg or interactive prompt
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
            raw = await ctx.prompt(f'Use which item (1-{len(entries)}, Enter to cancel)')
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

        item = entry.item
        if not isinstance(item, Item):
            await ctx.send(f'You play with the {getattr(item, "name", "it")}..')
            return CommandResult.ok()

        for line in _apply_item(item, player):
            await ctx.send(line)
        return CommandResult.ok()
