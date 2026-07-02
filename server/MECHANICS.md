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
- ✅ **Bad weapon choice warning** — "(bad weapon choice)" when `p2 < 3` (`SPUR.COMBAT.S:119`)

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
- ✅ **Strength drain on hit** — taking damage reduces player Strength by `damage/2` (`ps=ps-(a/2)`); `ps` = Player Strength, not food (`SPUR.COMBAT.S:307`)
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
- **Bar** — ally hiring, drink/food purchase (`SPUR.BAR.S`, `SPUR.BAR2.S`, `SPUR.BAR3.S`) — see **Bar** section below
- **Ship / Space level** — space-themed level (likely level 7); room data in `SPUR-data/level-7/` (requires gbbs-io to decode); `SPUR.SHIP.S` handles its specific mechanics (`SPACE SUIT` replaces `BOAT` for water-room traversal at level 6+, per `SPUR.MAIN.S:158`)
- **Gates** — zone gate travel (`SPUR.GATES.S`)
- **Annex** — visitor area (`SPUR.ANNEX.S`) — see **Annex** section below
- **Shop** — buy/sell items, ammo, shields (`SPUR.SHOP.S`) — see **Merchant Shoppe** section below
- **Bulletin board / news log** (`SPUR.MISC2.S`) — see expanded design in **News & Mail** and **Threaded Message Boards** sections below
- **Pray / Rest** — recover HP or stats out of combat (`SPUR.MISC2.S`)
- **READ command** — read a book item from inventory; increases Wisdom on completion (`SPUR.MISC3.S`; tips.txt: "READ books to increase your wisdom!")
- **QUOTE command** — player sets a short quote displayed to others who encounter their parked character; referenced in `t_main.lbl` command list and tips.txt
- **LOOT command** — search an unconscious player's inventory; one item per session; Civilians barred from the Shoppe after looting (tips.txt); see also Items section above
- **The Dwarf** — permanent NPC on a fixed room on level 1; steals gold from all players until killed; killing him awards all accumulated stolen gold; room does not change between sessions (tips.txt)
- **Special room traversal requirements** — snow/mountain rooms (`**` flag) require a Great Coat (item #78) or player freezes; water rooms (`@@` flag) require a Boat (levels 1–5) or Space Suit (level 6+); checks in `SPUR.MAIN.S:313–319` and `t_main.lbl`
- **Wraith Master title** — players with `WRAITH_MASTER` flag get ", Wraith Master of Spur!" appended to their name at login (stubbed in `commands/connect.py:242`)
- **WHO command** — lists currently online players; replaces the SPUR "last adventurer" login display (stubbed in `commands/connect.py:247`)
- **Guild follow** — player character automatically follows guild members to their location when logged off; toggle in settings (stubbed in `commands/connect.py:274`)
- **DIG command** — dig for buried items or gold (`SPUR.MAIN.S`)
- **WEAKEN command** — sysop-only stat reduction command (`SPUR.MAIN.S`)
- **GET command** — pick up items, food, monsters, cursed items, or another player from the room (`SPUR.MISC.S`)
- **DROP command** — drop items, compass, or weapons into the room (`SPUR.MISC.S`)
- **GIVE / TAKE** — transfer items to and from allies in your party (`SPUR.MISC.S`)
- **Booby-trapped items** — items that trigger a trap effect when picked up (`SPUR.MISC.S`)
- **Pandora's Box** — special item with unique pickup/open effect (`SPUR.MISC.S`)
- **ORDER command** — rearrange the tactical order of allies in the party (point / flank / rear) (`SPUR.MISC2.S`)
- **Ally payment** — allies require weekly payment (gold) to remain loyal; non-payment triggers desertion (`SPUR.MISC2.S`)
- **Allies joining you** — conditions under which free allies in a room may voluntarily join the party (`SPUR.MISC2.S`)
- **Ally searching** — allies can autonomously find and return gold to the player (`SPUR.MISC6.S`)
- **Ally desertion / death** — allies may die or leave if unpaid, injured, or mistreated; status reverts to FREE (`SPUR.MISC6.S`)
- **Random events** — location-triggered events: little girl encounter, meteor strike, Enforcer arrival, Galadriel appearance (`SPUR.MISC6.S`)
- **Statue carving** — player action to carve a permanent statue in a room (`SPUR.MISC6.S`)
- **AMMO command** — view and manage ammunition counts (`SPUR.MISC5.S`)
- **STATS / STAT2** — two-level stat display; STAT2 shows extended information (`SPUR.MISC5.S`)
- **FOLLOW ME command** — causes nearby players or allies to follow the player (`SPUR.MISC5.S`)

### Future
- **Chat channels** — named, persistent channels players can join/leave (e.g. `#general`, `#claw`,
  `#trade`); guild channels auto-populated by membership; messages broadcast to all online
  subscribers; history stored server-side so joiners can see recent backlog.  Ties naturally into
  the prompt_toolkit split-pane client work: incoming channel messages scroll the output pane
  while the player types in the input area.

---

## Merchant Shoppe (`server/shoppe/main.py`)

### Implemented
- ✅ **General Store** — sells rations 1–10 (safe food/drink); duplicate check; silver deduction; pack-full guard
- ✅ **Elevator** — travel between levels 1–5 (`shoppe/elevator.py`)
- ✅ **Player List** — browse online/offline players by wildcard pattern

### Stubs (not yet implemented)
- **Armory** — buy and sell weapons; max 6 weapons per player (`SPUR.SHOP.S`)
- **Protection** — buy armor and shields; max 5 items per player (`SPUR.SHOP.S`)
- **Bank of SPUR** — deposit, withdraw, transfer gold; level 2+ required for transfers (`SPUR.SHIP.S bank`)
- **Wizard** — buy spells; Wizards pay half price, Druids two-thirds; max 10 spells (`SPUR.SHOP.S`)
- **Clan / Guild office** — change guild affiliation (Claw, Sword, Iron Fist, Civilian, Outlaw); costs gold and honor (`SPUR.SHOP.S`)
- **Pawn Shop** — sell (not buy) items to the merchant; all found items are sellable (tips.txt) (`SPUR.SHOP.S`)
- **Olly's Ammo** — buy ammunition for ranged and energy weapons (`SPUR.SHOP.S`)

---

## Merchant's Annex (`server/annex/main.py`)

All sections are stubs. Source: `SPUR.ANNEX.S`.

### Stubs (not yet implemented)
- **School info** — character class descriptions and stat bonuses
- **System message** — sysop broadcast message of the day
- **Tips** — in-game tips display (content from `SPUR-data/tips.txt`)
- **School spells** — list of spells available to the player's class
- **Recent news / Older news** — two-tier news log (ties into News & Mail design)
- **Guild standings** — ranking of guilds by kills/XP
- **Personal records** — player's own stats history
- **System data view** — server-level statistics (total players, kills, etc.)
- **Message boards (×3)** — three separate threaded boards (ties into Threaded Message Boards design)
- **Player rosters** — separate lists for Civilians, Mark of the Claw, Mark of the Sword, Iron Fist, and Outlaws

---

## Bar (`server/bar/main.py`)

### Partially Implemented
- ✅ **Fat Olaf** — slave/servant trader; buy allies; sell servant stub present (`bar/fat_olaf.py`)
- ✅ **Food/drink menu** — `food_menu()` helper exists; rations list rendered

### Stubs (not yet implemented)
- **Vinny** — loan shark; apply for loans, pay back, store gold in bar; also arranges thugs (`SPUR.BAR.S`, `SPUR.BAR3.S`); stub present, full dialog not wired
- **Skip** — sells hash or coffee; simple food/drink vendor (`SPUR.BAR2.S`)
- **Bar None** — Guss the barkeep; coin flips, blackjack (`SPUR.BAR2.S`); our stub is `bar/bar_none.py`
- **Zelda** — reanimates monsters for players; studies and displays player stats (`SPUR.BAR.S`)
- **Blue Djinn** — hired hits; pay to have another player attacked (`SPUR.BAR.S`)
- **Bouncer** — enforces entry rules; role partially referenced
- **Bar brawl / PvP** — fighting other players in the bar; stub message "combat not yet available" (`bar/main.py:269`)

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

## Horses

Source references: `text-listings/t_mount.lbl`, `t_charge.lbl`, `t_main.lbl`, `t_stat.lbl`,
`t_startup.lbl`, `t_ma_blacksmith.lbl`.

### Overview
A horse occupies **ally slot 4** (`a$(4)`).  The string `"---"` in that slot means no horse.
At login, if the player has a horse, it is announced: *"Your faithful steed `<name>` is here."*
`[MOUNTED]` is shown in the player status line when the mounted bit is set.

### Not Implemented

#### Acquiring a horse
- **Stable** — horses are bought/stabled somewhere on level 6 (exact room TBD).
- **Naming** — the horse has a name stored in the ally-4 name field (e.g. `STRAWBERRY`); player
  presumably names it at purchase time.

#### MOUNT / DISMOUNT
- `MOUNT` — checks `a$(4) <> "---"` (horse exists); checks mounted bit (bit 4 of `v1+65`);
  handles water rooms gracefully ("(Luckily, `<name>` can swim.)"); sets mounted bit and prints
  "You leap upon your noble steed, `<name>`..."
  - TODO in source: check character class size for mounting difficulty; check for saddle; check
    player strength vs. weight of armor.
- `DISMOUNT` — clears mounted bit.  Source notes that MOUNT and DISMOUNT may be folded into one
  toggle command.

#### CHARGE
- Requires horse in slot 4; fails with "You don't have a horse."
- Requires a live monster present; fails with a sarcastic message if nothing to charge toward.
- Water room: special joke message ("Clopping two coconut halves...").
- Horse strength gate: `peek(v1+119) < 5` → "Your horse is too weak to charge."
- Class attack bonuses: Fighter/Thief/Archer (cl 1/6/7): −25; Paladin (cl 3): +25; Assassin
  (cl 8): +35.
- Roll determines hit/miss; damage = `rnd(roll/4)`.
- TODOs in source: consider monster size (missing over its head); Knight lance bonus; player or
  horse taking return-attack damage; being unseated without a saddle on a heavy blow.

#### Horse stats & equipment
- **Constitution & HP** — displayed on the stat screen alongside armor; "looks sick" / "looks
  weak" messages when low (same health-check loop as allies).
- **Armor** — horse has an armor rating; displayed in stat screen; no shield slot.
- **Race** — horse has a race (bits 6–0 of `v2+189`); cross-breeding possible by setting multiple
  bits (noted in source: "Thanks for the idea, DracoSilv").
- **Saddlebags** — bit 7 of `v2+189`; without saddlebags the horse carries no gold and no items;
  with saddlebags it can carry things (extra inventory).  Gold display routines explicitly check
  for this flag before showing horse gold.
- **Saddle** — referenced in MOUNT and CHARGE TODOs; affects mounting checks and unseating risk;
  presumably a purchasable item.
- **Lasso** — referenced by the user; likely used to catch/acquire a horse (exact mechanic TBD).
- **Horseshoes** — listed as a TODO service at the Blacksmith (`t_ma_blacksmith.lbl:
  "todo: shoe horse"`); effect on speed or armor TBD.
- **Food** — horses presumably need feeding (appropriate food items TBD; ties into the
  food/ration system).

### Future
- Decide on stable location (level 6 per user notes) and lasso / purchase flow.
- Implement `MOUNT` / `DISMOUNT` as toggle or separate commands.
- Implement `CHARGE` with class bonuses, horse-strength gate, and unseating risk.
- Wire saddlebags into inventory as an extra carry slot on the horse.
- Add horseshoe service to the Blacksmith shoppe section.

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

## Administration

Admin access is controlled by `PlayerFlags.ADMIN`.  Set it on a player via
`editplayer → Flags → Administrator` or with `editplayer` in-game.  The flag is
checked at the start of every admin command; non-admins receive "You lack the
authority to do that."

### Implemented

#### Player management
- **`editplayer` (`ep`)** — full in-game player editor: alignment, attributes,
  character names, combinations, flags/counters, hit points, inventory, money
  (In Hand / In Bank / In Bar), statistics, weapons (`commands/editplayer.py`).
  Changes are written on save/quit.
- **`ban <user> [reason]`** — permanently suspend an account; player is rejected
  at login with a "permanently suspended" message (`commands/ban.py`,
  `commands/connect.py`).
- **`ban <user> until <date> [reason]`** — temporary ban expiring at the given
  date; player is told when they may log in again.
- **`ban <user> from <date> to <date> [reason]`** — ban active only within a
  date window; outside the window the account is not blocked.
- **`unban <user>`** — lifts any ban immediately.
- **`ban #view`** — lists all ban entries with issue date, period, issuing admin,
  and reason; expired / pending bans are marked `[EXPIRED]` / `[pending]`.
- Ban storage: `run/server/net/ban-list.json`.
  Date parsing uses `parse_date.py` (see **Date Parsing Utility** below).

#### Navigation
- **`teleport <room>` / `t <room>` / `#<room>`** — instant movement to any room
  by number or name fragment.  Name search lists matches; unique match teleports
  immediately.  Guild-aligned destination rooms launch the guild HQ session
  (same as walking in). Admin only (`commands/teleport.py`).

#### World editing
- **`editmonsters`** — in-game monster editor; admin only (`commands/editmonsters.py`).

#### Visibility
- **`whereat`** — shows location of every online player; available to admins and
  players with DEBUG flag (`commands/whereat.py`).
- **`who`** — lists online players; admins see the player's account ID in addition
  to character name (`commands/who.py`).

### Not Implemented / Future

- **`kick <user>`** — disconnect an online player immediately without banning;
  useful for stuck sessions or rule violations that don't warrant a ban.
- **`broadcast <message>`** — send a server-wide message to all online players
  (equivalent to a SPUR sysop page).
- **`mute <user> [duration]`** — prevent a player from using `say`/`shout`/`page`
  for a given period.
- **`freeze <user>`** — temporarily prevent all actions (movement, combat) without
  disconnecting; useful for in-game moderation.
- **Invite management** — generate, list, and revoke invite codes via an in-game
  command rather than the setup CLI (see **Server Configuration** above).
- **Log viewer** — in-game or web utility to search and filter the pipe-delimited
  server log by player, level, module, and date range; `parse_date.py` is ready
  to back the date-range picker.
- **MOTD editor** — edit the login message-of-the-day from in-game rather than
  via `setup/server_setup.py`.
- **Audit trail** — dedicated admin-action log (ban/unban/kick/editplayer) separate
  from the main server log so moderation history is easy to review.

---

## Date Parsing Utility

`server/parse_date.py` — backed by `python-dateutil`.

### API
- **`parse_date(text)`** → `date | None` — parse a single date string.
- **`parse_date_range(text)`** → `tuple[date, date] | None` — parse a range.
- **`DATE_HELP`** — ready-made help string listing all accepted formats; embed in
  any prompt that accepts a date.

### Supported formats
| Input | Parsed as |
|---|---|
| `7/1/26` | 2026-07-01 (M/D/YY) |
| `7/1/2026` | 2026-07-01 (M/D/YYYY) |
| `7/1` | 2026-07-01 (current year assumed) |
| `2026-07-01` | 2026-07-01 (ISO 8601) |
| `Jul 1` | 2026-07-01 |
| `July 1 2026` | 2026-07-01 |

Range separators accepted: `to`, ` - ` (spaced hyphen), `–` (en-dash), `—` (em-dash).
Leading `from` is stripped.  Example: `from Jul 1 to Dec 31`.

**Ambiguity note:** dash-separated numbers (`1-7-26`) are read M-D-YY, so
`1-7-26 = January 7`.  Use slashes or month names to be unambiguous.

---

## Economy / Currency

### Future / Research Needed
- **Multi-denomination currency** — replace the current flat silver system with a period-appropriate
  coin hierarchy (e.g. copper → silver → electrum → gold → platinum, or whatever breakdown best
  matches common Middle Ages monetary conventions).  Need to research the actual exchange rates and
  relative prevalence of each denomination before committing to a design.  The existing
  `PlayerMoneyTypes` enum and `player.silver` dict are the main touch-points; shop prices,
  bank transfers, and all display strings would also need updating.
