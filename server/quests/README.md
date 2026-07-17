# Quests

A survey of multi-step item-fetch/repair/riddle mechanics found in the SPUR BASIC
source (`SPUR-code/*.S`), traced across both `master` and the `skip` branch (skip
sometimes has a fuller version of a mechanic that master only stubs — same pattern
as `SPUR.COMBAT.S`'s CHARGE, MOUNT, etc.). None of what's documented here is
implemented in the Python port yet — this is a research/planning doc to work from.

**Sourcing rule**: `.S` files are authoritative. `.lbl` files (`text-listings/`) are
from an abandoned, incompatible C64 porting attempt — flavor-text hints only, never
a mechanic source.

**A recurring blocker**: several quests hardcode room numbers (`cr=`) against
SPUR's *original* room-numbering scheme, which doesn't line up 1:1 with the already
-converted `server/level_N.json` files (see the room-1 gap investigation in git
history, and the confirmed case below where quest room 582 doesn't exist at all in
the current `level_6.json`). Anyone implementing these will likely need to re-derive
room numbering from the original `SPUR-data/level-N` binaries rather than trust the
`cr=` literals verbatim.

**Another gotcha, relevant to quests #2 and #6 below**: the `@@` room-condition
flag (our port's `RoomFlag.WATER`/`water_with_rocks`) is reused by SPUR to mean two
different things depending on level. `SPUR.MAIN.S:158,179` literally swaps the
requirement string: `i$="BOAT":if cl=6 i$="SPACE SUIT"`. So on levels 1–5, a
`water`-flagged room needs a Boat; on level 6, the *same* flag on a room means it's
vacuum and needs a Spacesuit instead. Confirmed against data: all 86 rooms literally
named "Outer Space" in `level_6.json` (black-void descriptions) carry the `water`/
`water_with_rocks` flag, not some dedicated space flag. **TODO**: give this a
level-aware label wherever it reaches the player or game logic (e.g.
`room_hazard_label(level, flags)` → "water"/"Boat" below level 6, "vacuum"/
"Spacesuit" at level 6+) instead of hardcoding `"water"` — see MECHANICS.md
"Special room traversal requirements" for the full note, including a heads-up about
`commands/mount.py`'s water check being one place that would misfire on level 6.

---

## Quest Table

| # | Quest | Required Item(s) | Reward | Branch | Confidence |
|---|-------|-------------------|--------|--------|------------|
| 1 | Headhunter's Island | Defeat "BIG CHIEF" (monster #84) | #40 Black Diamond, #78 Great Coat, weapon #57 Wraith Dagger | master | Confirmed (map/combat gauntlet, not a scripted fetch quest) |
| 2 | Spacesuit Repair | #133 Tool Kit + #134 Broken Spacesuit + #135 Spacesuit Parts | #122 Spacesuit (needed to survive `@@`-flagged vacuum rooms on level 6+ — see the flag-naming gotcha above) | master + skip | Confirmed |
| 3 | Communicator Repair | #133 Tool Kit + #141 Broken Communicator | #66 Communicator (USE to beam up to level 6, room 1) | master + skip | Confirmed |
| 4 | Security Cards | Search (`~*`) qualifying level-6 rooms | #131 Red Card (opens east doors) / #132 Green Card (opens west doors) | master | Confirmed mechanic; room placement is a loose end |
| 5 | Radiation Suit + Geiger Counter | — | #124 Radiation Suit (damage protection), #123 Geiger Counter (early warning) | master | Confirmed |
| 6 | Space Tracker | #138 Space Tracker | Shows galactic coordinates while traveling space rooms on level 6 | master | Confirmed |
| 7 | Ruby Slippers (Wizard of Oz) | #145 Broomstick, dropped in front of an NPC at level 6 room 582 | #144 Ruby Slippers (USE to teleport home to level 1, room 1) | master | Confirmed mechanic; broomstick acquisition and NPC identity untraced; room 582 doesn't exist in current `level_6.json` |
| 8 | Test of Galadriel | None (random encounter; riddle) | #143 Galadriel's Vial (full) | master | Confirmed |
| 9 | Fountain of Youth / Galadriel's Vial | #142 Empty Vial (to fill); #76 Amulet of Life (to arm) | Full stat restore + cures poison/disease; vial is a portable one-shot charge | master | Confirmed |
| 10 | Excalibur / Sword in the Stone | Class = Knight (`pc=9`) AND Honor ≥ 1200 | Weapon #17 Excalibur | master | Confirmed |
| 11 | Palintar (Enlightenment) | #96 Palantir; Enlightenment score `(INT+WIS)×level` ≥ 240 | Reveals room/level layout (monsters, items, exits) | **skip only** | Confirmed in skip; master is a stub |
| 12 | Lasso/Saddle/Armor a Horse | #161 Lasso (on a HORSE monster), then #162 Saddle / #163 Horse Armor | Named mount ally (already ported — see MECHANICS.md "Horses") | **skip only** | Confirmed — already implemented in this port |
| 13 | Power Armor / Shield Recharge | #112 Armor Power Pak / #117 Shield Power Pak | Recharges shield/armor to full (120%) effectiveness | **skip only** | Confirmed in skip; master's shield system is simpler (flat % add, no recharge) |
| 14 | Copper Key / Wraith Master | #80 Copper Key, `USE`d in a specific level-5 room | Grants Wraith Master status (`PlayerFlags.WRAITH_MASTER`) | master | Confirmed mechanic; room placement and flavor text untraced (see below) |
| 15 | Wraith King / RONNEY | Defeat monster #93 "RONNEY" (disguised King of the Wraiths) at level 5 room 262 "Kings Chamber" | +1 level, Honor (`vk`) +100 (capped 1900), advances the same `zu$[7]` status tier as quest #14, teleport to level 5 room 390 (the same ruins location quest #14's Copper Key checks) | master | Confirmed trigger and full effects; not yet implemented; room 390's actual content is a gap (see below) |
| 16 | Tut's Treasure | Item #86 "Tut's Treasure" — level 2, room 158 "Secret Chamber"; monster #102 "KING TUT" guards the adjacent room 157 "Mummy's Tomb" | `EXAMINE` it first — disarms a trap, +2 INT (only while under 25), marks `zu$[9]="1"` (examined). `GET` afterward — awards a huge gold bonus (`iv×1000`) and marks `zu$[9]="2"` (looted); this is the exact flag `commands/stats.py`'s "Tut's Treasure: Looted../Somewhere.." line already displays, and the same flag SPUR's original win check reads for its gold-riches gate (`SPUR.MISC7.S`'s `win2`, generalized away by this port's `config.py` into a flat `victory_gold_amount` — see `MECHANICS.md`'s "Win/escape detection"). `GET` it *without* examining first — "Ain't you heard of the Mummy's curse?!?!", jumps to the same `pandora` punishment used for other cursed items (-XP capped to 100, -CON capped to 5, -INT -5 with "You feel dumber!", -HP to 5 if higher) | master | Confirmed — full mechanic traced (`SPUR.MISC.S:245-252,294-297`, `SPUR.MISC3.S:416-422`, `SPUR.MISC5.S:230`); nothing in this port sets the flag — `player.tuts_treasure_looted` / `flags.py`'s `TutTreasure` dataclass are unwired stubs, and neither `commands/get.py` nor `commands/examine.py` special-case item #86 |

Quest #12 is already implemented (LASSO, Saddle/Horse Armor, MOUNT/DISMOUNT/CHARGE —
see `MECHANICS.md` "Horses"). Everything else in this table is unimplemented.

