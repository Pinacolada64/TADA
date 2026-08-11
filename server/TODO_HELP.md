7/14/26:

Scoured the codebase for gaps in the help system (`commands/help.py`):
every `Command` subclass's `help = Help(...)` attribute, and the
standalone `register_topic(...)` concept topics (currently: `about`,
`commandline`, `bhr`, `rooms`).

## Commands with no real `help = Help(...)`

Good news: every *live* command (anything `commands/command_processor.py`'s
auto-discovery actually registers -- requires a concrete `execute()`
override and a non-empty `name`) already has a filled-out `help`. The
gaps below are all dead/legacy code that predates the current
`Command`/`Help` system and is never registered, so there's no player-
facing hole here -- listed for completeness/cleanup awareness, not as
help-writing work:

- `commands/admin.py`: `ExampleAdminCommand` (scaffold, no `name`),
  `RestartCommand`, `ShutdownCommand`, `BootCommand`, `UnbanCommand` --
  these four use the old `help_summary()`/`_execute()` style, not
  `execute()`, so they're not even instantiable against the current
  abstract base `Command`.
- `commands/guest.py`: `GuestCommand` -- generic base-class scaffolding,
  no `name`, no concrete `execute()`.
- `commands/login.py`: `LoginCommand` -- no `name`, so it can't
  auto-register; real login is `ConnectCommand`
  (`commands/connect.py`, `aliases = ["con", "login"]`), which already
  has full help.
- `future/main.py` -- defines its own separate `Command` ABC
  (`class Command(abc.ABC)`), unrelated to `commands.base_command.
  Command`. Its `AttackCommand`/`DebugCommand`/`GoCommand`/etc. are a
  prototype file, not wired into the real game at all.

If any of these get resurrected into real commands later, give them
proper `Help` objects at that point -- not worth writing help text for
dead code now.

## Concept topics worth adding (`register_topic(..., category=HelpCategory.CONCEPT)`)

Grounded in where each concept actually lives in the code, same
convention as the existing `bhr`/`rooms`/`commandline` topics:

- **✅ Done (8/10/26).** ~~Honor / alignment~~ -- written as the
  `honor`/`alignment` CONCEPT topic.
- **✅ Done (8/10/26).** ~~Guilds~~ -- written as the `guilds`/`guild`
  CONCEPT topic. Notes it explicitly flags that live guild dueling
  isn't implemented yet, rather than repeating the choice-screen's
  aspirational "dueling, territory control" flavor text as fact.
- **✅ Done (8/10/26).** ~~Experience levels vs. `xp_level`~~ -- written
  as the `experience`/`xplevel`/`levels` CONCEPT topic, folded together
  with the "Battle experience tiers" entry below since they're the same
  disambiguation.
- **✅ Done (8/10/26).** ~~The More Prompt / paging system~~ -- written
  as the `moreprompt`/`paging` CONCEPT topic.
- **✅ Done (8/10/26).** ~~Virtual areas~~ -- written as the
  `virtualareas` CONCEPT topic.
- **Weapon classes** (bash/slash, poke/jab, pole/range, projectile,
  energy, proximity) and class/race weapon affinities --
  `WeaponClass` enum + `weapon_bonus()` (`item_system.py:241`, used by
  `commands/ready.py`'s displayed skill/damage bonus).
- **✅ Done (8/10/26).** ~~Shield/armor condition ("intactness")~~ --
  written as the `armorcondition`/`shieldcondition`/`intactness`
  CONCEPT topic.
- **✅ Done (8/10/26).** ~~Battle experience tiers (GREEN/VETERAN/ELITE)~~
  -- folded into the `experience` topic above rather than a separate
  one, since the whole point is disambiguating it from `xp_level` in
  the same breath.
- **✅ Done (8/10/26).** ~~Stat rolling~~ -- written as the
  `statrolling`/`rollstats`/`4d6` CONCEPT topic.
- **Duels** -- BHR's own help text already references dueling
  ("sizing up other adventurers before a duel"), but dueling itself
  isn't implemented yet (MECHANICS.md's Live Duel / Autoduel are both
  "Not Implemented", `combat/duel.py` has design notes only). Hold off
  on a dedicated `duel` concept topic until the feature exists --
  premature to document a mechanic that doesn't work yet.
- **✅ Done (8/10/26).** ~~Parties / allies~~ -- written as the
  `parties`/`allies` CONCEPT topic (cross-linked with the new
  `eliteally` topic from the tips.txt pass below).
- **✅ Done (8/10/26).** ~~PETSCII vs. ANSI terminal types~~ -- written
  as the `petscii`/`ansi`/`clienttype` CONCEPT topic. Correction while
  writing it: `Translation` (`terminal.py`) has only three members --
  PETSCII/ASCII/ANSI. This file's earlier note claiming a fourth
  `COMMODORE` value was wrong; no such member exists.
