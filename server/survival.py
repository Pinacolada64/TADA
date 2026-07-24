"""survival.py — Hunger, thirst, poison, and disease tick mechanics.

Mirrors SPUR.COMBAT.S lines 12-20 and SPUR.MAIN.S lines 13-22/227.

player.food/player.drink both run 0-config.survival_max (default 20,
sysop-tunable -- see config.py's SETTINGS_METADATA). (Note: SPUR's own
`ps`/`pe` are player Strength/Energy, not food/drink -- corrected here
after an earlier wrong guess.)
Every config.survival_tick_interval commands each depletes by 1 (also
sysop-tunable -- Ryan felt the shipped default of 10 was too aggressive;
rather than pick new hardcoded values for either, both are CONFIG
settings). Setting survival_tick_interval to -1 disables depletion
entirely (Ryan's call, for a sysop who doesn't want this feature at
all) -- food/drink stay wherever they are; poison/disease/starvation
checks below are unaffected, since those are independent of the passive
depletion step.
Poison deals -2 HP per tick (30% chance); disease deals -1 HP per tick
(30% chance).  Warnings are shown whenever either drops below threshold
-- those thresholds (3/7/4) are still fixed absolute numbers, not scaled
to survival_max, so a sysop raising the max well past 20 will see the
"hungry"/"thirsty" warnings fire much later relative to a full meter than
at the default.
Both food and drink reaching 0 is fatal.

Admins and Dungeon Masters are immune to the whole tick (Ryan's call) --
no depletion, no poison/disease damage, no starvation -- so a sysop
debugging live doesn't have to babysit their own hunger/thirst meter.
"""

from __future__ import annotations
import random


def survival_tick(player) -> list[str]:
    """Decrement food/drink on schedule; apply poison/disease; return warnings.

    Call once per command in the game loop.  Returns a (possibly empty)
    list of strings to send to the player.  Sets player.hit_points = 0
    and appends a death line when the player starves or is killed by poison.
    Admins/DMs are immune -- see module docstring -- and return [] without
    touching food/drink/hit_points or advancing the counter at all.
    """
    from config import config
    from flags import PlayerFlags

    if player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER):
        return []

    # Persisted on the player (player.py's simple_keys) so logging out and
    # back in doesn't reset the countdown.
    counter = getattr(player, '_survival_counter', 0) + 1
    player._survival_counter = counter

    max_value = config.survival_max
    interval  = config.survival_tick_interval

    if interval != -1 and counter % interval == 0:
        player.food  = max(0, getattr(player, 'food',  max_value) - 1)
        player.drink = max(0, getattr(player, 'drink', max_value) - 1)
        player.unsaved_changes = True

    food  = getattr(player, 'food',  max_value)
    drink = getattr(player, 'drink', max_value)

    # Keep the boolean HUNGER/THIRST flags (flags.py, shown by editplayer/
    # STATS) in sync with the actual counters -- same < 7 threshold as the
    # warning messages below. Nothing else in the codebase ever set these;
    # they'd stay permanently "No" regardless of real hunger/thirst.
    (player.set_flag if food  < 7 else player.clear_flag)(PlayerFlags.HUNGER)
    (player.set_flag if drink < 7 else player.clear_flag)(PlayerFlags.THIRST)

    msgs: list[str] = []

    # Poison: 30% chance per tick, -2 HP (SPUR.COMBAT.S:15).
    if getattr(player, 'poisoned', False) and random.randint(1, 10) < 4:
        player.hit_points = getattr(player, 'hit_points', 0) - 2
        player.unsaved_changes = True
        msgs.append('THE POISON WEAKENS YOU!')
        if player.hit_points < 1:
            player.hit_points = 0
            return msgs + ['You have succumbed to the poison!']

    # Disease: 30% chance per tick, -1 HP (SPUR.COMBAT.S:16).
    if getattr(player, 'diseased', False) and random.randint(1, 10) < 4:
        player.hit_points = getattr(player, 'hit_points', 0) - 1
        player.unsaved_changes = True
        msgs.append('THE DISEASE WEAKENS YOU!')
        if player.hit_points < 1:
            player.hit_points = 0
            return msgs + ['You have succumbed to the disease!']

    # Starvation: both completely exhausted (SPUR.COMBAT.S:12).
    if food < 1 and drink < 1:
        player.hit_points = 0
        player.unsaved_changes = True
        return msgs + ['YE HAVE STARVED TO DEATH!!']

    # Faint warning takes priority over individual messages (SPUR line 19).
    if food < 3 or drink < 3:
        msgs.append('YOU ARE BECOMING FAINT!')
    else:
        if drink < 7:
            msgs.append("YOU'RE THIRSTY." if drink >= 4 else "YOU'RE VERY THIRSTY!")
        if food < 7:
            msgs.append("YOU'RE HUNGRY." if food >= 4 else "YOU'RE VERY HUNGRY!")

    return msgs


def restore_food(player, amount: int) -> None:
    """Add *amount* to player.food, capped at config.survival_max."""
    from config import config
    player.food = min(config.survival_max, getattr(player, 'food', 0) + amount)
    player.unsaved_changes = True


def restore_drink(player, amount: int) -> None:
    """Add *amount* to player.drink, capped at config.survival_max."""
    from config import config
    player.drink = min(config.survival_max, getattr(player, 'drink', 0) + amount)
    player.unsaved_changes = True


def ration_restore(item) -> int:
    """Return how many points a ration item restores (1-9).

    Mirrors SPUR's gs variable (item quality).  Derived from price since
    rations.json has no explicit quality field.
    """
    price = getattr(item, 'price', 10) or 10
    return max(1, min(9, price // 10))


def apply_poison(player) -> None:
    player.poisoned = True
    player.unsaved_changes = True


def cure_poison(player) -> None:
    player.poisoned = False
    player.unsaved_changes = True


def apply_disease(player) -> None:
    player.diseased = True
    player.unsaved_changes = True


def cure_disease(player) -> None:
    player.diseased = False
    player.unsaved_changes = True
