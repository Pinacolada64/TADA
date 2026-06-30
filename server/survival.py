"""survival.py — Hunger and thirst tick mechanics.

Mirrors SPUR.COMBAT.S lines 12-20 and SPUR.MAIN.S lines 13-22/227.

pe (SPUR) = drink; ps (SPUR) = food.  Both run 0-20.
Every TICK_INTERVAL commands each depletes by 1.
Warnings are shown whenever either drops below threshold.
Both reaching 0 is fatal.
"""

from __future__ import annotations

_TICK_INTERVAL = 10   # commands between each depletion step
_MAX           = 20   # starting / maximum value for both food and drink


def survival_tick(player) -> list[str]:
    """Decrement food/drink on schedule and return any warning lines.

    Call once per command in the game loop.  Returns a (possibly empty)
    list of strings to send to the player.  Sets player.hit_points = 0
    and appends a death line when the player starves.
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

    # Starvation: both completely exhausted (SPUR.COMBAT.S:12).
    if food < 1 and drink < 1:
        player.hit_points = 0
        player.unsaved_changes = True
        return ['YE HAVE STARVED TO DEATH!!']

    msgs: list[str] = []

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