---

## Quest Details

### 1. Headhunter's Island
- **Source**: no scripted `.S` logic — purely map data. `server/level_5.json` rooms
  139–141 (`Isle Of Headhunters` → `Village` → `The Chief's Treasure Room`).
- **Trigger**: sail to room 139; monster #83 HEADHUNTER present.
- **Mechanic**: defeating monster #84 BIG CHIEF in the Village room reveals a hidden
  east exit (`Room.hidden_exit_east = 141`, MECHANICS.md's Hidden exits entry) into
  the treasure room.
- **Reward**: #40 Black Diamond in the Village; #78 Great Coat + weapon #57 Wraith
  Dagger in the treasure room.
- **Flavor**: "This is apparently the head hunters village... surround a large fire
  pit"; "various odd artifacts lie about" in the treasure room.
- Note: #78 Great Coat is separately required to survive `**` (snow/mountain) rooms
  generally (see MECHANICS.md), so this isn't its only use.

### 2. Spacesuit Repair
- **Source**: `SPUR.USE.S:58–72` (`tool` subroutine); confirmed on both branches.
- **Trigger**: `USE` the tool kit while carrying both parts.
- **Required**: #133 Tool Kit + #134 Broken Spacesuit + #135 Spacesuit Parts.
- **Reward**: consumes #134+#135, adds #122 Spacesuit — required to traverse
  `@@`-flagged vacuum rooms at level ≥ 6 (`SPUR.MAIN.S:151–159, 301–309`; see the
  flag-naming gotcha at the top of this doc — these are `RoomFlag.WATER` in the
  converted JSON, not literal water).
- **Item locations**: Tool Kit (133) — "Dingy Closet" (room 40); Broken Spacesuit
  (134) — "Equipment Locker" (room 48, "One very broken looking suit..."); Spacesuit
  Parts (135) — "Storage Locker" (52) or "Vent Duct" (63).
- **Flavor**: "You don't have all the parts to the spacesuit." / "Bingo! Using the
  tools, you repair the spacesuit!"

### 3. Communicator Repair
- **Source**: `SPUR.USE.S:70` (same `tool` subroutine, chained after the spacesuit
  check).
- **Required**: #141 Broken Communicator + #133 Tool Kit (same kit as the spacesuit).
- **Reward**: consumes #141, adds #66 Communicator. `USE`ing it calls the `comm`
  subroutine (`SPUR.USE.S:128–140`) to teleport the player to level 6, room 1.
- **Malfunction branch**: 10–30% chance of "buzzing"/malfunction on use — strips the
  working communicator back to broken (#141) and drops the player on a random level
  (`malfunction`, `SPUR.USE.S:221–231`).
- **skip-branch difference**: the tool kit is consumed/exhausted after fixing the
  communicator (tracked via a `"*TO"` flag in `ys$`); master's tool kit is reusable
  indefinitely.

### 4. Security Cards
- **Source**: `SPUR.USE.S:74–83` (`card`/`no.cd`); discovery via `SPUR.MISC3.S:333`
  (`hidden` search subroutine).
- **Items**: #131 Red Security Card (opens east doors, room `lo$` contains `->`),
  #132 Green Security Card (opens west doors, `lo$` contains `<-`).
- **Trigger**: search (`~*`) a qualifying room at level 6; source hardcodes room
  `cr=752` for the red card discovery.
- **Penalty**: wrong card in a slot → "Sticking the wrong card in the slot gives you
  an electric shock!" for 4 HP.
- **Caveat**: hardcoded `cr` values (752, 93, 180, 557) use SPUR's original room
  numbering, which doesn't map cleanly to `server/level_6.json`'s 292 compacted
  entries — needs the `SPUR-data/level-6` binary re-decoded to place these correctly.

### 5. Radiation Suit + Geiger Counter
- **Source**: `SPUR.MAIN.S:311,314–317`, `SPUR.USE.S:125` (nuke sequence),
  `SPUR.MISC3.S:334–335` (discovery).
- **Items**: #124 Radiation Suit (protects against radiation damage/poisoning), #123
  Geiger Counter (early warning: "[Tick... tick...]" in `&` radiation-flagged rooms).
- **Mechanic**: entering an `&&` (extreme radiation) room without the suit → "You
  feel funny!" plus HP/energy/strength drain. Carrying the counter without the suit
  gives only a vague warning ("You have a strange feeling that you should know
  something..").
- **Nuke event**: a nuclear rocket triggers a blast; the radiation suit negates the
  "radiation poisoning" outcome, "power armor" negates blast damage outright.
- **Room example**: `level_6.json` room 93 "Vent Duct" — flagged `radiation_extreme`,
  monster #107 GUARD DROID present (room `desc` reads "Hey! This fellow looks
  familiar!" — see Loose Ends).

### 6. Space Tracker
- **Source**: `SPUR.MAIN.S:153–156, 511–514` (`tracker` subroutine).
- **Item**: #138 Space Tracker — found in "Security Bunker" (level 6, room 108).
- **Reward**: while traveling a `@@`-flagged (i.e. `water`-flagged — see gotcha
  above) vacuum room at level 6, carrying the tracker
  prints "The SPACE TRACKER powers up! (Giving galactic space coordinates)" and
  appends `[GC:<room>]` to the status line; without it: "(Too bad you don't have a
  SPACE TRACKER..)".

### 7. Ruby Slippers (Wizard of Oz chain)
- **Source**: `SPUR.MISC.S:120–158` (`drop.b`/`drp.itm3`/`broom` chain),
  `SPUR.MISC3.S:336` (discovery), `SPUR.USE.S:142–145` (`slippers`); map data
  `level_6.json` rooms 115/116/118 ("Witches Coven", "Witches House", "Chamber Of
  Oz"), `monsters.json` #125 OZ, #126 WICKED WITCH.
- **Item placement**: #145 Broomstick is placed at level 6, room 557
  (`SPUR-code/SPUR.MISC3.S:336`).
- **Trigger**: dropping/giving *any* item routes through `drp.itm3`, which checks
  `if a=145 goto broom`. The `broom` subroutine only fires when: a monster/NPC is
  present in the room (`mw` truthy — the NPC's identity isn't named near this label,
  presumed to be the Oz figure or witch), the player is specifically at level 6, room
  582, and the player doesn't already hold #144 (checked against both player and ally
  inventories, so the reward can't double-grant).
- **Reward**: #144 Ruby Slippers. `USE`ing them (or an automatic check elsewhere,
  `SPUR.MISC3.S:328–330`) teleports the player home to level 1, room 1 — "The
  slippers glow strangely!", then message #19 (recovered, `server/messages.json`):
  "You slip the slippers on your feet (they fit, amazingly enough). For some
  reason, you start mumbling: 'There is no place like home. There is no place
  like home...' Then you start clicking your heels together, for all the world
  like some sort of Gestapo trooper. / The area fades from view..." — not yet
  wired into code.
- **Known gap**: **room 582 does not exist in the current `server/level_6.json`**
  (rooms only go up to ~292) — the delivery location isn't reachable in the current
  port at all. The broomstick's *acquisition* trigger (witch-kill drop vs. static
  room item) also wasn't fully traced.

### 8. Test of Galadriel
- **Source**: `SPUR.MISC6.S:504–534` (`galad` subroutine), triggered from a random
  -event table (`SPUR.MISC6.S:139–158`).
- **Trigger**: random encounter roll (~0–15% band of the event table), or a manual
  sysop test via the `random` menu.
- **Mechanic**: NPC Galadriel asks a riddle (5 variants, messages #25–29); player
  picks 1 of 4 answers. Correct → awarded #143 Galadriel's Vial (full). Wrong →
  "Return when Ye are worthy," sent home empty-handed.
- **Intro (message #24, recovered)**: "A soft vision floats before your eyes!
  She peers at you curiously for a long moment, before speaking. 'I am
  Galadriel, Lady of Lorien. I have journeyed far to give a gift of some
  importance to one of worth. Could Ye be such a person?' She is quite tall,
  with a grave sort of beauty. Clad all in white, with bright golden hair
  flowing over slender shoulders."
- **The five riddles (recovered, `server/messages.json`; correct answer is baked
  into the source as `zz$`, not derivable from the text alone)**:
  1. #25 — "Who lies in the tomb of Moria? 1) Khazad-dum 2) Gimli 3) Balin
     4) EntWood" — correct: **3**.
  2. #26 — "In what great battle was Sting first used? (Spiders don't count)
     1) Battle of Helms Deep 2) Battle of the Five Armies 3) Siege of Minas
     Tirith 4) Battle of The Pygmies" — correct: **2**.
  3. #27 — "What is a Treebeard? 1) Ent the earthborn, old as mountains 2) A
     type of moss found on old trees, with poisonous nettles 3) An old dwarf,
     famous for his earthy sense of humor 4) A fruit, famous for its woody
     flavor." — correct: **1**.
  4. #28 — "What is a Gollum? 1) A short, slimy creature who has a taste for
     some types of jewelry. 2) A powerful evil warrior, clad entirely in black
     armor. 3) A type of wheel barrow, useful in Middle earth for carrying
     computers. 4) The guardian of Helm's Keep." — correct: **1**.
  5. #29 — "Who is Sharkey? 1) The leader of the Five Armies. 2) A fisherman
     famous for catching sharks with his hands. 3) Frodo's personal servant.
     4) A big ruffian, who lived in Bag End." — correct: **4**.
  One is picked at random each time the test is offered. Not yet wired into
  code.
