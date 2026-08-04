"""commands/give.py — Give an item to an ally, player, or monster.

Mirrors SPUR.MISC.S GIVE (vq=1 flag sets vq before falling through to
drop.itm, which transfers the item to the ally's ai$ inventory string).

Supported targets (in lookup order):
  ally    — transfers item to ally.items list (ally carries it)
  player  — transfers item directly to co-located player's inventory
  monster — humorous response; monster usually declines (item returned)
            or occasionally keeps it (food, gold to greedy monsters)
"""
from __future__ import annotations

import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from bar.allies import purchased_allies
from flags import PlayerFlags
from network_context import GameContext

_RING_ID = 67  # ring of invisibility (objects.json) -- see commands/wear.py


# New in TADA -- no SPUR precedent for mount carrying capacity at all
# (checked SPUR.USE.S's eq.horse and every source mention of "saddle"/
# "bag"; ally.items itself has never had any capacity limit for any ally
# type). A mount specifically needs AllyFlags.SADDLEBAGS (commands/
# use.py's USE saddlebags) before it can carry anything; once equipped,
# it can hold this many items. Other ally types are unaffected -- they
# keep the original unlimited ally.items list. Ryan's request.
_MOUNT_CAPACITY_WITH_SADDLEBAGS = 5


def _mount_capacity(ally) -> int:
    """Return how many more items *ally* can carry if it's a mount, or
    None if capacity doesn't apply to this ally (not a mount -- no
    limit)."""
    from bar.ally_data import AllyFlags

    flags = ally.flags or []
    if AllyFlags.MOUNT not in flags:
        return None
    if AllyFlags.SADDLEBAGS not in flags:
        return 0
    return _MOUNT_CAPACITY_WITH_SADDLEBAGS


def _monster_in_room(ctx: GameContext) -> dict | None:
    """Return the monster dict for the current room, or None."""
    game_map = getattr(ctx.server, 'game_map', None)
    monsters = getattr(ctx.server, 'monsters', [])
    room_no  = getattr(ctx.client, 'room', None)
    if not (game_map and monsters and room_no is not None):
        return None
    level = int(getattr(ctx.player, 'map_level', 1) or 1)
    room  = game_map.get_room(level, int(room_no))
    if not room:
        return None
    mon_number = int(getattr(room, 'monster', 0) or 0)
    if not mon_number:
        return None

    from encounters.dwarf import MONSTER_NUMBER as _DWARF_MONSTER_NUMBER, visible_to
    if mon_number == _DWARF_MONSTER_NUMBER and not visible_to(ctx.player):
        return None

    from monsters import get_monster
    return get_monster(monsters, mon_number)


def _players_in_room(ctx: GameContext) -> list:
    """Return player objects of other players sharing this room."""
    my_room = getattr(ctx.client, 'room', None)
    results = []
    for client in ctx.server.clients.values():
        if client is ctx.client:
            continue
        if getattr(client, 'room', None) != my_room:
            continue
        p = getattr(client, 'player', None)
        if p:
            results.append(p)
    return results


_FOOD_KINDS = {'food', 'ration', 'drink'}

# Strength threshold below which a hungry ally benefits from food (SPUR: a[123] < 11)
_BODY_BUILD_STR_CAP = 11


def _consume_ally_entry(ally, entry) -> None:
    """Remove *entry* (or one unit of it) from ally.items -- the item was
    eaten/drunk, so it shouldn't keep sitting in the ally's inventory."""
    entry.quantity -= 1
    if entry.quantity <= 0:
        if entry in ally.items:
            ally.items.remove(entry)
    # else: leave the (now-decremented) entry in place for the remaining stack


