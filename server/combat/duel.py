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

# Duel implementation is not yet written.
# See notes above for the design constraints inherited from SPUR.
