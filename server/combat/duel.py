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
# Rough draft, SPORT DUEL only (both players online and in the same room)
# ---------------------------------------------------------------------------
#
# SPUR.DUEL.S's actual tactic system (attack/parry/bash/flee/roll, with a
# hidden AI that predicts your next move from your recent history -- see
# op.tact/tac.bash) is a genuinely deep turn-by-turn state machine. Building
# a live, synchronous two-player turn loop across two independent asyncio
# connections is its own can of worms (whose "turn" is it, what happens if
# one side disconnects mid-round, etc.) -- deliberately deferred.
#
# This first pass instead resolves a SPORT DUEL automatically, round by
# round, the moment both sides have accepted -- closer in spirit to how
# SPUR's own AUTODUEL (offline defender) already worked, just applied to
# both directions instead of one. Reuses combat/resolution.py's
# monster_attacks() for the actual hit/shield/armor/damage math by handing
# it a small synthetic "monster" dict standing in for whichever player is
# attacking that swing -- this means duels automatically get the same
# shield-block chance, armor degradation, and (new this session)
# shield_proficiency progression as PvE combat, instead of a separate,
# parallel formula. Porting the real move-by-move tactic AI is future work
# (see TODO.md/TODO_HELP.md).
#
# No weapon = no fight, mirroring SPUR.DUEL.S's no.wep gate (deducts 1 INT,
# refuses to swing) -- unlike AUTODUEL's auto-pick-best-weapon-from-file
# behaviour (this port has no separate weapon file to pick from anyway;
# player.readied_weapon already covers that role via inventory).

import random
from dataclasses import dataclass, field

from item_system import weapon_bonus
from combat.resolution import monster_attacks

_MAX_ROUNDS = 20        # safety cap -- SPUR duels can in principle run long
_MIN_HP_AFTER_LOSS = 15  # SPUR.DUEL2.S hell/hell2: loser left at hp=15, not dead


@dataclass
class DuelRoundResult:
    attacker_name: str
    defender_name: str
    hit: bool
    damage: int
    shield_blocked: int = 0
    armor_blocked: int = 0
    shield_destroyed: bool = False
    armor_destroyed: bool = False


@dataclass
class DuelOutcome:
    winner_name: str
    loser_name: str
    rounds: list = field(default_factory=list)   # list[DuelRoundResult]
    fled: bool = False   # True if the cap was hit with nobody down (treated as a draw/flee)


