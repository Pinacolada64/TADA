"""commands/get.py — Pick up an item from the current room."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import InventoryEntry
from item_system import ItemType
from items import Item, ItemCategory
from network_context import GameContext
from quests.tuts_treasure import get as tuts_treasure_get, is_tuts_treasure

# Weapon id_numbers for fireballs and staves (weapons.json)
_FIREBALL_IDS = {14, 15, 39}   # FIREBALL, LARGE FIREBALL, SMALL FIREBALL
_STAFF_IDS    = {3, 47}         # WOOD STAFF, STORM STAFF
_GAUNTLETS_ID = 68              # gauntlets (objects.json)

# Special item id_numbers (objects.json)
_BOOBY_TRAP_IDS = {70, 72}     # strange weapon, funny doll — explode on pickup (SPUR.MISC.S:282)
_PANDORAS_BOX   = 71            # Pandora's box (SPUR.MISC.S:283)
_GOLD_ROSE      = 41            # gold rose — poisoned stickers (SPUR.MISC.S get.itm)
_FIREPLACE      = 81            # fireplace — USE only (SPUR.MISC.S:285)
_OBELISK        = 139           # huge black obelisk — too large (SPUR.MISC.S:287)


def _hp5_effect(player) -> tuple[str, ...]:
    """SPUR hp.5: reduce INT by 5, reduce HP to 5. Returns message lines."""
    msgs = []
    stats = getattr(player, 'stats', None) or {}
    pi = int(stats.get('Intelligence', 10))
    if pi > 5:
        stats['Intelligence'] = pi - 5
        player.stats = stats
        msgs.append('You feel dumber!')
    hp = int(getattr(player, 'hit_points', 1) or 1)
    if hp > 5:
        msgs.append(f'You take {hp - 5} damage!')
        player.hit_points = 5
    player.unsaved_changes = True
    return tuple(msgs)


def _raw_item_data(ctx, item) -> dict | None:
    """Find *item*'s original objects.json/weapons.json/rations.json entry
    by id_number.

    Deliberately separate from commands/look.py's identical-looking
    helper of the same name: that one keys off isinstance(item, Weapon)/
    isinstance(item, Rations), but every room item constructed here
    (_room_available_items()) is a plain items.Item tagged with an
    ItemCategory, never an actual Weapon/Rations subclass instance -- so
    look.py's version would always fall through to the objects.json pool
    and silently miss weapon/food data. Keys off item.category instead.
    """
    item_id = getattr(item, 'id_number', None)
    if item_id is None:
        return None
    category = getattr(item, 'category', None)
    if category == ItemCategory.WEAPON:
        pool = getattr(ctx.server, 'weapons', None) or []
    elif category == ItemCategory.FOOD:
        pool = getattr(ctx.server, 'rations', None) or []
    else:
        pool = getattr(ctx.server, 'items', None) or []
    for raw in pool:
        if raw.get('number') == item_id:
            return raw
    return None


def _is_cursed(raw: dict | None) -> bool:
    """objects.json marks a cursed item via "type": "cursed"; weapons.json/
    rations.json (no "type" field) use "kind" for the same purpose --
    e.g. rations.json's EMBALMING FLUID/POISON APPLE/THE APPLE OF EVE."""
    if not raw:
        return False
    return raw.get('type') == 'cursed' or raw.get('kind') == 'cursed'


def _cursed_penalty(player, name: str, price: int) -> list[str]:
    """SPUR.MISC.S 'cursed' subroutine (get.itm/get.wpn/get.fd's
    i1$/wt$/ft$="C" checks, all three routed to the same 'cursed' label):
    getting a cursed item/weapon/food always inflicts damage split
    between Intelligence and HP, scaled by the item's own value (or a
    flat 10 if it has none) -- regardless of whether it was examined
    first. EXAMINE (commands/look.py's _examine_item()) only reveals the
    "This X is Cursed" flavor text in advance so a player can choose not
    to GET it; it doesn't set any flag that reduces or prevents this
    penalty. Can be fatal if HP drops to 0 (SPUR's dead2 branch) --
    mirrors survival.py's own inline pattern for non-combat death (set
    hit_points=0, return a death message) rather than combat/engine.py's
    CombatEngine._player_dies(), which is tied to a live monster
    encounter this isn't part of.

    The cursed item is never added to inventory either way (SPUR's
    'cursed' subroutine returns without reaching the normal add-to-
    inventory code) -- the caller should not call inventory.add() for it.
    """
    severity = int(price) or 10
    intel_loss = random.randint(0, severity - 1)
    hp_loss    = severity - intel_loss

    lines = [f'{name} is Cursed!']

    stats = getattr(player, 'stats', None) or {}
    intel = int(stats.get('Intelligence', 10))
    stats['Intelligence'] = max(0, intel - intel_loss)
    player.stats = stats

    hp = int(getattr(player, 'hit_points', 1) or 1)
    player.hit_points = hp - hp_loss
    player.unsaved_changes = True

    if player.hit_points <= 0:
        player.hit_points = 0
        lines.append('You have been slain by the curse!')
        return lines

    lines.append('You feel dumber..')
    lines.append('(Try examining things first!)')
    return lines


