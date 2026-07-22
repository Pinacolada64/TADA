"""combat/duel.py — Player-vs-player duel mechanics.

Research notes from SPUR.DUEL.S and SPUR.DUEL2.S
--------------------------------------------------

WEAPON STORAGE
  Weapons are tracked in a separate binary file (`spur.weapons` / `weapons`),
  NOT in inventory.  Each player has a weapon list keyed by their position in
  the file (variable `yp`).

  Relevant SPUR variables:
    xw    — weapon count for the current player
    xw$   — weapon slot index strings (record numbers inside the binary file)
    wr$   — name of the currently readied weapon (empty string = none)

LIVE DUEL (both players online)
  After accepting a challenge the attacker runs `gosub rdy.wp` (DUEL.S line 82),
  which presents an interactive menu of weapons from the binary file and sets
  `wr$` to the chosen weapon name.

  Fighting without a readied weapon (`wr$=""`) jumps to the `no.wep` label
  (DUEL.S line 30), which:
    - prints "NO WEAPON READIED! (You feel dumber)"
    - deducts one point of Intelligence
    - skips the attack entirely (DUEL.S lines 51-54)

OFFLINE / AUTODUEL (defender is not logged in)
  `auto.c` (DUEL.S line 82) calls `gosub opnt.wp` (DUEL2.S line 137) to
  automatically select the defender's best weapon:

    1. Opens the defender's position in `spur.weapons` (binary, 64-byte records)
    2. Iterates their weapon list; picks the entry with the highest `zt+zs` score
       (zt = to-hit modifier, zs = stability/ease-of-use)
    3. Sets `cw$` to that weapon name for the rest of the duel

  If the defender has NO weapons at all (`c=0`, DUEL2.S line 168):
    - The attacker is asked whether to fight hand-to-hand
    - If yes: `wr$="FISTS"`, `cw$="FISTS"`, combat proceeds
    - If no: the duel is cancelled

  Conclusion: **inventory is not checked at all during offline duels**.  Any
  weapon in the player's weapon file is sufficient for auto-defense; no
  pre-readying is required.

TADA IMPLICATIONS
  - `player.readied_weapon` is a session-only attribute (excluded from JSON
    save via `_SESSION_ONLY` in Player.save); it resets to None each login.
  - When TADA implements duels it will need a separate weapon roster distinct
    from inventory — mirroring the SPUR binary file — or store weapon records
    inside the player JSON as a list separate from `inventory`.
  - Offline defense should auto-pick the best weapon from that roster, matching
    the `opnt.wp` behaviour above.
"""

# ---------------------------------------------------------------------------
# Live tactic loop, SPORT DUEL only (both players online and in the same room)
# ---------------------------------------------------------------------------
#
# SPUR.DUEL.S's actual system has each side pick a move every exchange --
# Attack, Parry, Shield Bash, or (while knocked Down) Roll/Stand-up -- and a
# hidden AI (op.tact/tac.bash) predicts the *other* side's move from its
# recent history, since the original game is single-player: you always
# fight a computer-controlled opponent. TADA's duels are real player vs.
# real player, so there's no prediction to port -- both sides' moves are
# real choices, submitted independently over two separate asyncio
# connections via `duel attack|parry|bash|flee`. A DuelSession (below)
# holds each side's pending choice; the round resolves the instant both are
# in, and both connections get pushed the identical result.
#
# The tactic INTERACTION table (_INTERACTION) is a simplified,
# self-consistent reinterpretation of DUEL.S's attack/attack1 "STRIKE
# CHANCE MOD"/"HIT CHANCE MOD" two-stage system (lines ~188-297), collapsed
# into one stage -- not a byte-exact port of every percentage, but the same
# rock-paper-scissors shape SPUR's numbers imply: Attack beats passive
# Parry-spam less than you'd think (Parry actually *counters* Attack),
# Bash punishes a Parry stance (knocks the parrier Down) but is risky
# against a straight Attack, and matched tactics are a rough, lower-damage
# clash. Repeating the same tactic 3+ times running gets read as
# predictable (tac.bash's xu/zn/zp streak counters) and costs you a hit-
# chance penalty, same idea as the original.
#
# Shield/armor absorption (_absorb_shield_armor) is copied from combat/
# resolution.py's monster_attacks() block math rather than imported,
# because that function also owns its own hit-roll (SPUR's "ma"/"p1"),
# which duels no longer use now that hit chance comes from the tactic
# table instead -- small deliberate duplication, kept in sync by hand.
#
# Not ported yet: Roll (an evasive Down-state move distinct from Stand-up),
# re-readying a different weapon mid-duel, the Verbose commentary toggle,
# and SPUR's turf-bonus/Wizard-glow/guild-support modifiers. Noted in
# TODO.md/TODO_HELP.md.
#
# No weapon = no fight, mirroring SPUR.DUEL.S's no.wep gate (deducts 1 INT,
# refuses to swing) -- unlike AUTODUEL's auto-pick-best-weapon-from-file
# behaviour (this port has no separate weapon file to pick from anyway;
# player.readied_weapon already covers that role via inventory).