- **Horses / mounts** -- `commands/mount.py`/`commands/dismount.py`
  have command-level help, but the broader concept (acquiring a horse,
  CHARGE, unseating, SADDLED/ARMORED flags -- spread across
  MECHANICS.md:828-963 and touching `mount`, `dismount`, `lasso`,
  `attack`) doesn't have a single place tying it together the way
  `bhr` does for its own topic.

Not flagged: **groups** (fully covered already by `help groups`, no gap
even though `page`/`whisper` cross-reference `#<group>` syntax), **news**
(fully covered by `commands/news.py`'s own help), **threaded message
boards** (not implemented yet -- `threaded_messages.py` is a skeleton
per MECHANICS.md's "Design Ideas (not yet decided)" section, nothing to
document).

- **Room alignment / territory control** (Ryan): each guild duel win in
  a room shifts that room's alignment to the winning guild, and
  thereafter members of that guild get a duel bonus while standing in
  it. Searched `SPUR-code/SPUR.DUEL2.S`/`SPUR.GUILD.S` and this repo's
  Python for anything matching ("territ", "align" near "guild/room",
  room-ownership fields) and found nothing -- the closest existing
  things are (a) `commands/new_player.py`'s Guild step already
  advertises "territory control" in its flavor text without any backing
  mechanic, and (b) tips.txt's "park your character in your guild's HQ
  ... duel bonus if anybody attacks while you are gone" (a *player*-HQ
  bonus, not a room-capture system). This looks like a genuinely new
  mechanic (or one from a part of the original SPUR source not in this
  checkout) rather than a restoration -- needs design work (how
  alignment is stored per room, decay/contest rules, HQ vs. any-room)
  before it's ready for a help topic; noted here so it isn't lost.
  - **Checked `remotes/origin/skip` too (7/14/26)**: that branch's
    `SPUR-code/` has six files master's checkout doesn't --
    `SPUR.ARMORY.S`, `SPUR.BACKUP.S`, `SPUR.COMPILE.S`, `SPUR.MISC8.S`,
    `SPUR.MISC9.S`, `SPUR.NEW.S` -- none mention room/territory
    alignment either. Its `SPUR.DUEL.S`/`SPUR.DUEL2.S`/`SPUR.GUILD.S`
    only differ from master's copies in cosmetic text/typo fixes (e.g.
    "Roll on the ground.." capitalization, `flag(32)` vs `un=1`
    variable-naming variants) -- no functional difference in the
    `guild` label's logic. Grepped the *entire* skip branch tree (388
    files) for "territ"/"conquer" near room/guild context; the only
    hit was an unrelated Wikipedia quote about military "point man"
    terminology in a `text-listings/t_combat.lbl` comment. Still no
    source evidence this mechanic ever existed in code -- treating it
    as a from-scratch design, not a restoration, unless something turns
    up in an even earlier/different source snapshot.
  - **Found something adjacent and real while looking, though**:
    `SPUR.DUEL2.S`'s `guild` label (lines ~316-336, identical on both
    branches) tallies **guild win/loss standings** to a
    `guild.standings` data file after any guild-vs-guild duel (`vv`/`yz`
    are the two duelists' guild numbers; `zz`/`yw` are running win/loss
    counters per guild, position-addressed by guild slot 1/2/3). This
    is a real, previously-ungrounded mechanic -- MECHANICS.md:683
    already lists "**Guild standings** — ranking of guilds by kills/XP"
    as a not-yet-implemented stub, but without this citation. Worth
    updating that MECHANICS.md line to point at `SPUR.DUEL2.S`'s
    `guild` label, and worth keeping **separate** from the room-
    alignment idea above -- a guild-wide scoreboard is a different
    mechanic from any individual room "belonging" to a guild.

## Additional pass: SPUR-data/tips.txt and SPUR-data/SPUR.HELP.TXT

Read both source text files directly (63 and 45 lines) for concepts the
original game's own player-facing help/tips already considered
important enough to mention. Cross-checked each against this port's
code/MECHANICS.md before listing, same as above -- only flagging things
that are either implemented-but-unexplained (real gap) or
not-implemented (parked, not a help gap yet).

**Implemented, no help topic yet** -- ready to write:
- **✅ Done (8/10/26).** ~~Special weapons required for certain
  monsters~~ -- written as the `specialweapon`/`silverbullet` CONCEPT
  topic.
