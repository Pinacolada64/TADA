"""encounters/meteor.py — the "meteor" / "flying banshee" random encounter.

SPUR source: SPUR.MISC6.S's `meteor`/`met.a` labels, gated by the `*ME`
token in `ys$` (see TODO.md's "7/15/26" once-per-session flag inventory).
Part of the same random-event dispatcher as encounters/little_girl.py
(SPUR.MAIN.S's 2% per-move roll, then a d100 sub-roll across six
sub-events) -- see that module's docstring for why this rolls its own
flat composite share instead of a shared dispatcher for now. That
caveat now applies doubly: little_girl and meteor currently roll
independently, so (unlike the original, where only one sub-event can
fire per successful roll) both could in principle trigger on the same
move. Worth fixing once a third sub-event is built.

Not a fight -- a dodge check. A "FLYING BANSHEE" swoops in (or, on level
6 in a water/vacuum-flagged room specifically, a literal "METEOR"
instead -- SPUR.MISC6.S:481, matching the same @@-flag-means-vacuum-on
-level-6 convention documented elsewhere in this port), then a d100
dodge roll, worsened by low stats:
  - DEX < 18: +10 (worse odds)
  - INT < 18: +5
  - Energy < 18: +5
  - STR < 18: +5
Dodge succeeds (roll < 90, or HP is already critically low as a mercy
rule) -- "Whew... Missed..", flat +50 XP. Otherwise -- HP is halved
("CRUNCH!! X DAMAGE!"), unless a readied Lazer Shield (objects.json
#116) blocks it -- see _lazer_shield_block_chance()'s docstring for that
one, since it's not from SPUR at all.

Ryan: use master's numbers for now (checked master vs. skip and they
diverge here -- skip's success threshold is a much harsher `z<70`, not
`z<90`, and its Energy/Strength penalties are -7% each, not -5%; this
isn't a stub-vs-complete situation like some other quests, just two
different balance passes on a finished mechanic). A server-config
difficulty toggle to pick between them is a good future addition --
see TODO.md.

The original's growing-symbol approach animation (`met.a`: prints one
character at a time with a delay, backspacing to overwrite -- raw
terminal cursor control) doesn't translate to this port's line-based
JSON/ANSI wire protocol, so it's compressed into a single line here
instead of an actual per-frame animation.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

_ONCE_PER_DAY_KEY = 'meteor_seen'

# SPUR.MAIN.S:239 (2% world-event roll) x SPUR.MISC6.S's meteor slice
# (master: z<30 after the z<15 Galadriel check, i.e. a 15%-wide band) =
# 0.3% composite chance per move.
_ENCOUNTER_CHANCE_PCT = 0.3

_GROWTH_ANIMATION = '. . . . . . , .,.,.,.,;,; ,;,;,+,+;+ ;+o+o+*o* +*+*+*#* +#*#*#* #*0*# *#0 *@'

_LOW_STAT_THRESHOLD = 18
_DEX_PENALTY    = 10
_INT_PENALTY    = 5
_ENERGY_PENALTY = 5
_STR_PENALTY    = 5

_DODGE_SUCCESS_MAX  = 90  # roll < this succeeds (master's numbers)
_MERCY_HP_THRESHOLD = 3   # hp < this always dodges, regardless of roll
_DAMAGE_HP_FLOOR    = 2   # hp must be > this to actually take damage

_XP_REWARD_ON_DODGE = 50

# objects.json #116 "lazer shield". SPUR.MISC4.S/SPUR.COMBAT.S's LAZ.SH
# mechanic (level 6+ monster energy-weapon attacks) unconditionally
# halves damage once the player has USEd a Lazer Shield that session --
# not from SPUR: Ryan's suggestion to tie the meteor's CRUNCH damage to
# the same item, but gated by shield skill (shield_proficiency for that
# specific shield, same GREEN/VETERAN/ELITE tiers combat/resolution.py
# uses) instead of SPUR's unconditional block, since a raw meteor impact
# and a monster's aimed energy weapon aren't really the same threat.
_LAZER_SHIELD_ITEM_ID = 116
_SHIELD_BLOCK_CHANCE_GREEN   = 33
_SHIELD_BLOCK_CHANCE_VETERAN = 66
_SHIELD_BLOCK_CHANCE_ELITE   = 100


def _lazer_shield_block_chance(player) -> int:
    """0 if the Lazer Shield isn't the player's currently-readied shield;
    otherwise a block chance (0-100) from shield_proficiency with that
    specific shield."""
    if getattr(player, 'active_shield_id', None) != _LAZER_SHIELD_ITEM_ID:
        return 0
    proficiency = int((getattr(player, 'shield_proficiency', None) or {})
                       .get(str(_LAZER_SHIELD_ITEM_ID), 0))
    if proficiency >= 99:
        return _SHIELD_BLOCK_CHANCE_ELITE
    if proficiency >= 40:
        return _SHIELD_BLOCK_CHANCE_VETERAN
    return _SHIELD_BLOCK_CHANCE_GREEN


def _armor_damage_reduction_pct(player) -> int:
    """Percentage of remaining meteor damage absorbed by the player's
    current armor rating (player.armor, normally 0-100% but pushed to a
    flat 150% "for this play session" once Power Armor is energized --
    SPUR.SUB.S's pwr.ar, "PROTECTS FROM NUCLEAR BACK-BLAST"). Not from
    SPUR -- Ryan's suggestion, same reasoning as the Lazer Shield: this
    encounter should respect the same defensive stats combat already
    does, even though the original meteor code never checks them.
    Capped at 100% so a meteor can never heal you."""
    armor = int(getattr(player, 'armor', 0) or 0)
    return min(100, max(0, armor))


def _has_been_seen(player) -> bool:
    return _ONCE_PER_DAY_KEY in (getattr(player, 'once_per_day', None) or [])


def _mark_seen(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _ONCE_PER_DAY_KEY not in once:
        once.append(_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


async def try_encounter(ctx: 'GameContext') -> None:
    """Call on every player move (mirrors wild_horse_events.py's
    try_wandering_horse_encounter() call site). No-op if this player has
    already met it this session, the room already has a monster in it,
    or the roll fails."""
    player = ctx.player
    if _has_been_seen(player):
        return

    room = _current_room(ctx)
    if room is None or getattr(room, 'monster', 0):
        return

    if random.uniform(0, 100) > _ENCOUNTER_CHANCE_PCT:
        return

    _mark_seen(player)

    level = int(getattr(player, 'map_level', 1) or 1)
    room_flags = getattr(room, 'flags', None) or []
    is_vacuum = 'water' in room_flags or 'water_with_rocks' in room_flags
    threat_name = 'METEOR' if (level == 6 and is_vacuum) else 'FLYING BANSHEE'

    await ctx.send(['', f'LOOK OUT!! {threat_name}!!'])
    await ctx.send(_GROWTH_ANIMATION)
    await ctx.send('YOU DODGE WILDLY!')

    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(
        f'{name} dives for cover as a {threat_name.lower()} hurtles past!',
        exclude_self=True,
    )

    stats = getattr(player, 'stats', None) or {}
    pd = int(stats.get('Dexterity', 10))
    pi = int(stats.get('Intelligence', 10))
    pe = int(stats.get('Energy', 10))
    ps = int(stats.get('Strength', 10))

    z = random.randint(1, 100)
    penalty_lines = []
    if pd < _LOW_STAT_THRESHOLD:
        z += _DEX_PENALTY
        penalty_lines.append('(Low dexterity: -10%)')
    if pi < _LOW_STAT_THRESHOLD:
        z += _INT_PENALTY
        penalty_lines.append('(Low IQ: -5%)')
    if pe < _LOW_STAT_THRESHOLD:
        z += _ENERGY_PENALTY
        penalty_lines.append('(Low energy: -5%)')
    if ps < _LOW_STAT_THRESHOLD:
        z += _STR_PENALTY
        penalty_lines.append('(Low strength: -5%)')
    if penalty_lines:
        await ctx.send(penalty_lines)

    hp = int(getattr(player, 'hit_points', 1) or 1)
    if z < _DODGE_SUCCESS_MAX or hp < _MERCY_HP_THRESHOLD:
        player.experience = int(getattr(player, 'experience', 0) or 0) + _XP_REWARD_ON_DODGE
        player.unsaved_changes = True
        await ctx.send(f'Whew... Missed...(+{_XP_REWARD_ON_DODGE} ep)')
        return

    if hp > _DAMAGE_HP_FLOOR:
        base_damage = hp // 2  # SPUR: hp=hp/2 -- same expression printed and reassigned
        block_chance = _lazer_shield_block_chance(player)
        if block_chance and random.randint(1, 100) <= block_chance:
            await ctx.send('YOUR LAZER SHIELD KICKS IN!')
            damage = base_damage // 2
        elif block_chance:
            await ctx.send("(Your Lazer Shield didn't kick in fast enough!)")
            damage = base_damage
        else:
            await ctx.send("(Too bad you didn't USE a LAZER SHIELD)")
            damage = base_damage

        armor_pct = _armor_damage_reduction_pct(player)
        if armor_pct and damage > 0:
            absorbed = (damage * armor_pct) // 100
            if absorbed:
                damage -= absorbed
                await ctx.send(f'Your armor absorbs {absorbed} of the impact!')

        new_hp = max(1, hp - damage)
        await ctx.send(f'CRUNCH!! {damage} DAMAGE!')
        player.hit_points = new_hp
        player.unsaved_changes = True
        await ctx.send_room(
            f'{name} is struck hard by the {threat_name.lower()}!',
            exclude_self=True,
        )
