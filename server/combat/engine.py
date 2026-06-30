"""combat/engine.py — Async combat loop.

Owns all I/O (ctx.send / ctx.send_room) and state mutation.
Delegates all math to resolution.py, which is pure and testable.

Entry point:

    session = CombatSession(monster_dict, room_no=ctx.client.room)
    await session.start(ctx)

    # Later, a bystander types "attack goblin":
    await session.join(bystander_ctx)

    # Player types "flee":
    fled = await session.flee(ctx)

A CombatSession is stored per room in server.active_combats so that
additional players can join mid-fight.  It is removed from that dict
when the monster dies or all players have fled/died.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional, TYPE_CHECKING

from combat.resolution import (
    AttackResult,
    player_attacks,
    monster_attacks,
    ally_attacks,
    flee_attempt,
    assemble_zu_zv,
    check_special_weapon,
)
from combat.rewards import gold_from_monster, exp_per_swing

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player_name(ctx: 'GameContext') -> str:
    return getattr(ctx.player, 'name', 'Someone')


def _weapon_class_str(weapon) -> str:
    wc = getattr(weapon, 'weapon_class', None)
    if wc is None:
        return 'hack_slash_bash'
    return wc.value if hasattr(wc, 'value') else str(wc)


def _class_race_strs(player) -> tuple[str, str]:
    cls  = getattr(player, 'char_class', None)
    race = getattr(player, 'char_race',  None)
    cls_str  = (cls.value  if hasattr(cls,  'value') else str(cls))  if cls  else 'Fighter'
    race_str = (race.value if hasattr(race, 'value') else str(race)) if race else 'Human'
    return cls_str, race_str


def _room_ctxs(ctx: 'GameContext', exclude: Optional['GameContext'] = None) -> list['GameContext']:
    """All GameContext objects in the same room as *ctx*, optionally excluding one."""
    room_no = getattr(ctx.client, 'room', None)
    if room_no is None:
        return []
    result = []
    for client in ctx.server.clients.values():
        c_ctx = getattr(client, 'ctx', None)
        if c_ctx is None or c_ctx is exclude:
            continue
        if getattr(client, 'room', None) == room_no:
            result.append(c_ctx)
    return result


def _award_weapon_exp(ctx: 'GameContext', weapon_id: int) -> None:
    """Award one point of battle exp to player for weapon_id."""
    try:
        ctx.player.gain_weapon_experience(weapon_id)
    except Exception:
        log.exception('_award_weapon_exp: error awarding exp to %s', _player_name(ctx))


def _add_exp(ctx: 'GameContext', amount: int) -> None:
    """Add experience points to the player."""
    player = ctx.player
    player.experience = int(getattr(player, 'experience', 0) or 0) + amount
    player.unsaved_changes = True


def _record_kill(player, monster: dict) -> None:
    """Record the monster ID in player.monsters_killed (no duplicates)."""
    mid = monster.get('number') or monster.get('id_number') or monster.get('id')
    if mid is None:
        return
    mk = getattr(player, 'monsters_killed', None)
    if isinstance(mk, list) and mid not in mk:
        mk.append(mid)
        player.unsaved_changes = True


def _give_silver(player, amount: int) -> None:
    from base_classes import PlayerMoneyTypes
    try:
        kind = PlayerMoneyTypes.IN_HAND
        current = player.get_silver(kind)
        player.set_silver_absolute(kind, current + amount)
        player.unsaved_changes = True
    except Exception:
        log.exception('_give_silver: error giving %d silver', amount)


def _monster_hp(monster: dict) -> int:
    return int(monster.get('strength') or monster.get('hit_points') or 5)


def _set_monster_hp(monster: dict, hp: int) -> None:
    if 'strength' in monster:
        monster['strength'] = hp
    elif 'hit_points' in monster:
        monster['hit_points'] = hp


# ---------------------------------------------------------------------------
# CombatSession
# ---------------------------------------------------------------------------

class CombatSession:
    """A live fight between one or more players and a single monster.

    Lifecycle:
        session = CombatSession(monster, room_no)
        server.active_combats[room_no] = session
        await session.start(ctx)          # blocks until combat ends
        del server.active_combats[room_no]
    """

    def __init__(self, monster: dict, room_no: int):
        # Work on a copy so we don't mutate the server's monster template.
        self.monster   = dict(monster)
        self.room_no   = room_no
        self.leader    : Optional[GameContext] = None
        # All contexts that have attacked at least once this fight.
        self.attackers : list[GameContext] = []
        self._done     = asyncio.Event()
        self._lock     = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, ctx: 'GameContext') -> None:
        """Initiate combat and run the full turn loop for the leader."""
        self.leader = ctx
        await self._join_attacker(ctx)
        await self._run_loop(ctx)

    async def join(self, ctx: 'GameContext') -> None:
        """A bystander joins mid-fight (they typed 'attack <monster>')."""
        if self._done.is_set():
            await ctx.send('That monster is already dead.')
            return
        await self._join_attacker(ctx)
        # Bystanders fire one swing then wait; the leader's loop drives the fight.
        async with self._lock:
            if self._done.is_set():
                return
            result = self._swing(ctx)
            _add_exp(ctx, exp_per_swing())
            await self._narrate_player_swing(ctx, result, bystander=True)
            _set_monster_hp(self.monster, _monster_hp(self.monster) - result.damage)
            if result.weapon_id:
                _award_weapon_exp(ctx, result.weapon_id)
            if _monster_hp(self.monster) <= 0:
                await self._monster_dies(ctx)

    async def flee(self, ctx: 'GameContext') -> bool:
        """Attempt to flee.  Returns True if the player escaped."""
        if self._done.is_set():
            return True
        result = flee_attempt(ctx.player, self.monster, monster_is_following=True)
        if result.blocked_by_monster:
            mname = self.monster.get('name', 'The monster')
            await ctx.send(f'{mname} blocks your escape!')
            return False

        # Pick a random navigable exit and move the player there.
        direction = self._random_exit(ctx)
        if direction:
            await ctx.send(f'You flee {direction}!')
        else:
            await ctx.send('You manage to escape!')
        await ctx.send_room(f'{_player_name(ctx)} flees the battle!', exclude_self=True)
        self._remove_attacker(ctx)
        if not self.attackers:
            self._done.set()
        if direction:
            await ctx.server._move(ctx, direction)
        return True

    def _random_exit(self, ctx: 'GameContext') -> str | None:
        """Return a random navigable exit direction from the player's current room, or None."""
        import random
        room_no = getattr(ctx.client, 'room', None)
        game_map = getattr(ctx.server, 'game_map', None)
        room = game_map.rooms.get(int(room_no)) if game_map and room_no else None
        if not room:
            return None
        exits = getattr(room, 'exits', {}) or {}
        choices = [d for d, dest in exits.items() if dest]
        return random.choice(choices) if choices else None

    # ------------------------------------------------------------------
    # Internal: turn loop
    # ------------------------------------------------------------------

    async def _run_loop(self, ctx: 'GameContext') -> None:
        """Main per-leader combat loop.  Runs until monster dies, player dies, or fled."""
        mname = self.monster.get('name', 'monster')
        player = ctx.player

        await ctx.send(f'Combat begins!  You face the {mname}!')
        await ctx.send_room(
            f'{_player_name(ctx)} attacks the {mname}!',
            exclude_self=True,
        )

        while not self._done.is_set():
            # ---- player prompt ----
            raw = await ctx.prompt(
                f'[A]ttack  [F]lee  (HP:{getattr(player, "hit_points", "?")}'
                f'  {mname} HP:{_monster_hp(self.monster)})',
            )
            if raw is None:
                # Client disconnected mid-fight
                break

            cmd = (raw.strip().lower() or 'a')[0]

            if cmd == 'f':
                fled = await self.flee(ctx)
                if fled:
                    return
                continue

            # Default: attack
            async with self._lock:
                if self._done.is_set():
                    break

                # Player swings — +1 ep per attempt (SPUR.COMBAT.S line 103)
                result = self._swing(ctx)
                _add_exp(ctx, exp_per_swing())
                await self._narrate_player_swing(ctx, result)
                _set_monster_hp(self.monster, _monster_hp(self.monster) - result.damage)
                if result.weapon_id:
                    _award_weapon_exp(ctx, result.weapon_id)
                    # Bystanders in the attacker list also get exp for this weapon
                    for b_ctx in self.attackers:
                        if b_ctx is not ctx and result.weapon_id:
                            _award_weapon_exp(b_ctx, result.weapon_id)

                if _monster_hp(self.monster) <= 0:
                    await self._monster_dies(ctx)
                    return

                # Ally swings (party members)
                await self._ally_swings(ctx)

                if _monster_hp(self.monster) <= 0:
                    await self._monster_dies(ctx)
                    return

                # Monster swings back at leader
                m_result = monster_attacks(self.monster, player)
                await self._narrate_monster_swing(ctx, m_result)
                self._apply_monster_damage(ctx, m_result)

                if getattr(player, 'hit_points', 1) <= 0:
                    await self._player_dies(ctx)
                    return

    # ------------------------------------------------------------------
    # Internal: single swing
    # ------------------------------------------------------------------

    def _swing(self, ctx: 'GameContext') -> AttackResult:
        """Compute one player attack swing."""
        player  = ctx.player
        weapon  = getattr(player, 'readied_weapon', None)
        cls_str, race_str = _class_race_strs(player)
        class_to_hit = class_damage = 0
        if weapon:
            try:
                from item_system import weapon_bonus
                class_to_hit, class_damage = weapon_bonus(weapon, cls_str, race_str)
            except Exception:
                pass
        weapons_data = getattr(ctx.server, 'weapons', None) or []
        return player_attacks(
            player, weapon, self.monster,
            class_to_hit=class_to_hit,
            class_damage=class_damage,
            weapons_data=weapons_data,
        )

    # ------------------------------------------------------------------
    # Internal: ally swings
    # ------------------------------------------------------------------

    async def _ally_swings(self, ctx: 'GameContext') -> None:
        """Each live ally in the player's party attacks the monster once."""
        try:
            from bar.ally_data import Ally, AllyFlags, AllyStatus
        except ImportError:
            return

        party = getattr(ctx.player, 'party', None)
        if not party:
            return

        for member in party:
            if not isinstance(member, Ally):
                continue
            if getattr(member, 'status', None) in (AllyStatus.DEAD, AllyStatus.UNCONSCIOUS):
                continue
            hp = getattr(member, 'hit_points', 0)
            if hp <= 0:
                continue

            has_light = AllyFlags.ELITE in (member.flags or [])
            result = ally_attacks(
                member.name,
                member.strength,
                self.monster,
                has_light_armor=has_light,
            )
            if result.hit:
                dmg = result.damage
                await ctx.send(f'{member.name} strikes for {dmg} damage!')
                await ctx.send_room(
                    f'{member.name} strikes the {self.monster.get("name", "monster")} for {dmg} damage!',
                    exclude_self=True,
                )
                _set_monster_hp(self.monster, _monster_hp(self.monster) - dmg)
                if _monster_hp(self.monster) <= 0:
                    return
            else:
                await ctx.send(f'{member.name} misses!')

    # ------------------------------------------------------------------
    # Internal: narration
    # ------------------------------------------------------------------

    async def _narrate_player_swing(
        self, ctx: 'GameContext', result: AttackResult, bystander: bool = False
    ) -> None:
        mname = self.monster.get('name', 'the monster')
        pname = _player_name(ctx)

        if result.ease_helped:
            await ctx.send('(Ease of use helps!)')

        if result.instant_kill:
            msg  = f'Fire flashes from the {result.weapon_name}!  The {mname} is destroyed!'
            room = f'Fire flashes from {pname}\'s {result.weapon_name}!  The {mname} is destroyed!'
        elif result.ineffective:
            msg  = f'The {result.weapon_name} is ineffective against the {mname}!'
            room = f'{pname}\'s {result.weapon_name} is ineffective against the {mname}!'
        elif result.hit:
            crit = '  CRITICAL HIT!' if result.is_critical else ''
            surp = '  (Surprise!)' if result.is_surprise else ''
            msg  = f'You strike the {mname} for {result.damage} damage!{crit}{surp}'
            room = f'{pname} strikes the {mname} for {result.damage} damage!{crit}'
        else:
            msg  = f'You miss the {mname}.'
            room = f'{pname} misses the {mname}.'

        await ctx.send(msg)
        if bystander:
            await ctx.send_room(room, exclude_self=True)
        else:
            # Leader's send_room is already addressed to the whole room
            others = _room_ctxs(ctx, exclude=ctx)
            for other in others:
                await other.send(room)

    async def _narrate_monster_swing(
        self, ctx: 'GameContext', result
    ) -> None:
        mname = self.monster.get('name', 'The monster')

        if not result.hit:
            await ctx.send(f'{mname} misses you.')
            await ctx.send_room(f'{mname} misses {_player_name(ctx)}.', exclude_self=True)
            return

        lines = []
        if result.shield_blocked:
            lines.append(f'Your shield absorbs {result.shield_blocked} damage.')
            if result.shield_destroyed:
                lines.append('|red|Your shield is destroyed!|reset|')
            elif result.shield_degraded:
                lines.append(f'Your shield condition drops by {result.shield_degraded}%.')
        if result.armor_blocked:
            lines.append(f'Your armor absorbs {result.armor_blocked} damage.')
            if result.armor_destroyed:
                lines.append('|red|Your armor is destroyed!|reset|')
            elif result.armor_degraded:
                lines.append(f'Your armor condition drops by {result.armor_degraded}%.')
        lines.append(f'{mname} hits you for {result.damage} damage!')
        if result.poisoned:
            lines.append('|yellow|You feel a burning sensation -- you have been POISONED!|reset|')
        if result.diseased:
            lines.append('|yellow|You feel sick -- you have been DISEASED!|reset|')

        await ctx.send(lines)
        await ctx.send_room(
            f'{mname} hits {_player_name(ctx)} for {result.damage} damage!',
            exclude_self=True,
        )

    # ------------------------------------------------------------------
    # Internal: state mutation after outcomes
    # ------------------------------------------------------------------

    def _apply_monster_damage(self, ctx: 'GameContext', result) -> None:
        """Apply monster-attack damage and degradation to the player."""
        player = ctx.player
        if not result.hit:
            return

        # Shield degradation
        if result.shield_destroyed:
            player.shield = 0
        elif result.shield_degraded:
            player.shield = max(0, int(getattr(player, 'shield', 0) or 0) - result.shield_degraded)
        player.unsaved_changes = True

        # Armor degradation
        if result.armor_destroyed:
            player.armor = 0
        elif result.armor_degraded:
            player.armor = max(0, int(getattr(player, 'armor', 0) or 0) - result.armor_degraded)

        # HP loss
        hp = int(getattr(player, 'hit_points', 1) or 1)
        player.hit_points = hp - result.damage
        player.unsaved_changes = True

    async def _monster_dies(self, ctx: 'GameContext') -> None:
        """Handle monster death: rewards, records, cleanup."""
        self._done.set()
        mname = self.monster.get('name', 'The monster')

        await ctx.send(f'|green|You have slain the {mname}!|reset|')
        await ctx.send_room(
            f'{_player_name(ctx)} slays the {mname}!',
            exclude_self=True,
        )

        # Gold loot (probability + amount from rewards.py / SPUR.MISC.S p.a4)
        player = ctx.player
        gold = gold_from_monster(self.monster)
        if gold:
            _give_silver(player, gold)
            await ctx.send(f'You find {gold} gold pieces on the {mname}!')

        _record_kill(player, self.monster)

        # Notify bystanders of the kill (they earned exp per-swing already)
        for b_ctx in self.attackers:
            if b_ctx is ctx:
                continue
            await b_ctx.send(f'|green|{mname} is slain!|reset|')

    async def _player_dies(self, ctx: 'GameContext') -> None:
        """Handle player death during combat."""
        self._done.set()
        mname = self.monster.get('name', 'the monster')
        await ctx.send([
            f'|red|You have been slain by the {mname}!|reset|',
            'Your adventure ends here...',
        ])
        await ctx.send_room(
            f'|red|{_player_name(ctx)} has been slain by the {mname}!|reset|',
            exclude_self=True,
        )
        # Mark player dead (caller handles disconnect/respawn flow)
        ctx.player.hit_points = 0
        ctx.player.unsaved_changes = True

    # ------------------------------------------------------------------
    # Internal: participant tracking
    # ------------------------------------------------------------------

    async def _join_attacker(self, ctx: 'GameContext') -> None:
        if ctx not in self.attackers:
            self.attackers.append(ctx)

    def _remove_attacker(self, ctx: 'GameContext') -> None:
        if ctx in self.attackers:
            self.attackers.remove(ctx)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

