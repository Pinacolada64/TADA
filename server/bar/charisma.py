"""bar/charisma.py — shared Charisma-tier helpers for bar NPC reactions.

Charisma has no SPUR precedent (see server/CHARISMA_AUDIT.md) and, until
this module, had no mechanical effect anywhere in the game. This gives
Vinny/Skip/Zelda one consistent way to read a player's Charisma instead of
each NPC growing its own ad hoc threshold.

Tiers (not a raw roll) drive dialogue *tone*, so an NPC's attitude toward
a given player stays consistent visit to visit. charisma_check() is
reserved for one-off yes/no favor rolls, so charm doesn't become a
guaranteed unlock.
"""
import random

from base_classes import PlayerStat

# Cutoffs sit either side of the midpoint of a 4d6-drop-lowest roll (3-18,
# average ~10.5) -- roughly the bottom/top quarters of the range.
_LOW_MAX  = 8
_HIGH_MIN = 16


def _get_charisma(player) -> int:
    # Mirrors bar/vinny.py's _gender_terms() / bar/skip.py's
    # _gender_address() -- both swallow a broad Exception here because
    # test fixtures commonly pass a MagicMock() player without real
    # stats; treat anything that isn't a usable int as "no data".
    try:
        chr_ = player.stats.get(PlayerStat.CHR, 0)
    except Exception:
        return 0
    return chr_ if isinstance(chr_, int) else 0


def charisma_tier(player) -> str:
    """Return 'low', 'mid', or 'high' based on the player's Charisma."""
    chr_ = _get_charisma(player)
    if chr_ <= _LOW_MAX:
        return 'low'
    if chr_ >= _HIGH_MIN:
        return 'high'
    return 'mid'


def charisma_check(player, dc: int) -> bool:
    """d20 + Charisma modifier vs dc -- for one-off NPC favor rolls.

    Modifier is (CHR - 10) // 2, the standard ability-score-to-modifier
    curve, so an average Charisma (10-11) roughly breaks even.
    """
    modifier = (_get_charisma(player) - 10) // 2
    return random.randint(1, 20) + modifier >= dc
