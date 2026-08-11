# Charisma Usage Audit

Date: 2026-08-11

Scope: every read/write of the `CHR` player stat across `server/` (live game
paths in `simple_server.py` / `commands/new_player.py`, plus dead/legacy
paths noted separately).

## TL;DR

Charisma is almost entirely decorative. It has zero mechanical effect
anywhere in the game — no combat, shop, spell, quest, or NPC-reaction code
ever reads it. Worse: the live character-creation flow doesn't even roll
it, so most characters don't have a `CHR` key in their stats dict at all,
and the `stats` command doesn't display it even if they did. Charisma also
has no SPUR precedent — the original BASIC game had 6 stats, not 7. TADA
added Charisma but never gave it a job.

---

## It's not part of the live stat lineup

- `commands/new_player.py:1105-1107` — `_STAT_ORDER` (the list actually
  rolled at character creation) is `[STR, DEX, CON, INT, WIS, EGY]`.
  **CHR is not in this list.**
- `commands/new_player.py:1122-1131` (`_roll_stats`) — builds a fresh
  `stats = {}` from only those 6 stats and **overwrites**
  `ctx.player.stats` with it, discarding the CHR key that
  `set_up_stats()` (`player.py:124-128`) had originally put there.
  **Result: no newly created character has a `CHR` key in their stats
  dict at all**, except—
- `characters.py:137-148` (`apply_race_class_deltas`) — for **Dwarves
  only**, the +2 CHR racial bonus (`base_classes.py:408`) re-creates the
  key via `stats.get(stat, 0) + delta` → `CHR = 2`. Every other race
  never gets the key back. No class bonus ever touches CHR
  (`base_classes.py:434-443`).
- That stray Dwarf `CHR = 2` does leak into one number: HP at creation is
  `round(sum(after.values()) / len(after)) + random.randint(0, 9)`
  (`commands/new_player.py:1171`), averaged over whatever keys exist — so
  Dwarves silently average over 7 stats instead of 6. That's an
  accident of dict-summing, not a designed effect.

## Players can't even see it

- `commands/stats.py:159-224` (`_build_stats_lines`, the live `stats`
  command) prints Strength, Constitution, Intelligence, Dexterity,
  Wisdom, Energy — **six lines, no Charisma line at all.** A player has
  no in-game way to check their own Charisma score.

## Complete list of every place CHR is touched, anywhere

1. `base_classes.py:390` — enum member (`CHR = "Charisma"`).
2. `base_classes.py:408` — Dwarf +2 creation bonus (mostly orphaned, see above).
3. `base_variables.py:9-12` — display name + flavor phrases
   ("less/more influential") — **defined but never read anywhere else in
   the codebase.**
4. `create_character.py:829` — shown in the **legacy/dead** creation flow
   (not wired into `simple_server.py`).
5. `player.py:934-937`, `new_player_2.py:345,372` — docstring/doctest
   examples only.
6. `commands/editplayer.py:713-740` — admin `editplayer` iterates all 7
   `PlayerStat` members generically, so a DM *can* view/set CHR — the
   only uniformly-reachable path to it.