- **Gate**: only offered if the player doesn't already have #142/#143, or a `*GAL`
  "already met her" flag.
- **Logged**: pass/fail written to `battle.log` as "PASSed/FAILed the Test Of
  Galadriel!" (server-wide log, same pattern as a boss-kill announcement).

### 9. Fountain of Youth / Galadriel's Vial cycle
- **Source**: `SPUR.SUB.S:83–137` (`drink`/`fountain`/`pool`), `SPUR.USE.S:234–247`
  (`vial`/`fl.vial`).
- **Location**: level 5, room 105 — "the fountain."
- **Mechanic**:
  - Drinking directly at the fountain fully restores all seven stats (HP, STR, CON,
    INT, Energy, WIS, DEX) to max-for-level and cures poison/disease.
  - Carrying #76 Amulet of Life to the fountain permanently "arms" it if not already
    charged (see Loose Ends — prevents one permanent death later), printing message
    #3 (recovered, `server/messages.json`): "Vaguely at first, than with increasing
    fury, the AMULET OF LIFE comes alive! You drop it in horror, as it seethes and
    pulsates with a fierce blue light. You are slowly backing away from it, when a
    thundering lightning bolt strikes the amulet. The blast knocks you flat. You lie
    there for long moments before you realize that all is again quiet, except for
    the chirping of birds (who do not seem in the least upset by this turn of
    events). / Approaching the amulet, you see it is again quiet, except for a soft
    bluish glow. Gently, you pick it up, and place it in your pack..." Not yet wired
    into code.
  - `USE`ing #142 Empty Vial while at the fountain converts it to #143 Full Vial —
    "You kneel and fill the vial with precious water from the pool."
  - `USE`ing #143 anywhere grants the same full-restore effect away from the
    fountain, then reverts to #142 (a portable one-shot fountain charge).