import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from item_system import weapon_bonus
from combat.resolution import shield_exp_bonus

_MIN_HP_AFTER_LOSS = 15   # SPUR.DUEL2.S hell/hell2: loser left at hp=15, not dead
_STREAK_LEN = 3           # repeating a tactic this many times running reads as predictable
_STREAK_PENALTY = 10      # hit-chance penalty for being predictable


class DuelTactic(StrEnum):
    ATTACK = 'attack'
    PARRY = 'parry'
    BASH = 'bash'
    FLEE = 'flee'


_TACTIC_ALIASES: dict[str, DuelTactic] = {
    'attack': DuelTactic.ATTACK, 'a': DuelTactic.ATTACK,
    'parry':  DuelTactic.PARRY,  'p': DuelTactic.PARRY,
    'bash':   DuelTactic.BASH,   'b': DuelTactic.BASH,
    'flee':   DuelTactic.FLEE,   'f': DuelTactic.FLEE,
}

# (my tactic, opponent's tactic) -> (hit_chance_delta, damage_multiplier)
# applied to MY swing at THEM this exchange. BASH pairs are handled
# separately in _resolve_swing (knockdown roll comes first) -- this table
# only covers the ATTACK/PARRY sub-grid. Numbers are a simplified,
# consistent reinterpretation of DUEL.S's attack/attack1 mod tables (see
# module comment above), not a 1:1 percentage port.
_INTERACTION: dict[tuple[DuelTactic, DuelTactic], tuple[int, float]] = {
    (DuelTactic.ATTACK, DuelTactic.ATTACK): (10, 1.00),   # both swing recklessly
    (DuelTactic.ATTACK, DuelTactic.PARRY):  (-15, 0.75),  # they parry your swing away
    (DuelTactic.PARRY,  DuelTactic.ATTACK): (-10, 0.75),  # parrying, less of your own opening
    (DuelTactic.PARRY,  DuelTactic.PARRY):  (-20, 0.33),  # mutual caution, glancing at best
}


@dataclass
class _DuelSide:
    player: object
    ctx: object
    tactic: Optional[DuelTactic] = None
    down: bool = False
    history: list = field(default_factory=list)   # last few DuelTactic choices, streak tracking


@dataclass
class DuelOutcome:
    winner_name: str
    loser_name: str
    fled: bool = False
    fled_name: str = ''


