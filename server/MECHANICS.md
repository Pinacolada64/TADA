# TADA Mechanics Roadmap

Tracks game mechanics from the SPUR source that are either implemented, partially
implemented, or not yet started. Source references are to files under `SPUR-code/`.

---

## Combat

### Implemented
- **Player attack roll** — to-hit vs. monster dexterity; ease-of-use check (`resolution.py`)
- **Player damage** — base damage (stability) + class/race bonus + XP scaling (`resolution.py`)
- **Monster attack** — hit/miss vs. player stats; light/heavy armor reduction (`resolution.py`)
- **Special weapons** — `check_special_weapon()` enforces per-monster required weapon; EXCALIBUR ×2 vs evil/÷2 vs good; WRAITH DAGGER +40 vs wraith #70 (`resolution.py`)
- **STORM — asserts its will** — 30% auto-attack when monster has attacked fewer than 6 times (`engine.py`, `SPUR.COMBAT.S:59`)
- **STORM — armor penetration** — +XP after armor reduction for STORM/CANNON/hack-slash (`resolution.py`, `SPUR.COMBAT.S:158`)
- **STORM — screams in glee** — message on monster kill if STORM weapon readied (`engine.py`, `SPUR.COMBAT.S:197`)
- **STORM — scare** — 10% chance loud weapon scares unarmored monster in first 2 exchanges (`resolution.py`, `SPUR.COMBAT.S:423–430`)
- **Surprise attack** — when monster has not yet spotted player, +2 to-hit + damage for player (`resolution.py`)
- **Double attack** — 40% chance of a second monster attack in rooms marked `]` (`engine.py`)
- **Allies** — up to 3 allies attack each round; morale failure / sacrifice on near-death (`engine.py`)
- **XP gain per swing** (`engine.py`)
- **Monster kill rewards** — gold and XP awarded on kill (`engine.py`, `combat/rewards.py`)

### Not Implemented

#### Weapon / attack mechanics
- **Ammo system** — `vn`/`vl`/`vm` tracking; "NO AMMO READY" check for projectile/energy weapons; burst/auto-fire modes (S/B/A prompt, `SPUR.COMBAT.S:98–101`); ammo consumed per shot; STORM bypasses ammo (`SPUR.USE.S:155`, `SPUR.COMBAT.S:44`, `SPUR.COMBAT.S:84`)
- **Ammo recovery** — after combat, ranged weapons (non-STORM) have a chance to recover spent rounds (`SPUR.MISC.S:427`)
- **USE ammo command** — loads ammo into a readied ranged weapon (`SPUR.USE.S:147–162`)
- **Missile: first strike** — when ammo is loaded and enemy hasn't attacked yet, player gets a free first strike (`SPUR.COMBAT.S:219`)
- **Pole weapon: first strike** — chance to get first strike based on dexterity vs. monster agility (`SPUR.COMBAT.S:221`)
- **Fireball/energy weapon secondary damage** — 10% chance of secondary heat damage (`SPUR.COMBAT.S:143`)
- **LURK mode** — player fires over allies' shoulders; to-hit penalty; requires at least one living ally (`SPUR.COMBAT.S:87–96`)
- **Assassin critical hit** — class 8 (Assassin), 10% chance to double damage (`SPUR.COMBAT.S:135`)
- **Ease-of-use help message** — "(EASE OF USE HELPS!)" when roll barely misses and weapon skill is high (`SPUR.COMBAT.S:139`)
- **Bad weapon choice warning** — "(bad weapon choice)" when `p2 < 3` (`SPUR.COMBAT.S:119`)

