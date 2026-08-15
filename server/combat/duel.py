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
# Not ported yet: re-readying a different weapon mid-duel, and SPUR's
# turf-bonus (accuracy/damage for fighting in your own guild's
# territory -- distinct from turf CAPTURE, which is ported, see
# room_alignment.py) and Wizard-glow (+20 shield status flag)
# modifiers. Noted in TODO.md/TODO_HELP.md.
#
# Guild support (SPUR.DUEL.S:113-136 "follow"): ported as _guild_support(),
# computed once per side at duel start and stored on _DuelSide.support --
# see that function's docstring for how it's simplified from SPUR's own
# yt$/mark-counter parsing down to a room-local guildmate headcount.
#
# Initiative (SPUR.DUEL.S:83-86 "vw"/"zr", tac.bash's "INITIATIVE BONUS"
# +/-10% branch): ported as _compute_initiative(), computed once per side
# at duel start from level + weapon accuracy/damage bonus + STR+DEX+INT
# (_initiative_score()) and stored as a flat _DuelSide.initiative
# hit-chance delta (+10/0/-10) applied every swing alongside guild
# support. Turf's own contribution to the SPUR formula (zz*5) is left out,
# same deferred turf-bonus gap as above.
#
# Wizard spell-casting / Druid self-heal (SPUR.DUEL.S "wiz.a"/"wiz.b",
# "druid.a"/"druid.b"): a Wizard has a flat _WIZARD_CAST_CHANCE (30%) per
# swing to fire a guaranteed-hit spell bolt instead of a weapon attack --
# bypasses the hit/miss roll and shield/armor absorption entirely, same
# as SPUR's "goto wiz.a" jump skipping the whole "staff.0" hit-roll
# section. One shot per duel (_DuelSide.cast_used, SPUR's wx$ "cast.a"/
# "cast.b" tag is set once and never cleared). A Druid defender under a
# comfortable HP ceiling has a flat _DRUID_HEAL_CHANCE (10%) chance to
# channel any incoming hit -- weapon swing or spell bolt alike -- into a
# heal instead of taking it (_DuelSession._apply_final_damage(), the
# shared tail both damage paths funnel through, mirroring SPUR's shared
# wiz.a/druid.a label).
#
# Down-state menu (SPUR.DUEL.S:20-45 duel/down labels): while knocked down
# (_DuelSide.down), Attack/Parry/Bash/Flee are unavailable -- only Stand
# (DuelTactic.STAND, SPUR zw=1) or the evasive Roll (DuelTactic.ROLL, SPUR
# zw=5) can be submitted (_submit_tactic's down-gate). Both clear the down
# flag and skip that side's swing this round; Roll additionally blunts the
# "downed target is easy to hit" bonus an attacker gets this round (SPUR's
# yx=3/4/13/14 +3 STRIKE/HIT CHANCE MOD, approximated here as a flat
# hit-chance delta in _swing) from +20 down to +5. That bonus is computed
# from a per-round snapshot of down state taken before either side's swing
# resolves (DuelSession._was_down, set in _resolve_round) rather than the
# live side.down flag -- both sides' actions are simultaneous in SPUR (and
# in intent here), so reading the live flag would make the bonus depend on
# iteration order (self.a always resolves before self.b) and silently
# never fire, since the downed side's own recovery clears it before the
# opponent's swing is evaluated in the same round.
#
# Verbose commentary (SPUR.DUEL.S:47-49 "verbose", zq): `duel verbose`
# flips a per-side flag (_DuelSide.verbose) that doesn't consume a turn.
# When on, that side's personal view of each round gets an extra
# breakdown line per swing/bash (DuelSession._commentary, built in
# _swing/_resolve_bash, appended per-side in _resolve_round) showing the
# effective hit-chance modifier, stability, roll, and damage multiplier
# -- a condensed one-line-per-swing version of SPUR's multi-line "STRIKE
# CHANCE MOD"/"HIT CHANCE MOD"/"DAMAGE MOD" prints (attack/attack1,
# lines ~188-297), not a line-for-line reprint of every individual SPUR
# modifier term (TADA's _INTERACTION table already collapses those into
# one hit_delta/dmg_mult pair -- see module comment above).
#
# No weapon = no fight, mirroring SPUR.DUEL.S's no.wep gate (deducts 1 INT,
# refuses to swing) -- unlike AUTODUEL's auto-pick-best-weapon-from-file
# behaviour (this port has no separate weapon file to pick from anyway;
# player.readied_weapon already covers that role via inventory).

import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from item_system import weapon_bonus, weapon_sfx
from combat.resolution import shield_exp_bonus

_MIN_HP_AFTER_LOSS = 15   # SPUR.DUEL2.S hell/hell2: loser left at hp=15, not dead
_STREAK_LEN = 3           # repeating a tactic this many times running reads as predictable
_STREAK_PENALTY = 10      # hit-chance penalty for being predictable
_WIZARD_CAST_CHANCE = 30      # SPUR DUEL.S "if pc=1 ... if z>70 a=1": 30% per swing, once per duel
_DRUID_HEAL_CHANCE = 10       # SPUR DUEL.S "if yg=2 ... if z>90": 10% chance to heal instead of taking a hit
_DRUID_HEAL_HP_CEILING = 26   # SPUR DUEL.S "if h+w1<26": only eligible while not already comfortably healthy


class DuelTactic(StrEnum):
    ATTACK = 'attack'
    PARRY = 'parry'
    BASH = 'bash'
    FLEE = 'flee'
    STAND = 'stand'   # SPUR zw=1, "down" menu only: recover with no defensive bonus
    ROLL = 'roll'     # SPUR zw=5, "down" menu only: recover, blunting the attacker's bonus


