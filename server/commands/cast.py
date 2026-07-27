"""commands/cast.py — Cast a known spell (SPUR.MISC3.S's `cast`/`cst.outc`/
`cast.spl` labels, verified directly against source with CRLF-stripped
`grep`, not summarized secondhand).

Spells are one-shot: a spell is removed from wherever spellbook.py's
spell_entries() found it (Spell Book or, for non-adepts/legacy saves, the
main inventory) *before* the outcome roll runs -- SPUR removes the known-
spell entry (xs$) before reading the spell record at all, so a fizzle or
backfire still costs the scroll, exactly like a real cast attempt should.

Outcome roll (cst.outc): b = max(3, 20 - INT), +2 if the caster's race is
Ogre (SPUR: pr=2 -- a race, not Druid, correcting an earlier secondhand
summary this session that conflated the two). a = random(b*100)/100+1,
compared against the spell's original 1-9 success stat -- this port's
Spell.cast_chance is that value already scaled x10 for display (per
items.py's own docstring: "q3 * 10 in SPUR display"), so the threshold
here is cast_chance/10 to recover it. a < threshold -> success; otherwise
a second random(10) roll, <5 -> backfire, else -> fizzle. Fizzle never
reaches an effect handler at all (SPUR: `if (not b) goto spl.fail` skips
`cast.spl` entirely) -- only success/backfire do.

Bonuses (cast.spl, applied only on a successful roll): Druids get +2
("DRUID POWER!") on every non-monster-damage spell; Wizards with a staff
readied (commands/get.py's _STAFF_IDS) get +1 on stat spells ("The staff
trembles..") or +4 on monster-damage specifically, plus (Wizard-only)
+5 XP and a damage bump on monster-damage.

Scope (Ryan's own choice, see /home/ryan/.claude/plans/abstract-tinkering-
wadler.md): built this pass -- stat spells (S/W/D/C/E/I), heal (P),
monster damage (M, requires an active CombatSession -- see
commands/attack.py's _active_session()/_monster_in_room(), a deliberate
simplification vs. SPUR's "usable any time a monster's in the room"), and
gold-to-bank transfer (T). Deferred and refused gracefully without
consuming the spell: level up/down (U/L), teleport-to-shoppe (R), and the
Aura sub-effects other than BOOTS (DISPEL POISON/APPLE A DAY/DRUID
HEALTH/WIZARD'S GLOW -- each has a real hook already, just not wired in
this pass). Deferred but flavor-stubbed (rolls normally, spell IS
consumed, success text with no mechanical payload, since Ryan asked for
these two specifically): G (SUMMON SPUR -- no SPUR NPC exists to summon)
and Aura's BOOTS OF SPEED (no session-countdown clock exists to extend).
"""
from __future__ import annotations

import random

import spellbook
from commands.base_command import Command, CommandResult, Mode
from commands.get import _STAFF_IDS
from commands.help import Help, HelpCategory
from network_context import GameContext

_STAT_LETTERS = 'SWDCEI'

_STAT_SUCCESS_FLAVOR = {
    'S': 'a bit stronger',
    'W': 'a bit wiser',
    'D': 'a bit more skillful',
    'C': 'healthier',
    'E': 'a surge of energy',
    'I': 'a bit smarter',  # SPUR's exact `smart` subroutine text
                            # (SPUR.MISC3.S:255).
}
_STAT_BACKFIRE_FLAVOR = {
    'S': 'a bit weaker',
    'W': 'a bit more foolish',
    'D': 'a bit more clumsy',
    'C': 'a bit less healthy',
    'E': 'a bit tired',
    'I': 'a bit dumber',
}

# Not-yet-wired-in effect types (see module docstring's scope section).
_DEFERRED_TYPES = {'U', 'L', 'R'}
_DEFERRED_AURA_NAMES = {'DISPEL POISON', 'APPLE A DAY', 'DRUID HEALTH', "WIZARD'S GLOW"}


def _stat_enum(effect_type: str):
    from base_classes import PlayerStat
    return {
        'S': PlayerStat.STR, 'W': PlayerStat.WIS, 'D': PlayerStat.DEX,
        'C': PlayerStat.CON, 'E': PlayerStat.EGY, 'I': PlayerStat.INT,
    }[effect_type]


