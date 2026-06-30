"""combat/rewards.py — Loot and experience calculation after a monster kill.

Gold formula (adapted from SPUR.MISC.S p.a4, lines 400-404):

    SPUR flags control the *probability* of finding gold on the body:
        X  (no_gold)        →  0% — never carries gold
        :  (mechanical)     →  0% — robots don't carry coin
        no flag             → 25% — small chance
        >  (chance_find_gold)   → 50% — usually carries something
        >> (chance_find_gold_2x)→ 100% — always has gold

    Amount when gold is found (unchanged from SPUR):
        p1 = max(3, min(8, (ma + zo - 1) // 2))   ← monster attack threshold
        g2 = p1 * 25 + randint(0, 49) + 10

Experience:
    SPUR awards +1 ep per attack attempt (SPUR.COMBAT.S line 103, ep=ep+1).
    Kill grants no separate exp bonus — accumulation is per-swing.
"""
from __future__ import annotations

import random

# Probability of finding gold by flag tier (0.0 – 1.0)
_GOLD_CHANCE_NONE   = 0.25   # no > flag: small chance
_GOLD_CHANCE_SINGLE = 0.50   # >  flag: "gold on body"
_GOLD_CHANCE_DOUBLE = 1.00   # >> flag: "twice the chance" → guaranteed


def gold_from_monster(monster: dict) -> int:
    """Return gold pieces found on the monster's body, or 0 if none found."""
    flags = monster.get('flags', {})

    if flags.get('no_gold') or flags.get('mechanical'):
        return 0

    # Determine probability tier
    if flags.get('chance_find_gold_2x'):
        chance = _GOLD_CHANCE_DOUBLE
    elif flags.get('chance_find_gold'):
        chance = _GOLD_CHANCE_SINGLE
    else:
        chance = _GOLD_CHANCE_NONE

    if random.random() >= chance:
        return 0

    # Amount formula (SPUR.MISC.S): p1 * 25 + random(50) + 10
    # p1: monster attack threshold; zo (carry weight) placeholder = 1
    ma = int(monster.get('to_hit') or 4)
    zo = 1
    p1 = max(3, min(8, (ma + zo - 1) // 2))
    return p1 * 25 + random.randint(0, 49) + 10


def exp_per_swing() -> int:
    """Experience gained per attack attempt (hit or miss).

    SPUR.COMBAT.S line 103: ep=ep+1
    """
    return 1
