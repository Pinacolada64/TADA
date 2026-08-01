"""ally_events/capture_horse.py — turn a wild horse monster into a MOUNT
ally: gender roll, name prompt, breed/colour roll, party add, battle log.

Extracted (8/1/26, Ryan) out of combat/engine.py's CombatSession, which
had this inline as `_finalize_mount_capture()`/`_prompt_horse_name()` --
same motivation as starvation.py living in ally_events/ rather than
encounters/: this is ally-mechanic logic, not the combat-round bookkeeping
that has to stay on CombatSession itself (self._done.set(),
self._remove_attacker(ctx) -- those still live in combat/engine.py, which
calls capture_mount() below and then does that session-specific cleanup).

Two entry points, both from combat/engine.py:
  CombatSession.lasso()          -- explicit LASSO command, guaranteed
                                     capture once a monster/slot check
                                     passes (SPUR.USE.S "lasso").
  CombatSession._try_class_tame() -- passive per-round Druid/Ranger taming
                                      chance, no SPUR precedent.

Breed/colour are pure display flavor (base_classes.HorseBreed/HorseColor,
surfaced via LOOK <horse name>) -- no SPUR precedent, new to TADA.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from network_context import GameContext
    from bar.ally_data import Ally

# Classic-sounding horse names for the 'R' random-name option (SPUR original
# has no equivalent -- mounts weren't gendered there at all). All 4-12
# characters, no punctuation, so they pass prompt_horse_name()'s own rules.
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

_FORBIDDEN_NAME_CHARS = set('!@#$%^&*()_-+=[{]}\\|:;<,>.?/')


def _random_horse_name(gender: str) -> str:
    names = _FEMALE_HORSE_NAMES if gender == 'f' else _MALE_HORSE_NAMES
    return random.choice(names)


def _monster_hp(monster: dict) -> int:
    return int(monster.get('strength') or monster.get('hit_points') or 5)


async def prompt_horse_name(ctx: 'GameContext', gender: str = 'm') -> Optional[str]:
    """Prompt for a horse name (4-12 chars, no symbols).  None on cancel.

    'R' picks a random gender-appropriate name (mirrors 'R' for a random
    pronounceable password in commands/new_player.py's character
    creation) -- checked before the length/forbidden-char rules so a
    bare 'R' doesn't get rejected as "too short".
    """
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
        bad = _FORBIDDEN_NAME_CHARS.intersection(name)
        if bad:
            await ctx.send(f'"{next(iter(bad))}" not allowed in name.')
            continue
        return name


async def mount_slot_available(ctx: 'GameContext', *, verbose: bool) -> bool:
    """True if ctx.player has room for a new mount ally.

    verbose=True sends the usual refusal message on failure (used by the
    explicit LASSO command); verbose=False stays silent (used by the
    passive Druid/Ranger taming check, which shouldn't spam a message
    every round just because the player's party happens to be full).
    """
    from bar.ally_data import AllyFlags
    from bar.allies import owned_allies

    def _is_mount(a) -> bool:
        return AllyFlags.MOUNT in (a.flags or [])

    allies = owned_allies(ctx.player)
    # The original game's 3-ally cap is on top of, not inclusive of, a mount
    # -- a horse doesn't take one of the 3 regular ally slots (Ryan,
    # confirmed against original gameplay). Only count non-MOUNT allies
    # against the cap.
    if len([a for a in allies if not _is_mount(a)]) >= 3:
        if verbose and not ctx.player.is_expert:
            await ctx.send('Only 3 allies allowed, sell one to Fat Olaf at the Bar first.')
        return False
    if any(_is_mount(a) for a in allies):
        if verbose:
            await ctx.send('Only 1 mount per customer.')
        return False
    return True


async def capture_mount(ctx: 'GameContext', monster: dict) -> Optional['Ally']:
    """Prompt for a horse name and, if given, add it as a MOUNT ally.

    Shared tail end of both LASSO and the passive Druid/Ranger taming
    event. Returns the new Ally on success, None if the player cancelled
    the name prompt. Does NOT touch any CombatSession state (self._done,
    attacker list) -- that bookkeeping stays with the caller in
    combat/engine.py.
    """
    from bar.ally_data import Ally, AllyFlags, AllyStatus
    from base_classes import HorseBreed, HorseColor

    player = ctx.player

    # SPUR never tracked a mount's own gender (lasso.b stores mounts as
    # packed name+flag strings with no gender slot, so its flavor text
    # just always says "he"/"him") -- this port gives Ally a real
    # .gender field, so roll it for real instead of hardcoding male.
    gender = random.choice(('m', 'f'))
    # Breed/colour are pure display flavor (base_classes.HorseBreed/
    # HorseColor, see LOOK <horse>) -- no SPUR precedent, new to TADA.
    # Rolled up front so the capture-announcement line can name them.
    breed = random.choice(list(HorseBreed))
    color = random.choice(list(HorseColor))
    gender_word = 'male' if gender == 'm' else 'female'
    await ctx.send(f'Your horse seems to be a {gender_word} {color} {breed}!')

    name = await prompt_horse_name(ctx, gender)
    if name is None:
        return None

    # SPUR lasso.b: ms (monster strength) + 5, h1=0 -- unlike a purchased
    # ally, a freshly-lassoed mount starts with unseeded hit_points.
    strength = _monster_hp(monster) + 5
    mount = Ally(name=name, gender=gender, strength=strength, to_hit=0,
                 flags=[AllyFlags.MOUNT])
    mount.breed       = breed
    mount.color       = color
    mount.status      = AllyStatus.SERVANT
    mount.owner       = player.name
    mount.hit_points   = 0
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

    return mount
