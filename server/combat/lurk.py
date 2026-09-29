"""combat/lurk.py — LURK combat command (SPUR.COMBAT.S:82-96, 247-262, 324-341).

Requires a living ally; costs Honor; a loaded ammo weapon fires over the
ally's head at a to-hit/damage penalty (`player_attacks(is_lurking=True)`
in combat/resolution.py handles that penalty), while any other weapon
(melee, empty ammo weapon, or a LIGHT-named weapon) skips the player's own
swing entirely so only the allies attack. While lurking, the monster's
counter-attack is redirected off the player and onto a living ally, who
may then flee outright if lightly wounded and the player's Honor is low
(SPUR.COMBAT.S:324-341, "m.a1").

combat/engine.py's CombatSession round loop calls into this module rather
than owning the mechanic itself; see CombatSession._is_lurking_this_round
for how the per-round choice threads through to the monster's swing.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from bar.ally_data import Ally, AllyFlags, AllyPosition, AllyStatus
from monsters import monster_display_name

if TYPE_CHECKING:
    from combat.engine import CombatSession
    from network_context import GameContext


def has_living_ally(player) -> bool:
    """True if the player's party has at least one ally who can still fight
    (SPUR.COMBAT.S:82 "(a1+a2+a3)<1" -- summed hit points of the three ally
    slots)."""
    party = getattr(player, 'party', None)
    if not party:
        return False
    for member in party:
        if not isinstance(member, Ally):
            continue
        if member.status in (AllyStatus.DEAD, AllyStatus.UNCONSCIOUS):
            continue
        if (member.hit_points or 0) > 0:
            return True
    return False


def _living_allies(player) -> list:
    return [
        m for m in (getattr(player, 'party', None) or [])
        if isinstance(m, Ally)
        and m.status not in (AllyStatus.DEAD, AllyStatus.UNCONSCIOUS)
        and (m.hit_points or 0) > 0
    ]


async def resolve_swing(ctx: 'GameContext') -> bool:
    """Resolve the Honor cost and fire/skip branch for a LURK swing
    (SPUR.COMBAT.S:87-96, p.attack). Sends the "you lurk behind your
    allies"/"you fire over your ally's head" message and deducts Honor.

    Returns True if the player still gets to swing this round (ammo
    weapon, loaded, not a LIGHT-named weapon); False if the swing is
    skipped entirely and only the allies attack.
    """
    player = ctx.player
    weapon = getattr(player, 'readied_weapon', None)
    weapon_name = (getattr(weapon, 'name', '') or '').upper()
    wc = getattr(weapon, 'weapon_class', None) if weapon else None
    wc_str = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
    is_ammo_type = wc_str in ('projectile', 'energy')
    ammo_rounds = int(getattr(player, 'ammo_rounds', 0) or 0)

    # zz$="*" cases (SPUR.COMBAT.S:91-92): out of ammo for an ammo
    # weapon, or a LIGHT-named weapon (e.g. LIGHT SABRE) -- both cost
    # an extra point of Honor and never fire.
    out_of_ammo = is_ammo_type and ammo_rounds < 1
    light_named = 'LIGHT' in weapon_name
    zz_star = out_of_ammo or light_named
    fires = is_ammo_type and not zz_star

    # Honor cost (SPUR.COMBAT.S:87-93)
    from base_classes import PlayerClass
    p2 = 3 if getattr(player, 'char_class', None) == PlayerClass.ASSASSIN else 2
    hp = getattr(player, 'hit_points', 0)
    if hp > 20:
        p2 += 1
    if hp < 10:
        p2 -= 1
        if hp < 5:
            p2 -= 1
    if zz_star:
        p2 -= 1
    p2 = max(p2, 0)

    if int(getattr(player, 'honor', 0) or 0) > p2:
        player.adjust_honor(-p2)

    if fires:
        await ctx.send("You fire over your ally's head..")
    else:
        await ctx.send('You lurk behind your allies.')
    return fires


async def try_redirect_to_ally(session: 'CombatSession', ctx: 'GameContext', result) -> bool:
    """SPUR.COMBAT.S lurk.a / m.a1 (COMBAT.S:247-262, 324-341): while
    lurking, the monster's counter-attack is forced off the player and
    onto a random living ally instead. Unlike
    CombatSession._try_redirect_to_mount() (a roll-gated chance active
    whenever mounted), this is guaranteed once a living ally exists --
    SPUR's reroll loop (`if vq=2 then if d=1 goto lurk.a`) never lands
    back on d=1 (the player) while lurking, and the LURK gate at the top
    of the round already required one.

    Unlike the mount redirect, the ally actually takes the hit (SPUR's
    m.a1 branch subtracts it from a1/a2/a3 and can kill the ally) -- here
    it's the same damage that would otherwise have landed on the player,
    since m.a1 skips the player's own shield/armor mitigation block
    entirely for an ally target. m.a1 also shaves the redirected hit down
    by 1 point outright, and 2 more for an Elite ("!"-flagged, same
    AllyFlags.ELITE this port already uses for the ambush-immunity and
    ally-attack accuracy checks -- see CombatSession._check_tactical_ambush()
    and combat.resolution.ally_attacks()'s has_light_armor) ally, clamped
    at 0 ("No damage!").

    If the ally survives the hit, it may still lose its nerve and flee
    outright (COMBAT.S:328-330, 341) -- a 0-9 roll, shifted by the
    player's current Honor (vk; see ../../programming-notes/spur-variables.md)
    the same way resolve_swing() spent it this round, compared against
    the ally's *remaining* hit points: low HP or low Honor both raise the
    odds. An Elite ally never rolls this at all (SPUR forces z=0 in the
    same branch that grants its damage reduction). A fleeing ally reverts
    to AllyStatus.FREE and leaves the party outright, same as
    encounters/monster.py's _try_ally_tactical() desertion roll -- not
    death, but gone from this fight either way.
    """
    if not result.hit or result.damage <= 0:
        return False

    player = ctx.player
    living = _living_allies(player)
    if not living:
        return False

    target = random.choice(living)
    elite = AllyFlags.ELITE in (target.flags or [])

    dmg = result.damage - 1
    if elite:
        dmg -= 2
    dmg = max(dmg, 0)

    target.hit_points = max(0, (target.hit_points or 0) - dmg)
    player.unsaved_changes = True

    pname = getattr(player, 'name', 'Someone')
    mname = monster_display_name(session.monster, capitalize=True)
    dmg_text = f'(-{dmg} HP)' if dmg else '(No damage!)'
    prefix = '[Light Armor] ' if elite else ''
    await ctx.send(
        f'{prefix}{mname} attacks you, but strikes {target.name} instead!  {dmg_text}'
    )
    await ctx.send_room(
        f'{mname} attacks {pname}, but strikes {target.name} instead!',
        exclude_self=True,
    )

    if target.hit_points <= 0:
        target.status = AllyStatus.DEAD
        await ctx.send(f'{target.name} is dead.')
        await ctx.send_room(
            f'{target.name} falls, fighting for {pname}!',
            exclude_self=True,
        )
        return True

    if not elite:
        roll = random.randint(1, 10) - 1
        honor = int(getattr(player, 'honor', 0) or 0)
        if honor < 400:
            roll += 2
        elif honor < 800:
            roll += 1
        if honor > 1600:
            roll -= 2
        elif honor > 1200:
            roll -= 1
        roll = max(roll, 0)

        if roll > target.hit_points:
            await ctx.send(f'{target.name} throws down all weapons and runs away!')
            await ctx.send_room(
                f"{target.name} deserts {pname}'s party!", exclude_self=True,
            )
            target.status = AllyStatus.FREE
            target.owner = None
            target.position = AllyPosition.EMPTY
            party = getattr(player, 'party', None)
            if party and target in party:
                party.remove(target)

    return True