def _stat_cap(effect_type: str, char_race) -> int:
    from base_classes import PlayerRace
    if effect_type == 'S' and char_race == PlayerRace.OGRE:
        return 24
    if effect_type == 'E':
        if char_race == PlayerRace.HUMAN:
            return 24
        if char_race == PlayerRace.HALF_ELF:
            return 22
    return 20


def _spell_list_lines(ctx) -> list[str]:
    from formatting import border_style_for_ctx
    from table import Align, Column, Table

    try:
        width = ctx.player.client_settings.screen_columns
    except AttributeError:
        width = 78

    t = Table(
        headers=[
            Column('#',      align=Align.RIGHT, min_width=2),
            Column('Name',                      min_width=14),
            Column('Effect',                     min_width=6),
            Column('Chance',  align=Align.RIGHT, min_width=6),
        ],
        title='Known Spells',
        border=True,
        border_style=border_style_for_ctx(ctx),
    )
    for i, entry in enumerate(spellbook.spell_entries(ctx.player), 1):
        item = entry.item
        t.add_row([
            str(i),
            getattr(item, 'name', '?'),
            getattr(item, 'effect_type', '?'),
            f"{getattr(item, 'cast_chance', 0)}%",
        ])
    return [''] + t.render(width=width) + ['']


def _roll_outcome(player, cast_chance: int) -> str:
    """Returns 'success', 'backfire', or 'fizzle' -- see module docstring
    for the full derivation. cast_chance is this port's 0-100 scaling of
    SPUR's original 1-9 success stat (items.py's Spell.cast_chance
    docstring: "q3 * 10 in SPUR display") -- divide by 10 to recover it."""
    from base_classes import PlayerRace, PlayerStat

    intelligence = player.stats.get(PlayerStat.INT, 10) if player.stats else 10
    b = max(3, 20 - intelligence)
    if getattr(player, 'char_race', None) == PlayerRace.OGRE:
        b += 2

    a = random.randint(1, b * 100) / 100 + 1
    threshold = cast_chance / 10
    if a < threshold:
        return 'success'
    return 'backfire' if random.randint(1, 10) < 5 else 'fizzle'


def _fizzle_lines(player) -> list[str]:
    """SPUR spl.fail: "Your spell fizzles..." plus a low-INT hint
    (SPUR.MISC3.S: `if pi<15 print "(Prehaps, if you were smarter..)"` --
    ported with the typo corrected to "Perhaps")."""
    from base_classes import PlayerStat

    lines = ['Your spell fizzles...']
    intelligence = player.stats.get(PlayerStat.INT, 10) if player.stats else 10
    if intelligence < 15:
        lines.append('(Perhaps, if you were smarter..)')
    return lines


def _caster_bonus(player, effect_type: str) -> tuple[int, str | None]:
    """Druid/staff bonus applied on a successful cast. Returns
    (flat_bonus, flavor_line_or_None)."""
    from base_classes import PlayerClass

    char_class = getattr(player, 'char_class', None)
    if char_class == PlayerClass.DRUID and effect_type != 'M':
        return 2, 'DRUID POWER!'

    if char_class == PlayerClass.WIZARD:
        weapon = getattr(player, 'readied_weapon', None)
        if getattr(weapon, 'id_number', None) in _STAFF_IDS:
            if effect_type == 'M':
                return 4, None  # monster-damage's own flavor line covers this
            if effect_type in _STAT_LETTERS:
                return 1, 'The staff trembles..'

    return 0, None


def _cast_stat(player, effect_type: str, magnitude: int, bonus: int, success: bool) -> tuple[str, str]:
    """Returns (outcome, flavor_line). Mirrors SPUR's cst.strn/wisd/etc.:
    even a successful roll collapses to a "backfire"-style decrease if the
    stat's already at its cap -- ported faithfully, not a bug."""
    stat = _stat_enum(effect_type)
    cap  = _stat_cap(effect_type, getattr(player, 'char_race', None))
    current = player.stats.get(stat, 10)

    if success and current < cap:
        player.stats[stat] = current + magnitude + bonus
        return 'success', f'(You feel {_STAT_SUCCESS_FLAVOR[effect_type]})'

    if current >= magnitude:
        player.stats[stat] = current - magnitude
        return 'backfire', f'(You feel {_STAT_BACKFIRE_FLAVOR[effect_type]})'
    return 'backfire', ''