#### Defence
- **Shield** — blocks some incoming damage; degrades; can be destroyed; max rating varies by class/race; shield items usable via USE command (`SPUR.COMBAT.S`, `SPUR.USE.S:34–43`)
- **Armor** — degrades each hit; "ARMOR GONE" when reaches 0; heavy armor blocks more but is not penetrated by STORM/CANNON (`SPUR.COMBAT.S:289–302`)
- **Gauntlets** — absorb one hit (10% chance destroyed) when player takes a hit (`SPUR.COMBAT.S:210–217`, `SPUR.WEAPON.S:spec4`)
- **Wizard's glow** — item `zu$[7]` values 2/3 reduce incoming damage by 2 (`SPUR.COMBAT.S:266`)
- **Lazer shield** — energized shield variant; blocks laser fire at half damage (`SPUR.USE.S:86`)
- **Power armor** — specific item; halves blast damage (`SPUR.USE.S:124`)

#### Monster abilities
- **Monster spellcasting** — monsters with `+` flag in `wy$` can cast spells when low HP (`SPUR.COMBAT.S` `lnk.msc4`)
- **Turn to stone** — monsters with `#` flag; 10% chance per attack; player dies if fails second roll (`SPUR.COMBAT.S:229–235`)
- **Monster fire/laser** — monsters with `-` flag shoot fire; laser-equipped rooms use laser fire (`SPUR.COMBAT.S:240–248`)
- **Poison on hit** — monsters with `*` flag; 30% chance to poison player (`SPUR.COMBAT.S:312–313`)
- **Disease on hit** — monsters with `@` flag; 30% chance to disease player (`SPUR.COMBAT.S:315–316`)
- **Experience drain on hit** — monsters with `&` flag; drains XP×13 experience (`SPUR.COMBAT.S:317`)
- **Multiple guards** — if player is treacherous in a guard room, whistles summon more guards and monster HP multiplies (`SPUR.COMBAT.S mad.gd`)
- **Dexterity loss on heavy hit** — taking >4 damage reduces player DEX by 1 (`SPUR.COMBAT.S:318`)
- **Dexterity gain** — dealing >4 damage has small chance to increase player DEX (`SPUR.COMBAT.S:143`)
- **Wisdom gain on kill** — player `pw` increases by 1 on every non-ally kill (`SPUR.COMBAT.S:188`)

#### Status effects / survival
- ✅ **Hunger / thirst** — `food` and `drink` deplete every 10 commands; "VERY HUNGRY/THIRSTY", "FAINT" warnings; starvation death when both reach 0; `eat` and `drink` commands restore them (`survival.py`, `commands/eat.py`, `commands/drink.py`, `SPUR.COMBAT.S:12–19`)
- **Poison** — tick damage (−2 HP); 30% chance per tick; tick also reduces STR if ring is worn (`SPUR.COMBAT.S:15`)
- **Disease** — tick damage (−1 HP); 30% chance per tick (`SPUR.COMBAT.S:16`)
- **Ring of power weakening** — wearing the ring has a 10% per-tick chance to reduce STR/WIS (`SPUR.COMBAT.S:14`)
- **Fatigue** — taking damage also depletes food (`ps`) proportionally (`SPUR.COMBAT.S:307`)
- **Too weak to wield** — if `ps < 4` (extremely hungry), weapon is automatically unreadied (`SPUR.COMBAT.S:321`)
- **Dusk warning** — message when session time < 120 ticks remain (`SPUR.COMBAT.S:11`)

---

## Flee

### Implemented
- Basic flee command exists (`commands/flee.py`)

### Not Implemented
- **Monster blocks path** — if player HP > 7 and room has `.` flag, monster may block flee (`SPUR.COMBAT.S:75`)
- **Energy cost** — fleeing costs 1 energy (`SPUR.COMBAT.S:76`)
- **Impassable rooms** — rooms flagged `@@`, `**`, or `<<` cannot be fled from (`SPUR.COMBAT.S:74`)

---

## Weapons & Readying