_TACTIC_ALIASES: dict[str, DuelTactic] = {
    'attack': DuelTactic.ATTACK, 'a': DuelTactic.ATTACK,
    'parry':  DuelTactic.PARRY,  'p': DuelTactic.PARRY,
    'bash':   DuelTactic.BASH,   'b': DuelTactic.BASH,
    'flee':   DuelTactic.FLEE,   'f': DuelTactic.FLEE,
    'stand':  DuelTactic.STAND,  's': DuelTactic.STAND,
    'roll':   DuelTactic.ROLL,   'r': DuelTactic.ROLL,
}

# Only these are submittable while _DuelSide.down is True (SPUR's restricted
# "down" menu: S)tand, R)oll, V, H, ? -- no Attack/Parry/Bash/Flee).
_DOWN_TACTICS = frozenset((DuelTactic.STAND, DuelTactic.ROLL))
_DOWNED_HIT_BONUS = 20   # SPUR yx=3/4/13/14: standing target's easy shot at a downed one
_ROLLED_HIT_BONUS = 5    # same shot, but blunted by an evasive Roll

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
    verbose: bool = False   # SPUR zq, toggled by `duel verbose` -- see _swing/_resolve_bash commentary
    support: int = 0        # SPUR zv, "follow" -- see _guild_support(), computed once at duel start
    initiative: int = 0     # SPUR vu -- see _compute_initiative(), flat hit-chance delta for the whole duel
    cast_used: bool = False  # SPUR wx$'s "cast.a"/"cast.b" tag -- a Wizard gets one guaranteed-hit bolt per duel
    history: list = field(default_factory=list)   # last few DuelTactic choices, streak tracking


@dataclass
class DuelOutcome:
    winner_name: str
    loser_name: str
    fled: bool = False
    fled_name: str = ''


# SPUR.DUEL.S:115 "rdy.wp1": wa=8 (missile/projectile) or wa=10 (energy)
# needs ammo, unless it's a STORM weapon (STORM bypasses ammo entirely --
# same exception combat/resolution.py's own _needs_ammo gate uses for PvE
# combat). Named _duel_needs_ammo here to avoid colliding with that
# function-local variable of the same name in resolution.py.
def _duel_needs_ammo(weapon) -> bool:
    if weapon is None:
        return False
    wc = getattr(weapon, 'weapon_class', None)
    wc_str = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
    wname = (getattr(weapon, 'name', '') or '').upper()
    return wc_str.lower() in ('projectile', 'energy') and 'STORM' not in wname


# SPUR.DUEL.S:115: "No ammo readied! All weapon attributes reduced by
# half." -- unlike PvE combat, where the same empty-weapon check just
# misses the swing outright (combat/resolution.py), a duel doesn't refuse
# the fight over it: wd/ws/zt/zs (damage, ease-of-use, accuracy, and the
# class/race damage bonus) are all halved for the rest of the duel
# instead. This port recomputes those values fresh at several call sites
# (_offense_rating, _initiative_score, _weapon_damage, and _swing's own
# stability read) rather than caching them once at weapon-ready time like
# SPUR does, so the penalty is applied at each of those sites instead of
# a single mutation.
_UNLOADED_PENALTY = 0.5