def _cast_heal(player, magnitude: int, bonus: int, success: bool) -> tuple[str, str]:
    """SPUR cst.plyr: heal cap is 23 + xp_level (+2 for Ogre) -- this port
    has no fixed max-HP concept, so that dynamic formula *is* the cap."""
    from base_classes import PlayerRace

    xp_level = int(getattr(player, 'xp_level', 1) or 1)
    cap = 23 + xp_level
    if getattr(player, 'char_race', None) == PlayerRace.OGRE:
        cap += 2

    hp = int(getattr(player, 'hit_points', 0) or 0)
    if success and hp < cap:
        player.hit_points = hp + magnitude + bonus
        return 'success', '(You feel invigorated!)'

    if hp > magnitude:
        player.hit_points = hp - magnitude
        return 'backfire', '(You feel a wave of nausea.)'
    return 'backfire', ''


def _cast_transfer(player, success: bool) -> tuple[str, str]:
    """SPUR cst.xfer: success moves ALL hand silver to the bank; backfire
    moves all BANK silver to hand instead -- not magnitude-based, the
    whole pool either way."""
    from base_classes import PlayerMoneyTypes

    if success:
        amount = player.get_silver(PlayerMoneyTypes.IN_HAND)
        player.subtract_silver(PlayerMoneyTypes.IN_HAND, amount)
        player.subtract_silver(PlayerMoneyTypes.IN_BANK, -amount)  # add
        return 'success', 'Your silver has been transferred to your bank account.'

    amount = player.get_silver(PlayerMoneyTypes.IN_BANK)
    player.subtract_silver(PlayerMoneyTypes.IN_BANK, amount)
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, -amount)  # add
    return 'backfire', 'Spell has backfired. You are now carrying all your silver.'


async def _cast_monster(ctx, player, magnitude: int, bonus: int, success: bool) -> tuple[str, str] | None:
    """SPUR cst.mons. Requires an active CombatSession (deliberate
    simplification vs. SPUR's "any time a monster's in the room" -- see
    module docstring). Returns None if there's nothing to cast at (caller
    refuses the whole attempt, spell not consumed)."""
    from base_classes import PlayerClass
    from combat.engine import _monster_hp, _set_monster_hp
    from commands.attack import _active_session

    session = _active_session(ctx)
    if session is None:
        return None

    monster = session.monster
    flags   = monster.get('flags', {}) or {}
    mname   = monster.get('name', 'the monster')

    if flags.get('mechanical'):
        return 'fizzle', 'Mechanical devices are unaffected by magic!'
    if flags.get('magic_resistant'):
        return 'fizzle', f'{mname} sneers at your feats of magic.'
    if flags.get('appears_unaffected'):
        is_wizard_check = getattr(player, 'char_class', None) == PlayerClass.WIZARD
        resist_threshold = 6 if is_wizard_check else 5
        if random.randint(1, 10) > resist_threshold:
            return 'fizzle', f'{mname} appears unaffected!'

    is_wizard = getattr(player, 'char_class', None) == PlayerClass.WIZARD

    if not success and not is_wizard:
        # Non-wizard backfire heals the monster instead of hurting it.
        _set_monster_hp(monster, _monster_hp(monster) + magnitude)
        return 'backfire', f'The spell appears to have made {mname} stronger!'

    damage = magnitude
    lines  = []
    if is_wizard and success:
        player.experience = int(getattr(player, 'experience', 0) or 0) + 5
        damage += bonus
        weapon = getattr(player, 'readied_weapon', None)
        if getattr(weapon, 'id_number', None) in _STAFF_IDS:
            lines.append('Power BLASTS from the staff!')
        else:
            lines.append('Fire sizzles from your fingertips!')

    _set_monster_hp(monster, _monster_hp(monster) - damage)
    lines.append('The area glows with an eerie blue light..')
    if _monster_hp(monster) <= 0:
        await session._monster_dies(ctx)
    elif not success:
        lines.append(f'{mname} appears to have weakened.')

    return ('success' if success else 'backfire'), '\n'.join(lines)


