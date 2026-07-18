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
import re
from pathlib import Path
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
from flags import PlayerFlags

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player_name(ctx: 'GameContext') -> str:
    return getattr(ctx.player, 'name', 'Someone')


# Monster-quote pools (SPUR.MISC4.S mon.ret / perm.qt): a monster picks a fixed
# quote if one is assigned (monster['quote_number']), otherwise a random one --
# aggressive taunt (1-52) normally, or a friendly greeting (61-71) if the
# player's race is thematically simpatico with the monster's alignment flag
# (Ogre/Half-Elf + an evil monster, or Pixie/Elf + a good monster).
_TAUNT_RANGE    = (1, 52)
_FRIENDLY_RANGE = (61, 71)
_FRIENDLY_EVIL_RACES = {'Ogre', 'Half-Elf'}
_FRIENDLY_GOOD_RACES = {'Pixie', 'Elf'}

_CRYSTAL_PENDANT_ID = 82   # objects.json -- blocks turn-to-stone (SPUR.MISC4.S)


def _pick_monster_quote(ctx: 'GameContext', monster: dict) -> Optional[str]:
    """Return a monster quote string (player name substituted for '$'), or None
    if no quotes are loaded."""
    quotes = getattr(ctx.server, 'monster_quotes', None) or {}
    if not quotes:
        return None

    quote_number = monster.get('quote_number')
    if not quote_number:
        m_flags = monster.get('flags', {}) or {}
        race = str(getattr(ctx.player, 'char_race', '') or '')
        friendly = ((m_flags.get('evil') and race in _FRIENDLY_EVIL_RACES) or
                    (m_flags.get('good') and race in _FRIENDLY_GOOD_RACES))
        lo, hi = _FRIENDLY_RANGE if friendly else _TAUNT_RANGE
        available = [n for n in range(lo, hi + 1) if n in quotes]
        if not available:
            return None
        quote_number = random.choice(available)

    text = quotes.get(quote_number)
    if not text:
        return None
    return text.replace('$', _player_name(ctx))


def _weapon_class_str(weapon) -> str:
    wc = getattr(weapon, 'weapon_class', None)
    if wc is None:
        return 'hack_slash_bash'
    return wc.value if hasattr(wc, 'value') else str(wc)


def _roll_charge_first_strike(player, monster: dict) -> bool:
    """Mounted first-strike roll (skip branch SPUR.COMBAT.S m.attack):

        a = rnd.10a; a -= 4 if projectile weapon else a += 4
        eligible if a + (monster_agility * 4) < player Dexterity

    Only called on the first exchange; determines CHARGE eligibility.
    """
    from combat.resolution import _WA
    weapon  = getattr(player, 'readied_weapon', None)
    wc_str  = _weapon_class_str(weapon)
    wa      = _WA.get(wc_str.lower(), 1)
    roll    = random.randint(1, 10)
    roll    = roll - 4 if wa == 5 else roll + 4   # wa=5: projectile ("POLE WEAPON" label in source)
    roll    = max(1, roll)
    ma      = int(monster.get('to_hit', 4) or 4)
    pd      = int((getattr(player, 'stats', None) or {}).get('Dexterity', 10))
    return roll + (ma * 4) < pd


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
    """Award one point of battle (weapon-specific) exp to player for weapon_id.

    SPUR.MISC.S:384 (`p.a3`, the monster-just-died cleanup routine) is the
    ONLY place `vp` is ever incremented in the whole source -- confirmed by
    grepping every .S file for `vp=vp+1` / `vp = vp+1`. There is no per-swing
    accrual; `ep` (general character XP, SPUR.COMBAT.S:103) is the per-swing
    counter and is a completely separate variable (see _add_exp()). Call
    this only from _monster_dies(), gated on player_killed, never per-swing.
    """
    try:
        ctx.player.gain_weapon_experience(weapon_id)
    except Exception:
        log.exception('_award_weapon_exp: error awarding exp to %s', _player_name(ctx))


async def _add_exp(ctx: 'GameContext', amount: int) -> None:
    """Add experience points; announce level-up if threshold crossed.

    SPUR.COMBAT.S line 9: if ep>(999+(xp*100)) xp=xp+1:ep=1:gosub lvl.msg
    Threshold grows by 100 per level, so level N requires 999+(N×100) to advance.
    """
    player = ctx.player
    player.experience = int(getattr(player, 'experience', 0) or 0) + amount
    player.unsaved_changes = True
    level = int(getattr(player, 'xp_level', 1) or 1)
    if player.experience > 999 + level * 100:
        player.xp_level    = level + 1
        player.experience  = 1
        player.unsaved_changes = True
        log.info('level_up: %s is now level %d', _player_name(ctx), player.xp_level)
        await ctx.send(f'Congratulations!  You are now a Level {player.xp_level} player!')


def _record_statue(monster_name: str, player_name: str) -> None:
    """Append player_name to a per-monster memorial file (SPUR.MISC6.S `statue`
    subroutine): dy$=dx$+m$ (stripping a leading "THE "), one victim name
    appended per line, never cleared. No I/O errors should interrupt combat,
    so failures are logged and swallowed.
    """
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None) or Path('./run/server')
        base = Path(base)
        statues_dir = base / 'statues'
        statues_dir.mkdir(parents=True, exist_ok=True)

        name = monster_name.strip()
        if name.upper().startswith('THE '):
            name = name[4:]
        safe_name = re.sub(r'[^A-Za-z0-9 _-]', '', name).strip() or 'unknown'

        path = statues_dir / f'{safe_name}.txt'
        with open(path, 'a') as f:
            f.write(f'{player_name}\n')
    except Exception:
        log.exception('_record_statue: failed to record %s petrified by %s', player_name, monster_name)


def first_statue_victim(monster_name: str) -> Optional[str]:
    """Return the first (oldest) name in *monster_name*'s memorial file, or
    None if it has none yet.

    SPUR.MAIN.S's `statue` subroutine (called from ply.locD:386 whenever a
    petrify monster is present in the room, alive or dead --
    `if (mw>0) or (md>0) then if instr("#",wy$) ... gosub statue`):
    `open #1, dy$:input #1,dy$:close` reads just the *first line* of the
    same per-monster memorial file _record_statue() writes, and shows it
    as "There is a statue of {name} here!" room dressing. Not a separate
    corpse/room-object system -- just a display of that monster's oldest
    victim, reusing the memorial file wherever the monster happens to be.
    """
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None) or Path('./run/server')
        base = Path(base)

        name = monster_name.strip()
        if name.upper().startswith('THE '):
            name = name[4:]
        safe_name = re.sub(r'[^A-Za-z0-9 _-]', '', name).strip() or 'unknown'

        path = base / 'statues' / f'{safe_name}.txt'
        if not path.exists():
            return None
        with open(path) as f:
            first_line = f.readline().strip()
        return first_line or None
    except Exception:
        log.exception('first_statue_victim: failed to read memorial for %s', monster_name)
        return None