### 10. Excalibur / Sword in the Stone
- **Source**: `SPUR.MISC.S:255–278` (`get.wpn`/`excalibur`).
- **Item**: weapon #17 Excalibur (level 1).
- **Required**: character class Knight (`pc=9`) **and** Honor ≥ 1200.
- **Failure text**: wrong class or low honor → "YOU CAN NOT PULL THE SWORD OUT!";
  right class but honor 1000–1199 → "A VOICE BOOMS, 'THOU ARE NOT WORTHY!'"
- **Reward**: Excalibur added to the weapon rack; logged to `battle.log` as "PULLED
  EXCALIBUR OUT OF THE STONE!!" (server-wide bragging-rights announcement).
- **Related honor gate**: Knight with Honor > 1600 makes death non-permanent — "THE
  SAINTLY KNIGHT WAS REVIVED BY THE GODS!!" (`SPUR.MISC6.S:108,112`).

### 11. Palintar (Enlightenment) — skip branch only
- **Source**: master `SPUR.USE.S:20` is a bare stub (just links to misc6); **skip**
  has the full mechanic (`SPUR.USE.S` `room.dsp` + `pal`).
- **Item**: #96 Palantir.
- **Mechanic**: `USE`ing it computes an Enlightenment score `(INT+WIS) × level`, with
  class/race bonuses (Druid +20, Pixie +30, Elf +20, Half-Elf +10). Score ≥ 240
  reveals the current room number, level dimensions, and a scrollable room-by-room
  listing (monsters/items/weapons/food/exits) — effectively a stat-gated "reveal
  map" tool. Below threshold: "Thou are not enlightened enough to use the Great
  Palintar!" (with an option to see the formula).