def _offense_rating(player, weapon) -> int:
    """Synthetic 'ma' (SPUR: size/attack rating), used only to scale shield
    degradation in _absorb_shield_armor() -- see combat/resolution.py's
    identical use of 'ma' there. Built from weapon class/race bonus
    (item_system.weapon_bonus()) and character level; no canonical PvP
    formula exists to port, so this is a reasonable stand-in.
    """
    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    # .value, not str() -- char_class/char_race are PlayerClass/PlayerRace
    # StrEnum members; str() on them yields "PlayerClass.WIZARD", not
    # "Wizard" (see commands/ready.py's class_str/race_str for the same
    # guard, needed for the same reason).
    class_str = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
    race_str  = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
    skill_bonus, _dmg_bonus = weapon_bonus(weapon, class_str, race_str) if weapon else (0, 0)
    level = int(getattr(player, 'xp_level', 1) or 1)
    return max(3, min(9, 4 + skill_bonus + (level // 3)))


def _is_predictable(history: list, tactic: DuelTactic) -> bool:
    """SPUR's tac.bash: repeating the same move 3+ times running is
    predictable and costs a hit-chance penalty for the repeater."""
    return len(history) >= _STREAK_LEN and all(t == tactic for t in history[-_STREAK_LEN:])


def _absorb_shield_armor(raw: float, attacker, defender) -> tuple:
    """Shield/armor block math, copied from combat/resolution.py's
    monster_attacks() (see module comment for why this isn't imported).
    Returns (remaining_damage, shield_blocked, armor_blocked,
    shield_degraded, armor_degraded, shield_destroyed, armor_destroyed).
    """
    ma = _offense_rating(attacker, getattr(attacker, 'readied_weapon', None))

    shield_blocked = shield_degraded = 0
    shield_destroyed = False
    shield = int(getattr(defender, 'shield', 0) or 0)
    if shield > 0:
        block_roll = random.randint(1, 10)
        active_shield_id = getattr(defender, 'active_shield_id', None)
        prof_dict = getattr(defender, 'shield_proficiency', {}) or {}
        shield_prof = int(prof_dict.get(str(active_shield_id), 0)) if active_shield_id is not None else 0
        shield_thresh = 2 + (shield // 25) + random.randint(0, 2) + shield_exp_bonus(shield_prof)
        if block_roll <= shield_thresh:
            shield_blocked = min(int(raw), shield_thresh)
            shield_degraded = 1 + random.randint(0, max(0, 10 - ma))
            if random.randint(0, 59) < shield_degraded * 2:
                shield_destroyed = True
                shield_degraded = shield
            raw -= shield_blocked
            defender.gain_shield_proficiency(active_shield_id)

    armor_blocked = armor_degraded = 0
    armor_destroyed = False
    armor = int(getattr(defender, 'armor', 0) or 0)
    if armor > 0 and raw > 0:
        block_base = 2 + (armor // 10)
        p_roll = 2 + random.randint(0, block_base)
        ar_deg = 1 + (armor // 20) + random.randint(0, 2)
        if p_roll <= ar_deg:
            armor_blocked = min(int(raw), p_roll)
            armor_degraded = ar_deg
            if random.randint(0, 99) < ar_deg * 2:
                armor_destroyed = ar_deg >= armor
                armor_degraded = min(ar_deg, armor)
            raw -= armor_blocked

    return (max(0, int(raw)), shield_blocked, armor_blocked,
            shield_degraded, armor_degraded, shield_destroyed, armor_destroyed)


def _apply_degradation(defender, shield_degraded, armor_degraded, shield_destroyed, armor_destroyed) -> None:
    if shield_destroyed:
        defender.shield = 0
    elif shield_degraded:
        defender.shield = max(0, int(getattr(defender, 'shield', 0) or 0) - shield_degraded)
    if armor_destroyed:
        defender.armor = 0
    elif armor_degraded:
        defender.armor = max(0, int(getattr(defender, 'armor', 0) or 0) - armor_degraded)


def _weapon_damage(player, weapon) -> float:
    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    class_str = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
    race_str  = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
    _skill_bonus, dmg_bonus = weapon_bonus(weapon, class_str, race_str) if weapon else (0, 0)
    to_hit = float(getattr(weapon, 'to_hit', 40) or 40) if weapon else 20.0
    base = (to_hit / 10.0) + dmg_bonus
    r1, r2, r3 = random.randint(1, 10), random.randint(1, 10), random.randint(1, 10)
    return base + (r1 + r2 + r3) / 10.0


class DuelSession:
    """One in-progress live SPORT DUEL between two players. Stored on both
    players via player.active_duel (session-only, see player.py) so either
    side's next `duel <tactic>` command can find it.
    """

    def __init__(self, challenger, challenger_ctx, defender, defender_ctx):
        self.a = _DuelSide(challenger, challenger_ctx)
        self.b = _DuelSide(defender, defender_ctx)
        self.round_num = 1
        self.done = False
        self._terse_notes: list[str] = []

    def side_for(self, player) -> _DuelSide:
        return self.a if player is self.a.player else self.b

    def other(self, player) -> _DuelSide:
        return self.b if player is self.a.player else self.a

    async def _broadcast_bystanders(self, *lines: str) -> None:
        """Tell everyone else in the room a terse version of what's
        happening -- mirrors commands/attack.py's PvE fight broadcast
        (ctx.send_room()), which this duel would otherwise be invisible
        next to. Excludes BOTH duelists (send_room's own exclude_self
        only ever excludes the calling side, so calling it from just one
        duelist's ctx would double up the other duelist's own detailed
        log with this terse one)."""
        server = getattr(self.a.ctx, 'server', None)
        if server is None:
            return
        my_room = getattr(getattr(self.a.ctx, 'client', None), 'room', None)
        exclude = {getattr(self.a.ctx, 'client', None), getattr(self.b.ctx, 'client', None)}
        for other_client in getattr(server, 'clients', {}).values():
            if other_client in exclude:
                continue
            if getattr(other_client, 'room', None) != my_room:
                continue
            other_ctx = getattr(other_client, 'ctx', None)
            if other_ctx:
                await other_ctx.send(*lines)

    async def submit(self, player, tactic: DuelTactic) -> None:
        if self.done:
            return
        side = self.side_for(player)
        opp = self.other(player)
        side.tactic = tactic
        if opp.tactic is None:
            await side.ctx.send(
                f"You choose to {tactic.value.upper()}. Waiting for {opp.player.name}..."
            )
            return
        await self._resolve_round()

    async def _resolve_round(self) -> None:
        self._terse_notes = []
        lines = [f'|yellow|--- Round {self.round_num} ---|reset|']
        for side, opp in ((self.a, self.b), (self.b, self.a)):
            if self.done:
                break
            line = self._resolve_swing(side, opp)
            if line:
                lines.append(line)
            if self.done:
                break

        for side in (self.a, self.b):
            side.history.append(side.tactic)
            side.history = side.history[-_STREAK_LEN:]
            side.tactic = None

        end_lines = getattr(self, 'end_lines', {})
        for side in (self.a, self.b):
            side_lines = list(lines)
            personal = end_lines.get(id(side))
            if personal:
                side_lines.append(personal)
            await side.ctx.send(side_lines)

        if not self._terse_notes:
            self._terse_notes.append(f'{self.a.player.name} and {self.b.player.name} trade blows.')
        await self._broadcast_bystanders(*self._terse_notes)

        if self.done:
            return

        self.round_num += 1
        for side in (self.a, self.b):
            await side.ctx.send("Choose: duel attack | duel parry | duel bash | duel flee")

    def _resolve_swing(self, side: _DuelSide, opp: _DuelSide) -> str:
        """side takes their turn against opp. Mutates HP/shield/armor;
        may end the duel (self.done=True) on a kill or successful flee."""
        attacker, defender = side.player, opp.player

        if side.tactic == DuelTactic.FLEE:
            # SPUR.DUEL.S's flee: escape chance from INT+WIS+EGY.
            from base_classes import PlayerStat
            stats = getattr(attacker, 'stats', {}) or {}
            escape_score = (int(stats.get(PlayerStat.INT, 0) or 0)
                             + int(stats.get(PlayerStat.WIS, 0) or 0)
                             + int(stats.get(PlayerStat.EGY, 0) or 0))
            if random.randint(1, 100) + escape_score > 90:
                self.done = True
                self._end(fled_side=side)
                self._terse_notes.append(f'{attacker.name} flees from a duel with {defender.name}!')
                return f'{attacker.name} flees the duel!'
            # Failed flee: opponent gets a free, undefended hit (SPUR falls
            # through flee -> attack1, the opponent's normal swing).
            side.tactic = DuelTactic.PARRY  # worst-case stance for the miss
            return f'{attacker.name} tries to flee but is blocked!' + self._swing(opp, side, free=True)

        if side.down:
            side.down = False
            return f'{side.player.name} stands back up.'

        if side.tactic == DuelTactic.BASH:
            return self._resolve_bash(side, opp)

        return self._swing(side, opp)

    def _resolve_bash(self, side: _DuelSide, opp: _DuelSide) -> str:
        attacker, defender = side.player, opp.player
        # Bash beats a Parrying opponent (knocks them down); risky against
        # a straight Attack (the basher is exposed mid-shove).
        if opp.tactic == DuelTactic.PARRY:
            success_chance = 65
        elif opp.tactic == DuelTactic.ATTACK:
            success_chance = 35
        else:
            success_chance = 50
        if _is_predictable(side.history, DuelTactic.BASH):
            success_chance -= _STREAK_PENALTY

        shield = int(getattr(attacker, 'shield', 0) or 0)
        success_chance += shield // 10  # a shield helps you shove, per tips.txt's shield-scaling flavor
        # TODO: success_chance only factors the shield's condition rating.
        # A shove-to-the-ground move like this should plausibly also weigh
        # STR (PlayerStat.STR -- raw shoving power) and DEX (PlayerStat.DEX
        # -- balance/agility, both attacker's chance to stay upright after
        # overextending and defender's chance to keep their footing) the
        # way _absorb_shield_armor()'s shield_thresh above already folds in
        # shield_proficiency via shield_exp_bonus() (attacker.shield_proficiency,
        # keyed by attacker.active_shield_id) as a trained-skill bonus. None
        # of STR/DEX/shield_proficiency are read here yet.

        if random.randint(1, 100) <= max(10, min(90, success_chance)):
            opp.down = True
            self._terse_notes.append(f'{attacker.name} bashes {defender.name} to the ground!')
            return f'{attacker.name} SHIELD BASHES {defender.name} to the ground!'
        return f"{attacker.name}'s shield bash fails -- overextended!" + self._swing(
            opp, side, free=True, hit_bonus=15,
        )

    def _swing(self, side: _DuelSide, opp: _DuelSide, *, free: bool = False, hit_bonus: int = 0) -> str:
        """side attacks opp once. free=True skips reading side.tactic
        (used for bash-fail/flee-fail follow-up swings)."""
        attacker, defender = side.player, opp.player
        my_tactic = DuelTactic.ATTACK if free else (side.tactic or DuelTactic.ATTACK)
        their_tactic = opp.tactic or DuelTactic.ATTACK

        hit_delta, dmg_mult = _INTERACTION.get((my_tactic, their_tactic), (0, 1.0))
        hit_delta += hit_bonus
        if not free and _is_predictable(side.history, my_tactic):
            hit_delta -= _STREAK_PENALTY
        if opp.down:
            hit_delta += 20  # SPUR yx=3/4/13/14: hitting a downed opponent is much easier

        weapon = getattr(attacker, 'readied_weapon', None)
        stability = float(getattr(weapon, 'stability', 50) or 50) if weapon else 30.0
        roll = random.randint(1, 100)
        if roll > (stability + hit_delta):
            return f' {attacker.name} swings at {defender.name} and misses.'

        raw = _weapon_damage(attacker, weapon) * dmg_mult
        level_diff = int(getattr(attacker, 'xp_level', 1) or 1) - int(getattr(defender, 'xp_level', 1) or 1)
        if level_diff > 0:
            raw += level_diff / 2

        damage, shield_blocked, armor_blocked, shield_deg, armor_deg, shield_destroyed, armor_destroyed = (
            _absorb_shield_armor(raw, attacker, defender)
        )
        _apply_degradation(defender, shield_deg, armor_deg, shield_destroyed, armor_destroyed)

        defender.hit_points = int(getattr(defender, 'hit_points', 1) or 1) - damage
        defender.unsaved_changes = True

        extra = []
        if shield_blocked:
            extra.append(f'shield absorbs {shield_blocked}')
        if armor_blocked:
            extra.append(f'armor absorbs {armor_blocked}')
        extra_txt = f' ({", ".join(extra)})' if extra else ''
        line = f' {attacker.name} hits {defender.name} for {damage} damage!{extra_txt}'

        if defender.hit_points <= 0:
            self.done = True
            self._end(winner_side=side, loser_side=opp)
        return line

    def _end(self, *, winner_side: Optional['_DuelSide'] = None, loser_side: Optional['_DuelSide'] = None,
             fled_side: Optional['_DuelSide'] = None) -> None:
        """Clear both players' active_duel and, on a decisive result, queue
        SPUR.DUEL2.S's hell/hell2 consequences (loser left at 15 HP, winner
        takes their silver) and guild standings. self.end_lines is read by
        _resolve_round()/_resolve_swing() callers and appended to the round
        broadcast (keyed by side identity, not id() of the player, so it
        survives even if callers hold onto the dataclass instances)."""
        self.a.player.active_duel = None
        self.b.player.active_duel = None
        self.end_lines: dict[int, str] = {}

        if fled_side is not None:
            return

        winner, loser = winner_side.player, loser_side.player
        loser.hit_points = _MIN_HP_AFTER_LOSS
        loser.unsaved_changes = True
        self._terse_notes.append(f'{winner.name} defeats {loser.name} in a duel!')

        from base_classes import Guild, PlayerMoneyTypes
        stolen = loser.get_silver(PlayerMoneyTypes.IN_HAND)
        if stolen:
            loser.subtract_silver(PlayerMoneyTypes.IN_HAND, stolen)
            winner.set_silver_absolute(
                PlayerMoneyTypes.IN_HAND,
                winner.get_silver(PlayerMoneyTypes.IN_HAND) + stolen,
            )

        win_line = f'|light_green|You have vanquished {loser.name}!|reset|' + (f' (+{stolen} silver)' if stolen else '')
        lose_line = f'|red|You have been vanquished by {winner.name}!|reset|' + (' He takes your silver!' if stolen else '')
        self.end_lines[id(winner_side)] = win_line
        self.end_lines[id(loser_side)] = lose_line

        winner_guild = getattr(winner, 'guild', Guild.CIVILIAN)
        loser_guild = getattr(loser, 'guild', Guild.CIVILIAN)
        if winner_guild not in (Guild.CIVILIAN, Guild.OUTLAW) and loser_guild not in (Guild.CIVILIAN, Guild.OUTLAW):
            winner_g = str(winner_guild.value if hasattr(winner_guild, 'value') else winner_guild)
            loser_g = str(loser_guild.value if hasattr(loser_guild, 'value') else loser_guild)
            record_duel_result(winner_g, loser_g)


# ---------------------------------------------------------------------------
# DuelCommand -- the player-facing DUEL command
# ---------------------------------------------------------------------------
#
# Lives here rather than commands/duel.py so the whole duel feature --
# resolution math and command UX -- stays in one file while it's still a
# rough draft. Registered via CommandProcessor.discover('combat') (see
# create_command_processor() in commands/command_processor.py) alongside
# the usual discover('commands') pass.
#
# Flow:
#   duel <player>    -- challenge someone in your current room (needs a
#                        readied weapon, mirrors SPUR.DUEL.S's no.wep gate)
#   duel accept       -- accept a pending challenge against you
#   duel decline      -- decline a pending challenge against you
#   duel #standings   -- show guild win/loss standings (guild_standings.py)
#
# Only one challenge can be pending against a player at a time
# (player.pending_duel_challenge, session-only -- see player.py).

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import find_online
from commands.stats import _bhr  # reused rather than re-deriving BHR here
from guild_standings import load_standings, record_duel_result
from network_context import GameContext


async def _send_challenge(ctx: GameContext, target_ctx) -> CommandResult:
    challenger = ctx.player
    target = target_ctx.player

    if getattr(target, 'pending_duel_challenge', None):
        await ctx.send(f'{target.name} already has a pending challenge to answer.')
        return CommandResult.fail('Target already has a pending challenge.')

    if getattr(challenger, 'readied_weapon', None) is None:
        await ctx.send(
            "NO WEAPON READIED! (You feel dumber)",
            "Use READY to prepare a weapon before you DUEL.",
        )
        # SPUR.DUEL.S's no.wep: docks a point of INT for the attempt.
        stats = getattr(challenger, 'stats', {}) or {}
        from base_classes import PlayerStat
        stats[PlayerStat.INT] = max(1, int(stats.get(PlayerStat.INT, 10)) - 1)
        challenger.stats = stats
        challenger.unsaved_changes = True
        return CommandResult.fail('No weapon readied.')

    target.pending_duel_challenge = challenger.name

    await ctx.send(f'You challenge {target.name} to a duel!')
    await target_ctx.send(
        '',
        f'|red|{challenger.name} challenges you to a duel!|reset|',
        f'  Your BHR: {_bhr(target)}   {challenger.name}\'s BHR: {_bhr(challenger)}',
        "Type 'duel accept' or 'duel decline'.",
        '',
    )
    return CommandResult.ok(f'Challenged {target.name}.')


async def _resolve_challenge(ctx: GameContext, accept: bool) -> CommandResult:
    defender = ctx.player
    challenger_name = getattr(defender, 'pending_duel_challenge', None)
    if not challenger_name:
        await ctx.send('Nobody has challenged you to a duel.')
        return CommandResult.fail('No pending challenge.')

    defender.pending_duel_challenge = None

    found, _not_found = find_online(ctx, [challenger_name], same_room_only=True)
    if not found:
        await ctx.send(f'{challenger_name} is no longer here to duel.')
        return CommandResult.fail('Challenger not available.')
    challenger_ctx = found[0]
    challenger = challenger_ctx.player

    if not accept:
        await ctx.send(f"You decline {challenger_name}'s challenge.")
        await challenger_ctx.send(f'{defender.name} declines your challenge.')
        return CommandResult.ok('Declined.')

    if getattr(defender, 'readied_weapon', None) is None:
        await ctx.send(
            "NO WEAPON READIED! (You feel dumber) -- you can't accept without one.",
        )
        return CommandResult.fail('No weapon readied.')

    session = DuelSession(challenger, challenger_ctx, defender, ctx)
    challenger.active_duel = session
    defender.active_duel = session

    header = f'|yellow|=== DUEL: {challenger.name} vs. {defender.name} ===|reset|'
    prompt = "Choose: duel attack | duel parry | duel bash | duel flee"
    await challenger_ctx.send('', header, prompt)
    await ctx.send('', header, prompt)
    await session._broadcast_bystanders(f'{challenger.name} and {defender.name} begin a duel!')
    return CommandResult.ok(f'Duel between {challenger.name} and {defender.name} begun.')


async def _submit_tactic(ctx: GameContext, tactic: DuelTactic) -> CommandResult:
    session = getattr(ctx.player, 'active_duel', None)
    if session is None:
        await ctx.send("You're not in a duel. Use DUEL <player> to challenge someone.")
        return CommandResult.fail('No active duel.')
    await session.submit(ctx.player, tactic)
    return CommandResult.ok(f'Submitted {tactic.value}.')


async def _show_standings(ctx: GameContext) -> CommandResult:
    standings = load_standings()
    if not standings:
        await ctx.send('No guild duels recorded yet.')
        return CommandResult.ok('No standings.')
    lines = ['', '|yellow|Guild Standings|reset|', '']
    for guild, record in sorted(standings.items()):
        wins, losses = record.get('wins', 0), record.get('losses', 0)
        lines.append(f'  {guild:<20} {wins:>3} W  {losses:>3} L')
    lines.append('')
    await ctx.send(lines)
    return CommandResult.ok('Standings shown.')


class DuelCommand(Command):
    name    = 'duel'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Challenge another player in your room to a duel.',
        category = HelpCategory.COMBAT,
        usage    = [
            ('duel <player>',   'Challenge a player in your current room.'),
            ('duel accept',     'Accept a pending challenge against you.'),
            ('duel decline',    'Decline a pending challenge against you.'),
            ('duel attack',     'In an active duel: swing at your opponent.'),
            ('duel parry',      'In an active duel: defend, countering Attack.'),
            ('duel bash',       'In an active duel: shield bash, countering Parry.'),
            ('duel flee',       'In an active duel: try to escape the fight.'),
            ('duel #standings', 'Show guild win/loss standings.'),
        ],
        examples = [
            ('duel Railbender', 'Challenge Railbender to a duel.'),
            ('duel accept',     'Fight the player who challenged you.'),
            ('duel attack',     'Swing at your opponent this round.'),
        ],
        description = (
            'Challenges another online player in your room to a SPORT '
            'DUEL. Both sides need a weapon readied (see READY). Once '
            'accepted, each round both duelists privately choose Attack, '
            'Parry, Bash, or Flee -- the round resolves the instant both '
            'have chosen, and both sides see the same result. Parry '
            'counters Attack; Bash counters Parry (knocking them down) but '
            'is risky against a straight Attack; repeating the same move '
            '3+ times running makes you predictable. The loser is left at '
            'low HP (not killed) and the winner takes their silver in hand. '
            'See "help bhr" for the danger rating shown before you decide '
            'whether to accept.'
        ),
        notes = [
            'Rough draft: SPUR\'s Roll (an evasive move while knocked '
            'down) and re-readying a different weapon mid-duel are not '
            'ported yet -- a knockdown always resolves as an automatic '
            'stand-up on your next turn.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not args:
            if getattr(ctx.player, 'active_duel', None) is not None:
                await ctx.send('Choose: duel attack | duel parry | duel bash | duel flee')
                return CommandResult.ok('Awaiting tactic.')
            await ctx.send(
                'Usage: duel <player> | duel accept | duel decline | duel #standings'
            )
            return CommandResult.fail('No arguments.')

        first = args[0].lower()
        if first == '#standings':
            return await _show_standings(ctx)
        if first == 'accept':
            return await _resolve_challenge(ctx, accept=True)
        if first in ('decline', 'grovel'):
            return await _resolve_challenge(ctx, accept=False)
        if first in _TACTIC_ALIASES:
            return await _submit_tactic(ctx, _TACTIC_ALIASES[first])

        target_name = args[0]
        if target_name.lower() == ctx.player.name.lower():
            await ctx.send("You can't duel yourself.")
            return CommandResult.fail('Cannot duel self.')

        found, not_found = find_online(ctx, [target_name], same_room_only=True)
        if not found:
            await ctx.send(f'{target_name} is not here.')
            return CommandResult.fail('Target not found in room.')

        return await _send_challenge(ctx, found[0])
