"""party.py — Party management for players and their allies/companions."""
import logging

log = logging.getLogger(__name__)


class Party:
    """Holds a player's party members and provides sync/async management methods.

    Implements the list interface (__iter__, __len__, __bool__, __contains__,
    __getitem__) so existing code that iterates or checks truthiness of
    player.party continues to work without modification.

    Serialization
    -------------
    ``to_json()``   → list[dict]   (store under the ``"party"`` key in player JSON)
    ``from_json()`` → Party        (call in Player.__init__ with kwargs.get('party', []))

    Ally members round-trip fully, including items/weapon/ammo given via
    GIVE.  Player-in-party members are saved by name/id but not restored
    on load (they rejoin when they log back in).
    """

    def __init__(self, members=None):
        self.members: list = list(members) if members else []

    # ------------------------------------------------------------------
    # List-like interface
    # ------------------------------------------------------------------

    def __iter__(self):
        return iter(self.members)

    def __len__(self):
        return len(self.members)

    def __bool__(self):
        return bool(self.members)

    def __contains__(self, item):
        return item in self.members

    def __getitem__(self, idx):
        return self.members[idx]

    def __repr__(self):
        names = [getattr(m, 'name', repr(m)) for m in self.members]
        return f"Party([{', '.join(names)}])"

    # ------------------------------------------------------------------
    # Sync primitives (no I/O — safe to call from legacy sync code)
    # ------------------------------------------------------------------

    def add_member(self, owner, member) -> tuple[bool, str | None]:
        """Validate and add *member* to this party.

        Returns (success, message) so callers can display the message via
        their preferred output method (ctx.send, player.output, etc.).
        """
        if member is owner:
            return False, (f"This is getting a bit surreal. "
                           f"You can't add {owner.name} to {owner.name}'s party.")
        if member in self.members:
            return False, (f"Seeing another {member.name} is already in your party, "
                           f"they turn sadly away.")
        self.members.append(member)
        log.debug("Party.add_member: %s joined %s's party", member.name, owner.name)
        return True, f"{member.name} joins {owner.name}'s party!"

    def is_member(self, member) -> bool:
        return member in self.members

    def remove(self, member) -> bool:
        if member in self.members:
            self.members.remove(member)
            log.debug("Party.remove: %s removed", getattr(member, 'name', member))
            return True
        return False

    # ------------------------------------------------------------------
    # JSON serialization
    # ------------------------------------------------------------------

    def to_json(self) -> list[dict]:
        """Serialize party members to a JSON-safe list of dicts."""
        result = []
        for m in self.members:
            try:
                from bar.ally_data import Ally
                if isinstance(m, Ally):
                    gender_str = 'm' if getattr(m.gender, 'name', '') == 'MALE' else 'f'
                    readied_weapon = getattr(m, 'readied_weapon', None)
                    weapon_dict = None
                    if readied_weapon is not None:
                        weapon_dict = {
                            'item_id':       getattr(readied_weapon, 'id_number', None),
                            'item_name':     getattr(readied_weapon, 'name', ''),
                            'item_category': str(getattr(readied_weapon, 'category', '')),
                            'item_flags':    getattr(readied_weapon, 'flags', None) or [],
                        }

                    def _worn_dict(worn):
                        if worn is None:
                            return None
                        d = {
                            'item_id':       getattr(worn, 'id_number', None),
                            'item_name':     getattr(worn, 'name', ''),
                            'item_category': str(getattr(worn, 'category', '')),
                            'item_flags':    getattr(worn, 'flags', None) or [],
                        }
                        item_type = getattr(worn, 'type', None)
                        if item_type:
                            d['item_type'] = str(item_type)
                        condition = getattr(worn, 'condition', None)
                        if condition is not None:
                            d['item_condition'] = condition
                        return d

                    armor_dict  = _worn_dict(getattr(m, 'readied_armor',  None))
                    shield_dict = _worn_dict(getattr(m, 'readied_shield', None))
                    result.append({
                        'type':           'ally',
                        'name':           m.name,
                        'gender':         gender_str,
                        'strength':       m.strength,
                        'to_hit':         m.to_hit,
                        'flags':          [f.name for f in (m.flags or [])],
                        'hit_points':     m.hit_points,
                        'status':         m.status.name if hasattr(m.status, 'name') else 'FREE',
                        'position':       m.position.name if hasattr(m.position, 'name') else 'EMPTY',
                        'breed':          m.breed.name if getattr(m, 'breed', None) else None,
                        'color':          m.color.name if getattr(m, 'color', None) else None,
                        # Items given via GIVE (commands/give.py) -- see
                        # inventory.InventoryEntry.to_json() for the format.
                        # Previously dropped on every save, so anything
                        # handed to an ally vanished on the next login.
                        'items':          [e.to_json() for e in (getattr(m, 'items', None) or [])],
                        'readied_weapon': weapon_dict,
                        'ammo_rounds':    getattr(m, 'ammo_rounds', 0),
                        'ammo_max':       getattr(m, 'ammo_max', 0),
                        'ammo_damage':    getattr(m, 'ammo_damage', 0),
                        'readied_armor':  armor_dict,
                        'readied_shield': shield_dict,
                        # Only non-None while status == BOLTED, see
                        # bar/ally_data.py's Ally.bolt_room_no docstring.
                        'bolt_room_no':   getattr(m, 'bolt_room_no', None),
                        'bolt_map_level': getattr(m, 'bolt_map_level', None),
                        'bolt_at_water':  getattr(m, 'bolt_at_water', False),
                    })
                    continue
            except ImportError:
                pass
            # Player members: save identity only; they rejoin on next login
            result.append({
                'type': 'player',
                'id':   getattr(m, 'id',   None),
                'name': getattr(m, 'name', str(m)),
            })
        return result

    @classmethod
    def from_json(cls, data: list, weapons_data: list | None = None) -> 'Party':
        """Reconstruct a Party from the JSON list produced by to_json().

        *weapons_data* is the server's raw weapons.json list (see
        items.resolve_weapon()), needed to fully resolve a readied weapon
        or a weapon handed to an ally via GIVE -- same plumbing as
        Inventory.from_json()'s weapons_data param.
        """
        if not isinstance(data, list):
            return cls()
        members = []
        for item in data:
            if not isinstance(item, dict):
                continue
            member_type = item.get('type')
            try:
                if member_type == 'ally':
                    from bar.ally_data import Ally, AllyFlags, AllyPosition, AllyStatus
                    from base_classes import HorseBreed, HorseColor
                    from inventory import Inventory
                    flags = [
                        AllyFlags[n] for n in item.get('flags', [])
                        if n in AllyFlags.__members__
                    ]
                    ally = Ally(
                        item['name'],
                        item.get('gender', 'm'),
                        item.get('strength', 1),
                        item.get('to_hit', 1),
                        flags,
                    )
                    ally.hit_points = item.get('hit_points', 0)
                    breed_name = item.get('breed')
                    if breed_name in HorseBreed.__members__:
                        ally.breed = HorseBreed[breed_name]
                    color_name = item.get('color')
                    if color_name in HorseColor.__members__:
                        ally.color = HorseColor[color_name]
                    status_name = item.get('status', 'FREE')
                    if status_name in AllyStatus.__members__:
                        ally.status = AllyStatus[status_name]
                    position_name = item.get('position', 'EMPTY')
                    if position_name in AllyPosition.__members__:
                        ally.position = AllyPosition[position_name]
                    ally.bolt_room_no   = item.get('bolt_room_no')
                    ally.bolt_map_level = item.get('bolt_map_level')
                    ally.bolt_at_water  = bool(item.get('bolt_at_water', False))

                    # Items given via GIVE (see to_json() above and
                    # commands/give.py). Reuse Inventory.from_json()'s item
                    # reconstruction rather than duplicating it here.
                    items_data = item.get('items') or []
                    ally.items = list(
                        Inventory.from_json(items_data, weapons_data=weapons_data).entries()
                    )
                    weapon_data = item.get('readied_weapon')
                    if weapon_data:
                        weapon_entries = Inventory.from_json(
                            [weapon_data], weapons_data=weapons_data
                        ).entries()
                        if weapon_entries:
                            ally.readied_weapon = weapon_entries[0].item
                    ally.ammo_rounds = item.get('ammo_rounds', 0)
                    ally.ammo_max = item.get('ammo_max', 0)
                    ally.ammo_damage = item.get('ammo_damage', 0)

                    for slot in ('armor', 'shield'):
                        worn_data = item.get(f'readied_{slot}')
                        if worn_data:
                            worn_entries = Inventory.from_json(
                                [worn_data], weapons_data=weapons_data
                            ).entries()
                            if worn_entries:
                                setattr(ally, f'readied_{slot}', worn_entries[0].item)

                    members.append(ally)
                elif member_type == 'player':
                    # Player members are not reconstructed on load; they
                    # rejoin automatically when they log back in.
                    log.info(
                        "Party.from_json: skipping player member %r (rejoins on login)",
                        item.get('name'),
                    )
            except Exception:
                log.exception("Party.from_json: failed to reconstruct member %r", item)
        return cls(members)

    # ------------------------------------------------------------------
    # Async methods (require a ctx for output)
    # ------------------------------------------------------------------

    async def add(self, ctx, owner, member) -> bool:
        """Add *member* to the party and send the result message via *ctx*."""
        success, msg = self.add_member(owner, member)
        if msg:
            await ctx.send(msg)
        return success

    async def list_members(self, ctx, owner_name: str) -> None:
        """Send the party roster to the player via *ctx*."""
        if not self.members:
            await ctx.send(f"There are no other members in {owner_name}'s party.")
            return
        lines = [f"Members of {owner_name}'s party:"]
        for i, m in enumerate(self.members, 1):
            lines.append(f"{i}. {getattr(m, 'name', str(m))}")
        await ctx.send(lines)