- **Secondary use**: also gates a "travel intel" bonus affecting monster-blocking
  rolls during travel (`SPUR.MAIN.S:162`, `SPUR.MISC7.S:516–524`).
- Recommend porting the skip version outright rather than master's stub — same
  pattern as CHARGE.

### 12. Lasso/Saddle/Armor a Horse — skip branch only, already implemented
- **Source**: skip-only `SPUR.USE.S` (`lasso`, `name.hrs`, `eq.horse`) — absent from
  master entirely.
- Already ported in this codebase — see `MECHANICS.md` "Horses" for the full writeup
  (LASSO, Saddle/Horse Armor, MOUNT/DISMOUNT/CHARGE). Listed here for completeness
  since it fits this table's shape.

### 13. Power Armor / Shield Recharge — skip branch only
- **Source**: skip-only `SPUR.USE.S` (`power.up`, `power.sh`, `get.sh`,
  `store.sh`/`store.pw`); master's shield logic (`SPUR.USE.S:34–43`) is a simpler
  flat "add %" system with no recharge.
- **Items**: #112 Armor Power Pak, #117 Shield Power Pak (has a `rounds: 6` flag in
  `objects.json` — limited uses). Shields/armor above a size/bulk threshold need a
  power pak to reach full (120%) effectiveness.
