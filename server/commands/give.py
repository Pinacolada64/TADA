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
_PENDANT_ID = 82  # crystal pendant (objects.json) -- see commands/wear.py


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


# Mount-specific feeding (8/4/26, Ryan -- no SPUR precedent): a mount's
# hit_points is otherwise a dead end after purchase -- it's seeded once
# from strength (bar/fat_olaf.py's _HP_PER_STRENGTH, "hit_points seeded
# as strength x this on purchase") and only ever goes down (combat
# friendly-fire, _try_redirect_to_mount), with nothing anywhere to bring
# it back up. Feeding restores a few points per item, capped at that
# same strength x _HP_PER_STRENGTH ceiling, so hay/oats/carrots/etc.
# double as the mount's only stamina-recovery mechanic. Doesn't apply to
# non-mount allies -- their strength-only body build is unchanged.
_MOUNT_HP_GAIN_RANGE = (2, 5)

# rations.json numbers a mount actually recognizes as horse food -- Sugar
# Cube, Oats, Apples, Hay, Carrots, Salt Lick, Bucket of Water, Bran Mash
# (street/jakes.py's _SUGAR_CUBE_RATION_NUM/_OATS_RATION_NUM/
# _APPLES_RATION_NUM/_HAY_RATION_NUM/_CARROTS_RATION_NUM/
# _SALT_LICK_RATION_NUM/_WATER_RATION_NUM/_MASH_RATION_NUM -- same
# numbers, keep both lists in sync if either changes). Any other
# food/drink offered to a mount is declined instead of eaten.
_MOUNT_FOOD_RATION_NUMBERS = frozenset({16, 25, 78, 79, 80, 81, 82, 83})