def _ammo_penalty(player, weapon) -> float:
    """1.0 normally; _UNLOADED_PENALTY if *weapon* needs ammo (see
    _duel_needs_ammo) and *player* has none loaded."""
    if not _duel_needs_ammo(weapon):
        return 1.0
    ammo_rounds = int(getattr(player, 'ammo_rounds', 0) or 0)
    return _UNLOADED_PENALTY if ammo_rounds < 1 else 1.0


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
    skill_bonus = int(skill_bonus * _ammo_penalty(player, weapon))
    level = int(getattr(player, 'xp_level', 1) or 1)
    return max(3, min(9, 4 + skill_bonus + (level // 3)))


def _guild_support(side: '_DuelSide') -> int:
    """SPUR.DUEL.S:113-136 "follow": count of online guildmates present to
    cheer this side on, capped at 5, added flatly to accuracy and damage
    for the rest of the duel (SPUR: "You are supported by N Guild
    members!" / "Guild support adds: Damage & accuracy = N"). Computed
    once at duel start (SPUR computes it once at weapon-ready time too,
    not per-round).

    Simplified from SPUR's own yt$ status-string parsing (which also
    folds in a server-wide per-guild mark counter, zm/vy/vq, tallied
    elsewhere in SPUR.MISC5.S) down to a plain "how many same-guild
    players are in this room right now" headcount -- this port's duels
    are already room-scoped (see module comment), so a room-local count
    is the natural equivalent without needing to port the mark-counter
    machinery. Civilian/Outlaw duelists have no guild to draw support
    from.
    """
    from base_classes import Guild
    guild = getattr(side.player, 'guild', Guild.CIVILIAN)
    if guild in (Guild.CIVILIAN, Guild.OUTLAW):
        return 0
    server = getattr(side.ctx, 'server', None)
    my_client = getattr(side.ctx, 'client', None)
    my_room = getattr(my_client, 'room', None)
    if server is None or my_room is None:
        return 0
    count = 0
    for other_client in getattr(server, 'clients', {}).values():
        if other_client is my_client:
            continue
        if getattr(other_client, 'room', None) != my_room:
            continue
        other_ctx = getattr(other_client, 'ctx', None)
        other_player = getattr(other_ctx, 'player', None) if other_ctx else None
        if other_player is not None and getattr(other_player, 'guild', None) == guild:
            count += 1
    return min(count, 5)


_INITIATIVE_BONUS = 10  # SPUR DUEL.S:83-86 vu=5/vu=3: +/-10% hit chance for the whole duel
_INITIATIVE_GAP = 10    # must lead by more than this many initiative points to claim it


def _initiative_score(side: '_DuelSide') -> int:
    """SPUR.DUEL.S:83 (player's own 'vw') / DUEL2.S's 'zr' (opponent's,
    computed the same way): 2x level, plus the readied weapon's
    accuracy/damage bonuses (SPUR's zt/zs, 'Weapon adds: Damage=.. /
    Accuracy=..'), plus raw Strength+Dexterity+Intelligence (SPUR's
    ps/pd/pi -- see programming-notes/spur-variables.md). Turf's own
    initiative contribution (SPUR's zz*5) is intentionally left out here,
    same as the turf accuracy/damage bonus elsewhere in this module --
    both are the still-deferred turf-bonus gap, not this one.
    """
    from base_classes import PlayerStat
    player = side.player
    level  = int(getattr(player, 'xp_level', 1) or 1)

    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    class_str = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
    race_str  = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
    weapon = getattr(player, 'readied_weapon', None)
    skill_bonus, dmg_bonus = weapon_bonus(weapon, class_str, race_str) if weapon else (0, 0)
    penalty = _ammo_penalty(player, weapon)
    skill_bonus, dmg_bonus = int(skill_bonus * penalty), int(dmg_bonus * penalty)

    stats = getattr(player, 'stats', {}) or {}
    str_dex_int = (int(stats.get(PlayerStat.STR, 0) or 0)
                   + int(stats.get(PlayerStat.DEX, 0) or 0)
                   + int(stats.get(PlayerStat.INT, 0) or 0))

    return (level * 2) + skill_bonus + dmg_bonus + str_dex_int


def _compute_initiative(session: 'DuelSession') -> None:
    """Sets session.a.initiative/session.b.initiative from each side's
    _initiative_score(). Whoever leads by more than _INITIATIVE_GAP gets
    a flat +_INITIATIVE_BONUS hit-chance edge for the rest of the duel and
    their opponent a matching penalty (SPUR: 'YOU HAVE INITIATIVE' /
    '<opponent> HAS THE INITIATIVE!' / 'Neither has the initiative..').
    Computed once at duel start (SPUR computes it once too, right after
    weapons are readied), not per-round.
    """
    score_a = _initiative_score(session.a)
    score_b = _initiative_score(session.b)
    if score_a - score_b > _INITIATIVE_GAP:
        session.a.initiative, session.b.initiative = _INITIATIVE_BONUS, -_INITIATIVE_BONUS
    elif score_b - score_a > _INITIATIVE_GAP:
        session.b.initiative, session.a.initiative = _INITIATIVE_BONUS, -_INITIATIVE_BONUS
    else:
        session.a.initiative = session.b.initiative = 0


def _tactic_prompt(side: '_DuelSide') -> str:
    if side.down:
        return "You're on the ground! Choose: duel stand | duel roll"
    return "Choose: duel attack | duel parry | duel bash | duel flee"


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
    """Writes to the equipped item's own .condition (2026-08-08 durability
    redesign, shared with combat/engine.py's _apply_monster_damage() via
    player.py's apply_equipment_degradation()), not just the flat
    defender.shield/armor mirror -- destroyed removes it from inventory."""
    from player import apply_equipment_degradation
    if shield_destroyed or shield_degraded:
        apply_equipment_degradation(defender, 'shield', shield_degraded, shield_destroyed)
    if armor_destroyed or armor_degraded:
        apply_equipment_degradation(defender, 'armor', armor_degraded, armor_destroyed)


def _weapon_damage(player, weapon) -> float:
    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    class_str = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
    race_str  = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
    _skill_bonus, dmg_bonus = weapon_bonus(weapon, class_str, race_str) if weapon else (0, 0)
    to_hit = float(getattr(weapon, 'to_hit', 40) or 40) if weapon else 20.0
    base = ((to_hit / 10.0) + dmg_bonus) * _ammo_penalty(player, weapon)
    r1, r2, r3 = random.randint(1, 10), random.randint(1, 10), random.randint(1, 10)
    return base + (r1 + r2 + r3) / 10.0


def _wizard_bolt_damage(weapon) -> float:
    """SPUR.DUEL.S "wiz.a"/"wiz.b": a Wizard's spell bolt deals
    (roll(1-100)/20)+3 damage, +3 more if wielding a weapon whose name
    contains STAFF ('Your staff amplifies it!'). Unlike _weapon_damage(),
    this is independent of the weapon's own to_hit/class stats -- it's
    not a weapon swing, it's a spell (see _swing()'s cast branch, which
    also skips shield/armor absorption entirely for this reason)."""
    roll = random.randint(1, 100)
    dmg = (roll / 20.0) + 3
    if weapon is not None and 'STAFF' in (getattr(weapon, 'name', '') or '').upper():
        dmg += 3
    return dmg


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
        self._was_down: dict[int, bool] = {}   # snapshot, see module comment on Down-state menu
        self._commentary: list[str] = []       # SPUR's zq-gated "STRIKE/HIT CHANCE MOD" breakdown

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
        self._commentary = []
        # Snapshot down state before either side's swing mutates it -- both
        # sides' actions are simultaneous this round (see module comment).
        self._was_down = {id(self.a): self.a.down, id(self.b): self.b.down}
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
            if side.verbose and self._commentary:
                side_lines.extend(self._commentary)
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
            await side.ctx.send(_tactic_prompt(side))

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
                room_name = _current_room_name(side.ctx)
                net_common.append_battle_log(
                    f'{attacker.name} FLED a duel with {defender.name}, IN {room_name}'
                )
                return f'{attacker.name} flees the duel!'
            # Failed flee: opponent gets a free, undefended hit (SPUR falls
            # through flee -> attack1, the opponent's normal swing).
            side.tactic = DuelTactic.PARRY  # worst-case stance for the miss
            return f'{attacker.name} tries to flee but is blocked!' + self._swing(opp, side, free=True)

        if side.down:
            side.down = False
            if side.tactic == DuelTactic.ROLL:
                return f'{side.player.name} rolls out of danger and gets back up!'
            return f'{side.player.name} stands back up.'

        if side.tactic == DuelTactic.BASH:
            return self._resolve_bash(side, opp)

        return self._swing(side, opp)

    def _resolve_bash(self, side: _DuelSide, opp: _DuelSide) -> str:
        attacker, defender = side.player, opp.player
        shield     = int(getattr(attacker, 'shield', 0) or 0)
        opp_shield = int(getattr(defender, 'shield', 0) or 0)

        # Bash beats a Parrying opponent (knocks them down); risky against
        # a straight Attack (the basher is exposed mid-shove).
        if opp.tactic == DuelTactic.PARRY:
            success_chance = 65
            # SPUR.DUEL.S:449/454: a parrying defender with the SMALLER
            # shield is more agile and harder to bash -- (attacker_shield -
            # defender_shield) / 3 knocked off the bash's success chance.
            # Only the smaller side benefits; a larger shield grants nothing
            # here (SPUR's mirror-image checks are each one-directional).
            if opp_shield < shield:
                success_chance -= (shield - opp_shield) // 3
        elif opp.tactic == DuelTactic.ATTACK:
            success_chance = 35
        else:
            success_chance = 50
        if _is_predictable(side.history, DuelTactic.BASH):
            success_chance -= _STREAK_PENALTY

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

        clamped_chance = max(10, min(90, success_chance))
        roll = random.randint(1, 100)
        self._commentary.append(
            f'  [commentary] {attacker.name} bash vs {defender.name} ({opp.tactic.value}): '
            f'{clamped_chance}% chance, rolled {roll} -> {"SUCCESS" if roll <= clamped_chance else "FAIL"}'
        )
        if roll <= clamped_chance:
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

        # Ring of invisibility (#67, SPUR.DUEL.S:264): a defender wearing
        # the ring has a flat 20% chance per swing of the attacker simply
        # losing track of them, ahead of (not stacked with) the normal
        # hit/miss roll below.
        from flags import PlayerFlags
        if defender.query_flag(PlayerFlags.RING_WORN) and random.randint(1, 100) <= 20:
            return f' {attacker.name} swings at {defender.name}, but loses sight of them!'

        # Wizard spell-casting (SPUR.DUEL.S "wiz.a"/"wiz.b"): once per
        # duel (SPUR's wx$ "cast.a"/"cast.b" tag is set once and never
        # cleared, so this is a one-shot, not a per-round reroll), a
        # Wizard has a flat _WIZARD_CAST_CHANCE per swing to fire a bolt
        # instead of swinging their weapon. The bolt bypasses the hit/miss
        # roll and shield/armor absorption entirely -- SPUR's "goto wiz.a"
        # jumps clean over the "staff.0" hit-roll section -- so it's a
        # guaranteed hit, and (unlike a weapon swing) isn't boosted by
        # guild support/initiative/level differential.
        from base_classes import PlayerClass
        weapon = getattr(attacker, 'readied_weapon', None)
        if (not side.cast_used and getattr(attacker, 'char_class', None) == PlayerClass.WIZARD
                and random.randint(1, 100) <= _WIZARD_CAST_CHANCE):
            side.cast_used = True
            bolt = _wizard_bolt_damage(weapon)
            staff_note = (' Your staff amplifies it!'
                          if weapon is not None and 'STAFF' in (weapon.name or '').upper() else '')
            self._commentary.append(
                f'  [commentary] {attacker.name} casts a spell bolt for {bolt:.1f} damage '
                f'(bypasses hit roll & shield/armor)'
            )
            return (f" Energy flashes from {attacker.name}'s fingers! Thunder rocks the chamber!{staff_note}"
                    + self._apply_final_damage(side, opp, bolt))

        my_tactic = DuelTactic.ATTACK if free else (side.tactic or DuelTactic.ATTACK)
        their_tactic = opp.tactic or DuelTactic.ATTACK

        hit_delta, dmg_mult = _INTERACTION.get((my_tactic, their_tactic), (0, 1.0))
        hit_delta += hit_bonus
        hit_delta += side.support   # SPUR "follow": guild support adds to accuracy too
        hit_delta += side.initiative   # SPUR vu=5/vu=3: whoever has initiative hits easier
        if not free and _is_predictable(side.history, my_tactic):
            hit_delta -= _STREAK_PENALTY
        if self._was_down.get(id(opp)):
            # Snapshot from before this round's swings, not the live flag --
            # see module comment on the Down-state menu for why.
            if opp.tactic == DuelTactic.ROLL:
                hit_delta += _ROLLED_HIT_BONUS
            else:
                hit_delta += _DOWNED_HIT_BONUS

        stability = float(getattr(weapon, 'stability', 50) or 50) if weapon else 30.0
        stability *= _ammo_penalty(attacker, weapon)
        miss_sfx, hit_sfx = weapon_sfx(weapon) if weapon else (None, None)
        roll = random.randint(1, 100)
        hit = roll <= (stability + hit_delta)
        self._commentary.append(
            f'  [commentary] {attacker.name} ({my_tactic.value}) vs {defender.name} '
            f'({their_tactic.value}): strike chance mod {hit_delta:+d} (stability '
            f'{stability:.0f}), rolled {roll} -> {"HIT" if hit else "MISS"}'
        )
        if not hit:
            sfx = f'{miss_sfx}  ' if miss_sfx else ''
            return f' {sfx}{attacker.name} swings at {defender.name} and misses.'

        raw = _weapon_damage(attacker, weapon) * dmg_mult
        raw += side.support   # SPUR "follow": guild support adds to damage too
        level_diff = int(getattr(attacker, 'xp_level', 1) or 1) - int(getattr(defender, 'xp_level', 1) or 1)
        if level_diff > 0:
            raw += level_diff / 2

        damage, shield_blocked, armor_blocked, shield_deg, armor_deg, shield_destroyed, armor_destroyed = (
            _absorb_shield_armor(raw, attacker, defender)
        )
        _apply_degradation(defender, shield_deg, armor_deg, shield_destroyed, armor_destroyed)
        self._commentary.append(
            f'  [commentary] damage mod x{dmg_mult:.2f}: raw {raw:.1f} -> '
            f'{damage} after shield/armor absorption'
        )

        extra = []
        if shield_blocked:
            extra.append(f'shield absorbs {shield_blocked}')
        if armor_blocked:
            extra.append(f'armor absorbs {armor_blocked}')
        extra_txt = f' ({", ".join(extra)})' if extra else ''
        sfx = f'{hit_sfx}  ' if hit_sfx else ''
        return sfx + self._apply_final_damage(side, opp, damage, extra_txt=extra_txt)

    def _apply_final_damage(self, side: _DuelSide, opp: _DuelSide, raw_damage: float, *,
                             extra_txt: str = '') -> str:
        """Shared tail for every damage source in a duel -- weapon swings
        (from _swing()'s shield/armor-absorbed tail) and Wizard bolts
        (from _swing()'s spell-cast branch) alike, mirroring how
        SPUR.DUEL.S's "wiz.a"/"wiz.b" is a shared label both paths jump
        into.

        Druid self-heal (SPUR.DUEL.S "druid.a"/"druid.b"): a Druid
        defender under a comfortable HP ceiling (SPUR: `if h+w1<26`) has a
        flat _DRUID_HEAL_CHANCE chance of channeling the incoming hit into
        a heal instead of taking it -- applies to any damage source, not
        just spell bolts, since SPUR's normal weapon-hit path falls
        through into the same wiz.a/druid.a label after shield/armor
        absorption.

        Ends the duel (self.done=True, self._end()) on a killing blow,
        same as the pre-refactor inline version.
        """
        attacker, defender = side.player, opp.player
        damage = int(raw_damage)
        cur_hp = int(getattr(defender, 'hit_points', 1) or 1)

        from base_classes import PlayerClass
        if (getattr(defender, 'char_class', None) == PlayerClass.DRUID
                and (cur_hp + damage) < _DRUID_HEAL_HP_CEILING
                and random.randint(1, 100) <= _DRUID_HEAL_CHANCE):
            defender.hit_points = cur_hp + damage
            defender.unsaved_changes = True
            return f' {defender.name} channels nature and heals {damage} instead of taking the hit!'

        defender.hit_points = cur_hp - damage
        defender.unsaved_changes = True
        line = f' {attacker.name} hits {defender.name} for {damage} damage!{extra_txt}'
        if defender.hit_points <= 0:
            self.done = True
            self._end(winner_side=side, loser_side=opp)
        return line

    async def forfeit(self, disconnected_player) -> None:
        """A duelist disconnected mid-fight (SPUR.DUEL.S's "dropped" label:
        a lost carrier goes straight to hell2, the same automatic-loss
        consequences as being defeated in a fair fight -- DUEL2.S's
        sendmail also logs "=> <name> BROKE THE CONNECTION <="). Called
        from simple_server.py's connection cleanup, so only the opponent's
        ctx is still live -- unlike _resolve_round()'s normal per-side
        send loop, this pushes the win notice directly to the opponent
        and never touches disconnected_player's (already-dead) ctx.
        """
        if self.done:
            return
        self.done = True
        disconnected_side = self.side_for(disconnected_player)
        winner_side = self.other(disconnected_player)
        self._terse_notes = []
        self._end(winner_side=winner_side, loser_side=disconnected_side, disconnected=True)
        lines = [f'{disconnected_player.name} disconnects, forfeiting the duel!']
        win_line = self.end_lines.get(id(winner_side))
        if win_line:
            lines.append(win_line)
        await winner_side.ctx.send(lines)
        await self._broadcast_bystanders(*self._terse_notes)

    def _end(self, *, winner_side: Optional['_DuelSide'] = None, loser_side: Optional['_DuelSide'] = None,
             fled_side: Optional['_DuelSide'] = None, disconnected: bool = False) -> None:
        """Clear both players' active_duel and, on a decisive result, queue
        SPUR.DUEL2.S's hell/hell2 consequences (loser left at 15 HP, winner
        takes their silver) and guild standings. self.end_lines is read by
        _resolve_round()/_resolve_swing() callers and appended to the round
        broadcast (keyed by side identity, not id() of the player, so it
        survives even if callers hold onto the dataclass instances)."""
        self.a.player.active_duel = None
        self.b.player.active_duel = None
        self.end_lines: dict[int, str] = {}

        # Clear the "In a duel" virtual location set in _resolve_challenge()
        # so WHEREAT goes back to showing their real room.
        a_client = getattr(self.a.ctx, 'client', None)
        if a_client is not None and getattr(a_client, 'virtual_location', None) == 'In a duel':
            a_client.virtual_location = None
        b_client = getattr(self.b.ctx, 'client', None)
        if b_client is not None and getattr(b_client, 'virtual_location', None) == 'In a duel':
            b_client.virtual_location = None

        if fled_side is not None:
            return

        winner, loser = winner_side.player, loser_side.player
        loser.hit_points = _MIN_HP_AFTER_LOSS
        # SPUR.DUEL2.S's "uncon" subroutine: a duel loser is left
        # unconscious (can't be re-challenged, shows "(Unconscious)" in
        # room listings, wakes up at next login -- see
        # logon_events/unconscious_wake.py) rather than just docked HP.
        from flags import PlayerFlags
        loser.set_flag(PlayerFlags.UNCONSCIOUS)
        loser.defeated_by = winner.name
        loser.unsaved_changes = True
        if disconnected:
            self._terse_notes.append(f'{loser.name} disconnects, forfeiting a duel to {winner.name}!')
        else:
            self._terse_notes.append(f'{winner.name} defeats {loser.name} in a duel!')

        # Personal duel win/loss record (SPUR.DUEL2.S's "personal" label) --
        # distinct from the guild-vs-guild tally below.
        winner.duel_wins = int(getattr(winner, 'duel_wins', 0) or 0) + 1
        loser.duel_losses = int(getattr(loser, 'duel_losses', 0) or 0) + 1
        winner.unsaved_changes = True

        room_name = _current_room_name(winner_side.ctx)
        if disconnected:
            # SPUR.DUEL2.S's sendmail: "=> <name> BROKE THE CONNECTION <="
            net_common.append_battle_log(
                f'{loser.name} disconnected during a duel with {winner.name} '
                f'-- {winner.name} wins by forfeit, IN {room_name}'
            )
        else:
            net_common.append_battle_log(
                f'{winner.name} defeated {loser.name} in a duel, IN {room_name}'
            )

        from base_classes import Guild, PlayerMoneyTypes
        stolen = loser.get_silver(PlayerMoneyTypes.IN_HAND)
        if stolen:
            loser.subtract_silver(PlayerMoneyTypes.IN_HAND, stolen)
            winner.set_silver_absolute(
                PlayerMoneyTypes.IN_HAND,
                winner.get_silver(PlayerMoneyTypes.IN_HAND) + stolen,
            )

        if disconnected:
            win_line = (f'|light_green|{loser.name} disconnected -- you win the duel by forfeit!|reset|'
                        + (f' (+{stolen} silver)' if stolen else ''))
        else:
            win_line = f'|light_green|You have vanquished {loser.name}!|reset|' + (f' (+{stolen} silver)' if stolen else '')
        lose_line = f'|red|You have been vanquished by {winner.name}!|reset|' + (' He takes your silver!' if stolen else '')
        self.end_lines[id(winner_side)] = win_line
        self.end_lines[id(loser_side)] = lose_line

        # SPUR.DUEL2.S's sendmail: mails the loser a permanent record of
        # the duel result. In SPUR's BBS door-game model this was how
        # someone who wasn't present at the time still found out; kept
        # for the same reason here -- a disconnected loser's ctx is
        # already dead by the time forfeit() runs (see its docstring),
        # so mail is the only way they ever learn what happened, and it
        # doubles as a permanent record for the ordinary live case too.
        import mail
        if disconnected:
            mail_body = f'You disconnected during a duel with {winner.name} in {room_name} and lost by forfeit.'
        else:
            mail_body = f'You were defeated by {winner.name} in a duel in {room_name}.'
        if stolen:
            mail_body += f' They took {stolen} silver from you.'
        mail.add_system_message(loser.name, mail_body)

        winner_guild = getattr(winner, 'guild', Guild.CIVILIAN)
        loser_guild = getattr(loser, 'guild', Guild.CIVILIAN)
        if winner_guild not in (Guild.CIVILIAN, Guild.OUTLAW) and loser_guild not in (Guild.CIVILIAN, Guild.OUTLAW):
            winner_g = str(winner_guild.value if hasattr(winner_guild, 'value') else winner_guild)
            loser_g = str(loser_guild.value if hasattr(loser_guild, 'value') else loser_guild)
            record_duel_result(winner_g, loser_g)

        self._try_capture_turf(winner_side, winner_guild)

    def _try_capture_turf(self, winner_side: '_DuelSide', winner_guild) -> None:
        """Ryan's own extension, NOT a SPUR mechanic (see room_alignment.py's
        module docstring -- SPUR's own turf is permanent, baked into room
        names at map-build time and never mutated by combat). Winning a
        decisive SPORT DUEL flips the room's RoomAlignment to the winner's
        guild, unless the room is a guild HQ or a FREE_FIRE zone (both
        immutable forever, checked both here and again in
        room_alignment.apply_overrides() as belt-and-suspenders) or
        already aligned to that guild. Civilian/Outlaw winners have no
        guild to plant a flag for, so they can't capture turf at all.
        """
        from base_classes import Guild, RoomAlignment
        if winner_guild not in (Guild.FIST, Guild.CLAW, Guild.SWORD):
            return
        game_map = getattr(getattr(winner_side.ctx, 'server', None), 'game_map', None)
        if game_map is None:
            return
        winner = winner_side.player
        level = int(getattr(winner, 'map_level', 1) or 1)
        room_number = int(getattr(winner, 'map_room', 0) or 0)
        room = game_map.get_room(level, room_number)
        if room is None or room.alignment in (RoomAlignment.HQ, RoomAlignment.FREE_FIRE):
            return
        target = RoomAlignment[winner_guild.name]
        if room.alignment == target:
            return

        room.alignment = target
        from room_alignment import record_capture
        record_capture(level, room_number, target)

        self._terse_notes.append(f'{winner.name} claims {room.name} for {winner_guild.value}!')
        capture_line = f'|yellow|You claim this room for {winner_guild.value}!|reset|'
        existing = self.end_lines.get(id(winner_side))
        self.end_lines[id(winner_side)] = f'{existing}\n{capture_line}' if existing else capture_line


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
#   duel grovel       -- beg out of a pending challenge (SPUR.DUEL.S
#                        gvl.chk/SPUR.DUEL2.S grovel): 50% chance it fails
#                        and forces the duel to start anyway; on success, a
#                        further 50% chance of dropping your silver in hand
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
import net_common


async def _send_challenge(ctx: GameContext, target_ctx) -> CommandResult:
    challenger = ctx.player
    target = target_ctx.player

    # SPUR.DUEL2.S chlng2: "You can't duel unconcious people!"
    from flags import PlayerFlags
    if target.query_flag(PlayerFlags.UNCONSCIOUS):
        await ctx.send(f"You can't duel {target.name} -- they're unconscious!")
        return CommandResult.fail('Target is unconscious.')

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

    # WHEREAT (commands/whereat.py) reads ctx.client.virtual_location --
    # duelists don't actually leave their room, but "In a duel" is a more
    # useful location than the room name while they're locked in combat.
    challenger_ctx.client.virtual_location = 'In a duel'
    ctx.client.virtual_location = 'In a duel'

    session.a.support = _guild_support(session.a)
    session.b.support = _guild_support(session.b)
    _compute_initiative(session)

    header = f'|yellow|=== DUEL: {challenger.name} vs. {defender.name} ===|reset|'
    prompt = "Choose: duel attack | duel parry | duel bash | duel flee"
    challenger_lines = ['', header, prompt]
    defender_lines = ['', header, prompt]
    if session.a.support:
        plural = 's' if session.a.support > 1 else ''
        challenger_lines.insert(1, f'You are supported by {session.a.support} Guild member{plural}!')
    if session.b.support:
        plural = 's' if session.b.support > 1 else ''
        defender_lines.insert(1, f'You are supported by {session.b.support} Guild member{plural}!')
    if session.a.initiative > 0:
        challenger_lines.insert(1, 'You have the initiative!')
        defender_lines.insert(1, f'{challenger.name} has the initiative!')
    elif session.b.initiative > 0:
        defender_lines.insert(1, 'You have the initiative!')
        challenger_lines.insert(1, f'{defender.name} has the initiative!')

    # SPUR.DUEL.S:115 -- announced once at weapon-ready time, same as
    # guild support/initiative above; see _ammo_penalty()'s module comment
    # for why the actual halving is instead applied at each of its several
    # read sites rather than mutated once here.
    if _ammo_penalty(challenger, getattr(challenger, 'readied_weapon', None)) < 1.0:
        challenger_lines.insert(1, 'No ammo readied! All weapon attributes reduced by half.')
    if _ammo_penalty(defender, getattr(defender, 'readied_weapon', None)) < 1.0:
        defender_lines.insert(1, 'No ammo readied! All weapon attributes reduced by half.')

    await challenger_ctx.send(challenger_lines)
    await ctx.send(defender_lines)
    await session._broadcast_bystanders(f'{challenger.name} and {defender.name} begin a duel!')
    return CommandResult.ok(f'Duel between {challenger.name} and {defender.name} begun.')


def _current_room_name(ctx: GameContext) -> str:
    game_map = getattr(ctx.server, 'game_map', None)
    room_no  = getattr(ctx.client, 'room', None)
    if not game_map or not room_no:
        return 'the field'
    level = int(getattr(ctx.player, 'map_level', 1) or 1)
    room  = game_map.get_room(level, int(room_no))
    return getattr(room, 'name', None) or 'the field'


async def _resolve_grovel(ctx: GameContext) -> CommandResult:
    """Grovel out of a pending challenge (SPUR.DUEL.S:74-77 "gvl.chk",
    SPUR.DUEL2.S:198-211 "grovel"): a 50% chance the challenger sees
    through it and forces the duel to start anyway; on success, a
    further 50% chance you drop your entire silver-in-hand fleeing, and
    the encounter is logged to battle.log (SPUR: "<name>, GROVELED
    BEFORE <opponent>, IN <room>").
    """
    defender = ctx.player
    challenger_name = getattr(defender, 'pending_duel_challenge', None)
    if not challenger_name:
        await ctx.send('Nobody has challenged you to a duel.')
        return CommandResult.fail('No pending challenge.')

    if random.randint(1, 100) > 50:
        await ctx.send("'Groveling will do you no good!'")
        return await _resolve_challenge(ctx, accept=True)

    found, _not_found = find_online(ctx, [challenger_name], same_room_only=True)
    defender.pending_duel_challenge = None
    if found:
        await found[0].send(f'{defender.name} grovels before you and slinks away.')
    await ctx.send(f'{challenger_name} snickers, and waves you on.')

    room_name = _current_room_name(ctx)
    net_common.append_battle_log(
        f'{defender.name}, GROVELED BEFORE {challenger_name}, IN {room_name}'
    )

    if random.randint(1, 100) > 50:
        from base_classes import PlayerMoneyTypes
        dropped = defender.get_silver(PlayerMoneyTypes.IN_HAND)
        if dropped:
            defender.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
            defender.unsaved_changes = True
            await ctx.send(
                f'In your haste to depart, you dropped your silver sack! ({dropped} silver)'
            )
    return CommandResult.ok('Groveled.')


async def _submit_tactic(ctx: GameContext, tactic: DuelTactic) -> CommandResult:
    session = getattr(ctx.player, 'active_duel', None)
    if session is None:
        await ctx.send("You're not in a duel. Use DUEL <player> to challenge someone.")
        return CommandResult.fail('No active duel.')
    side = session.side_for(ctx.player)
    if side.down and tactic not in _DOWN_TACTICS:
        await ctx.send("You're on the ground! Choose: duel stand | duel roll")
        return CommandResult.fail('Down -- must stand or roll.')
    if not side.down and tactic in _DOWN_TACTICS:
        await ctx.send("You're not down -- nothing to stand up from.")
        return CommandResult.fail('Not down.')
    await session.submit(ctx.player, tactic)
    return CommandResult.ok(f'Submitted {tactic.value}.')


async def _toggle_verbose(ctx: GameContext) -> CommandResult:
    """SPUR.DUEL.S:47-49 "verbose" (zq): flips per-side commentary showing
    the strike-chance/damage modifier breakdown behind each swing (see
    DuelSession._commentary, appended in _swing/_resolve_bash). Unlike a
    tactic, this doesn't consume your turn -- flips instantly and doesn't
    wait on the opponent."""
    session = getattr(ctx.player, 'active_duel', None)
    if session is None:
        await ctx.send("You're not in a duel. Use DUEL <player> to challenge someone.")
        return CommandResult.fail('No active duel.')
    side = session.side_for(ctx.player)
    side.verbose = not side.verbose
    await ctx.send(f"Duel commentary - {'ON' if side.verbose else 'OFF'}")
    return CommandResult.ok(f"Verbose {'on' if side.verbose else 'off'}.")


async def _show_standings(ctx: GameContext) -> CommandResult:
    standings = load_standings()
    lines = ['', '|yellow|Guild Standings|reset|', '']
    if not standings:
        lines.append('  No guild duels recorded yet.')
    for guild, record in sorted(standings.items()):
        wins, losses = record.get('wins', 0), record.get('losses', 0)
        lines.append(f'  {guild:<20} {wins:>3} W  {losses:>3} L')

    # Personal duel record (SPUR.DUEL2.S's "personal" label) -- distinct
    # from the guild tally above, tracked per-player regardless of guild.
    player = ctx.player
    wins = int(getattr(player, 'duel_wins', 0) or 0)
    losses = int(getattr(player, 'duel_losses', 0) or 0)
    win_word = 'win' if wins == 1 else 'wins'
    loss_word = 'loss' if losses == 1 else 'losses'
    lines.append('')
    lines.append(f'  Your record: {wins} {win_word}, {losses} {loss_word}')
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
            ('duel grovel',     'Beg out of a pending challenge -- may fail and force the duel anyway.'),
            ('duel attack',     'In an active duel: swing at your opponent.'),
            ('duel parry',      'In an active duel: defend, countering Attack.'),
            ('duel bash',       'In an active duel: shield bash, countering Parry.'),
            ('duel flee',       'In an active duel: try to escape the fight.'),
            ('duel stand',      'While knocked down: stand back up (only option besides Roll).'),
            ('duel roll',       'While knocked down: an evasive recovery, harder to punish than Stand.'),
            ('duel verbose',    "Toggle a modifier breakdown after each swing -- doesn't cost a turn."),
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
            '3+ times running makes you predictable. Knocked down, your '
            'only options are STAND (plain recovery) or ROLL (an evasive '
            'recovery that blunts, but doesn\'t erase, how easy a target '
            'you are that round). The loser is left at '
            'low HP (not killed) and the winner takes their silver in hand. '
            'See "help bhr" for the danger rating shown before you decide '
            'whether to accept. GROVEL is a riskier alternative to DECLINE: '
            'there\'s a 50% chance your opponent sees through it and forces '
            'the duel to start anyway, but if it works you may still drop '
            'your silver in hand fleeing. If online guildmates (up to 5) '
            'are in the room when the duel begins, they lend you Guild '
            'support -- a flat bonus to your accuracy and damage for the '
            'whole fight. Winning as a guild member also claims the room '
            'for your guild, unless it\'s a guild HQ or free-fire zone.'
        ),
        notes = [
            'Rough draft: SPUR\'s re-readying a different weapon mid-duel, '
            'turf bonus (fighting on your own guild\'s territory), and '
            'Wizard glow are not ported yet.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not args:
            session = getattr(ctx.player, 'active_duel', None)
            if session is not None:
                await ctx.send(_tactic_prompt(session.side_for(ctx.player)))
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
        if first == 'decline':
            return await _resolve_challenge(ctx, accept=False)
        if first == 'grovel':
            return await _resolve_grovel(ctx)
        if first == 'verbose':
            return await _toggle_verbose(ctx)
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