def _monster_in_room(ctx: GameContext) -> dict | None:
    """Return the monster dict for the current room, or None if none present."""
    game_map = getattr(ctx.server, 'game_map', None)
    monsters = getattr(ctx.server, 'monsters', [])
    if not game_map or not monsters:
        return None
    room_no = getattr(ctx.client, 'room', None)
    if room_no is None:
        return None
    level   = int(getattr(ctx.player, 'map_level', 1) or 1)
    room    = game_map.get_room(level, int(room_no))
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
    """Return player objects for other players sharing this room."""
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


def _room_available_items(ctx: GameContext) -> list[tuple]:
    """Return (display_name, InventoryEntry, remove_fn) for items the player can pick up.

    Static map items already in the player's picked_up_items list are hidden.
    remove_fn() records the pickup for static items; pops the entry for dropped items.
    """
    server  = ctx.server
    player  = ctx.player
    room_no = getattr(ctx.client, 'room', None)
    level   = int(getattr(player, 'map_level', 1) or 1)
    room    = (server.game_map.get_room(level, int(room_no))
               if server.game_map and room_no else None)
    if not room:
        return []

    picked_up = getattr(player, 'picked_up_items', [])
    available = []

    # Static room items (item / weapon / food are 1-based indices into server collections)
    for attr, collection, category in (
        ('item',   server.items,   ItemCategory.ITEM),
        ('weapon', server.weapons, ItemCategory.WEAPON),
        ('food',   server.rations, ItemCategory.FOOD),
    ):
        idx = int(getattr(room, attr, 0) or 0) - 1
        if not (0 <= idx < len(collection)):
            continue
        raw = collection[idx]
        name = (raw.get('name') if isinstance(raw, dict)
                else getattr(raw, 'name', None))
        if not name:
            continue
        item_id = (raw.get('id_number', idx + 1) if isinstance(raw, dict)
                   else getattr(raw, 'id_number', idx + 1))

        if item_id in picked_up:
            continue

        item  = Item(id_number=item_id, name=name, category=category)
        # Preserve objects.json's own "type" field (e.g. "book") as a real
        # ItemType -- read.py's book list keys off this, and without it a
        # room-found book (a scroll, say) would never show up there at all;
        # weapon/ration dicts have no comparable "type" key, so this is a
        # harmless no-op for those.
        raw_type = raw.get('type') if isinstance(raw, dict) else None
        if raw_type:
            try:
                item.type = ItemType(raw_type)
            except ValueError:
                pass
        entry = InventoryEntry(item=item)

        def _record(iid=item_id, p=player):
            if iid not in p.picked_up_items:
                p.picked_up_items.append(iid)
                p.unsaved_changes = True

        available.append((name, entry, _record))

    # Items dropped by players this session (global — real transfers between players)
    dropped = server.room_items.get(int(room_no) if room_no else -1, [])
    for i, entry in enumerate(dropped):
        name = getattr(entry.item, 'name', '?')
        captured_i       = i
        captured_room_no = int(room_no)
        def _remove_dropped(ri=captured_i, rn=captured_room_no):
            lst = server.room_items.get(rn, [])
            if ri < len(lst):
                lst.pop(ri)
        available.append((name, entry, _remove_dropped))

    return available


