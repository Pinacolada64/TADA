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

- **Honor / alignment** -- `honor` (int stat, 0-2000) drives
  `Alignment` (Good/Neutral/Evil, `base_classes.py`) and ally loyalty
  checks (`courage > honor` in `ally_events.py`). Players see "Current
  alignment" on `stats` with no explanation of how it's earned/lost.
- **Guilds** (Civilian / Iron Fist / Mark of the Sword / Mark of the
  Claw / Outlaw) -- `Guild` StrEnum (`base_classes.py`), chosen during
  character creation (`commands/new_player.py`'s Guild step),
  `PlayerFlags.GUILD_MEMBER`/`GUILD_AUTODUEL`/`GUILD_FOLLOW_MODE`.
  Ties into dueling/territory concepts the Guild step's own text
  already gestures at but doesn't fully explain.
- **Experience levels vs. `xp_level`** -- character level
  (`player.xp_level`, `player.py`) vs. battle experience (next entry)
  are two different "experience" concepts that share vocabulary and
  will confuse new players. No topic currently disambiguates them.
- **The More Prompt / paging system** -- command-level help exists
  (`commands/more_prompt.py`, `commands/prefs.py`'s 'M' row), but no
  general CONCEPT topic explains screen-by-screen "-- More --"
  pagination the way `rooms` explains a general term. Could mostly
  reuse `more_prompt.py`'s existing description text.
- **Virtual areas** (Bar / Shoppe / Elevator / guild HQs) and how they
  relate to ordinary rooms -- `bar/main.py`, `shoppe/main.py`,
  `shoppe/elevator.py`, `annex/main.py`; MECHANICS.md:315-322
  documents the `rc`/`rt` room-exit fields that route into them. This
  is a genuinely confusing mechanic (a "virtual area" isn't a room
  number) worth its own topic, distinct from `rooms`.
- **Weapon classes** (bash/slash, poke/jab, pole/range, projectile,
  energy, proximity) and class/race weapon affinities --
  `WeaponClass` enum + `weapon_bonus()` (`item_system.py:241`, used by
  `commands/ready.py`'s displayed skill/damage bonus).
- **Shield/armor condition ("intactness")** -- now directly relevant
  since the starting-equipment feature landed
  (`starting_equipment.py`'s `_roll_intactness()`, 10-69% on a 50/50
  roll); players will see "Shield: NN% intact" / "Armor: NN% intact"
  with no explanation of what the percentage means or how it degrades
  (`combat/resolution.py`'s block/degrade math).
- **Battle experience tiers (GREEN/VETERAN/ELITE)** -- per-weapon
  tracked experience (`player.weapon_experience`, `player.py`'s
  `gain_weapon_experience()`, +1 per killing blow per
  `SPUR.MISC.S:384`), VETERAN at 40, ELITE at 99
  (`combat/resolution.py`'s `battle_exp_bonuses()`), shown as a
  colored badge on `ready`. Should explicitly distinguish this from
  character `xp_level` above -- same "experience" word, different
  systems. The new `shield_proficiency` mechanic
  (`player.py`'s `gain_shield_proficiency()`) mirrors this exactly and
  should probably be covered by the same topic.
- **Stat rolling** -- character creation's attribute-roll step
  (`commands/new_player.py`'s `_roll_stats()`, 4d6-drop-lowest per
  stat) already has decent inline explanation text shown during
  creation (`_ROLL_EXPLANATION`), but no standalone `help stats`-
  adjacent CONCEPT topic for looking it up later outside of character
  creation.
- **Duels** -- BHR's own help text already references dueling
  ("sizing up other adventurers before a duel"), but dueling itself
  isn't implemented yet (MECHANICS.md's Live Duel / Autoduel are both
  "Not Implemented", `combat/duel.py` has design notes only). Hold off
  on a dedicated `duel` concept topic until the feature exists --
  premature to document a mechanic that doesn't work yet.
- **Parties / allies** -- `Party` (`party.py`), `Ally`/`Horse(Ally)`
  characters (`characters.py`, `character_editor.py`).
  `commands/take.py`/`commands/give.py` both say "party ally" in their
  help text with nothing to link to that explains what a party/ally
  actually is or how one is formed.
- **PETSCII vs. ANSI terminal types** -- `Translation` enum
  (`terminal.py`: PETSCII/ANSI/COMMODORE/ASCII), selected via
  `commands/prefs.py`'s Client Type row; affects rendering throughout
  `formatting.py` (e.g. guild sigils differ by translation). A "why
  does this look different on my terminal" topic would help new
  players picking a Client Type during/after character creation.
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
- **Special weapons required for certain monsters** (tips.txt: "the
  silver bullet for the Werewolf... any other weapon is just wasting
  your time") -- `combat/resolution.py`'s `check_special_weapon()`,
  monster's `special_weapon` field (`characters.py:86`). No topic
  explains that some monsters are effectively immune to ordinary
  weapons.
- **Examine before you pick things up** (tips.txt: cursed objects raise
  IQ if successfully examined first, lower it if picked up blind) --
  `commands/look.py`'s `_examine_item()` flags magic/cursed items on
  LOOK; `commands/get.py`'s cursed-item INT/HP penalty (`hp.5`, line
  ~25). The mechanic is real; nothing tells a player LOOK-before-GET is
  the way to avoid it.
- **Item persistence rule** (tips.txt: a found item reappears next
  session *unless* you're still carrying it -- eat it before you log
  off to reset it) -- `player.picked_up_items` (`player.py:307`,
  `commands/get.py`'s `_record()`). Worth a topic since it's
  counter-intuitive (most MUDs don't work this way).
- **Elite allies** (tips.txt: allies with a `!` after their name are
  more loyal, lightly armored, won't attack you over refused food) --
  `combat/resolution.py`'s `has_light_armor` param (`ally has "!" flag
  in SPUR`, line ~774), `+2` armor bonus. The flag/bonus exist in
  combat math; nothing surfaces what `!` means to a player looking at
  their ally list.
- **LOOT and the Pawn Shop together** -- pawn shop (sell anything you
  find) is implemented (`shoppe/pawn.py`), and LOOT (search an
  unconscious player, once per session) is listed "Not Implemented" in
  MECHANICS.md -- so this one's half-blocked; could still write the
  Pawn Shop half now and extend once LOOT lands.
- **"Dusk Approaches" / session time limit** -- ✅ implemented per
  MECHANICS.md:202 (`SPUR.COMBAT.S:11`, warning under 120 ticks
  remaining), but tips.txt's actual advice (don't start a tough fight,
  your weakened stats save as-is if time runs out, the monster resets
  but your combat hits on it don't) isn't explained anywhere in-game.
  Good concept-topic candidate once the exact current-port behavior is
  double-checked against tips.txt's claims (worth confirming the
  "monster resets, your hits carry over" half is still true here before
  writing it up as fact).

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