async def _try_body_build(ctx: GameContext, ally, entry) -> None:
    """If *entry*'s item is food/drink, attempt ally body building.

    Poisoned food (kind='cursed') harms the ally instead of helping.
    Normal food only boosts strength when the ally is below _BODY_BUILD_STR_CAP.
    Either way, a consumed item is removed from ally.items -- it doesn't
    persist after being eaten/drunk.
    """
    item  = entry.item
    ikind = (getattr(item, 'kind', '') or '').lower()
    aname = ally.name

    if ikind == 'cursed':
        # Cursed ration — poisons the ally regardless of strength
        ally.strength = max(1, ally.strength - 1)
        await ctx.send(f'{aname} clutches their stomach — something was wrong with that food!')
        _consume_ally_entry(ally, entry)
        return

    if ikind not in _FOOD_KINDS:
        return

    if ally.strength >= _BODY_BUILD_STR_CAP:
        return

    ally.strength += 1
    verb = 'drinks thirstily' if ikind == 'drink' else 'eats hungrily'
    await ctx.send(f'{aname} {verb} and looks stronger!  (Str {ally.strength})')
    _consume_ally_entry(ally, entry)


# Monsters known for hoarding gold
_GREEDY_KEYWORDS = ('DRAGON', 'GOBLIN', 'ORC', 'TROLL', 'KOBOLD', 'PIRATE')
# Keywords that suggest a valuable trinket a greedy monster would keep
_TREASURE_KEYWORDS = ('GOLD', 'GEM', 'RING', 'DIAMOND', 'JEWEL', 'COIN', 'CROWN')


def _monster_give_response(item, monster: dict) -> tuple[list[str], bool]:
    """Return (message_lines, item_consumed) for giving *item* to *monster*.

    item_consumed=True means the monster keeps it and it is removed from
    the player's inventory; False means it is returned (no removal).
    """
    from monsters import monster_display_name
    mname  = monster.get('name', 'monster')
    mdisp  = monster_display_name(monster, capitalize=True)
    iname  = getattr(item, 'name', 'it')
    ikind  = (getattr(item, 'kind', '') or '').lower()
    iupper = iname.upper()
    mupper = mname.upper()

    # Food: monster happily eats it
    if ikind in _FOOD_KINDS or 'MEAT' in iupper or 'RATION' in iupper:
        msg = random.choice([
            f'{mdisp} snatches the {iname} and wolfs it down!',
            f'{mdisp} sniffs at the {iname}... then devours it whole.',
            f'{mdisp} gulps down the {iname} without chewing.  Impressive.',
        ])
        return [msg], True

    # Weapons: monster examines, hands back
    cat = str(getattr(item, 'category', '') or '').upper()
    if 'WEAPON' in cat:
        return [
            f'{mdisp} hefts the {iname} appraisingly...',
            f'...and shoves it back at you, unimpressed.',
        ], False

    # Greedy monsters keep shiny things
    if any(k in mupper for k in _GREEDY_KEYWORDS):
        if any(w in iupper for w in _TREASURE_KEYWORDS):
            return [
                f"{mdisp}'s eyes light up!",
                f'It snatches the {iname} and stuffs it away greedily.',
                f'(That is NOT coming back.)',
            ], True

    # Compass: monster stares at needle in confusion
    if 'COMPASS' in iupper:
        return [
            f'{mdisp} stares at the {iname} blankly.',
            f'It spins it around a few times, then returns it.',
            f"(You suspect it was trying to eat the needle.)",
        ], False

    # Shield: worn as a hat
    if 'SHIELD' in iupper:
        return [
            f'{mdisp} places the {iname} on its head like a hat.',
            f'It tilts it at a rakish angle, almost pleased with itself.',
            f'Then it hands it back.',
        ], False

    # Ammo: monster tries to eat it, gives up
    if any(w in iupper for w in ('ARROW', 'BOLT', 'DART', 'ROUND', 'AMMO', 'BULLET', 'STONE')):
        return [
            f'{mdisp} pops the {iname} into its mouth.',
            f'Crunch.  It spits them out, one by one.',
            f'(You collect the slobbery pieces.)',
        ], False

    # Grenade: monster recognises danger, throws it back
    if 'GRENADE' in iupper:
        return [
            f'{mdisp} takes the {iname} and immediately recognises what it is.',
            f'It hurls it back at you!',
            f'(Grenade returned.  Perhaps keep that one to yourself.)',
        ], False

    # Generic fallbacks
    msg, consumed = random.choice([
        (f'{mdisp} sniffs the {iname} curiously, then shoves it back.', False),
        (f'{mdisp} examines the {iname}, makes a disgusted noise, and returns it.', False),
        (f'{mdisp} pokes the {iname} with one claw, then loses interest.', False),
        (f'{mdisp} seems offended by your gift of {iname}.', False),
    ])
    return [msg], consumed