def _offense_rating(player, weapon) -> int:
    """Synthetic 'ma' (SPUR: size/attack rating) for monster_attacks().

    Higher = hits more often. Built from the player's weapon class/race
    bonus (item_system.weapon_bonus()) and character level, in the same
    3-9ish range SPUR's monster to_hit values live in -- there's no
    canonical PvP formula to port (SPUR's real one is the attack/attack1
    percentage system noted above), so this is a reasonable stand-in, not
    a faithful port.
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


def _apply_round_result(attacker, defender, result) -> DuelRoundResult:
    """Mirror combat/engine.py's _apply_monster_damage() for a PvP round:
    HP loss, shield/armor degradation, and shield-block proficiency gain."""
    if result.shield_blocked:
        defender.gain_shield_proficiency(getattr(defender, 'active_shield_id', None))
    if result.shield_destroyed:
        defender.shield = 0
    elif result.shield_degraded:
        defender.shield = max(0, int(getattr(defender, 'shield', 0) or 0) - result.shield_degraded)

    if result.armor_destroyed:
        defender.armor = 0
    elif result.armor_degraded:
        defender.armor = max(0, int(getattr(defender, 'armor', 0) or 0) - result.armor_degraded)

    hp = int(getattr(defender, 'hit_points', 1) or 1)
    defender.hit_points = hp - result.damage
    defender.unsaved_changes = True

    return DuelRoundResult(
        attacker_name=getattr(attacker, 'name', '?'),
        defender_name=getattr(defender, 'name', '?'),
        hit=result.hit,
        damage=result.damage,
        shield_blocked=result.shield_blocked,
        armor_blocked=result.armor_blocked,
        shield_destroyed=result.shield_destroyed,
        armor_destroyed=result.armor_destroyed,
    )


def resolve_sport_duel(challenger, defender) -> DuelOutcome:
    """Resolve a full SPORT DUEL between two online players, round by round.

    Both sides must already have a readied weapon (caller's job to check --
    see DuelCommand.execute() below, which mirrors SPUR.DUEL.S's no.wep
    gate before ever calling this). Mutates both players' hit_points/
    shield/armor/shield_proficiency in place, same as PvE combat.
    """
    rounds: list[DuelRoundResult] = []

    for _ in range(_MAX_ROUNDS):
        # Challenger swings first each round (SPUR.DUEL2.S's "auto.c" always
        # has the challenging side act first).
        for attacker, defender_ in ((challenger, defender), (defender, challenger)):
            weapon = getattr(attacker, 'readied_weapon', None)
            synthetic_monster = {'to_hit': _offense_rating(attacker, weapon)}
            result = monster_attacks(synthetic_monster, defender_)
            rounds.append(_apply_round_result(attacker, defender_, result))

            if int(getattr(defender_, 'hit_points', 1) or 1) <= 0:
                winner, loser = attacker, defender_
                loser.hit_points = _MIN_HP_AFTER_LOSS
                loser.unsaved_changes = True
                return DuelOutcome(
                    winner_name=getattr(winner, 'name', '?'),
                    loser_name=getattr(loser, 'name', '?'),
                    rounds=rounds,
                )

    # Safety cap reached with both still standing -- treat as a draw.
    return DuelOutcome(winner_name='', loser_name='', rounds=rounds, fled=True)


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

from base_classes import Guild
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import find_online
from commands.stats import _bhr  # reused rather than re-deriving BHR here
from guild_standings import load_standings, record_duel_result
from network_context import GameContext


def _guild_display(guild) -> str:
    return str(guild.value if hasattr(guild, 'value') else guild or Guild.CIVILIAN)


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

    outcome = resolve_sport_duel(challenger, defender)

    lines_for_challenger = ['', f'|yellow|=== DUEL: {challenger.name} vs. {defender.name} ===|reset|']
    lines_for_defender = ['', f'|yellow|=== DUEL: {challenger.name} vs. {defender.name} ===|reset|']
    for r in outcome.rounds:
        if not r.hit:
            line = f'{r.attacker_name} swings at {r.defender_name} and misses.'
        else:
            extra = []
            if r.shield_blocked:
                extra.append(f'shield absorbs {r.shield_blocked}')
            if r.armor_blocked:
                extra.append(f'armor absorbs {r.armor_blocked}')
            extra_txt = f' ({", ".join(extra)})' if extra else ''
            line = f'{r.attacker_name} hits {r.defender_name} for {r.damage} damage!{extra_txt}'
        lines_for_challenger.append(line)
        lines_for_defender.append(line)

    if outcome.fled:
        draw_line = "Neither combatant could finish the fight -- it's a draw."
        lines_for_challenger.append(draw_line)
        lines_for_defender.append(draw_line)
        await challenger_ctx.send(lines_for_challenger)
        await ctx.send(lines_for_defender)
        return CommandResult.ok('Duel ended in a draw.')

    winner_ctx = challenger_ctx if outcome.winner_name == challenger.name else ctx
    loser_ctx  = ctx if winner_ctx is challenger_ctx else challenger_ctx
    winner, loser = winner_ctx.player, loser_ctx.player

    # SPUR.DUEL2.S hell/hell2: winner takes the loser's gold in hand.
    from base_classes import PlayerMoneyTypes
    stolen = loser.get_silver(PlayerMoneyTypes.IN_HAND)
    if stolen:
        loser.subtract_silver(PlayerMoneyTypes.IN_HAND, stolen)
        winner.set_silver_absolute(
            PlayerMoneyTypes.IN_HAND,
            winner.get_silver(PlayerMoneyTypes.IN_HAND) + stolen,
        )

    win_line  = f'|light_green|You have vanquished {loser.name}!|reset|' + (
        f' (+{stolen} gold)' if stolen else ''
    )
    lose_line = f'|red|You have been vanquished by {winner.name}!|reset|' + (
        ' He takes your gold!' if stolen else ''
    )
    lines_for_challenger.append(win_line if winner is challenger else lose_line)
    lines_for_defender.append(lose_line if winner is challenger else win_line)

    await challenger_ctx.send(lines_for_challenger)
    await ctx.send(lines_for_defender)

    winner_guild = getattr(winner, 'guild', Guild.CIVILIAN)
    loser_guild  = getattr(loser,  'guild', Guild.CIVILIAN)
    if winner_guild not in (Guild.CIVILIAN, Guild.OUTLAW) and loser_guild not in (Guild.CIVILIAN, Guild.OUTLAW):
        record_duel_result(_guild_display(winner_guild), _guild_display(loser_guild))

    return CommandResult.ok(f'{winner.name} defeated {loser.name}.')


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
            ('duel #standings', 'Show guild win/loss standings.'),
        ],
        examples = [
            ('duel Railbender', 'Challenge Railbender to a duel.'),
            ('duel accept',     'Fight the player who challenged you.'),
        ],
        description = (
            'Challenges another online player in your room to a SPORT '
            'DUEL. Both sides need a weapon readied (see READY). Once '
            'accepted, the duel resolves automatically -- the loser is '
            'left at low HP (not killed) and the winner takes their '
            'gold in hand. See "help bhr" for the danger rating shown '
            'before you decide whether to accept.'
        ),
        notes = [
            'This is a rough first pass: SPUR\'s original live tactic '
            'system (attack/parry/shield-bash/flee, with an AI that '
            'reads your recent moves) is not ported yet -- the duel '
            'resolves automatically once both sides accept.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not args:
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

        target_name = args[0]
        if target_name.lower() == ctx.player.name.lower():
            await ctx.send("You can't duel yourself.")
            return CommandResult.fail('Cannot duel self.')

        found, not_found = find_online(ctx, [target_name], same_room_only=True)
        if not found:
            await ctx.send(f'{target_name} is not here.')
            return CommandResult.fail('Target not found in room.')

        return await _send_challenge(ctx, found[0])
