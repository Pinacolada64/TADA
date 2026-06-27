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

    Ally members round-trip fully.  Player-in-party members are saved by
    name/id but not restored on load (they rejoin when they log back in).
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
                    result.append({
                        'type':       'ally',
                        'name':       m.name,
                        'gender':     gender_str,
                        'strength':   m.strength,
                        'to_hit':     m.to_hit,
                        'flags':      [f.name for f in (m.flags or [])],
                        'hit_points': m.hit_points,
                        'status':     m.status.name if hasattr(m.status, 'name') else 'FREE',
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
    def from_json(cls, data: list) -> 'Party':
        """Reconstruct a Party from the JSON list produced by to_json()."""
        if not isinstance(data, list):
            return cls()
        members = []
        for item in data:
            if not isinstance(item, dict):
                continue
            member_type = item.get('type')
            try:
                if member_type == 'ally':
                    from bar.ally_data import Ally, AllyFlags, AllyStatus
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
                    status_name = item.get('status', 'FREE')
                    if status_name in AllyStatus.__members__:
                        ally.status = AllyStatus[status_name]
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