def _apply_dex_change(player, delta: int) -> None:
    """Apply a DEX adjustment capped at [0, 25] (SPUR pd stat).  No I/O."""
    try:
        stats   = getattr(player, 'stats', None) or {}
        current = int(stats.get('Dexterity', 10) or 10)
        new_val = max(0, min(25, current + delta))
        if new_val != current:
            player.stats['Dexterity'] = new_val
            player.unsaved_changes = True
    except Exception:
        log.exception('_apply_dex_change: failed (delta=%d)', delta)


def _survival_warnings(player) -> list[str]:
    """Return hunger/thirst/faint warnings to display each combat round.

    SPUR.COMBAT.S lines 21-25 (shown each trip through advent):
      pe<7 → thirsty; pe<4 → very thirsty
      ps<7 → hungry;  ps<4 → very hungry
      (pe<3) or (ps<3) → becoming faint
    """
    food  = int(getattr(player, 'food',  20) or 20)
    drink = int(getattr(player, 'drink', 20) or 20)
    msgs: list[str] = []
    if drink < 7:
        msgs.append('You are thirsty.' + ('  VERY THIRSTY!' if drink < 4 else ''))
    if food < 7:
        msgs.append('You are hungry.' + ('  VERY HUNGRY!' if food < 4 else ''))
    if food < 3 or drink < 3:
        msgs.append('You are becoming faint!')
    return msgs


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


def _ammo_term(weapon_name: str) -> str:
    """Return the appropriate ammo noun for a weapon (singular)."""
    n = weapon_name.upper()
    if 'SLING' in n:
        return 'stone'
    if 'BLOWGUN' in n:
        return 'dart'
    if 'BOW' in n:
        return 'arrow'
    return 'bullet'


def _monster_hp(monster: dict) -> int:
    return int(monster.get('strength') or monster.get('hit_points') or 5)


def _set_monster_hp(monster: dict, hp: int) -> None:
    if 'strength' in monster:
        monster['strength'] = hp
    elif 'hit_points' in monster:
        monster['hit_points'] = hp


# Classic-sounding horse names for the 'R' random-name option (SPUR original
# has no equivalent -- mounts weren't gendered there at all). All 4-12
# characters, no punctuation, so they pass _prompt_horse_name()'s own rules.
_MALE_HORSE_NAMES = (
    'THUNDER', 'SHADOW', 'BLAZE', 'RANGER', 'SPIRIT',
    'MAJOR', 'TROOPER', 'STORM', 'BARON', 'DUKE',
    'CHAMPION', 'MAVERICK',
)
_FEMALE_HORSE_NAMES = (
    'BELLE', 'WILLOW', 'DAISY', 'SIERRA', 'MYSTIC',
    'HONEY', 'GINGER', 'PRINCESS', 'ANGEL', 'STARLIGHT',
    'CHERRY', 'MEADOW',
)