class GetCommand(Command):
    name    = 'get'
    aliases = ['g', 'pick']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Pick up an item from the room.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('get',        'List items in the room'),
            ('get <name>', 'Pick up a specific item by name'),
        ],
        examples = [
            ('get',        'Show what is on the ground'),
            ('get sword',  'Pick up the sword'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        available = _room_available_items(ctx)

        if args:
            target = ' '.join(args).lower()
            matches = [(name, entry, rm) for name, entry, rm in available
                       if target in name.lower()]

            # No item matched — check for a monster or other player by that name
            if not matches:
                return await self._try_get_living(ctx, target)

            if len(matches) == 1:
                return await self._pick_up(ctx, inventory, *matches[0])
            available = matches

        if not available:
            # "get" with no args and nothing on the ground — mention monster/players too
            await self._try_get_living(ctx, '*')
            if not _monster_in_room(ctx) and not _players_in_room(ctx):
                await ctx.send('There is nothing here to pick up.')
            return CommandResult.ok()

        lines = ['You see:', '']
        for i, (name, entry, _) in enumerate(available, 1):
            lines.append(f'  {i:>2}. {name}')
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt(f'Get which item (1-{len(available)}, or Enter to cancel)')
        if not raw or not raw.strip():
            return CommandResult.ok()

        try:
            choice = int(raw.strip()) - 1
            if not (0 <= choice < len(available)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            return CommandResult.ok()

        return await self._pick_up(ctx, inventory, *available[choice])

    async def _try_get_living(self, ctx: GameContext, target: str) -> CommandResult:
        """Handle attempts to GET a monster or another player (SPUR.MISC.S get.b / get.plyr)."""
        from inventory import InventoryEntry
        matched = False

        # Monster
        monster = _monster_in_room(ctx)
        if monster:
            mname = monster.get('name', 'the monster')
            if target == '*' or target in mname.lower():
                matched = True
                m_hp = int(monster.get('strength') or monster.get('hit_points') or 1)
                if m_hp > 0:
                    await ctx.send(f'THE {mname.upper()} WON\'T LET YOU!')
                else:
                    await ctx.send(f'YOU HACK UP THE {mname.upper()} INTO {mname.upper()} STEAKS..')
                    # Add meat to room so it can be picked up and eaten (SPUR.MISC3.S:369)
                    room_no = getattr(ctx.client, 'room', None)
                    if room_no is not None:
                        is_diseased = bool((monster.get('flags') or {}).get('diseased_attack'))
                        meat = Item(
                            id_number = 69,
                            name      = f'{mname} MEAT',
                            kind      = 'food',
                            category  = ItemCategory.FOOD,
                            diseased_meat = is_diseased,
                        )
                        meat_entry = InventoryEntry(item=meat)
                        room_items = getattr(ctx.server, 'room_items', None)
                        if room_items is not None:
                            room_items.setdefault(int(room_no), []).append(meat_entry)

        # Other players in room
        for other in _players_in_room(ctx):
            pname = getattr(other, 'name', 'Someone')
            if target == '*' or target in pname.lower():
                matched = True
                hp = int(getattr(other, 'hit_points', 1) or 1)
                if hp > 0:
                    await ctx.send(f'{pname} SKUTTLES OUT OF REACH!')
                else:
                    await ctx.send(f'{pname} WON\'T FIT IN YOUR SACK..')

        if not matched and target != '*':
            await ctx.send(f'You do not see any "{target}" here.')

        return CommandResult.ok()

    async def _pick_up(self, ctx: GameContext, inventory,
                       name: str, entry: InventoryEntry, remove_fn) -> CommandResult:
        player  = ctx.player
        item_id = getattr(entry.item, 'id_number', None)

        # --- Tut's Treasure: quest #16 (quests/tuts_treasure.py) -- checked
        # before the "inventory full" guard below, since a successful GET
        # here converts straight to gold and never actually needs a slot ---
        if is_tuts_treasure(item_id):
            outcome = tuts_treasure_get(player)
            for line in outcome.lines:
                await ctx.send(line)
            if outcome.remove_from_room:
                remove_fn()
            return CommandResult.ok()

        # Anti-hoarding: block if already in inventory OR already picked up this session
        if item_id and inventory is not None and inventory.find(item_id=item_id):
            await ctx.send(f'You already have {name}.')
            return CommandResult.ok()

        if inventory is not None and inventory.is_full():
            await ctx.send('You can carry no more.')
            return CommandResult.ok()

        # --- Fireplace: USE only (SPUR.MISC.S:285) ---
        if item_id == _FIREPLACE:
            await ctx.send('You can only USE this..')
            return CommandResult.ok()

        # --- Obelisk: too large to move (SPUR.MISC.S:287) ---
        if item_id == _OBELISK:
            await ctx.send(f'The {name} is MUCH too large to get!')
            return CommandResult.ok()

        # --- Cursed item/weapon/food: INT+HP damage, never added to inventory
        # (SPUR.MISC.S's i1$/wt$/ft$="C" checks -- see _cursed_penalty()).
        # Removed from the room after triggering once, matching this file's
        # own established precedent for the booby trap/Pandora's Box below
        # rather than SPUR's leave-it-in-the-room-forever original behavior.
        raw = _raw_item_data(ctx, entry.item)
        if _is_cursed(raw):
            remove_fn()
            for msg in _cursed_penalty(player, name, raw.get('price', 0)):
                await ctx.send(msg)
            return CommandResult.ok()

        # --- Booby trap: explodes on pickup (SPUR.MISC.S strange, items 70/72) ---
        if item_id in _BOOBY_TRAP_IDS:
            remove_fn()
            await ctx.send('ARGG!!  It is booby trapped!  It blows up!')
            await ctx.send('BOOOMM!!')
            for msg in _hp5_effect(player):
                await ctx.send(msg)
            return CommandResult.ok()

        # --- Pandora's Box: smoke, XP/CON/INT/HP penalties (SPUR.MISC.S pandora) ---
        if item_id == _PANDORAS_BOX:
            remove_fn()
            await ctx.send("FOOL!!  YOU SHOULD NOT DO THAT!!")
            await ctx.send('STRANGE SMOKE BILLOWS OUT!')
            ep = int(getattr(player, 'experience', 0) or 0)
            if ep > 100:
                await ctx.send(f'You lose {ep - 100} experience!')
                player.experience = 100
            stats = getattr(player, 'stats', None) or {}
            pt = int(stats.get('Constitution', 10))
            if pt > 5:
                stats['Constitution'] = 5
                player.stats = stats
                await ctx.send('Your constitution is reduced to 5!')
            for msg in _hp5_effect(player):
                await ctx.send(msg)
            return CommandResult.ok()

        # --- Gold Rose: poisoned stickers — DEX check (SPUR.MISC.S rose) ---
        if item_id == _GOLD_ROSE:
            pd  = int((getattr(player, 'stats', None) or {}).get('Dexterity', 10))
            roll = random.randint(1, 16) + 12   # random(16)+12, SPUR range ~12-27
            if pd > roll:
                await ctx.send('Whew!  You are dextrous enough to avoid the poisoned stickers!')
            else:
                await ctx.send('Akk!  You prick your finger!')
                await ctx.send('Poison!!')
                hp = int(getattr(player, 'hit_points', 1) or 1)
                player.hit_points = max(0, hp - 5)
                player.unsaved_changes = True
                from survival import apply_poison
                apply_poison(player)
            # item still picked up regardless

        # --- Fireball: burns non-Wizards unless gauntlets are worn (SPUR.WEAPON.S:30) ---
        if item_id in _FIREBALL_IDS:
            from base_classes import PlayerClass
            if getattr(player, 'char_class', None) != PlayerClass.WIZARD:
                gauntlets = (inventory.find(item_id=_GAUNTLETS_ID)
                             if inventory else None)
                if gauntlets:
                    await ctx.send('THE GAUNTLETS TAKE THE HEAT..')
                    if random.randint(1, 10) == 1:
                        inventory.remove(gauntlets.item)
                        await ctx.send('THE GAUNTLETS ARE DESTROYED!!')
                else:
                    dmg = random.randint(1, 4)
                    hp  = int(getattr(player, 'hit_points', 1) or 1)
                    player.hit_points = max(0, hp - dmg)
                    player.unsaved_changes = True
                    await ctx.send(f'Yelp!  You burn your fingers!  (-{dmg} HP)')

        if inventory is not None:
            inventory.add(entry.item,
                          quantity=getattr(entry, 'quantity', 1),
                          charges=entry.charges)

        remove_fn()
        await ctx.send(f'You pick up {name}.')

        # --- Staff: Wizards get a reminder that it enhances spellcasting (SPUR.MISC3.S:47) ---
        if item_id in _STAFF_IDS:
            from base_classes import PlayerClass
            if getattr(player, 'char_class', None) == PlayerClass.WIZARD:
                await ctx.send('(This staff will enhance your spell casting!)')

        return CommandResult.ok()
