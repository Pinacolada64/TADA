"""survival.py — Hunger, thirst, poison, and disease tick mechanics.

Mirrors SPUR.COMBAT.S lines 12-20 and SPUR.MAIN.S lines 13-22/227.

pe (SPUR) = drink; ps (SPUR) = food.  Both run 0-20.
Every TICK_INTERVAL commands each depletes by 1.
Poison deals -2 HP per tick (30% chance); disease deals -1 HP per tick
(30% chance).  Warnings are shown whenever either drops below threshold.
Both food and drink reaching 0 is fatal.
"""

from __future__ import annotations
import random

_TICK_INTERVAL = 10   # commands between each depletion step
_MAX           = 20   # starting / maximum value for both food and drink


def survival_tick(player) -> list[str]:
    """Decrement food/drink on schedule; apply poison/disease; return warnings.

    Call once per command in the game loop.  Returns a (possibly empty)
    list of strings to send to the player.  Sets player.hit_points = 0
    and appends a death line when the player starves or is killed by poison.
    """
    # Session-only counter — not persisted, resets each login.
    counter = getattr(player, '_survival_counter', 0) + 1
    player._survival_counter = counter

    if counter % _TICK_INTERVAL == 0:
        player.food  = max(0, getattr(player, 'food',  _MAX) - 1)
        player.drink = max(0, getattr(player, 'drink', _MAX) - 1)
        player.unsaved_changes = True

    food  = getattr(player, 'food',  _MAX)
    drink = getattr(player, 'drink', _MAX)

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
    """Add *amount* to player.food, capped at _MAX."""
    player.food = min(_MAX, getattr(player, 'food', 0) + amount)
    player.unsaved_changes = True


def restore_drink(player, amount: int) -> None:
    """Add *amount* to player.drink, capped at _MAX."""
    player.drink = min(_MAX, getattr(player, 'drink', 0) + amount)
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
