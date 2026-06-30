"""combat/resolution.py — Pure combat math.

No I/O, no async, no GameContext.  All functions take plain values and
return dataclasses.  engine.py drives I/O and applies the results.

Formulae ported from SPUR.COMBAT.S and SPUR.WEAPON.S.  SPUR variable
names are noted in comments where the mapping is non-obvious:

    wa   weapon class integer (1=hack/slash, 2=poke/jab, 3=pole/range,
                                5=projectile, 6=proximity, 10=energy)
    ma   monster size / attack rating (1=huge … 7=swift), stored as
         monster['to_hit'] in our JSON
    ws   ease-of-use score (5-9); stored as weapon.stability / 10 (JSON has ×10 form)
    wd   base damage score (3-9); stored as weapon.to_hit / 10   (JSON has ×10 form)
    zu   assembled to-hit skill  (class/race bonus + battle-exp bonus)
    zv   assembled damage bonus  (class/race bonus + battle-exp bonus)
    xp   player experience LEVEL (not raw points) — placeholder=1 until
         levelling is wired up
    vp   battle experience with a specific weapon (0-99)
    ms   monster current HP / strength, monster['strength']
    p2   hit-probability threshold the d10 roll must exceed
    p1   monster attack threshold the d10 roll must not reach

Special weapon (sw / sw$) — SPUR.MISC4.S lines 132-137, SPUR.COMBAT.S lines 127-151:
    sw   weapon number stored in the monster record (0 = no requirement)
    sw$  name of that weapon, looked up from the weapons file by record sw
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from player import Player

# ---------------------------------------------------------------------------
# Weapon-class → SPUR wa integer
# ---------------------------------------------------------------------------

_WA: dict[str, int] = {
    'hack_slash_bash': 1,
    'poke_jab':        2,
    'pole_range':      3,
    'projectile':      5,
    'proximity':       6,
    'energy':         10,
}

# ---------------------------------------------------------------------------
# Battle-experience (vp) tier bonuses — SPUR.WEAPON.S lines 58-59.
#   GREEN   (0-39):  no bonus
#   VETERAN (40-98): +1 to-hit (zu), +1 damage (zv)
#   ELITE   (99):    +2 to-hit, +xp_level damage (scales with player level)
# ---------------------------------------------------------------------------

def battle_exp_bonuses(vp: int, xp_level: int) -> tuple[int, int]:
    """Return (to_hit_bonus, damage_bonus) for a given vp and player level."""
    if vp >= 99:
        return 2, xp_level
    if vp >= 40:
        return 1, 1
    return 0, 0


def assemble_zu_zv(weapon, player_battle_exp: int, xp_level: int,
                   class_to_hit: int = 0, class_damage: int = 0,
                   ) -> tuple[int, int]:
    """
    Assemble zu (skill/to-hit) and zv (damage bonus) for one swing.

    class_to_hit / class_damage come from item_system.weapon_bonus()
    (SPUR yz / yx from the 'special' subroutine).
    """
    exp_hit, exp_dmg = battle_exp_bonuses(player_battle_exp, xp_level)
    return class_to_hit + exp_hit, class_damage + exp_dmg


# ---------------------------------------------------------------------------
# Hit-threshold computation (SPUR.COMBAT.S p.attack, lines 106-113)
# ---------------------------------------------------------------------------

def hit_threshold(weapon_class_str: str, monster_size: int,
                  zu: int, xp_level: int) -> int:
    """
    Compute p2: the d10 roll must be ≤ p2 to hit.

    weapon_class_str: WeaponClass.value, e.g. 'hack_slash_bash'
    monster_size:     1 (huge) … 7 (swift), from monster['to_hit'] (SPUR ma)
    """
    wa = _WA.get(weapon_class_str.lower(), 1)
    ma = monster_size or 4                       # default: man-sized

    if wa == 2:                                   # poke / jab
        p2 = ma - wa
    elif wa == 3 and ma < 6:                      # pole / range vs larger
        p2 = 7 - ma
    elif wa == 3 and ma >= 6:                     # pole / range vs swift/small
        p2 = ma - 3
    elif wa == 5 and ma < 6:                      # projectile vs larger
        p2 = ma
    elif wa == 5 and ma >= 6:                     # projectile vs swift/small
        p2 = 10 - ma
    elif wa in (8, 10):                           # ammo / energy
        p2 = wa - ma
    else:                                         # hack/slash/bash, proximity, unknown
        p2 = 3

    return min(7, p2 + zu + xp_level)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class SpecialWeaponResult:
    """Output of check_special_weapon().

    Encodes which SPUR.COMBAT.S special-weapon branch applies for one swing.
    engine.py reads this to choose narration; resolution.py applies it to
    the AttackResult before returning.

    SPUR source references:
      sw$=""  → no_requirement=True         (line 127: goto p.a0)
      STORM in wr$ + sw$!="" → instant_kill (lines 128-129: ms=0)
      wr$!=sw$ → is_ineffective             (line 134: goto advent)
      wr$==sw$ → guaranteed_hit + bonus 2   (lines 135, 151)
      EXCALIBUR vs evil/good → damage_multiplier   (lines 147-148)
      WRAITH DAGGER vs #70  → damage_flat_bonus=40 (line 150)
    """
    required_weapon_name: str   = ''     # '' → no special weapon required (sw$="")
    is_ineffective:       bool  = False  # wrong weapon → attack cancelled
    instant_kill:         bool  = False  # STORM weapon → monster hp → 0
    guaranteed_hit:       bool  = False  # correct weapon → p2=10
    damage_bonus:         int   = 0      # +2 for using the required weapon
    damage_multiplier:    float = 1.0    # EXCALIBUR vs evil (×2) or good (×0.5)
    damage_flat_bonus:    int   = 0      # WRAITH DAGGER +40


@dataclass
class AttackResult:
    """Outcome of one player (or bystander) swing at a monster."""
    hit:           bool
    damage:        int          # 0 on miss
    weapon_name:   str  = ''
    weapon_id:     int  = 0     # for awarding weapon battle exp to participants
    attacker_name: str  = ''
    ease_helped:   bool = False  # "(EASE OF USE HELPS!)" fast-path triggered
    is_surprise:   bool = False
    is_critical:   bool = False  # Assassin class critical hit
    ineffective:   bool = False  # special weapon required but wrong weapon used
    instant_kill:  bool = False  # STORM weapon vs special-weapon monster


@dataclass
class MonsterAttackResult:
    """Outcome of one monster swing at a player."""
    hit:               bool
    damage:            int
    shield_blocked:    int  = 0
    armor_blocked:     int  = 0
    shield_degraded:   int  = 0   # shield % lost this hit
    armor_degraded:    int  = 0   # armor % lost this hit
    shield_destroyed:  bool = False
    armor_destroyed:   bool = False
    # special effects — handled by effects.py after engine applies damage
    poisoned:  bool = False
    diseased:  bool = False


@dataclass
class AllyAttackResult:
    """Outcome of one ally swing at a monster (SPUR p.a1 section)."""
    ally_name: str
    hit:       bool
    damage:    int


@dataclass
class FleeResult:
    escaped:            bool
    blocked_by_monster: bool = False


# ---------------------------------------------------------------------------
# Special weapon check (SPUR.COMBAT.S lines 127-151, SPUR.MISC4.S lines 132-137)
# ---------------------------------------------------------------------------

def check_special_weapon(
    weapon,
    monster: dict,
    weapons_data: list,
) -> SpecialWeaponResult:
    """
    Determine which special-weapon branch applies for one player swing.

    monster['special_weapon'] is the weapon number (SPUR sw); 0 = no requirement.
    The required weapon name is looked up from weapons_data by that number (SPUR sw$).

    Named-weapon specials (EXCALIBUR, WRAITH DAGGER) are checked independently
    of the sw$ requirement and always apply when the weapon name matches.

    All interactions are logged at INFO level so they appear in the server console.
    """
    weapon_name    = (getattr(weapon, 'name', '') or '').upper() if weapon else ''
    monster_name   = monster.get('name', 'monster')
    monster_number = monster.get('number', 0) or 0
    flags          = monster.get('flags', {}) or {}

    result = SpecialWeaponResult()

    # --- Named-weapon specials (always apply, independent of sw$) ---
    if 'EXCALIBUR' in weapon_name:
        if flags.get('evil'):
            result.damage_multiplier = 2.0
            log.info('special_weapon: EXCALIBUR vs evil %r → damage ×2', monster_name)
        elif flags.get('good'):
            result.damage_multiplier = 0.5
            log.info('special_weapon: EXCALIBUR vs good %r → damage ÷2', monster_name)

    if 'WRAITH DAGGER' in weapon_name and monster_number == 70:
        result.damage_flat_bonus += 40
        log.info('special_weapon: WRAITH DAGGER vs wraith → +40 damage')

    # --- Required-weapon check (sw / sw$) ---
    sw = monster.get('special_weapon', 0) or 0
    if not sw:
        return result   # no requirement; normal combat

    sw_name = ''
    for w in (weapons_data or []):
        if w.get('number') == sw:
            sw_name = (w.get('name') or '').upper()
            break
    if not sw_name:
        log.warning(
            'check_special_weapon: monster %r requires weapon #%d but not found in weapons_data',
            monster_name, sw,
        )
        return result

    result.required_weapon_name = sw_name

    # STORM weapon: instant kill when a special weapon is required (SPUR.COMBAT.S lines 128-129)
    if 'STORM' in weapon_name:
        result.instant_kill = True
        log.info(
            'special_weapon: STORM weapon %r vs %r (requires %r) → instant kill',
            weapon_name, monster_name, sw_name,
        )
        return result

    # Wrong weapon: attack is ineffective (SPUR.COMBAT.S line 134)
    if weapon_name != sw_name:
        result.is_ineffective = True
        log.info(
            'special_weapon: %r is ineffective against %r (requires %r)',
            weapon_name or '(unarmed)', monster_name, sw_name,
        )
        return result

    # Correct special weapon: guaranteed hit + damage bonus (SPUR.COMBAT.S lines 135, 151)
    result.guaranteed_hit = True
    result.damage_bonus   = 2
    log.info(
        'special_weapon: %r is the required weapon for %r → guaranteed hit, +2 damage',
        weapon_name, monster_name,
    )
    return result


# ---------------------------------------------------------------------------
# Player attacks monster
# ---------------------------------------------------------------------------

def player_attacks(
    player,
    weapon,             # Weapon item or None (unarmed)
    monster: dict,
    *,
    is_surprise:  bool = False,
    is_lurking:   bool = False,
    xp_level:     int  = 1,      # TODO: derive from player.experience once levelling exists
    class_to_hit: int  = 0,      # pre-computed from item_system.weapon_bonus()
    class_damage: int  = 0,
    weapons_data: list = None,   # server.weapons list; required for special-weapon checks
) -> AttackResult:
    """
    Resolve one player attack swing.

    Returns AttackResult.  Caller (engine.py) is responsible for:
      - sending messages via ctx.send() / ctx.send_room()
      - applying monster HP reduction
      - calling player.gain_weapon_experience() for all participants
    """
    weapon_name = getattr(weapon, 'name', 'fists') if weapon else 'fists'
    weapon_id   = getattr(weapon, 'id_number', 0)  if weapon else 0
    # Weapon JSON stores stability and to_hit as the SPUR raw digit × 10 (50-90).
    # SPUR.COMBAT.S expects the raw digit (5-9), so divide by 10 here.
    ws          = (getattr(weapon, 'stability', 50) / 10) if weapon else 5  # SPUR ws: ease of use, 5-9
    wd          = (getattr(weapon, 'to_hit',    50) / 10) if weapon else 5  # SPUR wd: base damage,  3-9
    wc          = getattr(weapon, 'weapon_class', None) if weapon else None
    wc_str      = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else 'hack_slash_bash'

    exp_dict = getattr(player, 'weapon_experience', {})
    vp       = int(exp_dict.get(str(weapon_id), 0))
    zu, zv   = assemble_zu_zv(weapon, vp, xp_level, class_to_hit, class_damage)

    # Special weapon check (SPUR.COMBAT.S lines 127-151)
    sw = check_special_weapon(weapon, monster, weapons_data or [])

    # Ineffective: wrong weapon for this monster, attack cancelled (SPUR line 134)
    if sw.is_ineffective:
        return AttackResult(
            hit=False, damage=0, ineffective=True,
            weapon_name=weapon_name, weapon_id=weapon_id,
            attacker_name=getattr(player, 'name', ''),
        )

    # Instant kill: STORM weapon vs special-weapon monster (SPUR lines 128-129: ms=0)
    if sw.instant_kill:
        monster_hp = int(monster.get('strength') or monster.get('hit_points') or 9999)
        return AttackResult(
            hit=True, damage=monster_hp, instant_kill=True,
            weapon_name=weapon_name, weapon_id=weapon_id,
            attacker_name=getattr(player, 'name', ''),
        )

    ma = monster.get('to_hit') or 4              # SPUR ma
    p2 = hit_threshold(wc_str, ma, zu, xp_level)
    if is_surprise:
        p2 += 2
    # Lurking behind allies reduces effective hit skill (SPUR vq=2 → p2-vq)
    if is_lurking:
        p2 -= 2
    # Correct special weapon → guaranteed hit (SPUR line 135: p2=10)
    if sw.guaranteed_hit:
        p2 = 10

    a = random.randint(1, 10)                    # SPUR rnd.10a

    # Fast-path: "ease of use helps!" (SPUR line 139: if a > ws+2)
    ease_helped = not is_lurking and not sw.guaranteed_hit and (a > ws + 2)
    if ease_helped:
        dmg = _calc_player_damage(ws, wd, zv, monster, xp_level,
                                   is_surprise=is_surprise,
                                   char_class=getattr(player, 'char_class', None))
        dmg = _apply_special_weapon_damage(dmg, sw)
        return AttackResult(
            hit=True, damage=dmg,
            weapon_name=weapon_name, weapon_id=weapon_id,
            attacker_name=getattr(player, 'name', ''),
            ease_helped=True, is_surprise=is_surprise,
        )

    # Miss check (SPUR line 141: if a > p2-vq → missed)
    if a > p2:
        return AttackResult(
            hit=False, damage=0,
            weapon_name=weapon_name, weapon_id=weapon_id,
            attacker_name=getattr(player, 'name', ''),
        )

    # Hit
    char_class = getattr(player, 'char_class', None)
    dmg = _calc_player_damage(ws, wd, zv, monster, xp_level,
                               is_surprise=is_surprise, char_class=char_class)
    dmg = _apply_special_weapon_damage(dmg, sw)

    # Assassin critical hit: 1-in-10 chance to double damage (SPUR line 146)
    is_critical = False
    try:
        from base_classes import PlayerClass
        if char_class == PlayerClass.ASSASSIN and random.randint(1, 10) == 10:
            dmg *= 2
            is_critical = True
    except Exception:
        pass

    return AttackResult(
        hit=True, damage=dmg,
        weapon_name=weapon_name, weapon_id=weapon_id,
        attacker_name=getattr(player, 'name', ''),
        is_surprise=is_surprise, is_critical=is_critical,
    )


def _apply_special_weapon_damage(dmg: int, sw: SpecialWeaponResult) -> int:
    """Apply special-weapon damage modifiers after base damage is computed."""
    result = dmg + sw.damage_bonus
    result = int(result * sw.damage_multiplier)
    result = result + sw.damage_flat_bonus
    return max(0, result)


def _calc_player_damage(ws: float, wd: float, zv: int, monster: dict, xp_level: int,
                         is_surprise: bool = False, char_class=None) -> int:
    """
    Damage formula (SPUR.COMBAT.S p.a5, lines 126, 143-163):
        b = random(2.0 … wd+2)             ← wd = to_hit/10 (3-9), base damage roll
        b = (b * ws / 10) + zv - 1         ← ws = stability/10 (5-9), ease-of-use scale
        if surprise: b += 3
        if b > 10: b = (b * 4) // 5        ← soft damage cap
        armor reduction from monster flags
    """
    b = random.uniform(2.0, wd + 2.0)
    b = (b * ws / 10) + zv - 1
    if is_surprise:
        b += 3
    if b > 10:
        b = (b * 4) / 5

    # Monster armor reduces damage by xp_level-scaled amounts (SPUR lines 154-158)
    flags = monster.get('flags', {})
    if flags.get('heavy_armor'):
        b = b - (xp_level * 2) - 2 - xp_level
    elif flags.get('light_armor'):
        b = b - (xp_level * 2)

    return max(0, int(b))


# ---------------------------------------------------------------------------
# Monster attacks player
# ---------------------------------------------------------------------------

def monster_attacks(monster: dict, player) -> MonsterAttackResult:
    """
    Resolve one monster attack against the player.
    (SPUR.COMBAT.S m.attack / medusa section, lines 217-322)

    Returns MonsterAttackResult.  Caller applies hp loss, shield/armor
    degradation, and passes poisoned/diseased to effects.py.
    """
    ma  = monster.get('to_hit') or 4    # SPUR ma: size/attack rating
    ms  = monster.get('strength') or 5  # SPUR ms: monster damage capacity

    # Carrying-capacity dodge modifier (SPUR zo) — placeholder until
    # inventory weight is tracked
    zo = 1

    # Hit threshold (SPUR line 257: p1=(ma+zo-1)/2, clamped 3-8)
    p1 = max(3, min(8, int((ma + zo - 1) / 2)))
    a  = random.randint(1, 10)
    if a >= p1:                          # SPUR line 260: if a<p1 → hit
        return MonsterAttackResult(hit=False, damage=0)

    # Raw damage (SPUR lines 261-263: three rnd.10a rolls averaged)
    r1 = random.randint(1, 10)
    r2 = random.randint(1, 10)
    r3 = random.randint(1, 10)
    raw = float((r1 + r2 + r3) / 3)
    raw += (8 - ma)                      # bigger monsters hit harder

    # Shield block (SPUR lines 269-286)
    shield           = int(getattr(player, 'shield', 0) or 0)
    shield_blocked   = 0
    shield_degraded  = 0
    shield_destroyed = False
    if shield > 0:
        block_roll      = random.randint(1, 10)
        shield_thresh   = 2 + (shield // 25) + random.randint(0, 2)
        if block_roll <= shield_thresh:
            shield_blocked  = min(int(raw), shield_thresh)
            shield_degraded = 1 + random.randint(0, max(0, 10 - ma))
            # Small chance shield is smashed entirely (SPUR line 284)
            if random.randint(0, 59) < shield_degraded * 2:
                shield_destroyed = True
                shield_degraded  = shield
            raw -= shield_blocked

    # Armor block (SPUR lines 288-299)
    armor           = int(getattr(player, 'armor', 0) or 0)
    armor_blocked   = 0
    armor_degraded  = 0
    armor_destroyed = False
    if armor > 0 and raw > 0:
        block_base  = 2 + (armor // 10)
        p_roll      = 2 + random.randint(0, block_base)
        ar_deg      = 1 + (armor // 20) + random.randint(0, 2)
        if p_roll <= ar_deg:
            armor_blocked  = min(int(raw), p_roll)
            armor_degraded = ar_deg
            if random.randint(0, 99) < ar_deg * 2:
                armor_destroyed = ar_deg >= armor
                armor_degraded  = min(ar_deg, armor)
            raw -= armor_blocked

    damage = max(0, int(raw))

    # Special-effect triggers (checked by engine, applied by effects.py)
    flags    = monster.get('flags', {})
    poisoned = diseased = False
    if damage > 0:
        if flags.get('poisonous_attack') and random.randint(1, 10) < 3:
            poisoned = True
        if flags.get('diseased_attack') and random.randint(1, 10) < 3:
            diseased = True

    return MonsterAttackResult(
        hit=True, damage=damage,
        shield_blocked=shield_blocked, armor_blocked=armor_blocked,
        shield_degraded=shield_degraded, armor_degraded=armor_degraded,
        shield_destroyed=shield_destroyed, armor_destroyed=armor_destroyed,
        poisoned=poisoned, diseased=diseased,
    )


# ---------------------------------------------------------------------------
# Ally attacks monster (SPUR.COMBAT.S p.a1 section, lines 167-187)
# ---------------------------------------------------------------------------

def ally_attacks(ally_name: str, ally_strength: int, monster: dict,
                 has_light_armor: bool = False,
                 xp_level: int = 1) -> AllyAttackResult:
    """
    Resolve one ally attack.  Simpler than player attacks — allies use a
    flat d10 roll; damage is capped at 8 and scaled by player xp level.

    has_light_armor: ally has "!" flag in SPUR (light-armored ally)
    """
    armor_bonus = 2 if has_light_armor else 0

    # SPUR line 179: z-a > 4 → missed (a=armor_bonus)
    roll = random.randint(1, 10) - armor_bonus
    if roll > 4:
        return AllyAttackResult(ally_name=ally_name, hit=False, damage=0)

    # Damage (SPUR lines 180-186)
    b = (armor_bonus + ally_strength) / 2
    if b > 1:
        b = random.randint(1, int(b))
    b = min(8, b) + (xp_level / 2) + armor_bonus

    flags = monster.get('flags', {})
    if flags.get('heavy_armor') or flags.get('light_armor'):
        b = (b * 2) / 3

    return AllyAttackResult(ally_name=ally_name, hit=True, damage=max(0, int(b)))


# ---------------------------------------------------------------------------
# Flee attempt (SPUR.COMBAT.S flee section, line 75)
# ---------------------------------------------------------------------------

def flee_attempt(player, monster: dict, monster_is_following: bool = True) -> FleeResult:
    """
    Can the player escape?

    Monster blocks the path if all of:
      hp > 7, monster is following, monster is not mechanical,
      random(1-10) < xp_level / 3
    """
    hp    = int(getattr(player, 'hit_points', 1) or 1)
    xp    = 1   # TODO: replace with derived xp_level once levelling exists
    flags = monster.get('flags', {})

    if (hp > 7 and monster_is_following
            and not flags.get('mechanical')
            and random.randint(1, 10) < xp / 3):
        return FleeResult(escaped=False, blocked_by_monster=True)

    return FleeResult(escaped=True)