class CastCommand(Command):
    name    = 'cast'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Cast a spell you know.',
        category = HelpCategory.COMBAT,
        usage    = [
            ('cast',            'List your known spells and pick one to cast.'),
            ('cast ?',          'Relist your known spells.'),
        ],
        examples = [
            ('cast', 'Open the casting prompt.'),
        ],
        description = (
            'Casts one of the spells you’ve learned at the Wizard’s cave. '
            'Spells are one-shot -- casting removes it from your Spell Book (or '
            'inventory) whether it succeeds, fizzles, or backfires. Success chance '
            'rises with Intelligence; Wizards get a bonus from a readied staff, '
            'Druids from their own calling.'
        ),
        notes = [
            'A failed roll has a further chance to backfire (a worse outcome, '
            'e.g. losing stat points or healing the monster you aimed at) rather '
            'than just fizzling harmlessly.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        entries = spellbook.spell_entries(player)

        if not entries:
            await ctx.send('You have no spells.')
            return CommandResult.ok()

        await ctx.send(_spell_list_lines(ctx))

        while True:
            raw = await ctx.prompt('Cast which spell number? (?=list, Q to leave)')
            if raw is None:
                return CommandResult.ok()
            choice = raw.strip()
            if not choice or choice.upper() == 'Q':
                return CommandResult.ok()
            if choice == '?':
                await ctx.send(_spell_list_lines(ctx))
                continue

            entries = spellbook.spell_entries(player)  # re-fetch: may have changed
            try:
                index = int(choice)
            except ValueError:
                await ctx.send('Enter a spell number, ? to list, or Q to leave.')
                continue
            if index < 1 or index > len(entries):
                await ctx.send('You do not know that spell.')
                continue

            spell = entries[index - 1].item
            break

        await self._cast(ctx, player, spell)
        return CommandResult.ok()

    async def _cast(self, ctx: GameContext, player, spell) -> None:
        effect_type = getattr(spell, 'effect_type', '')
        magnitude   = int(getattr(spell, 'effect_magnitude', 0) or 0)
        name        = getattr(spell, 'name', 'spell')

        is_deferred = effect_type in _DEFERRED_TYPES or (
            effect_type == 'A' and name.upper() not in ('BOOTS OF SPEED',)
        )
        if is_deferred:
            await ctx.send(
                "The Wizard's cave hasn't taught anyone how to unlock this "
                "spell's power yet."
            )
            return

        # Monster-damage needs an active fight before the spell (and its
        # one-shot use) is committed -- SPUR: "No monster here!" refuses
        # outright rather than wasting the scroll.
        if effect_type == 'M':
            from commands.attack import _active_session
            if _active_session(ctx) is None:
                await ctx.send("You'll need to be in combat first.")
                return

        spellbook.remove_spell(player, spell)
        player.unsaved_changes = True

        cast_chance = int(getattr(spell, 'cast_chance', 0) or 0)
        outcome = _roll_outcome(player, cast_chance)

        if outcome == 'fizzle':
            await ctx.send(_fizzle_lines(player))
            return

        success = outcome == 'success'
        bonus, bonus_line = _caster_bonus(player, effect_type) if success else (0, None)
        if bonus_line:
            await ctx.send(bonus_line)

        result = await self._dispatch(ctx, player, effect_type, name, magnitude, bonus, success)
        if result is None:
            await ctx.send(_fizzle_lines(player))
            return

        final_outcome, flavor = result
        if flavor:
            await ctx.send(flavor)
        if final_outcome == 'success':
            await ctx.send('Spell successful!')
        else:
            await ctx.send('Spell backfired!')

    async def _dispatch(self, ctx, player, effect_type, name, magnitude, bonus, success):
        if effect_type in _STAT_LETTERS:
            return _cast_stat(player, effect_type, magnitude, bonus, success)
        if effect_type == 'P':
            return _cast_heal(player, magnitude, bonus, success)
        if effect_type == 'T':
            return _cast_transfer(player, success)
        if effect_type == 'M':
            return await _cast_monster(ctx, player, magnitude, bonus, success)
        if effect_type == 'G':
            return ('success' if success else 'backfire'), (
                "The air shimmers, but SPUR's spirit does not answer your call."
                if success else
                'Nothing happens. The silence feels almost disappointed.'
            )
        if effect_type == 'A' and name.upper() == 'BOOTS OF SPEED':
            return ('success' if success else 'backfire'), (
                'You feel a fleeting burst of speed.' if success else
                'Your feet feel unusually heavy.'
            )
        return None