### Implemented
- **Ready command** — choose weapon from inventory; display class/weapon stats (`commands/ready.py`)
- **Battle experience tiers** — GREEN / VETERAN / ELITE thresholds displayed on ready (`commands/ready.py`)
- **STORM — howls in rage** — refuses to be switched away from; zaps player; disintegrates (`commands/ready.py`)
- **STORM — jealous rage** — unreadied STORM in inventory howls when player readies something else (`commands/ready.py`)
- **STORM — servant** — accepts player with good class/race affinity; grants +2 skill/damage (`commands/ready.py`, `combat/engine.py`)
- **STORM — YOU ARE NOT MINE** — rejects player with no class/race affinity (`commands/ready.py`)
- **UNREADY command** — clears readied weapon (`SPUR.MAIN.S`)

### Not Implemented
- **Battle experience accumulation** — `vp`/`weapon_experience` incremented each time weapon is used in combat; VETERAN at 40, ELITE at 99 (`SPUR.WEAPON.S`)
- **ELITE damage scaling** — ELITE tier grants +XP damage instead of flat +1 (`SPUR.WEAPON.S`)
- **Dexterity requirement** — weapons have a minimum DEX to wield (`ws+4`); player refused if below threshold (`SPUR.WEAPON.S:46`)
- **STORM — duel behavior** — deferred until duels are implemented

---

## Item USE

### Not Implemented
- **Ammo loading** — `USE <ammo item>` loads rounds into readied ranged weapon (`SPUR.USE.S:147–162`)
- **Shield use** — `USE <shield item>` activates shield; class/race caps max rating (`SPUR.USE.S:34–43`)
- **Compass** — toggle compass on/off; compass can be damaged in combat (`SPUR.USE.S:44–50`, `SPUR.COMBAT.S druid`)
- **Ring of invisibility** — USE toggles ring worn/off; makes player hard to see; evil alignment penalty (`SPUR.USE.S:52–56`)
- **Potion** — restore HP or stats (`SPUR.USE.S`)
- **Grenade** — single-use explosive (`SPUR.USE.S:15`)
- **Rocket** — single-use ranged explosive (`SPUR.USE.S:28`)
- **Scrolls / spellcasting** (`SPUR.MISC3.S`)
- **Spacesuit assembly** — combine parts 134 + 135 with tool into item 122 (`SPUR.USE.S:58–72`)
- **Communicator repair** — USE tool on item 141 produces item 66 (`SPUR.USE.S:70`)
- **Slippers of Galad** — location-specific item effect (`SPUR.USE.S:25`)
- **Palintar** — links to misc6 (`SPUR.USE.S:20`)
- **Crystal vial** — location-specific effect (`SPUR.USE.S:23–24`)

---

## Items (Examine / Look)

### Implemented
- **look \<item\>** — searches inventory; STORM weapons show "There is much power in the {name}!"; potions, magic, cursed items have flavor text (`commands/look.py`, `SPUR.MISC3.S:316`)

### Not Implemented
- **Room item examination** — `look` at items on the floor / in the room, not just inventory
- **Magical/cursed detection** — currently uses `item.kind`; SPUR requires a skill roll first (60% failure) and tracks already-examined items in `xz$` (`SPUR.MISC3.S:295–307`)
- **Special item descriptions** — CRYSTAL PENDANT, ICE CRYSTAL, CROWN OF MIDAS, GOLD ROSE, PANDORAS BOX, TUT'S TREASURE, etc. (`SPUR.MISC3.S:310–323`)
- **LOOT command** — search dead monster for items (`SPUR.MISC3.S`)

---

## Flee / Travel

### Not Implemented
- **Stealth / sneak** — player class affects how likely monsters are to lose sight of them (classes 6/8 get `z=50` instead of class-based roll, `SPUR.COMBAT.S:24–28`)
- **Room travel** — N/S/E/W/U/D movement between rooms
- **Room flags** — monster blocking (`.`), no-flee (`@@`, `**`, `<<`), random encounter (`]`) — other flags (`+`, `#`, `-`, `*`, `@`, `&`, `E`/`G`, `;;`) belong to monsters, not rooms; see monster abilities in the Combat section above
- **Orator / Moderator player flag** — a player flag (name TBD — `Orator` or `Moderator`) that
  designates the speaker in an auditorium-type room.  While a flagged player is present, other
  players in the room cannot use `say`; instead they submit questions or comments via a `q` command
  which queues them for the Orator to address.  Good for town halls and structured announcements.
  Planned as one auditorium room per level for convenience; exact map placement TBD.