async def _try_body_build(ctx: GameContext, ally, entry) -> None:
    """If *entry*'s item is food/drink, attempt ally body building.

    Poisoned food (kind='cursed') harms the ally instead of helping.
    Normal food boosts strength when the ally is below _BODY_BUILD_STR_CAP.
    A MOUNT-flagged ally additionally recovers hit_points (see
    _MOUNT_HP_GAIN_RANGE above) -- mounts still consume the item for this
    even once strength is capped, since the HP recovery is a separate
    benefit. Any other ally that's already at the strength cap gets no
    effect and keeps the item (nothing to consume it for).

    A mount offered food/drink outside _MOUNT_FOOD_RATION_NUMBERS (e.g.
    a ration meant for a human, like Candy Bar or Jar of Honey) declines
    it outright -- no effect, item not consumed, stays in ally.items.
    """
    from bar.ally_data import AllyFlags, AllyStatus
    from bar.fat_olaf import _HP_PER_STRENGTH

    item  = entry.item
    ikind = (getattr(item, 'kind', '') or '').lower()
    aname = ally.name

    if ikind == 'cursed':
        # Cursed ration — poisons the ally regardless of strength
        ally.strength = max(1, ally.strength - 1)
        await ctx.send(f'{aname} clutches their stomach — something was wrong with that food!')
        _consume_ally_entry(ally, entry)
        # TODO: "You feel less honorable"
        return

    if ikind not in _FOOD_KINDS:
        return

    is_mount = AllyFlags.MOUNT in (ally.flags or [])

    if is_mount and getattr(item, 'number', None) not in _MOUNT_FOOD_RATION_NUMBERS:
        await ctx.send(f'{aname} sniffs at the {item.name.lower()} and eyes you warily.')
        return

    gained_strength = ally.strength < _BODY_BUILD_STR_CAP
    if gained_strength:
        ally.strength += 1

    gained_hp = False
    if is_mount and ally.status != AllyStatus.DEAD:
        max_hp = ally.strength * _HP_PER_STRENGTH
        current_hp = ally.hit_points or 0
        if current_hp < max_hp:
            gain = min(random.randint(*_MOUNT_HP_GAIN_RANGE), max_hp - current_hp)
            if gain > 0:
                ally.hit_points = current_hp + gain
                gained_hp = True

    if not gained_strength and not gained_hp:
        return

    verb = 'drinks thirstily' if ikind == 'drink' else 'eats hungrily'
    if gained_strength and gained_hp:
        await ctx.send(
            f'{aname} {verb}, looks stronger, and seems more energetic!'
            f'  (Str {ally.strength}, HP {ally.hit_points})'
        )
    elif gained_strength:
        await ctx.send(f'{aname} {verb} and looks stronger!  (Str {ally.strength})')
    else:
        await ctx.send(f'{aname} {verb} and seems more energetic!  (HP {ally.hit_points})')
    # TODO: "You feel more honorable."
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
            f'It spins the needle around a few times, then returns the compass.',
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
            ('give ration to batman', 'GIVE hands an item from your inventory to a party '
                                       'ally, another player, or a monster. Giving a ration '
                                       "to an ally named Batman transfers it into his "
                                       "inventory -- allies actually carry and use what "
                                       "you give them."),
            ('give sword to dragon',  "Giving a monster something is mostly flavor -- most "
                                       "just sniff at it and hand it back, though food or "
                                       "gold occasionally gets kept by a greedy one."),
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
            raw = await ctx.prompt(preamble_lines=f'(1-{len(entries)}, {ctx.player.return_key} to cancel)',
                                   prompt_text="Give which item")
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
        # id_number is only unique within its own category (weapons/items/
        # rations each number independently -- items.py:364), so this must
        # also check category or it collides with ration #67 DEAD BUG.
        from items import ItemCategory
        item_no  = getattr(item, 'number', None) or getattr(item, 'id_number', None)
        item_cat = getattr(item, 'category', None)
        if item_cat == ItemCategory.ITEM and item_no == _RING_ID and player.query_flag(PlayerFlags.RING_WORN):
            await ctx.send("Can't, you are wearing it!")
            return CommandResult.ok()

        # Crystal Pendant (#82): can't give it away while worn -- same
        # reasoning as the ring above (commands/wear.py). WEAR again first.
        if item_cat == ItemCategory.ITEM and item_no == _PENDANT_ID and player.query_flag(PlayerFlags.PENDANT_WORN):
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
            from bar.ally_data import add_ally_item
            if isinstance(item, Weapon):
                # Given-away weapon stops counting as the player's own
                # readied one -- otherwise STAT keeps showing "Weapon
                # readied: ..." for an item they no longer have, and
                # combat/resolution.py's player_attacks() takes `weapon`
                # as a plain parameter with no inventory check of its
                # own, so it would keep using that phantom weapon's stats
                # for every swing (player.py's unworn_if_given_away()).
                # Must run before inventory.remove() below -- see that
                # function's docstring for why.
                from player import unworn_if_given_away, unworn_notice
                unworn_slot = unworn_if_given_away(player, item)
                if inventory:
                    inventory.remove(item)
                ally.readied_weapon = item
                ally.ammo_rounds = 0
                ally.ammo_max = 0
                ally.ammo_damage = 0
                # add_ally_item(), not a raw ally.items.append(entry) --
                # (a) it stacks onto a matching existing entry instead of
                # always appending a duplicate (a given ally rarely holds
                # two of the same weapon, but stay consistent with the
                # plain-item branch below where it does bite), and (b) a
                # *fresh* entry either way, never the source `entry` --
                # inventory.remove() only decrements a stacked player-side
                # entry's quantity in place rather than always popping it,
                # so reusing `entry` here would hand the ally the *same
                # object* still sitting in the player's own inventory.
                add_ally_item(ally, item, quantity=1)
                player.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {ally.name}.')
                # Ryan's request: a non-expert who just gave away their
                # own readied weapon/armor/shield should be told, not left
                # to notice via a later STAT/attack -- experts already
                # know GIVE does this (see commands/wear.py's identical
                # `if not player.is_expert:` hint pattern for the ring).
                if not player.is_expert:
                    notice = unworn_notice(unworn_slot, iname)
                    if notice:
                        await ctx.send(notice)
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
                player.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {ally.name}.')
                await ctx.send(f'{ally.name} loads the {weapon.name}: '
                                f'{rounds} rounds ready, +{damage} damage.')
                await ctx.send_room(
                    f'{pself} gives {ally.name} {iname}, who loads it into the {weapon.name}.',
                    exclude_self=True)
                return CommandResult.ok()

            # Armor/shield: allies have no WEAR command of their own either
            # (same gap as the Weapon branch above), so a given armor- or
            # shield-type Item is auto-worn on the spot, replacing whatever
            # they had in that slot. Display-only for now (commands/
            # stats.py's Notes column has carried a hardcoded "[Worn: None]"
            # placeholder since 2026-08-08 for exactly this to fill in) --
            # no ally damage-mitigation model exists yet to hook a rating
            # into. Ryan's report: GIVEing an ally cloth armor said it
            # "takes the cloth armor and tucks it away", same generic
            # wording as a book or trinket, instead of anything suggesting
            # it got worn.
            from item_system import ItemType
            item_type = getattr(item, 'type', None)
            worn_slot = {ItemType.ARMOR: 'armor', ItemType.SHIELD: 'shield'}.get(item_type)
            if worn_slot is not None:
                from player import unworn_if_given_away, unworn_notice
                player_unworn_slot = unworn_if_given_away(player, item)
                if inventory:
                    inventory.remove(item)
                setattr(ally, f'readied_{worn_slot}', item)
                add_ally_item(ally, item, quantity=1)
                player.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                verb = 'straps on' if worn_slot == 'shield' else 'wears'
                await ctx.send(f'You give the {iname} to {ally.name}.')
                if not player.is_expert:
                    notice = unworn_notice(player_unworn_slot, iname)
                    if notice:
                        await ctx.send(notice)
                await ctx.send(f'{ally.name} {verb} the {iname}!')
                await ctx.send_room(
                    f'{pself} gives the {iname} to {ally.name}, who {verb} it!',
                    exclude_self=True)
                return CommandResult.ok()

            # Nothing left to unwear/unready here -- a Weapon or an
            # armor/shield-type Item both return earlier, in their own
            # dedicated branches above, so anything reaching this generic
            # fallback (a book, trinket, ration, etc.) was never a worn
            # or readied item to begin with.
            if inventory:
                inventory.remove(item)
            # add_ally_item(), not a raw ally.items.append(entry) -- see
            # the weapon branch's comment above for why a *fresh* entry
            # matters (inventory.remove() only decrements a stacked
            # player-side entry in place, so reusing `entry` would alias
            # the ally's copy to whatever's still left in the player's
            # own inventory), and why *stacking* matters here specifically:
            # Ryan's report -- repeated GIVEs of the same item type were
            # each appending a separate quantity-1 entry (4 distinct
            # "cloth armor" lines) instead of accumulating on one entry,
            # unlike every other inventory in this codebase.
            given_entry = add_ally_item(ally, item, quantity=1)
            player.unsaved_changes = True
            pself = getattr(player, 'name', 'Someone')
            await ctx.send(f'You give the {iname} to {ally.name}.')
            await ctx.send(f'{ally.name} takes the {iname} and tucks it away.')
            # Ryan's request: this branch had no send_room() at all, unlike
            # every other GIVE-to-ally branch above -- bystanders never
            # found out a plain item (book, trinket, ration, etc.) changed
            # hands.
            await ctx.send_room(
                f'{pself} gives the {iname} to {ally.name}.', exclude_self=True)
            await _try_body_build(ctx, ally, given_entry)
            return CommandResult.ok()

        # --- Other player in room ---
        for other in _players_in_room(ctx):
            pname = getattr(other, 'name', '')
            if target in pname.lower():
                other_inv = getattr(other, 'inventory', None)
                if other_inv and other_inv.is_full():
                    await ctx.send(f'{pname} cannot carry any more.')
                    return CommandResult.ok()
                from player import unworn_if_given_away, unworn_notice
                unworn_slot = unworn_if_given_away(player, item)
                if inventory:
                    inventory.remove(item)
                if other_inv:
                    # Always 1 unit, matching inventory.remove(item)'s own
                    # default above -- entry.quantity would read the stack's
                    # *remaining* count after that remove() already
                    # decremented it in place (same bug as the ally
                    # branches above), handing the other player everything
                    # still left in the giver's pack instead of the one
                    # unit actually taken off it.
                    other_inv.add(item, quantity=1)
                player.unsaved_changes = True
                other.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'You give the {iname} to {pname}.')
                if not player.is_expert:
                    notice = unworn_notice(unworn_slot, iname)
                    if notice:
                        await ctx.send(notice)
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
                    from player import unworn_if_given_away, unworn_notice
                    unworn_slot = unworn_if_given_away(player, item)
                    inventory.remove(item)
                    player.unsaved_changes = True
                    if not player.is_expert:
                        notice = unworn_notice(unworn_slot, iname)
                        if notice:
                            await ctx.send(notice)
                # This branch had no send_room() at all -- bystanders
                # never saw the offer or its outcome (eaten, hoarded, or
                # handed back). Ryan's request.
                from monsters import monster_display_name
                pself = getattr(player, 'name', 'Someone')
                mdisp = monster_display_name(monster, capitalize=True)
                if consumed:
                    await ctx.send_room(
                        f'{pself} gives {iname} to {mdisp}, who keeps it.', exclude_self=True)
                else:
                    await ctx.send_room(
                        f'{pself} offers {iname} to {mdisp}, who hands it back.', exclude_self=True)
                return CommandResult.ok()

        await ctx.send(f'There is no "{" ".join(target_words)}" here.')
        return CommandResult.ok()
