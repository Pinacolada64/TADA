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
from network_context import GameContext


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


async def _try_body_build(ctx: GameContext, ally, item) -> None:
    """If *item* is food/drink, attempt ally body building.

    Poisoned food (kind='cursed') harms the ally instead of helping.
    Normal food only boosts strength when the ally is below _BODY_BUILD_STR_CAP.
    """
    ikind = (getattr(item, 'kind', '') or '').lower()
    aname = ally.name

    if ikind == 'cursed':
        # Cursed ration — poisons the ally regardless of strength
        ally.strength = max(1, ally.strength - 1)
        await ctx.send(f'{aname} clutches their stomach — something was wrong with that food!')
        return

    if ikind not in _FOOD_KINDS:
        return

    if ally.strength >= _BODY_BUILD_STR_CAP:
        return

    ally.strength += 1
    await ctx.send(f'{aname} eats hungrily and looks stronger!  (Str {ally.strength})')


# Monsters known for hoarding gold
_GREEDY_KEYWORDS = ('DRAGON', 'GOBLIN', 'ORC', 'TROLL', 'KOBOLD', 'PIRATE')
# Keywords that suggest a valuable trinket a greedy monster would keep
_TREASURE_KEYWORDS = ('GOLD', 'GEM', 'RING', 'DIAMOND', 'JEWEL', 'COIN', 'CROWN')


def _monster_give_response(item, monster: dict) -> tuple[list[str], bool]:
    """Return (message_lines, item_consumed) for giving *item* to *monster*.

    item_consumed=True means the monster keeps it and it is removed from
    the player's inventory; False means it is returned (no removal).
    """
    mname  = monster.get('name', 'the monster')
    iname  = getattr(item, 'name', 'it')
    ikind  = (getattr(item, 'kind', '') or '').lower()
    iupper = iname.upper()
    mupper = mname.upper()

    # Food: monster happily eats it
    if ikind in _FOOD_KINDS or 'MEAT' in iupper or 'RATION' in iupper:
        msg = random.choice([
            f'The {mname} snatches the {iname} and wolfs it down!',
            f'The {mname} sniffs at the {iname}... then devours it whole.',
            f'The {mname} gulps down the {iname} without chewing.  Impressive.',
        ])
        return [msg], True

    # Weapons: monster examines, hands back
    cat = str(getattr(item, 'category', '') or '').upper()
    if 'WEAPON' in cat:
        return [
            f'The {mname} hefts the {iname} appraisingly...',
            f'...and shoves it back at you, unimpressed.',
        ], False

    # Greedy monsters keep shiny things
    if any(k in mupper for k in _GREEDY_KEYWORDS):
        if any(w in iupper for w in _TREASURE_KEYWORDS):
            return [
                f"The {mname}'s eyes light up!",
                f'It snatches the {iname} and stuffs it away greedily.',
                f'(That is NOT coming back.)',
            ], True

    # Compass: monster stares at needle in confusion
    if 'COMPASS' in iupper:
        return [
            f'The {mname} stares at the {iname} blankly.',
            f'It spins it around a few times, then returns it.',
            f"(You suspect it was trying to eat the needle.)",
        ], False

    # Shield: worn as a hat
    if 'SHIELD' in iupper:
        return [
            f'The {mname} places the {iname} on its head like a hat.',
            f'It tilts it at a rakish angle, almost pleased with itself.',
            f'Then it hands it back.',
        ], False

    # Ammo: monster tries to eat it, gives up
    if any(w in iupper for w in ('ARROW', 'BOLT', 'DART', 'ROUND', 'AMMO', 'BULLET', 'STONE')):
        return [
            f'The {mname} pops the {iname} into its mouth.',
            f'Crunch.  It spits them out, one by one.',
            f'(You collect the slobbery pieces.)',
        ], False

    # Grenade: monster recognises danger, throws it back
    if 'GRENADE' in iupper:
        return [
            f'The {mname} takes the {iname} and immediately recognises what it is.',
            f'It hurls it back at you!',
            f'(Grenade returned.  Perhaps keep that one to yourself.)',
        ], False

    # Generic fallbacks
    msg, consumed = random.choice([
        (f'The {mname} sniffs the {iname} curiously, then shoves it back.', False),
        (f'The {mname} examines the {iname}, makes a disgusted noise, and returns it.', False),
        (f'The {mname} pokes the {iname} with one claw, then loses interest.', False),
        (f'The {mname} seems offended by your gift of {iname}.', False),
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
            if inventory:
                inventory.remove(item)
            if not hasattr(ally, 'items') or ally.items is None:
                ally.items = []
            ally.items.append(entry)
            await ctx.send(f'You give the {iname} to {ally.name}.')
            await ctx.send(f'{ally.name} takes the {iname} and tucks it away.')
            await _try_body_build(ctx, ally, item)
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
                                  quantity=getattr(entry, 'quantity', 1),
                                  charges=entry.charges)
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
                    await ctx.send(f'The {mname} is dead.  It does not want anything.')
                    return CommandResult.ok()
                lines, consumed = _monster_give_response(item, monster)
                for line in lines:
                    await ctx.send(line)
                if consumed and inventory:
                    inventory.remove(item)
                return CommandResult.ok()

        await ctx.send(f'There is no "{" ".join(target_words)}" here.')
        return CommandResult.ok()