---

## Character Progression

### Implemented
- **Level-up** — XP threshold `999 + (xp_level × 100)` triggers level-up message (`SPUR.COMBAT.S:10`)
- **Stat rolling** — race/class bonuses applied at character creation (`characters.py`)

### Not Implemented
- **Level-up stat grants** — what increases on level-up (HP, stats) (`SPUR.COMBAT.S lvl.msg`)
- **Time limit** — session clock `ev`; player is forced to quit when time expires (`SPUR.COMBAT.S tim.chk`)
- **Battle experience** — weapon-specific kill counter; VETERAN/ELITE tiers (`SPUR.WEAPON.S`)

---

## Duels (PvP)

### Not Implemented
- **Live duel** — both players online; weapon chosen from weapon roster interactively (`SPUR.DUEL.S`)
- **Autoduel** — offline defender; best weapon auto-selected by `zt+zs` score (`SPUR.DUEL2.S`)
- **Weapon roster** — separate from inventory; needed for both duel modes (see `combat/duel.py` for design notes)
- **No weapon penalty** — fighting without a readied weapon deducts 1 INT (`SPUR.DUEL.S:30–54`)

---

## Social / World

### Not Implemented
- **Guilds** — three guilds (Claw, Sword, Iron Fist); bank, food locker, item locker, weapon box, chalk board, log (`SPUR.GUILD.S`)
- **Bar** — ally hiring, drink/food purchase (`SPUR.BAR.S`, `SPUR.BAR2.S`, `SPUR.BAR3.S`)
- **Ship** — travel between zones (`SPUR.SHIP.S`)
- **Gates** — zone gate travel (`SPUR.GATES.S`)
- **Annex** — visitor area (`SPUR.ANNEX.S`)
- **Shop** — buy/sell items, ammo, shields (`SPUR.SHOP.S`)
- **Bulletin board / news log** (`SPUR.MISC2.S`) — see expanded design in **News & Mail** and **Threaded Message Boards** sections below
- **Pray / Rest** — recover HP or stats out of combat (`SPUR.MISC2.S`)

---

## News & Mail

### News / Bulletin Board

#### Future
- **Startup display** — active news items are shown automatically when a player logs in, before the
  game loop starts.
- **`news` command** — lets players re-read current news at any time during a session.
- **Post editing** — sysops/admins create and edit posts via `text_editor.py` (the shared
  line-editor already used elsewhere in TADA).
- **Display lifetime** — each post carries one of three lifetime modes:
  - *One-time* — shown once per player, then silently suppressed on subsequent logins.
  - *Permanent* — always shown until manually deleted.
  - *Date range* — active only between a `start_date` and `end_date`; invisible outside that window.
- **Storage** — posts stored as JSON (e.g. `news.json`); each record: `id`, `body`, `lifetime`
  (`once` / `permanent` / `range`), optional `start_date` / `end_date`, and a `seen_by` list of
  player names (used for one-time suppression).

### Mail / Paging

#### Future
- **`page` command** — sends an instant message to an online player (appears in their session
  immediately).
- **Offline fallback** — if the target player is not online, prompt the sender to optionally
  deliver the message as mail instead.
- **Mail inbox** — unread mail is shown at login (similar to news display); a `mail` command lets
  players read, reply to, and delete messages mid-session.
- **Storage** — mailboxes stored per-player (e.g. `mail/<playername>.json`); each message: `from`,
  `timestamp`, `subject` (optional), `body`, `read` flag.

---

## Threaded Message Boards

### Skeleton — `server/threaded_messages.py`
A working prototype of a per-room threaded message system.  Current state:

- **Storage** — one JSON file per thread (`thread_<timestamp>.json`); each file holds `title`,
  `to`, `from`, `date`, `message`, and a `replies` array.  Currently written to a hardcoded
  scratch path; needs to be relocated to a proper data directory and scoped per room or board.