class GiveCommand(Command):
    name    = 'give'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Give an item from your inventory to an ally, player, or monster.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('give',                  'List carried items, then choose a target'),
            ('give <item> to <who>',  'Give a specific item to a named target'),
        ],
        examples = [
            ('give ration to batman', 'Give Batman a food ration'),
            ('give sword to dragon',  'Try giving a sword to a dragon (results vary)'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        # Parse "give <item> to <target>"
        arg_list     = list(args)
        item_words   = []
        target_words = []
        if 'to' in arg_list:
            to_idx       = arg_list.index('to')
            item_words   = arg_list[:to_idx]
            target_words = arg_list[to_idx + 1:]
        else:
            item_words = arg_list

        # Build the item pool from inventory
        entries = list(inventory.entries()) if inventory else []
        if not entries:
            await ctx.send('You have nothing to give.')
            return CommandResult.ok()

        # Resolve item
        if item_words:
            pattern = ' '.join(item_words).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(
                    f'You are not carrying anything matching "{" ".join(item_words)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['', 'Items you carry:']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Give which item (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                idx = int(raw.strip()) - 1
                if not (0 <= idx < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid selection.')
                return CommandResult.ok()
            entry = entries[idx]

        item  = entry.item
        iname = getattr(item, 'name', 'it')

        # Ring of invisibility (#67): can't give it away while worn
        # (SPUR.GUILD.S:237/SPUR.MISC6.S:188,298/SPUR.SHIP.S:490 "Can't, you
        # are USEing it!") -- WEAR again first.
        item_no = getattr(item, 'number', None) or getattr(item, 'id_number', None)
        if item_no == _RING_ID and player.query_flag(PlayerFlags.RING_WORN):
            await ctx.send("Can't, you are wearing it!")
            return CommandResult.ok()

        # Require a target
        if not target_words:
            await ctx.send('Give it to whom?  (Try: give <item> to <name>)')
            return CommandResult.ok()

        target = ' '.join(target_words).lower()

        # --- Ally ---
        allies = purchased_allies(player)
        ally_matches = [a for a in allies if target in a.name.lower()]
        if ally_matches:
            ally = ally_matches[0]
            if not hasattr(ally, 'items') or ally.items is None:
                ally.items = []

            # Ryan's request: saddlebags are meant to be worn (USE
            # saddlebags), not just handed to any ally -- a non-mount
            # ally has nowhere to strap them on, so flag that up rather
            # than silently letting them carry an unused pair of bags.
            # Still completes the give (they're a valid treasure item
            # either way, same as handing over any other object).
            from bar.ally_data import AllyFlags
            from commands.use import _SADDLEBAGS_ID
            if (getattr(item, 'id_number', None) == _SADDLEBAGS_ID
                    and AllyFlags.MOUNT not in (ally.flags or [])):
                await ctx.send(f"{ally.name} has no back to strap them to -- saddlebags are for a mount.")

            capacity = _mount_capacity(ally)
            if capacity is not None:
                if capacity == 0:
                    await ctx.send(f'{ally.name} has nowhere to carry it -- needs saddlebags first.')
                    return CommandResult.ok()
                if len(ally.items) >= capacity:
                    await ctx.send(f"{ally.name}'s saddlebags are full.")
                    return CommandResult.ok()

            # Weapon: allies have no READY command of their own, so a given
            # weapon is auto-readied on the spot (replacing whatever they
            # had -- combat/resolution.py ally_attacks() reads ally.readied_weapon).
            from items import Weapon
            if isinstance(item, Weapon):
                if inventory:
                    inventory.remove(item)
                ally.readied_weapon = item
                ally.ammo_rounds = 0
                ally.ammo_max = 0
                ally.ammo_damage = 0
                ally.items.append(entry)
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {ally.name}.')
                await ctx.send(f'{ally.name} readies the {iname}!')
                await ctx.send_room(
                    f'{pself} gives the {iname} to {ally.name}, who readies it!',
                    exclude_self=True)
                return CommandResult.ok()

            # Ammo: loads straight into the ally's readied weapon, same as
            # commands/use.py's player ammo branch (is_ammo_item/
            # ammo_load_error, shared from there so the two paths can't
            # drift out of sync again -- see give.py bug fixed 2026-08-01),
            # rather than sitting in ally.items -- an ally has no USE
            # command to load it later. An empty carrier (shoppe/ollys.py's
            # reusable, 'capacity'-flagged item) has nothing to load, so it
            # falls through to the plain-item give below instead of
            # pretending to load 0 rounds.
            from commands.use import ammo_load_error, is_ammo_item as _is_ammo_item
            flags = getattr(item, 'flags', None)
            rounds = int(flags.get('rounds', 0)) if _is_ammo_item(flags) else 0
            if _is_ammo_item(flags) and rounds > 0:
                weapon = getattr(ally, 'readied_weapon', None)
                if weapon is None:
                    await ctx.send(f'{ally.name} has no weapon readied to load {iname} into.')
                    return CommandResult.ok()
                wname_upper = (getattr(weapon, 'name', '') or '').upper()
                reason = ammo_load_error(weapon, flags)
                if reason == 'storm':
                    await ctx.send(f"The {wname_upper} doesn't use physical ammo.")
                    return CommandResult.ok()
                if reason == 'wrong_weapon':
                    await ctx.send(f'That ammo is not for the {wname_upper}.')
                    return CommandResult.ok()
                damage = int(flags.get('damage', 0))
                if inventory:
                    inventory.remove(item)
                ally.ammo_rounds = rounds
                ally.ammo_max = rounds
                ally.ammo_damage = damage
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {ally.name}.')
                await ctx.send(f'{ally.name} loads the {weapon.name}: '
                                f'{rounds} rounds ready, +{damage} damage.')
                await ctx.send_room(
                    f'{pself} gives {ally.name} {iname}, who loads it into the {weapon.name}.',
                    exclude_self=True)
                return CommandResult.ok()

            if inventory:
                inventory.remove(item)
            ally.items.append(entry)
            await ctx.send(f'You give the {iname} to {ally.name}.')
            await ctx.send(f'{ally.name} takes the {iname} and tucks it away.')
            await _try_body_build(ctx, ally, entry)
            return CommandResult.ok()

        # --- Other player in room ---
        for other in _players_in_room(ctx):
            pname = getattr(other, 'name', '')
            if target in pname.lower():
                other_inv = getattr(other, 'inventory', None)
                if other_inv and other_inv.is_full():
                    await ctx.send(f'{pname} cannot carry any more.')
                    return CommandResult.ok()
                if inventory:
                    inventory.remove(item)
                if other_inv:
                    other_inv.add(item,
                                  quantity=getattr(entry, 'quantity', 1))
                other.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {pname}.')
                await ctx.send_room(
                    f'{pself} gives {iname} to {pname}.', exclude_self=True)
                return CommandResult.ok()

        # --- Monster ---
        monster = _monster_in_room(ctx)
        if monster:
            mname = monster.get('name', 'the monster')
            if target in mname.lower():
                raw  = monster.get('strength')
                if raw is None:
                    raw = monster.get('hit_points')
                m_hp = int(raw if raw is not None else 1)
                if m_hp <= 0:
                    from monsters import monster_display_name
                    await ctx.send(f'{monster_display_name(monster, capitalize=True)} is dead.  It does not want anything.')
                    return CommandResult.ok()
                lines, consumed = _monster_give_response(item, monster)
                for line in lines:
                    await ctx.send(line)
                if consumed and inventory:
                    inventory.remove(item)
                return CommandResult.ok()

        await ctx.send(f'There is no "{" ".join(target_words)}" here.')
        return CommandResult.ok()