- **Persistence**: charge state is stored per-player in `misc.data` (position 217,
  14-char encoded string), surviving repacking — sturdier than master's ad-hoc
  per-session tracking.

### 14. Copper Key / Wraith Master
- **Source**: `SPUR.USE.S:19,182-185` (`key` subroutine).
- **Item**: #80 Copper Key. `USE`ing it only does anything at a hardcoded location
  (`if x=80 then if cl=5 then if cr=390 goto key`) — anywhere else on level 5, or on
  any other level, it just prints "(Not here!)".
- **Mechanic**: checks the player's Wraith Master status via `zu$[7]` (`"1"` or
  `"2"`); if already a Wraith Master, prints "There are only ruins here!" and stops.
  Otherwise prints message #4 (recovered, `server/messages.json`: "You insert the
  key into the lock and give it a twist. Slowly, slowly.... the great door swings
  silently inwards.. / So quiet is it, that the sudden voice laughing in your ear
  causes you to look around, even though you know that there is nobody but you
  here.. / 'Fool!! You dare to enter my castle?!?? Har, har! Be warned, my little
  pet: once you enter, you shall not leave again, til one of us is dead. It won't
  be me!! Har, har, har!' / The voice dies away, leaving you facing the open door
  north, pondering...") and sets `n=1`, granting the status. Not yet wired into
  code.
- **Already implemented, separately**: `PlayerFlags.WRAITH_MASTER` and its login
  title ("`, Wraith Master of Spur!`") are fully ported (`flags.py`,
  `commands/connect.py`) — only the *acquisition* path (this key) is missing.
