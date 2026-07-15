# encounters/

World NPC/event encounters that aren't tied to any one room's static
level data — they're placed, triggered, or rolled for dynamically at
runtime instead of living in `level_N.json`. Each module owns its full
mechanic (flavor text, stat effects, combat hookup where relevant) and
is self-contained; this package does not import from `commands/` or
`combat/` internals beyond the public `combat.enter_combat()` helper —
see each module's own docstring for the exact SPUR source citations.

Command/server modules import *from* here, not the other way around
(same one-way-dependency convention as `quests/`).

## Index

| Module | What | Trigger | Status |
|---|---|---|---|
| `dwarf.py` | Wandering level-1 thief. Steals silver (or an item once broke) via a per-move roll; appears as a fightable monster in his own room; pays out his entire shared hoard to whoever kills him. | 1% per move (`SPUR.MAIN.S`'s `gosub dwarf`), level 1 only | ✅ Implemented |
| `little_girl.py` | Approaches with a sob story (sick grandmother); G)ive/I)gnore/A)ttack — only Give is safe, the other two have a real chance she's EVILYNN (#106) in disguise. | 0.4% per move (2% world-event roll × 20% slice) | ✅ Implemented |
| `meteor.py` | A "FLYING BANSHEE" (or literal "METEOR" on level 6 in a vacuum room) swoops in; dodge check scaled by stats, HP halved on a miss unless a Lazer Shield or Power Armor absorbs it. | 0.3% per move (2% world-event roll × 15% slice) | ✅ Implemented |
| `djinn_sighting.py` | Not a fight at all -- an alternate trigger for the Bar's existing debt-collection ambush (`bar/thug_attack.py`). Owe Vinny money, and this sets `PlayerFlags.THUG_ATTACK` for next login; debt-free players just get a flavor sighting. **Skip branch only** -- master has no `djinn` label. | 0.34% per move (2% world-event roll × skip's 17% slice) | ✅ Implemented |

## The shared random-event dispatcher (not yet built)

`little_girl.py`, `meteor.py`, and `djinn_sighting.py` are all slices of
the *same* dispatcher in the original source (`SPUR.MAIN.S:239`'s 2%
per-move roll, then a d100 sub-roll across several sub-events in
`SPUR.MISC6.S`'s `random`/`no.test` labels). Master and skip disagree on
how many sub-events there even are:

| Sub-event | Master's slice | Skip's slice | Status |
|---|---|---|---|
| Galadriel | 15% (`z<15`) | 15% (`z<15`) | ✅ Implemented — but as its own quest trigger (quest #8, `quests/README.md`), not wired into this dispatcher |
| Meteor | 15% (`z<30`) | 17% (`z<32`) | ✅ `meteor.py` (master's numbers) |
| An ally finding gold | 15% (`z<45`, `al.find`) | 17% (`z<49`) | Not built |
| An ally's death | 15% (`z<60`, `dead.al`) | Called unconditionally every roll, not a slice at all | Not built |
| The Enforcer | 20% (`z<80`) | 17% (`z<66`) | Not built — see `TODO.md`'s "7/15/26" `ys$` inventory for the full trace (`*enf` token, a named NPC duel against "THE ENFORCER") |
| Blue Djinn sighting | *(doesn't exist)* | 17% (`z<83`) | ✅ `djinn_sighting.py` — **skip only** |
| Little Girl | 20% (`z>=80`) | 17% (`z>=83`) | ✅ `little_girl.py` |

Three of these sub-events exist now, each rolling its own **flat
composite share** independently (2% × its slice) instead of sharing one
real dispatcher. This means — unlike the original, where only one
sub-event can fire per successful roll — more than one could in
principle trigger on the same move right now. Worth replacing all three
flat rolls with a real shared dispatcher module (e.g.
`encounters/world_events.py`) that does the 2% roll once, then the d100
sub-roll, and routes to whichever `try_*` function corresponds to the
result — cleaner, and restores mutual exclusivity to match the source.

The skip branch's version of this dispatcher (`SPUR.MISC6.S:140-148`,
skip) is meaningfully different beyond just adding the Blue Djinn slice
-- per-event `ys$` gates are checked *inline during the roll* so a roll
that lands on an already-seen event's slice spills over into the next
untried one instead of just doing nothing that move (master's version,
by contrast, checks the gate *inside* the target label after the
`goto`, so a repeat roll just silently returns with no event at all that
move). Worth designing the real dispatcher off skip's version rather
than master's, if/when this gets built — it's the more polished design,
even though master is otherwise the default source of truth in this
project (see `quests/README.md`'s sourcing rule).

## Known master/skip balance divergences

Not every difference between the two branches is a stub-vs-complete
situation — sometimes both sides have a complete, working mechanic with
different numbers. `meteor.py` currently hardcodes master's numbers
(dodge succeeds on `z<90`; Energy/Strength penalties -5% each) — skip's
version is harsher (`z<70`; -7% each). See `TODO.md`'s "7/15/26" entry
for the plan to make this sysop-configurable instead of picking one
side permanently.

## Not from SPUR

A few additions in this package aren't ported mechanics at all, called
out individually in each module's docstring:

- `dwarf.py`'s periodic relocation timer and per-player kill immunity
  (the original places him once at world-init and never moves him, and
  tracks nothing per-player).
- `dwarf.py`'s mounted/Pixie 50% evasion chance.
- `little_girl.py`'s, `meteor.py`'s, and `djinn_sighting.py`'s
  `ctx.send_room()` bystander broadcasts (SPUR has no concept of other
  players witnessing an event).
- `meteor.py`'s Lazer Shield (objects.json #116) and Power Armor damage
  mitigation, tied to `shield_proficiency`/`player.armor` — the original
  meteor code never checks either stat; SPUR's real `LAZ.SH` mechanic
  (`SPUR.MISC4.S`/`SPUR.COMBAT.S`) is a *different*, unconditional
  energy-weapon-damage halving for level-6+ monster attacks, not tied to
  this encounter or to skill at all.