That's the entire inventory. No combat file, no shop pricing formula, no
spell (`commands/cast.py:83-97`'s stat-effect map has letters for S/W/D/C/E/I
but nothing for CHR — no spell can raise or lower it), no NPC-reaction
code (Skip's Bar, Vinny, Zelda) ever reads Charisma.

## The tempting near-miss: "CHARM" ≠ Charisma

The Charm Potion / spontaneous monster-taming mechanic sounds like a
natural Charisma home. It isn't:

- `spells/charm.py:80-159` — no stat check at all; gated only by monster
  flags (`mechanical`, `tough`).
- `encounters/monster.py:319-370,353` — spontaneous "d.charm" taming roll
  is **`INT + WIS + 2*xp`**, plus race/class modifiers — Charisma never
  enters the formula.

## Contrast: what the other stats do (rough mechanical-touchpoint counts)

| Stat | Touchpoints | Examples |
|---|---|---|
| Intelligence | ~11 | spell success (`commands/cast.py:139,158`), sell prices (`shoppe/armory.py:210`), charm roll, desert direction-sensing, read minimum |
| Strength | ~9 | duel initiative, weapon-ready minimum (`commands/ready.py:136`), PRAY restore, battle hit rating |
| Energy | ~7 | flee chance, unseat-check, PRAY, battle hit rating |
| Dexterity | ~6 | surprise roll (`encounters/monster.py:259`), duel initiative, BHR |
| Wisdom | ~6 | charm roll, direction-sensing, reading grants WIS |
| Constitution | ~5 | PRAY restore, Skip's Bar buffs, duel unseat-check |
| **Charisma** | **~0** | Dwarf creation bonus (usually invisible) + admin editor only |

Charisma is not just "less used than average" — it's the only one of the
seven with **no mechanical effect whatsoever**, and it's also the only one
players can't even see on their own character sheet.

## Where charisma could plausibly earn its keep

Some natural, low-risk homes for it, roughly in order of how well they fit
the existing systems:

- **Shop prices** — `shoppe/armory.py:210`'s sell formula already factors
  INT (`pi`); a CHR-scaled haggling discount/markup (buy *or* sell,
  `price *= 1 - (chr - 10) * 0.01`-style) would extend the same pattern
  across armory, wizard shop, and general store without touching combat
  balance.
- **NPC reactions** — Skip, Vinny, and Zelda already have gender-based
  dialogue branches (`bar/skip.py:40-49`, `bar/vinny.py:37-48`); a CHR
  check could unlock friendlier discounts/extra dialogue/tips, curt vs.
  warm variants, the same way.
- **Spontaneous charm taming** — folding CHR into (or alongside) the
  existing INT+WIS roll in `encounters/monster.py:353` would finally
  connect the "charm" name to the stat that sounds like it should drive
  it. Alternative: keep charm-taming as the INT/WIS "outsmart the beast"
  skill it already is, and give CHR its own distinct roll instead (see
  below) so the two don't collapse into redundancy.
- **Charm Potion success** (`spells/charm.py:80-159`, currently no roll
  at all) — potion could still always work on non-tough/non-mechanical
  monsters, but high CHR grants a bonus, e.g. the charmed monster starts
  with better morale/loyalty (less likely to desert per the tactical/
  desert roll referenced in `encounters/monster.py:29-34`).
- **A distinct "social" axis, separate from INT/WIS** — right now
  `INT+WIS` covers *both* charm-taming and desert/labyrinth navigation
  (`encounters/desert.py:57`) and duel-flee chances
  (`combat/duel.py:580-582`) — a lot of overlap for two stats. Charisma
  could own the emotional/social half instead:
  - A pre-combat de-escalation check: high CHR gives a chance to calm a
    *non*-charmable, non-tough monster into backing off without a fight
    (distinct from the existing DEX-based surprise roll at
    `encounters/monster.py:245-270`).
  - Ally desertion resistance — a charismatic owner's allies desert less
    often (ties into the existing tactical/desert roll).
  - Guild-guard interactions (`encounters/monster.py:36-41`) — a
    charismatic non-member could talk their way past a guard instead of
    fighting, on a CHR-gated roll.
  - Recruiting/servant mechanics (`bar/fat_olaf.py`'s Servant Trade, the
    post-kill ally recruitment roll in `encounters/monster.py`, ~50%
    chance) — a natural fit since it's literally "will this NPC agree to
    follow you."
  - Duel bystander reaction (`combat/duel.py:352-356`) — a charismatic
    duelist could get a small crowd-cheering/distraction bonus if a
    bystander broadcast is active, reusing the pattern already used in
    `spells/charm.py` and `combat/duel.py`.
  - PRAY (`commands/pray.py`) is probably the wrong fit thematically — a
    prayer isn't a social encounter — worth leaving alone.

## Plumbing that needs fixing before any of the above matters

- **CHR isn't rolled at character creation** for non-Dwarves
  (`commands/new_player.py:1105-1107` excludes it from `_STAT_ORDER`) —
  it needs to join STR/DEX/CON/INT/WIS/EGY in the roll, or every new
  mechanic will always read as "worst possible charisma."
- **CHR isn't shown in the `stats` command** (`commands/stats.py`) —
  needs a display line so players can see the stat before it starts
  mattering.
- **CHR isn't spell-targetable** (`commands/cast.py:83-97`'s
  `_stat_enum`/`_stat_cap` maps) — needed if a self-buff spell/item is
  ever added.
- **No dedicated admin display** (`commands/editplayer.py` reaches CHR
  only via the generic `for stat in PlayerStat` loop) — low priority, but
  worth a look if DMs want to tune it for testing.

The single lowest-effort fix, regardless of which mechanical idea (if
any) gets picked up: add CHR back into `_STAT_ORDER` and add a Charisma
line to `commands/stats.py` so it's at least a real, visible number.

**New player log/stat field note**: per this repo's `CLAUDE.md`, if CHR
becomes a "real" tracked stat with its own creation roll (rather than a
cosmetic afterthought), that's exactly the kind of change that should get
an `editplayer.py` menu entry — chat with Ryan about where it goes before
considering the change done.

---

## Sourcing

Findings compiled via a full-codebase grep/read pass (Explore-agent
research task, not a live test run). File:line references reflect the
state of the code as of 2026-08-11 — re-verify before relying on any
specific line number if the surrounding file has since been edited.