async def enter_combat(ctx: 'GameContext', monster: dict) -> None:
    """Start a CombatSession for *ctx* against *monster*.

    Stores the session in server.active_combats[room_no] so bystanders
    can join with join_combat().  Cleans up on completion.
    """
    room_no = getattr(ctx.client, 'room', None)

    # Ensure active_combats dict exists on server
    if not hasattr(ctx.server, 'active_combats'):
        ctx.server.active_combats = {}

    if room_no in ctx.server.active_combats:
        existing = ctx.server.active_combats[room_no]
        if not existing._done.is_set():
            await ctx.send('There is already a fight in progress here — joining!')
            await existing.join(ctx)
            return

    session = CombatSession(monster, room_no)
    if room_no is not None:
        ctx.server.active_combats[room_no] = session

    try:
        await session.start(ctx)
    finally:
        if room_no is not None and ctx.server.active_combats.get(room_no) is session:
            del ctx.server.active_combats[room_no]


async def join_combat(ctx: 'GameContext') -> bool:
    """Try to join an active fight in the player's room.

    Returns True if a fight was found and joined, False if the room is quiet.
    """
    room_no = getattr(ctx.client, 'room', None)
    active  = getattr(ctx.server, 'active_combats', {})
    session = active.get(room_no)
    if session and not session._done.is_set():
        await session.join(ctx)
        return True
    return False