def _random_horse_name(gender: str) -> str:
    names = _FEMALE_HORSE_NAMES if gender == 'f' else _MALE_HORSE_NAMES
    return random.choice(names)


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
        # How many times the monster has attacked this fight (SPUR vu).
        # Used by: STORM asserts its will (vu<6) and scare check (vu<=1).
        self._monster_attack_count = 0
        # Mounted CHARGE: whether this round's first-strike roll succeeded
        # (skip branch SPUR.COMBAT.S m.attack instr("*MNT",ys$) branch).
        # Only ever True on the first exchange (monster_attack_count == 0).
        self._charge_eligible = False
        # Crystal Pendant (item #82): resolved once per encounter (SPUR.MISC4.S
        # mon.set/stone, called when the monster is first set up, not per
        # round) -- if it blocks, the monster can never attempt turn-to-stone
        # for the rest of this fight. See _check_crystal_pendant().
        self._turn_to_stone_blocked = False
        # First-strike bonus from encounters/monster.py's surprise roll
        # (SPUR.MISC4.S:85-96 -> SPUR.COMBAT.S zs=997). Set by enter_combat()
        # when the player has a matching player.pending_surprise; stays True
        # for the whole fight, same as SPUR's zs=997 is never reset mid-fight.
        self.is_surprise = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, ctx: 'GameContext') -> None:
        """Initiate combat and run the full turn loop for the leader."""
        self.leader = ctx
        await self._join_attacker(ctx)
        await self._run_loop(ctx)

    async def join(self, ctx: 'GameContext') -> None:
        """A bystander joins mid-fight (they typed 'attack <monster>').

        Also how an already-joined bystander takes their next swing --
        commands/attack.py calls this every time a bystander re-types
        'attack', not just the first time (see AttackCommand.execute()'s
        docstring note) -- so the room-join announcement only fires once,
        on the swing where they weren't already in self.attackers.
        """
        if self._done.is_set():
            await ctx.send('That monster is already dead.')
            return
        is_new_attacker = ctx not in self.attackers
        if is_new_attacker and self.leader is not None and self.leader is not ctx:
            mname = self.monster.get('name', 'the monster')
            await ctx.send_room(
                f'{_player_name(ctx)} joins {_player_name(self.leader)} in fighting the {mname}!',
                exclude_self=True,
            )
        await self._join_attacker(ctx)

        # Druid/Ranger passive taming (TADA original, not SPUR) -- checked
        # for bystanders too, same as the leader's per-round check.
        if await self._try_class_tame(ctx):
            return

        # Bystanders fire one swing then wait; the leader's loop drives the fight.
        async with self._lock:
            if self._done.is_set():
                return
            result = self._swing(ctx)
            await _add_exp(ctx, exp_per_swing())
            await self._narrate_player_swing(ctx, result, bystander=True)
            if result.ammo_used:
                bystander_player = ctx.player
                rounds = int(getattr(bystander_player, 'ammo_rounds', 0) or 0)
                bystander_player.ammo_rounds = max(0, rounds - 1)
                bystander_player.unsaved_changes = True
                if not result.hit:
                    await self._stray_round(ctx, result.weapon_name,
                                            weapon_id=result.weapon_id)
            _set_monster_hp(self.monster, _monster_hp(self.monster) - result.damage)
            if _monster_hp(self.monster) <= 0:
                await self._monster_dies(ctx)

    async def flee(self, ctx: 'GameContext') -> bool:
        """Attempt to flee.  Returns True if the player escaped."""
        if self._done.is_set():
            return True
        room_no   = getattr(ctx.client, 'room', None)
        game_map  = getattr(ctx.server, 'game_map', None)
        room      = game_map.rooms.get(int(room_no)) if game_map and room_no else None
        result    = flee_attempt(ctx.player, self.monster, monster_is_following=True, room=room)
        if result.impassable_room:
            await ctx.send("Can't flee from here.")
            return False
        if result.blocked_by_monster:
            mname = self.monster.get('name', 'The monster')
            await ctx.send(f'{mname} blocks your escape!')
            return False

        # Fleeing costs 1 energy (SPUR.COMBAT.S:76: pe=pe-1).
        player = ctx.player
        current_drink = int(getattr(player, 'drink', 0) or 0)
        player.drink = max(0, current_drink - 1)

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

    async def lasso(self, ctx: 'GameContext') -> bool:
        """Attempt to capture the monster as a mount ally (SPUR.USE.S "lasso").

        Only works against a monster whose name contains "HORSE"; requires an
        open party slot and no existing mount ally.  Returns True if captured
        (combat ends -- the horse is tamed, not killed).
        """
        if self._done.is_set():
            return False

        mname = self.monster.get('name', '')
        if 'HORSE' not in mname.upper():
            await ctx.send('You practice with the lasso.')
            return False

        if not await self._mount_slot_available(ctx, verbose=True):
            return False

        await ctx.send('You capture the horse!')
        return await self._finalize_mount_capture(ctx)

    async def _mount_slot_available(self, ctx: 'GameContext', *, verbose: bool) -> bool:
        """True if ctx.player has room for a new mount ally.

        verbose=True sends the usual refusal message on failure (used by the
        explicit LASSO command); verbose=False stays silent (used by the
        passive Druid/Ranger taming check, which shouldn't spam a message
        every round just because the player's party happens to be full).
        """
        from bar.ally_data import AllyFlags
        from bar.allies import owned_allies

        allies = owned_allies(ctx.player)
        if len(allies) >= 3:
            if verbose:
                await ctx.send('Only 3 allies allowed, use ORDER to dismiss one.')
            return False
        if any(AllyFlags.MOUNT in (a.flags or []) for a in allies):
            if verbose:
                await ctx.send('Only 1 mount per customer.')
            return False
        return True

    async def _finalize_mount_capture(self, ctx: 'GameContext') -> bool:
        """Prompt for a horse name and, if given, add it as a MOUNT ally.

        Shared tail end of both LASSO and the passive Druid/Ranger taming
        event -- ends combat and removes ctx from the attacker list on
        success. Returns True if the horse was actually captured.
        """
        from bar.ally_data import Ally, AllyFlags, AllyStatus

        player = ctx.player

        # SPUR never tracked a mount's own gender (lasso.b stores mounts as
        # packed name+flag strings with no gender slot, so its flavor text
        # just always says "he"/"him") -- this port gives Ally a real
        # .gender field, so roll it for real instead of hardcoding male.
        gender = random.choice(('m', 'f'))
        await ctx.send(f"Your horse seems to be a {'male' if gender == 'm' else 'female'}.")

        name = await self._prompt_horse_name(ctx, gender)
        if name is None:
            return False

        # SPUR lasso.b: ms (monster strength) + 5, h1=0 -- unlike a purchased
        # ally, a freshly-lassoed mount starts with unseeded hit_points.
        strength = _monster_hp(self.monster) + 5
        mount = Ally(name=name, gender=gender, strength=strength, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        mount.status     = AllyStatus.SERVANT
        mount.owner      = player.name
        mount.hit_points  = 0
        # Party has no .append() -- it's not a plain list (see party.py's
        # add_member()/add()). Discovered live: unit tests fake player.party
        # as a bare list, which masked this raising AttributeError against a
        # real Player for every real capture attempt.
        player.party.add_member(player, mount)
        player.unsaved_changes = True

        await ctx.send(f'{name} joins your party as a mount!')
        # SPUR.USE.S lasso.b: appends a MOUNT entry to battle.log.
        import net_common
        net_common.append_battle_log(f'{player.name} got a mount!  Name of the mount - {name}')

        self._done.set()
        self._remove_attacker(ctx)
        return True

    # Per-round chance (not a guaranteed capture like LASSO): Druids and
    # Rangers, being especially attuned to animals, may simply win a wild
    # horse's trust mid-fight -- a TADA original mechanic, not from SPUR.
    async def _try_class_tame(self, ctx: 'GameContext') -> bool:
        """Give a Druid/Ranger a per-round chance to tame a wild horse
        outright, without needing LASSO. Silent no-op for any other class,
        any other monster, or if the player has no room for a new mount.
        Returns True if the horse was tamed (combat ends).
        """
        if self._done.is_set():
            return False

        mname = self.monster.get('name', '')
        if 'HORSE' not in mname.upper():
            return False

        from base_classes import PlayerClass
        player = ctx.player
        if getattr(player, 'char_class', None) not in (PlayerClass.DRUID, PlayerClass.RANGER):
            return False

        if not await self._mount_slot_available(ctx, verbose=False):
            return False

        if random.randint(1, 100) > 15:   # 15% chance per round
            return False

        from base_classes import Gender
        title = 'mistress' if getattr(player, 'gender', None) == Gender.FEMALE else 'master'
        await ctx.send(
            f'A certain look passes between the two of you, and the horse '
            f'seems to accept you as its {title}!'
        )
        return await self._finalize_mount_capture(ctx)

    async def _prompt_horse_name(self, ctx: 'GameContext', gender: str = 'm') -> str | None:
        """Prompt for a horse name (4-12 chars, no symbols).  None on cancel.

        'R' picks a random gender-appropriate name (mirrors 'R' for a random
        pronounceable password in commands/new_player.py's character
        creation) -- checked before the length/forbidden-char rules so a
        bare 'R' doesn't get rejected as "too short".
        """
        _FORBIDDEN = set('!@#$%^&*()_-+=[{]}\\|:;<,>.?/')
        while True:
            raw = await ctx.prompt("Name your horse (4-12 chars, 'R' for random, Enter to cancel)")
            if not raw or not raw.strip():
                return None
            name = raw.strip()
            if name.upper() == 'R':
                name = _random_horse_name(gender)
                await ctx.send(f'Random name chosen: {name}')
                return name
            if len(name) < 4 or len(name) > 12:
                await ctx.send('Name must be 4-12 characters.')
                continue
            bad = _FORBIDDEN.intersection(name)
            if bad:
                await ctx.send(f'"{next(iter(bad))}" not allowed in name.')
                continue
            return name

    async def _check_crystal_pendant(self, ctx: 'GameContext') -> None:
        """Crystal Pendant (item #82): if the monster can cast turn-to-stone
        and the player carries the pendant, roll once (not per-round) for
        whether it blocks that ability for the rest of this encounter.

        SPUR.MISC4.S mon.set/stone: 90% chance ("The CRYSTAL PENDANT flashes,
        preventing TURN TO STONE by <monster>!") permanently disables the
        monster's turn-to-stone for this fight; 10% chance the monster
        "happens to see" the pendant and counters it this one time (turn-to-
        stone remains possible for the rest of the fight either way).
        """
        if not (self.monster.get('flags', {}) or {}).get('petrify'):
            return
        player = ctx.player
        inventory = getattr(player, 'inventory', None)
        if not inventory or not inventory.find(item_id=_CRYSTAL_PENDANT_ID):
            return

        mname = self.monster.get('name', 'The monster')
        if random.randint(1, 10) != 5:
            self._turn_to_stone_blocked = True
            await ctx.send(f'The CRYSTAL PENDANT flashes, preventing TURN TO STONE by {mname}!')
        else:
            await ctx.send([
                f'{mname} happens to see you are',
                'wearing the CRYSTAL PENDANT, and',
                'quickly puts on ANTI-CRYSTAL PENDANT',
                'glasses!',
            ])

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

        # Monster taunt/greeting (SPUR.MISC4.S mon.ret/perm.qt)
        quote = _pick_monster_quote(ctx, self.monster)
        if quote:
            await ctx.send(f"'{quote}'")

        # Crystal Pendant (SPUR.MISC4.S mon.set/stone) -- resolved once, here,
        # when the monster is first set up for this encounter.
        await self._check_crystal_pendant(ctx)

        while not self._done.is_set():
            # ---- Druid/Ranger passive taming (TADA original, not SPUR) ----
            if await self._try_class_tame(ctx):
                return

            # ---- Per-round status warnings (SPUR.COMBAT.S lines 21-25, 88) ----
            hp = getattr(player, 'hit_points', 1)
            if hp < 9:
                await ctx.send('[+] HP DANGEROUSLY LOW [+]  (FLEE might be wiser!)')
            for warn in _survival_warnings(player):
                await ctx.send(warn)

            # Too weak to wield: low Strength forces weapon drop
            # (SPUR.COMBAT.S: if ps<4 then wr$="":print "YOU ARE TOO WEAK TO WIELD YOUR WEAPON!")
            _ps = int((getattr(player, 'stats', None) or {}).get('Strength', 10) or 10)
            if _ps < 4 and getattr(player, 'readied_weapon', None) is not None:
                player.readied_weapon = None
                await ctx.send('You are too weak to wield your weapon!')

            # ---- STORM asserts its will (SPUR.COMBAT.S line 59) ----
            # Early in the fight (monster attacked fewer than 6 times), a Storm
            # weapon has a 30% chance of auto-attacking without waiting for input.
            weapon = getattr(player, 'readied_weapon', None)
            weapon_name_upper = (getattr(weapon, 'name', '') or '').upper()
            auto_attack = False
            if (self._monster_attack_count < 6
                    and 'STORM' in weapon_name_upper
                    and not self._done.is_set()):
                if random.randint(1, 10) <= 3:   # SPUR: z<4 out of rnd.10z (1-10)
                    await ctx.send(f'THE {weapon_name_upper} ASSERTS ITS WILL!!')
                    auto_attack = True

            # ---- Mounted CHARGE eligibility roll (skip branch SPUR.COMBAT.S
            # m.attack, instr("*MNT",ys$) branch) -- only checked on the
            # first exchange. Independent of whether the player then picks
            # CHARGE or a plain attack, achieving first strike here means
            # the monster doesn't get to retaliate this round (see the
            # missile/pole first-strike checks below).
            self._charge_eligible = False
            if self._monster_attack_count == 0 and player.query_flag(PlayerFlags.MOUNTED):
                self._charge_eligible = _roll_charge_first_strike(player, self.monster)
                if self._charge_eligible:
                    await ctx.send('MOUNTED- YOU MANAGE TO GET FIRST STRIKE! (CHARGE if you want)')
                else:
                    await ctx.send("MOUNTED- OOPS, DIDN'T GET FIRST STRIKE..")

            # ---- player prompt (skipped if weapon auto-attacked) ----
            is_charge = False
            if not auto_attack:
                charge_opt = '  [C]harge' if self._charge_eligible else ''
                # Options go in the preamble, not the prompt line itself --
                # with [C]harge/[R]eady/e[X]it all present the full line
                # ran past narrow screen widths (e.g. 40-column PETSCII).
                preamble = [
                    f'[A]ttack{charge_opt}  [F]lee  [R]eady  e[X]it  ({player.return_key}: Attack)',
                    f'(HP:{getattr(player, "hit_points", "?")}'
                    f'  {mname} HP:{_monster_hp(self.monster)})',
                ]
                raw = await ctx.prompt('Command', preamble_lines=preamble)
                if raw is None:
                    # Client disconnected mid-fight
                    break
                cmd = (raw.strip().lower() or 'a')[0]
                if cmd == 'c' and not self._charge_eligible:
                    await ctx.send('You can not CHARGE now.')
                    continue
                if cmd == 'f':
                    fled = await self.flee(ctx)
                    if fled:
                        return
                    continue
                if cmd == 'r':
                    from commands.ready import ReadyCommand
                    await ReadyCommand().execute(ctx)
                    continue
                if cmd == 'x':
                    # Exit this menu for the round: no attack, no flee
                    # attempt -- just skip the turn and re-prompt.
                    continue
                is_charge = cmd == 'c'

            # Default: attack
            async with self._lock:
                if self._done.is_set():
                    break

                # Player swings — +1 ep per attempt (SPUR.COMBAT.S line 103)
                result = self._swing(ctx, is_charge=is_charge)
                await _add_exp(ctx, exp_per_swing())
                await self._narrate_player_swing(ctx, result)

                # Ammo consumed this swing (SPUR.COMBAT.S:99 vn=vn-1)
                if result.ammo_used:
                    rounds = int(getattr(player, 'ammo_rounds', 0) or 0)
                    player.ammo_rounds = max(0, rounds - 1)
                    player.unsaved_changes = True
                    if not result.hit:
                        await self._stray_round(ctx, result.weapon_name,
                                                weapon_id=result.weapon_id)

                # Apply DEX improvement from a significant hit
                if result.dex_improved:
                    _apply_dex_change(player, +1)

                # Scare: loud weapon frightens monster away early in fight
                # (SPUR.COMBAT.S scare subroutine, lines 423-430)
                if result.monster_scared:
                    mname_scare = self.monster.get('name', 'The monster')
                    await ctx.send(
                        f'THE THUNDERING NOISE OF THE {result.weapon_name} '
                        f'SCARES THE {mname_scare} AWAY!'
                    )
                    await ctx.send_room(
                        f'The {mname_scare} flees in terror from the noise!',
                        exclude_self=True,
                    )
                    self._done.set()
                    self._remove_attacker(ctx)
                    return

                # Total damage = direct + FIREBALL secondary heat
                total_player_dmg = result.damage + result.fireball_secondary
                _set_monster_hp(self.monster, _monster_hp(self.monster) - total_player_dmg)

                if _monster_hp(self.monster) <= 0:
                    await self._monster_dies(ctx, player_killed=True)
                    return

                # Ally swings (party members)
                await self._ally_swings(ctx)

                if _monster_hp(self.monster) <= 0:
                    await self._monster_dies(ctx, player_killed=False)
                    return

                # Unseat check: charging risks being thrown from the saddle,
                # win or lose (skip branch SPUR.COMBAT.S unmount, reached
                # after the charge attack sequence resolves).
                if is_charge:
                    if await self._charge_unseat_check(ctx):
                        return

                # Mounted first strike achieved this round (see the CHARGE
                # eligibility roll at the top of the loop) -- the monster's
                # retaliation is skipped regardless of whether the player
                # chose CHARGE or a plain attack (SPUR.COMBAT.S m.attack:
                # achieving first strike `return`s before the real attack).
                if self._charge_eligible:
                    self._monster_attack_count += 1
                    continue

                # Missile first strike: if ammo is loaded and monster hasn't
                # attacked yet, player's opening shot counts as first strike
                # and the monster skips its swing this round (SPUR.COMBAT.S:219).
                if (self._monster_attack_count == 0
                        and int(getattr(player, 'ammo_rounds', 0) or 0) > 0):
                    await ctx.send('MISSILE: FIRST STRIKE!')
                    self._monster_attack_count += 1
                    continue

                # Pole weapon first strike: chance to outreach monster on the
                # first exchange. Roll + (monster agility × 3) + 2 < player DEX
                # → first strike; otherwise monster still swings (SPUR.COMBAT.S:221).
                if self._monster_attack_count == 0:
                    _pw = getattr(player, 'readied_weapon', None)
                    _wc = getattr(_pw, 'weapon_class', None)
                    _wc_val = (_wc.value if hasattr(_wc, 'value') else str(_wc)).lower()
                    if _wc_val == 'pole/range':
                        _ma  = int(self.monster.get('to_hit', 4) or 4)
                        _pd  = int((getattr(player, 'stats', None) or {}).get('Dexterity', 10))
                        _roll = random.randint(1, 10)
                        await ctx.send('POLE WEAPON: ', end='')
                        if _roll + (_ma * 3) + 2 < _pd:
                            await ctx.send('YOU MANAGE TO GET FIRST STRIKE!')
                            self._monster_attack_count += 1
                            continue
                        else:
                            await ctx.send("OOPS, DIDN'T GET FIRST STRIKE..")

                # Monster swings back at leader
                m_result = monster_attacks(self.monster, player,
                                           stone_blocked=self._turn_to_stone_blocked)

                # Turn to stone (SPUR.COMBAT.S "medusa" section): replaces the
                # rest of the monster's attack this round entirely.
                if m_result.turn_to_stone_attempted:
                    mname_ts = self.monster.get('name', 'The monster')
                    await ctx.send(f'{mname_ts} CASTS TURN TO STONE ON YOU!')
                    if m_result.turned_to_stone:
                        await self._player_petrified(ctx)
                        return
                    await ctx.send('...IT FAILED!')
                    self._monster_attack_count += 1
                    continue

                # Druid regeneration: when nearly dead, 10% chance to heal
                # instead of taking damage (SPUR.COMBAT.S lines 204-207:
                # pc=2, (hp+a)<30, rnd.10z z=5 → "YO! YOU REGENERATE HIT POINTS!")
                druid_regen = False
                if m_result.hit and m_result.damage > 0:
                    try:
                        from base_classes import PlayerClass
                        hp_now = int(getattr(player, 'hit_points', 1) or 1)
                        if (getattr(player, 'char_class', None) == PlayerClass.DRUID
                                and (hp_now + m_result.damage) < 30
                                and random.randint(1, 10) == 5):
                            druid_regen = True
                    except Exception:
                        pass

                if druid_regen:
                    hp_now = int(getattr(player, 'hit_points', 1) or 1)
                    player.hit_points = hp_now + m_result.damage
                    player.unsaved_changes = True
                    await ctx.send('YO!  YOU REGENERATE HIT POINTS!')
                else:
                    if await self._resolve_monster_hit(ctx, m_result):
                        return

                self._monster_attack_count += 1

                # Double attack: some monsters swing twice per round (SPUR: ] flag, 40%)
                # (SPUR.COMBAT.S: if instr("]",wy$) rnd.10a: if a<5 → DOUBLE ATTACK!)
                m_flags = self.monster.get('flags', {}) or {}
                if (m_flags.get('double_attacks')
                        and random.randint(1, 10) <= 4
                        and not self._done.is_set()):
                    m_result2 = monster_attacks(self.monster, player,
                                                stone_blocked=self._turn_to_stone_blocked)
                    await ctx.send('DOUBLE ATTACK!')
                    if m_result2.turn_to_stone_attempted:
                        mname_ts2 = self.monster.get('name', 'The monster')
                        await ctx.send(f'{mname_ts2} CASTS TURN TO STONE ON YOU!')
                        if m_result2.turned_to_stone:
                            await self._player_petrified(ctx)
                            return
                        await ctx.send('...IT FAILED!')
                    elif await self._resolve_monster_hit(ctx, m_result2):
                        return
                    self._monster_attack_count += 1

                if getattr(player, 'hit_points', 1) <= 0:
                    await self._player_dies(ctx)
                    return

    # ------------------------------------------------------------------
    # Internal: single swing
    # ------------------------------------------------------------------

    def _swing(self, ctx: 'GameContext', is_charge: bool = False) -> AttackResult:
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
        # Storm servant bonus: +2 to skill/damage granted when player readied this
        # STORM weapon and it accepted them (SPUR.WEAPON.S spec5 servant path).
        sb = getattr(player, 'storm_servant_bonus', None)
        if sb:
            class_to_hit += sb[0]
            class_damage  += sb[1]
        weapons_data = getattr(ctx.server, 'weapons', None) or []
        return player_attacks(
            player, weapon, self.monster,
            class_to_hit=class_to_hit,
            class_damage=class_damage,
            weapons_data=weapons_data,
            monster_attack_count=self._monster_attack_count,
            is_mounted=player.query_flag(PlayerFlags.MOUNTED),
            is_charge=is_charge,
            is_surprise=self.is_surprise,
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
                mname = self.monster.get("name", "monster")
                if dmg == 0:
                    await ctx.send(f'{member.name} strikes the {mname}, but inflicts no damage!')
                    await ctx.send_room(
                        f'{member.name} strikes the {mname}, but inflicts no damage!',
                        exclude_self=True,
                    )
                else:
                    await ctx.send(f'{member.name} strikes for {dmg} damage!')
                    await ctx.send_room(
                        f'{member.name} strikes the {mname} for {dmg} damage!',
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

        if result.no_ammo:
            wn   = result.weapon_name or 'weapon'
            term = _ammo_term(wn).upper() + 'S'
            await ctx.send(f'NO {term} READY for the {wn}!')
            await ctx.send('(Try USE to load ammunition first.)')
            return
        if result.bad_weapon_choice:
            await ctx.send('(bad weapon choice)')
        if result.ease_helped:
            await ctx.send('(Ease of use helps!)')

        if result.is_charge:
            await ctx.send(f'YOU THUNDER DOWN UPON {mname}!')

        if result.instant_kill:
            msg  = f'Fire flashes from the {result.weapon_name}!  The {mname} is destroyed!'
            room = f'Fire flashes from {pname}\'s {result.weapon_name}!  The {mname} is destroyed!'
        elif result.ineffective:
            msg  = f'The {result.weapon_name} is ineffective against the {mname}!'
            room = f'{pname}\'s {result.weapon_name} is ineffective against the {mname}!'
        elif result.miss_over_top:
            msg  = f'You miss over the top of {mname}!'
            room = f'{pname} misses over the top of {mname}!'
        elif result.hit:
            crit = '  CRITICAL HIT!' if result.is_critical else ''
            surp = '  (Surprise!)' if result.is_surprise else ''
            if result.damage == 0:
                msg  = f'You strike the {mname}, but inflict no damage!{crit}{surp}'
                room = f'{pname} strikes the {mname}, but inflicts no damage!{crit}'
            else:
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

        # FIREBALL secondary heat burst (SPUR.COMBAT.S lines 162-163)
        if result.fireball_secondary > 0:
            mname = self.monster.get('name', 'the monster')
            await ctx.send(
                f'Secondary heat damage to {mname} +{result.fireball_secondary}!'
            )

        # DEX improvement notification (SPUR.COMBAT.S line 164)
        if result.dex_improved:
            await ctx.send('(You feel a bit more dexterous.)')

    async def _resolve_monster_hit(self, ctx: 'GameContext', result) -> bool:
        """Narrate and apply one monster swing, giving allies a death-save chance first.

        Returns True if the fight is over (a GOD/GODDESS ally whisked the
        player to safety) and the caller should stop the combat loop
        immediately; False if the hit was narrated/applied as normal.

        SPUR.COMBAT.S "dragon" label: sac.ally is only tried when the
        incoming blow would drop HP to 0 or below (`if a>hp-1`).
        """
        player = ctx.player
        if result.hit and await self._try_redirect_to_mount(ctx):
            return False

        hp = int(getattr(player, 'hit_points', 1) or 1)
        if result.hit and (result.damage + result.fire_damage) >= hp:
            from ally_events import try_ally_death_save
            if await try_ally_death_save(ctx, result.damage + result.fire_damage):
                self._done.set()
                self._remove_attacker(ctx)
                return True

        await self._narrate_monster_swing(ctx, result)
        self._apply_monster_damage(ctx, result)
        return False

    async def _try_redirect_to_mount(self, ctx: 'GameContext') -> bool:
        """Skip branch SPUR.COMBAT.S lurk.a: a mounted player's horse can
        take a monster's hit instead of the player. Roll d10 vs monster
        agility; success redirects.

        Narrative-only: this port doesn't yet track meaningful mount HP
        (a freshly-lassoed mount's hit_points is seeded to 0 -- see
        CombatSession.lasso -- and Horse Constitution/HP display is still
        unported, per MECHANICS.md "Horses"), so the redirect simply means
        the player takes no damage from this hit rather than applying
        damage to the mount.
        """
        player = ctx.player
        if not player.query_flag(PlayerFlags.MOUNTED):
            return False

        from bar.allies import find_mount
        mount = find_mount(player)
        if mount is None:
            return False

        ma = int(self.monster.get('to_hit', 4) or 4)
        if random.randint(1, 10) >= ma:
            return False

        mname = self.monster.get('name', 'The monster')
        await ctx.send(f'{mname} attacks you, but strikes {mount.name} instead!')
        await ctx.send_room(
            f'{mname} attacks {_player_name(ctx)}, but strikes {mount.name} instead!',
            exclude_self=True,
        )
        return True

    async def _charge_unseat_check(self, ctx: 'GameContext') -> bool:
        """Skip branch SPUR.COMBAT.S unmount/unmount2: risk of being thrown
        from the saddle after a CHARGE, win or lose. Returns True if the
        fall killed the player (caller should stop the combat loop).

        score = d100 + HP + STR + CON + INT + EGY + DEX + (level x 3),
        plus class/race modifiers; score > 160 keeps the seat. Otherwise
        a Saddle gives one more (~40%) save roll before the player is
        thrown and takes 2-11 fall damage.
        """
        player = ctx.player
        if not player.query_flag(PlayerFlags.MOUNTED):
            return False

        from base_classes import PlayerClass, PlayerRace, PlayerStat
        stats = getattr(player, 'stats', None) or {}
        hp = int(getattr(player, 'hit_points', 1) or 1)
        score = random.randint(1, 100) + hp
        score += int(stats.get(PlayerStat.STR, 10) or 10)
        score += int(stats.get(PlayerStat.CON, 10) or 10)
        score += int(stats.get(PlayerStat.INT, 10) or 10)
        score += int(stats.get(PlayerStat.EGY, 10) or 10)
        score += int(stats.get(PlayerStat.DEX, 10) or 10)
        score += int(getattr(player, 'xp_level', 1) or 1) * 3

        char_class = getattr(player, 'char_class', None)
        char_race  = getattr(player, 'char_race', None)
        if char_class == PlayerClass.KNIGHT:
            score += 35
        if char_class == PlayerClass.PALADIN:
            score += 25
        if char_race == PlayerRace.ELF:
            score += 25
        if char_race in (PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC):
            score -= 25

        if score > 160:
            await ctx.send('(You retain your mount!)')
            return False

        from bar.allies import find_mount
        from bar.ally_data import AllyFlags
        mount = find_mount(player)
        if mount is not None and AllyFlags.SADDLED in (mount.flags or []):
            if random.randint(1, 100) > 60:
                await ctx.send('The saddle saves you from being unseated!')
                return False

        await ctx.send('The jar knocks you from your mount!')
        player.clear_flag(PlayerFlags.MOUNTED)
        player.unsaved_changes = True

        fall_damage = min(random.randint(1, 10) + 1, hp)
        player.hit_points = hp - fall_damage
        player.unsaved_changes = True
        await ctx.send(f'You take {fall_damage} damage from the fall.')
        if player.hit_points <= 0:
            await self._player_dies(ctx)
            return True
        return False

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
        # SPUR medusa section: fire_attack flag → burn damage bypassing armor
        if result.fire_damage > 0:
            lines.append(f'|red|FIRE!  You are scorched for {result.fire_damage} additional damage!|reset|')
        # SPUR & flag: experience drain
        if result.experience_drained > 0:
            lines.append(
                f'|yellow|ARRGG!  The {mname}\'s attack drains you!  '
                f'(-{result.experience_drained} experience)|reset|'
            )
        # SPUR line 212: DEX reduction on a heavy hit
        if result.dex_lost:
            lines.append('(You feel a bit less dexterous.)')
        # SPUR.COMBAT.S:307: strength drain on any hit
        if result.strength_lost:
            lines.append(f'(The blow saps your strength. -{result.strength_lost} STR)')

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
        if result.shield_blocked:
            # New mechanic (not in original SPUR): a successful block builds
            # per-item shield-block proficiency, mirroring weapon_experience.
            # See player.py's gain_shield_proficiency() / resolution.py's
            # shield_exp_bonus().
            player.gain_shield_proficiency(getattr(player, 'active_shield_id', None))
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

        # HP loss (normal damage + fire damage which bypasses armor)
        hp = int(getattr(player, 'hit_points', 1) or 1)
        player.hit_points = hp - result.damage - result.fire_damage
        player.unsaved_changes = True

        # Experience drain (SPUR & flag): reduce player.experience
        if result.experience_drained > 0:
            ep = int(getattr(player, 'experience', 0) or 0)
            player.experience = max(1, ep - result.experience_drained)
            player.unsaved_changes = True

        # DEX reduction on a hard hit (SPUR.COMBAT.S line 212)
        if result.dex_lost:
            _apply_dex_change(player, -1)

        # Strength drain (SPUR.COMBAT.S:307: ps=ps-(a/2))
        if result.strength_lost:
            try:
                stats   = getattr(player, 'stats', None) or {}
                current = int(stats.get('Strength', 10) or 10)
                player.stats['Strength'] = max(0, current - result.strength_lost)
                player.unsaved_changes = True
            except Exception:
                log.exception('_apply_monster_damage: failed to apply strength_lost')

    async def _monster_dies(self, ctx: 'GameContext', *, player_killed: bool = True) -> None:
        """Handle monster death: rewards, records, cleanup.

        player_killed: True when the player dealt the killing blow (not an ally).
        Controls whether WIS is awarded (SPUR: if x1 goto p.a3 skips WIS gain
        when x1 is set by an ally kill).
        """
        self._done.set()
        mname = self.monster.get('name', 'The monster')

        await ctx.send(f'|green|You have slain the {mname}!|reset|')

        # A monster that can itself cast turn-to-stone becomes a statue upon
        # death, appropriately (SPUR.MAIN.S/SPUR.MISC.S/SPUR.MISC3.S: any
        # monster flagged "#" leaves "a statue of <name>" behind in the room --
        # too heavy to GET, examined as "made of stone, and kind of ugly").
        # Not yet persisted as a lasting room object (no corpse/room-object
        # tracking system exists in this port yet) -- flavor only for now.
        if (self.monster.get('flags', {}) or {}).get('petrify'):
            await ctx.send(f'{mname} turns to stone as it dies!')

        await ctx.send_room(
            f'{_player_name(ctx)} slays the {mname}!',
            exclude_self=True,
        )

        # The Dwarf (encounters/dwarf.py): killing him pays out his entire
        # accumulated hoard instead of the usual random gold_from_monster()
        # roll (his monsters.json entry is flagged no_gold for that reason)
        # and skips hidden-exit reveal below (SPUR.MISC.S:385: "if m$<>
        # 'THE DWARF' goto p.a4" -- the reveal only runs past that check).
        from encounters.dwarf import MONSTER_NUMBER as _DWARF_MONSTER_NUMBER
        is_dwarf = self.monster.get('number') == _DWARF_MONSTER_NUMBER
        if is_dwarf:
            from encounters.dwarf import on_killed
            for line in await on_killed(ctx):
                await ctx.send(line)

        # STORM weapon glee on kill (SPUR.COMBAT.S line 197)
        weapon = getattr(ctx.player, 'readied_weapon', None)
        wname  = (getattr(weapon, 'name', '') or '').upper()
        if 'STORM' in wname:
            await ctx.send(f'THE {wname} SCREAMS IN GLEE!!')

        # Gold loot (probability + amount from rewards.py / SPUR.MISC.S p.a4)
        player = ctx.player
        gold = gold_from_monster(self.monster)
        if gold:
            _give_silver(player, gold)
            await ctx.send(f'You find {gold} gold pieces on the {mname}!')

        _record_kill(player, self.monster)

        # WIS improvement on solo kill (SPUR.COMBAT.S line 194):
        #   if x1 goto p.a3  ← skip WIS if ally dealt killing blow (x1 set in p.a1)
        #   if pw<12 then pw=pw+1:print "(YOU FEEL A BIT WISER)"
        if player_killed:
            pw = int((getattr(player, 'stats', None) or {}).get('Wisdom', 10))
            if pw < 12:
                player.stats['Wisdom'] = pw + 1
                player.unsaved_changes = True
                if not getattr(player, 'is_expert', False):
                    await ctx.send('(You feel a bit wiser.)')

            # Battle experience (vp, SPUR.MISC.S:384 "p.a3"): +1 for
            # whatever weapon is currently readied, capped at 99 -- landing
            # the killing blow, not per swing (see _award_weapon_exp()'s
            # docstring for why -- vp is only ever incremented here in the
            # whole SPUR source).
            weapon_id = getattr(weapon, 'id_number', None)
            if weapon_id is not None:
                _award_weapon_exp(ctx, weapon_id)

        # Ammo recovery for bows/slings/blowguns (SPUR.MISC.S:427)
        await self._recover_ammo(ctx)

        # Hidden exit reveal (SPUR.MISC.S:419-420, right after "gosub
        # rec.ammo" in the source): killing a monster in a room flagged
        # hidden_exit_east/west reveals the secret passage it was guarding.
        # Excludes the Dwarf (see is_dwarf comment above).
        if not is_dwarf:
            await self._reveal_hidden_exit(ctx)

        # A would-be recruit stepping out of the shadows to offer to join
        # (SPUR.MISC.S:423 -> SPUR.MISC2.S "servant"/"ally"), right after the
        # hidden-exit reveal in source too. Excludes the Dwarf for the same
        # reason as the reveal above (m$<>"THE DWARF" gates all of p.a4).
        if not is_dwarf:
            from encounters.monster import try_shadow_ally
            await try_shadow_ally(ctx)

        # Notify bystanders of the kill. Only the ctx that landed the killing
        # blow gains weapon exp (above) or the general per-swing ep exp
        # (CombatSession._swing()'s own callers) -- a bystander watching
        # someone else's fight doesn't get credit for either.
        for b_ctx in self.attackers:
            if b_ctx is ctx:
                continue
            await b_ctx.send(f'|green|{mname} is slain!|reset|')

    async def _reveal_hidden_exit(self, ctx: 'GameContext') -> None:
        """Reveal a hidden_exit_east/west room's secret passage on monster death.

        SPUR.MISC.S:419-420: unconditional for any non-Dwarf kill in a room
        whose raw name field carried the "->"/"<-" marker -- no other gate.
        The Dwarf exclusion is enforced by _monster_dies()'s caller (only
        calls this when not is_dwarf), not inside this method.
        """
        game_map = getattr(ctx.server, 'game_map', None)
        room_no  = getattr(ctx.client, 'room', None)
        if not game_map or not room_no:
            return
        level = int(getattr(ctx.player, 'map_level', 1) or 1)
        room  = game_map.get_room(level, int(room_no))
        if not room:
            return
        room_flags = getattr(room, 'flags', None) or []
        has_east = 'hidden_exit_east' in room_flags or getattr(room, 'hidden_exit_east', None) is not None
        has_west = 'hidden_exit_west' in room_flags or getattr(room, 'hidden_exit_west', None) is not None
        if has_east:
            await ctx.send('A search reveals a secret hole, east!')
        if has_west:
            await ctx.send('A search reveals a secret hole, west!')

    async def _recover_ammo(self, ctx: 'GameContext') -> None:
        """After combat, bow/sling/blowgun weapons may recover spent rounds (SPUR.MISC.S:427).

        Conditions: projectile weapon, not STORM, ammo_max >= 3, weapon name
        contains BOW/SLING/BLOWGUN.  Recovers 1–ammo_max rounds, capped at ammo_max.
        """
        player = ctx.player
        weapon = getattr(player, 'readied_weapon', None)
        if weapon is None:
            return
        wname = (getattr(weapon, 'name', '') or '').upper()
        if 'STORM' in wname:
            return
        wc     = getattr(weapon, 'weapon_class', None)
        wc_val = (wc.value if hasattr(wc, 'value') else str(wc)).lower() if wc else ''
        if wc_val != 'projectile':
            return
        ammo_max = int(getattr(player, 'ammo_max', 0) or 0)
        if ammo_max < 3:
            return
        if not any(kw in wname for kw in ('BOW', 'SLING', 'BLOWGUN')):
            return
        current = int(getattr(player, 'ammo_rounds', 0) or 0)
        recovered = random.randint(1, ammo_max)
        new_total = min(ammo_max, current + recovered)
        actual = new_total - current
        if actual > 0:
            player.ammo_rounds = new_total
            player.unsaved_changes = True
            term = _ammo_term(wname)
            noun = term + ('s' if actual != 1 else '')
            await ctx.send(f'YOU RECOVER {actual} {noun.upper()}.')

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

    async def _player_petrified(self, ctx: 'GameContext') -> None:
        """Handle death by petrification (SPUR.MISC6.S death cause z=6).

        Unlike a normal kill, this doesn't announce "slain by" -- the flavor
        is that the player is turned to stone. Also writes a permanent
        memorial: a file named after the monster (stripped of a leading
        "THE "), one player name appended per victim, mirroring the original
        `statue` subroutine's `dy$=dx$+m$ ... print #1,n1$`.

        That memorial file is also the sole source for the in-world statue
        display -- commands/get.py's GET STATUE / commands/look.py's/
        commands/read.py's plaque text / simple_server.py's room
        description all show whoever's *first* in this monster's file
        whenever it's present in a room (SPUR.MAIN.S's `statue`
        subroutine -- see combat.engine.first_statue_victim()). No
        separate per-room registry: the same monster showing up
        elsewhere on the map displays the same statue there too, exactly
        like SPUR.
        """
        self._done.set()
        mname = self.monster.get('name', 'The monster')
        await ctx.send([
            f'|red|...ARGG!! YOU ARE TURNED TO STONE!|reset|',
            'Your adventure ends here...',
        ])
        await ctx.send_room(
            f'|red|{_player_name(ctx)} has been turned to stone by {mname}!|reset|',
            exclude_self=True,
        )
        await ctx.send('(Carving your statue!)')
        _record_statue(mname, _player_name(ctx))

        ctx.player.hit_points = 0
        ctx.player.unsaved_changes = True

    # ------------------------------------------------------------------
    # Internal: participant tracking
    # ------------------------------------------------------------------

    async def _stray_round(self, ctx: 'GameContext', weapon_name: str,
                           weapon_id: int = 0) -> None:
        """Missed ammo/energy round may hit a party ally or bystander.

        Chance scales with weapon experience (lower skill = more likely):
          GREEN   (vp  0-39): 1-in-3
          VETERAN (vp 40-98): 1-in-6
          ELITE   (vp    99): 1-in-10

        Targets: living Ally NPCs in the shooter's party, plus other player
        attackers in the same room (bystanders who joined the fight).
        Damage: 1–4 HP (stray round, not a clean shot).
        """
        import random as _random
        from bar.ally_data import Ally, AllyStatus

        exp_dict = getattr(ctx.player, 'weapon_experience', {}) or {}
        vp = int(exp_dict.get(str(weapon_id), 0))
        if vp >= 99:
            chance = 10   # ELITE: 1-in-10
        elif vp >= 40:
            chance = 6    # VETERAN: 1-in-6
        else:
            chance = 3    # GREEN: 1-in-3

        if _random.randint(1, chance) != 1:
            return

        # Build candidate pool: living allies then other player attackers.
        ally_targets = [
            m for m in (getattr(ctx.player, 'party', None) or [])
            if isinstance(m, Ally)
            and m.status not in (AllyStatus.DEAD, AllyStatus.UNCONSCIOUS)
            and (m.hit_points or 0) > 0
        ]
        player_targets = [c for c in self.attackers if c is not ctx]

        if not ally_targets and not player_targets:
            return

        dmg = _random.randint(1, 4)

        if ally_targets and (not player_targets or _random.randint(0, 1)):
            target_ally = _random.choice(ally_targets)
            target_ally.hit_points = max(0, (target_ally.hit_points or 0) - dmg)
            ctx.player.unsaved_changes = True
            await ctx.send(
                f'Stray round from the {weapon_name} clips {target_ally.name}!'
                f'  (-{dmg} HP)'
            )
            if target_ally.hit_points <= 0:
                target_ally.status = AllyStatus.DEAD
                await ctx.send(f'{target_ally.name} has been killed by friendly fire!')
        else:
            target_ctx = _random.choice(player_targets)
            tplayer = target_ctx.player
            hp = int(getattr(tplayer, 'hit_points', 1) or 1)
            tplayer.hit_points = max(0, hp - dmg)
            tplayer.unsaved_changes = True
            tname = getattr(tplayer, 'name', 'Someone')
            await ctx.send(
                f'Stray round from the {weapon_name} hits {tname}!  (-{dmg} HP)'
            )
            await target_ctx.send(
                f'A stray round from {_player_name(ctx)}\'s {weapon_name} hits you!'
                f'  (-{dmg} HP)'
            )

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

    # Consume encounters/monster.py's surprise roll, if it's still pending
    # for this exact room/monster (SPUR.COMBAT.S zs=998 -> zs=997 on the
    # first attack of the fight).
    pending_surprise = getattr(ctx.player, 'pending_surprise', None)
    if (pending_surprise and pending_surprise.get('room_no') == room_no
            and pending_surprise.get('monster_number') == monster.get('number')):
        session.is_surprise = True
    ctx.player.pending_surprise = None

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