- **✅ Done (8/10/26).** ~~Examine before you pick things up~~ --
  written as the `examine`/`lookfirst` CONCEPT topic. Correction while
  writing it: the TODO's original file references were stale --
  `_examine_item()` now lives in `commands/examine.py` (a real EXAMINE/
  `x` command), not `commands/look.py`; the cursed-pickup penalty is
  `commands/get.py`'s `_cursed_penalty()`, not a line-25 `hp.5` in
  `look.py`.
- **Item persistence rule** (tips.txt: a found item reappears next
  session *unless* you're still carrying it -- eat it before you log
  off to reset it) -- still not written up. Correction: the field is
  `player.item_history`/`player.ration_history` (`player.py:369-370`),
  not `player.picked_up_items` as this file previously said -- that
  name doesn't exist in the current codebase. Both histories are
  reseeded from current inventory on login
  (`record_item_pickup()`/`record_ration_pickup()`,
  `commands/get.py`/`simple_server.py` both read them to hide
  already-taken room items). Worth a topic since it's counter-intuitive.
- **✅ Done (8/10/26).** ~~Elite allies~~ -- written as the `eliteally`
  CONCEPT topic (folded into a new `parties`/`allies` topic too, since
  neither existed and they're closely related -- see this file's
  now-resolved "Parties / allies" entry above).
- **LOOT and the Pawn Shop together** -- still half-blocked on LOOT;
  not written yet.
- **"Dusk Approaches" / session time limit -- NOT actually implemented,
  despite this file previously saying "✅ implemented".** Re-checked
  8/10/26: grepped the whole non-test tree for `ticks`/`Dusk`/session-
  time enforcement -- `config.py`'s `session_time_limit_minutes` setting
  exists and is documented as sharing "the same budget the Dusk warning
  counts down", but nothing in the codebase actually reads that setting
  to enforce a limit or send a warning; `survival.py`'s `survival_tick()`
  has no ticks/Dusk logic at all. `MECHANICS.md:204`'s "Dusk warning —
  message when session time < 120 ticks remain" is aspirational/stale,
  not a description of working code. Do NOT write this help topic until
  the feature actually exists -- would otherwise document a mechanic
  players can't experience. Moved to TODO.md instead as a feature gap.

**Not implemented -- premature for a help topic, noted for TODO.md instead:**
- **WEAR** (don armor) and **LOOT** (search an unconscious player) --
  both listed in `SPUR.HELP.TXT`'s original command list, neither
  exists as a command in this port (`commands/` has no `wear.py` or
  `loot.py`). EXAMINE is already folded into LOOK (`commands/look.py`),
  so that one's not actually missing, just renamed/merged.
- **The Dwarf** (fixed level-1 NPC, steals gold until killed, killer
  gets all accumulated stolen gold) -- confirmed "Not Implemented" in
  MECHANICS.md, no matching code found (`DWARF_ALIVE` flag exists and
  is displayed on `stats`, but no NPC/mechanic backs it yet).
- **Victory conditions ("Conqueror" status)** -- now implemented
  (`victory.py`, `commands/movement.py`'s level-6 "Ladder Up" hook at
  room 117 "Shimmering Portal" -- SPUR's own escape point per
  `SPUR.MISC.S`'s `cl=6, di=5` trigger, not level 1 as `SPUR.HELP.TXT`'s
  flavor text implies). Gates: the King of the Wraiths must be dead
  (`PlayerFlags.WRAITH_KING_ALIVE`), plus `victory_gold_amount` silver in
  hand and/or `victory_item_number` carried per `config.victory_type`.
  Note: `SPUR.MISC7.S`'s actual win check never tests
  `PlayerFlags.SPUR_ALIVE` at all, despite `SPUR.HELP.TXT`'s "defeat
  SPUR" framing -- only the Wraith King gates it. A help topic
  explaining the real escape conditions (and clarifying that SPUR
  himself isn't a literal gate) would now be accurate and worth writing.

8/8/26:

**✅ Done (8/10/26). Show a command's aliases in `help <command>`'s detail view.** Right now
`commands/help.py`'s general `help` listing already shows aliases inline
next to each command name (`_show_general_help()`, ~line 787-793: `als =
[a for a in cmd.aliases if a != name]`, rendered as `name (alias1,
alias2)`), but `format_help()` -- the function that actually renders
`help <command>`'s detail view (summary/description/usage/examples) --
never reads `cmd.aliases` at all. So looking up a specific command's full
help doesn't tell you it's also reachable under another name; you'd only
learn that from the general list. Noticed while adding
`commands/unwear.py` (`aliases = ['remove', 'doff']`) -- `help unwear`
gives no hint that `remove`/`doff` work too. Small, self-contained fix
whenever picked up: add an "Aliases:" line to `format_help()`'s output,
same spot/style as the existing Usage/Examples sections.