- **Known gap**: `cr=390` — see quest #15 below; this is the *same* room quest #15's
  Wraith King fight teleports the player to. Room 390 doesn't exist in the current
  `level_5.json` at all (see quest #15's gap note) — this isn't a renumbering issue
  like the security-card rooms or Jake's Stable, the room data for it is simply
  missing from this level's conversion.
- **Same status field as quest #15**: `zu$[7]` is shared between this key and the
  Wraith King kill — `"0"` (never done either) → `"1"` (done one of them) → `"2"`
  (done both/killed him after already doing this). This port's
  `PlayerFlags.WRAITH_MASTER` is currently a plain boolean, so it doesn't yet model
  that third tier.

### 15. Wraith King / RONNEY
- **Source**: `SPUR.MISC.S:422` (dead-monster routine's `if m=93 i$="wraith":link
  dy$`), `SPUR.MISC2.S:369-380` (`wraith` subroutine).
- **Trigger**: killing monster #93, named plainly **"RONNEY"** in `monsters.json` —
  a disguised identity for the King of the Wraiths, revealed only by the death
  flavor text (same pattern as monster #120's "old man" → young man reveal, see
  MECHANICS.md). Placed at level 5 ("Land of the Wraiths"), room 262 "Kings
  Chamber" (`no_flee` flagged) — description: "This is a very richly decorated
  chamber indeed. There is a rather handsome fellow glaring at you from his
  throne..."
- **On death**:
  - `zu$[7]` status tier advances — see quest #14 above (shared field): `"0"→"1"`,
    or `"1"→"2"` if the player already did the Copper Key.
  - Prints message #7 (recovered, `server/messages.json`): "The body of the King
    of the Wraiths suddenly implodes upon itself. Searing flame quickly replaces
    it. The room is filled with foul black smoke. You back out the door to the
    throne room only to discover that the whole castle has become engulfed in
    flame... All the guards and Wraiths have disappeared... The walls are
    collapsing now... You are hit by a falling stone, and are knocked out cold...
    A pale young girl holds you in her warm hands... 'I, the Lady of the Mist,
    have long been held prisoner by the Wraith King, my son.. Through powerful
    black magic, he transformed me into the castle that is now dying... I can see
    you safely out, and reward you with some of my power..' (+1 level) / You
    awaken... outside the castle. The castle which is now in ruins..."
  - Global `battle.log` announcement (same convention as the Excalibur pull):
    "THE LADY OF THE MIST BECAME PART OF \<player\>, AFTER THE DEATH OF KING
    OF THE WRAITHS. (+1 level)". Correction: an earlier version of this note
    also cited "the Dwarf kill" as sharing this convention -- checked
    `SPUR.MISC.S`'s dwarf-kill block (`p.a3`) directly and it's just a
    `print`, no file write, in the original source. `encounters/dwarf.py`
    now writes a battle.log entry on his death anyway (Ryan's request,
    matching this port's own convention for notable kills, not a ported
    behavior).
  - Honor (`vk`) +100, capped at 1900 — `vk` is very likely this port's Honor stat
    (same variable gates the Excalibur quest's Honor≥1200 check).
  - An actual character level: `xp=xp+1`.
  - Teleports the player to level 5, room 390 (`i$="travel1"`) — same level, no
    level change — which is the exact same `cl=5, cr=390` quest #14's Copper Key
    subroutine checks. The two quests converge on the same location and the same
    status field; they're not independent.
- **Known gap**: level 5's own header (`D.LEVEL5.TXT`) declares `nr=400` rooms,
  but the current `level_5.json` only has rooms 1–373 — room 390 falls in the
  missing 374–400 range and doesn't exist in this port's data at all. Its actual
  content (presumably the ruins/castle-aftermath room both quests point to) can't
  be verified from the source alone; would need re-extraction from the original
  level 5 export data (or, if unavailable, invented as a reasonable "ruins of the
  castle" room and cross-linked from both quests).
- **Not yet implemented**: no code currently hooks monster #93's death to any of
  the above — `PlayerFlags.WRAITH_KING_ALIVE` (`flags.py`) exists as an
  EditPlayer-toggleable stats-display flag only (`commands/stats.py`), nothing
  currently sets it to false on a real kill. It's also gate 1 of the win check
  (`victory.py`, `MECHANICS.md`'s "Win/escape detection") — until this quest is
  implemented, that gate is a hard blocker for every player, only clearable by
  an admin.

### 16. Tut's Treasure
- **Source**: `SPUR.MISC.S:245-252` (`pandora` curse subroutine),
  `SPUR.MISC.S:294-297` (`get.itm`'s item-#86 special case),
  `SPUR.MISC3.S:416-422` (`exam3`'s "TUT'S TREASURE" name match + `treasure`
  subroutine), `SPUR.MISC5.S:230` (`status`'s "Tut's Treasure:" display line,
  the exact source `commands/stats.py`'s line already ports).
- **Placement**: item #86 "Tut's Treasure" sits in level 2, room 158 "Secret
  Chamber"; monster #102 "KING TUT" guards the adjacent room 157 "Mummy's
  Tomb" (which also holds item #22).
- **The mechanic** (tracked in `zu$[9]`, this port's equivalent of a per
  -player flag: 0=untouched, 1=examined, 2=looted):
  - `EXAMINE TUT'S TREASURE` while `zu$[9]="0"` — "AHAA! Whats this?!?! Your
    careful examination reveals a deadly trap, which you carefully disarm..",
    +2 INT (only while under 25, "You feel a bit smarter" -- a single application can overshoot slightly, matching SPUR's own `if pi<25 pi=pi+2`), sets `zu$[9]="1"`.
  - `GET TUT'S TREASURE` while `zu$[9]="1"` — "BINGO! SUCH WEALTH!!", awards
    `iv×1000` gold (a large multiple of the item's own value), sets
    `zu$[9]="2"`.
  - `GET TUT'S TREASURE` while `zu$[9]="0"` (skipping EXAMINE) — "(Ain't you
    heard of the Mummy's curse?!?!)", jumps to the `pandora` punishment
    subroutine also used for other cursed items: caps XP at 100, caps
    Constitution at 5, -5 INT ("You feel dumber!"), and drops HP to 5 if
    higher.
  - `GET`/`EXAMINE` again once `zu$[9]="2"` is a no-op (already resolved).
- **Feeds the original win check**: SPUR's actual gold-riches gate
  (`SPUR.MISC7.S`'s `win2` label) reads this exact flag — `zu$[9]="2"` is
  literally "found the riches of TUT". This port's `config.py` deliberately
  generalized that into a flat `victory_gold_amount` silver-in-hand check
  instead of porting the Tut-specific flag (see `MECHANICS.md`'s "Win/escape
  detection"), so `victory.py` doesn't read this flag — but the *display*
  line survived the generalization and is the one dangling loose end that
  originally prompted this research.
- **Not yet implemented**: `player.tuts_treasure_looted` (read by
  `commands/stats.py`) and `flags.py`'s `TutTreasure` dataclass are both
  unwired stubs — nothing ever sets either. Neither `commands/get.py` nor
  `commands/examine.py` special-cases item #86; taking or examining it today
  behaves like any other ordinary Treasure item, with no trap, no curse, and
  no gold bonus.

---

## Loose Ends

Items whose purpose was inferred from source usage but that don't belong to one of
the named quests above:

| Item # | Name | Inferred Purpose | Source |
|---|---|---|---|
| 76 | Amulet of Life | Prevents one permanent death (armed at the Fountain, quest #9); halves duel/combat penalty vs. the Amulet of Death. Death-save flavor recovered as message #20 (`server/messages.json`, `revive` subroutine, `SPUR.MISC6.S:132`); a second variant (message #21, "Thou are one of the Chosen Ones") fires instead when `flag(7)` is set — condition untraced | `SPUR.LOGON.S:237`, `SPUR.DUEL.S:146,155`, `SPUR.DUEL2.S:161,165`, `SPUR.WEAPON.S:70`, `SPUR.SUB.S:122` |
| 97 | Ice Crystal | Blocks one fire attack per encounter (10% chance monster "puts on anti-fire glasses" and negates it) | `SPUR.MISC4.S:180–184` |
| 82 | Crystal Pendant | ✅ Implemented — 90% chance to permanently block a `petrify` monster's petrification for the rest of the encounter (resolved once, not per round); 10% chance the monster counters it that one time | `SPUR.MISC4.S:186–189`, `combat/engine.py` `_check_crystal_pendant()` |
| 146 | Salvage Parts | Sell-only; redeemable for gold (×40 multiplier) at the Ship's Salvage Bay (level-6 alt-shoppe) | `SPUR.SHIP.S:460–500` |
| 151 | Shovel | Speeds up DIG (60 min vs. 180 min bare-handed) | `SPUR.MISC7.S:161–189` |
| 44/45/65/68 | Red Serum, Blue Pill, Potion of Skill, Charm Potion (rations.json) | Excluded from the "you should eat/drink something" hunger nag during PRAY — treated as non-nutritive magic consumables | `SPUR.MISC2.S:194–211` |
| 57 | Wraith Dagger (weapon) | Only found in the Headhunter's Chief's Treasure Room; no other reference found — likely just a strong reward weapon | `level_5.json` room 141 |
| 30 | Sun Blade (weapon) | Committed `level_1.json` room 63 ("Labyrinth", price 4999) has this weapon, but a fresh raw-source extraction shows 0 there — every other monster/weapon/food value across all 28 "Labyrinth"-named rooms lines up exactly between the two, so this is the one unexplained discrepancy. Ruled out a hex/ASCII mixup (`0x30` is decimal 48, not 30) — #30 is a real, legitimately expensive weapon, not garbage, so it's just as likely the committed value is correct (a valuable weapon deliberately hidden in an unremarkable maze room) as it is a stray leftover value. Left as-is, not resolved either way. | `level_1.json` room 63; `weapons.json` #30 |
| — | Monster #107 GUARD DROID | Room `desc` ("Hey! This fellow looks familiar!") reads like a recurring/storyline encounter — not traced further | `level_6.json` room 93 |
| — | Monster #103 ("guardian") | Repeat-encounter monster that "remembers" a previous player loss and returns stronger (`ms=ms+xp*6`) | `SPUR.MISC4.S:198–199` |
| — | Monsters #125/#126 (OZ, Wicked Witch) | Tied to the Ruby Slippers chain (quest #7) but the broomstick's first-acquisition trigger wasn't fully traced (witch-kill drop vs. static item) | `level_6.json` rooms 115/118 |
| — | School / re-training | Pay gold + lose 1 level to re-pick character class; flavor recovered as messages #8 (camp intro) and #6 (result) | `SPUR.MISC2.S:418,434` |
| — | Shield training (Odin the Shield Master) | Pay gold for permanent shield bonus (20% less chance of a monster getting past your shield, +1 protection); flavor recovered as message #13 | `SPUR.MISC2.S:460` |
| — | Duel help text | Full `H`elp screen for the duel (PvP) system recovered as message #16 — not yet ported into `commands/` duel help | `SPUR.DUEL.S:26,43` |

---

## On Flavor Text

Numbered `gosub messages` calls (e.g. `a=2,3,4,19,20,21,22,24,25–29,33`) pull prose
from a binary message-data file not present in the already-converted JSON files.
Full flavor text for the Fountain, Excalibur, the slippers-teleport, and the
Galadriel riddles beyond what's inline in the `.S` `print` statements above will need
the same `gbbs-io` decode path already used for `SPUR-data/level-N` room data (see
`MECHANICS.md`).