- **Operations** — create thread, reply to thread, list threads, view thread with N/P/R/Q
  in-message navigation.
- **Anonymous posting** — author prefixed with `?` to post anonymously; admins / Dungeon Masters
  see the real name behind the `?` (flag check stubbed with a TODO).
- **Input** — currently uses raw `input()` / `print()`; needs to be ported to `ctx.prompt` /
  `ctx.send` for the async game loop.

### Design Ideas (not yet decided)
- **`bulletin_board` room flag** — any room tagged `bulletin_board` would expose a board command
  (e.g. `board` or `bb`); the board's thread files would be stored under a key tied to that room.
- **Guild HQ boards** — each guild hall gets its own board; guild membership could gate who can
  post vs. who can only read.
- **Convergence with News & Mail** — the news system (see above) is single-author / broadcast;
  threaded boards are multi-author / conversational.  They share the JSON-per-post idea but serve
  different purposes and should stay separate.

### Future
- Relocate storage from the scratch path to `data/boards/<board_id>/`.
- Port all I/O to async `ctx` methods.
- Wire `bulletin_board` flag into the room system once room travel exists.
- Add `text_editor.py` for composing longer posts.

---

## Server Configuration

### In Progress — `setup/server_setup.py`
- **Invite toggle** — `config.require_invites` flag; toggled via the setup menu; controls whether
  new players need an invite code to register.
- **Invite management** — generate, list, and revoke invite codes (stubs in place).
- **Password encryption** — not yet wired up; plain-text passwords should be hashed before the
  server goes public.
- **Time zone** — server location / timezone configurable; feeds into the game clock (see Reactive
  Rooms below).
- **MOTD editor** — `edit_motd()` stub; edits `motd.txt` displayed at login (tie into
  `text_editor.py` when ready).
- **News editor** — `edit_news()` stub; separate from the in-game news system but could converge
  with `news.json` design in the **News & Mail** section above.

### Future
- Wire all stubs to `text_editor.py` and a proper `server_config.json` schema.
- Expose invite management as an in-game sysop command, not just a setup-time CLI option.

---

## Reactive Room Descriptions

### Prototype — `server/main.py` (Gemini AI, early 2025)
`main.py` contains a well-developed prototype worth preserving and eventually integrating into
`simple_server.py`:

- **`GameClock`** — singleton; wraps `astral` + `pytz`; can run on wall-clock time or advance a
  configurable number of minutes per player action.
- **`Season`** enum — `SPRING / SUMMER / AUTUMN / WINTER`; derived from current date.
- **`Terrain`** enum — `OUTDOORS / IN_BUILDING / INDOORS_CAVE / SNOWY / FOREST / WATER / DESERT`;
  rooms would carry a terrain tag.
- **Sun / moon position** — `astral` provides sunrise, sunset, moon phase for the configured
  server location; used to pick day/dusk/night/dawn description variants.
- **Reactive descriptions** — room descriptions vary by season, time of day, and terrain; e.g. a
  forest room reads differently at dawn in winter than at noon in summer.

### Future
- Move `GameClock`, `Season`, and `Terrain` out of `main.py` into a dedicated `game_clock.py`
  module so `simple_server.py` can import them cleanly.
- Attach terrain tag to room records; pipe current season + time-of-day into the room description
  renderer.
- Server timezone (from `server_setup.py`) should be the single source of truth passed to
  `GameClock` at startup.

---

## Economy / Currency

### Future / Research Needed
- **Multi-denomination currency** — replace the current flat silver system with a period-appropriate
  coin hierarchy (e.g. copper → silver → electrum → gold → platinum, or whatever breakdown best
  matches common Middle Ages monetary conventions).  Need to research the actual exchange rates and
  relative prevalence of each denomination before committing to a design.  The existing
  `PlayerMoneyTypes` enum and `player.silver` dict are the main touch-points; shop prices,
  bank transfers, and all display strings would also need updating.
