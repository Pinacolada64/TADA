# TADA Mechanics Roadmap

Tracks game mechanics from the SPUR source that are either implemented, partially
implemented, or not yet started. Source references are to files under `SPUR-code/`.

---

## Recovered SPUR Messages (`server/messages.json`)

`SPUR-data/SPUR Messages.txt` (a raw sysop-console dump, message # → flavor text)
recovered 54 messages (#2–#55; #1 and #23, #50–#55 are blank/unreadable in the
dump). Parsed into `server/messages.json` as `{"N": ["paragraph", ...], ...}`,
one entry per `gosub messages` call site's `a=N` in the SPUR source. Every
number below is cross-referenced to where the master branch actually prints it
(`a=N:gosub messages` / `gosub message`); ~33 recovered numbers have no
identified call site yet (no hits in the skip branch either) — likely either
computed `a=` values a literal grep can't catch, or genuinely unused slots.

✅ **Display function**: `messages.py`'s `load_messages()` (loaded once into
`Server.messages` alongside `monster_quotes`, same pattern) and
`send_message(ctx, number)` — the single way any feature should print a
recovered message, rather than embedding a duplicate copy of the text. Data
referencing a message uses `"message_number": N`, not inline text — e.g.
`level_1.json` room 89's `hidden_exit_east` (`Room.hidden_exit()` returns a
`HiddenExitTarget` with a `message_number` field; `Server._teleport_to()`
calls `send_message()` with it). `tests/test_messages.py` covers the loader
and display function directly.

| # | Subroutine (file:line) | Feature | Status |
|---|---|---|---|
| 3 | `fountain`→arm (`SPUR.SUB.S:122`) | Amulet of Life "comes alive" flavor at the Fountain of Youth | Quest #9 — text now available, not yet wired into code |
| 4 | `key` (`SPUR.USE.S:185`) | Copper Key / Wraith Master ruins entry ("Fool!! You dare to enter my castle?!??") | Quest #14 — text now available, not yet wired into code |
| 6 | `school.2` confirm (`SPUR.MISC2.S:434`) | Class re-training result flavor | Not yet documented as a quest/mechanic — new find |
| 7 | `wraith` victory (`SPUR.MISC2.S:373`) | **Wraith King final-boss defeat cinematic** — castle collapsing, Lady of the Mist reward (+1 level) | Quest #15 (`quests/README.md`) — full trigger traced, not yet wired into code |
| 8 | `school` intro (`SPUR.MISC2.S:418`) | Class re-training camp intro flavor | Not yet documented — new find |
| 9 | `new` (`SPUR.LOGON.S:50`) | New-player login MOTD/welcome text | Not yet wired in (current login flow has its own welcome text) |
| 10 | login banner (`SPUR.LOGON.S:27`) | Original BBS-door splash/credits screen | Historical only, not applicable to this port |
| 11 | `quote` (`SPUR.LOGON.S:619`) | QUOTE command instructions | `commands/quote.py` likely has its own help text already |
| 13 | shield training confirm (`SPUR.MISC2.S:460`) | Shield training (Odin the Shield Master) result flavor | Not yet documented — new find |
| 16 | duel `H`elp (`SPUR.DUEL.S:26,43`) | Duel help screen text | Duels are implemented (`## Duels (PvP)`); this specific help text not yet ported |
| 17 | monster #120 death (`SPUR.MISC.S:417`) | Disguised-old-man-monster transform-on-death flavor | Already tracked separately per this session's earlier GOD/GODDESS message work |
| 18 | room 89 teleport (`SPUR.MISC.S:448`) | ✅ Implemented — level 1 Teleport Room → level 5 | `level_1.json` room 89's `hidden_exit_east.message_number` |
| 19 | `slippers` (`SPUR.USE.S:144`) | Ruby Slippers teleport-home flavor ("There is no place like home...") | Quest #7 — text now available, not yet wired into code |
| 20 | `revive` default (`SPUR.MISC6.S:132`) | Amulet-of-Life death-save flavor | Ties to item #76 Amulet of Life; not yet wired into code |
| 21 | `revive` `flag(7)` (`SPUR.MISC6.S:132`) | Alternate "Chosen One" death-save flavor (condition behind `flag(7)` untraced) | Not yet documented — new find |
| 24–29 | `galad`/riddle (`SPUR.MISC6.S:506–518`) | ✅ Test of Galadriel's exact riddle text — #24 intro, #25–29 are 5 random Tolkien trivia riddles with answers baked into the source (`zz$`) | Quest #8 — text now available, not yet wired into code |
| 33 | `revive` SAINT (`SPUR.MISC6.S:132`) | Saint-class-specific death-save flavor ("So, this is what God looks like") | Not yet documented — new find |
| 34 | `train` (skip branch `SPUR.MISC8.S:88`) | ✅ Implemented — Jake's Stable Train Horse success flavor ("kick butt and take names"), followed by this port's own "X prances proudly" line naming the specific mount. The horse's own two pronouns are named placeholders (`{HORSE_OBJECTIVE}`/`{HORSE_SUBJECTIVE}`) resolved per-mount via `get_pronoun()`, not hardcoded "him"/"he" | `street/jakes.py` `_train_horse()`, `messages.send_message()`'s `**context` kwarg |
| 35 | `tips` (skip branch `SPUR.MISC8.S:91`) | ✅ Implemented — Jake's Stable Tips menu option: the "narrow grassy canyon" hint and the sugar-cube/lasso how-to | `street/jakes.py` `_tips()` |

The Wraith King ending (#7) trigger has since been fully traced — see
`quests/README.md`'s quest #15 ("Wraith King / RONNEY"). Monster #93 "RONNEY"
(`monsters.json`) is a disguised identity for the King, placed at level 5 room
262 "Kings Chamber." Killing it advances the *same* `zu$[7]` status field quest
#14's Copper Key checks, prints message #7, logs a `battle.log` announcement,
grants +1 level and +100 Honor (capped 1900), and teleports the player to
level 5 room 390 — the exact room the Copper Key is hardcoded to. The two
quests converge on one location and one status field. Room 390 itself is a
gap: level 5's header declares 400 rooms but `level_5.json` only has 1–373.

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
- ✅ **Ally death-save** — before a blow that would kill the player lands, an owned ally gets a chance to intervene: GOD/GODDESS allies always teleport the player to safety and depart for good; others roll courage (vs. player honor, elites get a bonus) and either flee (freed) or "leap in front" as flavor — only a GOD/GODDESS save actually cancels the damage, matching SPUR.MISC9.S exactly (`SPUR.COMBAT.S` `dragon`/`sac.ally`, `ally_events.py` `try_ally_death_save()`, `engine.py` `_resolve_monster_hit()`)
- ✅ **LASSO — capture a mount** — during combat against a horse-named monster, `lasso` captures it as a new MOUNT-flagged ally (name prompt with SPUR's length/character validation, plus an 'R' option for a random gender-appropriate name); blocked by a full party or an existing mount. A TADA original addition beyond SPUR: the mount's own gender is rolled 50/50 and announced ("Your horse seems to be a male/female") -- SPUR's `lasso.b` never tracked a mount's gender at all, hence its flavor text always saying "he"/"him" unconditionally (`SPUR.USE.S` `lasso`, `commands/lasso.py`, `engine.py` `CombatSession.lasso()`/`_finalize_mount_capture()`/`_random_horse_name()`)
- ✅ **Druid/Ranger passive taming** — a TADA original mechanic, not from
  SPUR: fighting a wild horse as a Druid or Ranger gives a 15% chance each
  round of taming it outright, without ever using LASSO — "A certain look
  passes between the two of you, and the horse seems to accept you as its
  master/mistress!" (gender-correct). Same full-party/existing-mount guard
  as LASSO, but silent on failure (no spam every round); checked for both
  the fight's leader and any bystander who joins (`CombatSession.
  _try_class_tame()`, `engine.py`).
- **XP gain per swing** (`engine.py`)
- **Monster kill rewards** — gold and XP awarded on kill (`engine.py`, `combat/rewards.py`)
- ✅ **Fights called out by name in the room description** — a TADA multiplayer
  addition, not from SPUR source: when a player walks into (or looks at) a room
  where someone is already fighting a monster, that fighter is called out by
  name against the monster instead of blending into the plain "X is here" list
  — "Railbender is fighting TROLL here!" — so the ongoing fight is obvious at a
  glance. Checks `Server.active_combats[room_no]`'s `attackers` against the
  room's player list (`simple_server.py` `_describe_room()`).
- ✅ **Bystander join announced to the room** — another TADA multiplayer addition:
  when a bystander joins a fight already underway (typing `attack <monster>` on
  a monster someone else is already fighting), the room is told who's joining
  whom — "Rulan joins Railbender in fighting the TROLL!" — instead of the new
  attacker silently appearing in the fight. Sent once, right when the bystander
  joins, naming `CombatSession.leader` as the original attacker
  (`CombatSession.join()`, `combat/engine.py`).
- ✅ **Fixed bug: an already-joined bystander couldn't keep swinging** —
  `CombatSession.join()` gives a bystander exactly one swing per call
  ("Bystanders fire one swing then wait; the leader's loop drives the
  fight."), so re-typing `attack` each round is how a bystander keeps
  fighting, not a mistake — but `commands/attack.py` treated a repeat
  `attack` from someone already in `session.attackers` as an error
  ("You're already in this fight!") and did nothing. Now it just calls
  `session.join()` again for another swing (`commands/attack.py`).
- ✅ **Leaving the room drops you from the fight** — another TADA
  multiplayer addition: a bystander who joined a fight then moves out of
  the room is removed from `CombatSession.attackers`, so they stop being
  eligible for the "monster is slain!" notice, stray-round hits, etc. once
  they're no longer actually present. Checked on every successful move,
  keyed off the room being left, before the destination room is applied
  (`Server._leave_combat_on_move()`, `simple_server.py`). Mainly relevant
  to bystanders — the fight's leader is normally occupied by
  `CombatSession._run_loop()`'s own prompt for the fight's duration and
  can't reach `_move()` mid-fight.
- ✅ **Monster taunts/greetings** — when combat begins, the monster picks a quote from
  `monster_quotes.json` (71 real lines recovered from `SPUR-data/MONSTER.QUOTE.TXT`, a
  flat 170-byte-record file, plus a captured play transcript): a fixed
  `monster['quote_number']` always wins if set (none currently are); otherwise a random
  aggressive taunt (quotes 1–52), or — if the player's race is thematically simpatico with
  the monster's alignment (Ogre/Half-Elf vs. an `evil`-flagged monster, Pixie/Elf vs. a
  `good`-flagged monster) — a random friendly greeting (quotes 61–71) instead. `'$'` in the
  quote is replaced with the player's name (`SPUR.MISC4.S` `mon.ret`/`perm.qt`, skip
  branch; `monsters.py` `load_quotes()`, `combat/engine.py` `_pick_monster_quote()`)

### Not Implemented

#### Weapon / attack mechanics
- ✅ **Ammo system (core)** — "NO AMMO READY" blocks attack for projectile/energy weapons; ammo consumed per shot; `ammo_damage` added to hit; STORM bypasses ammo (`SPUR.COMBAT.S:44,84,144`, `resolution.py`, `engine.py`)
- **Ammo — burst/auto-fire modes** — S/B/A fire-mode prompt; burst and auto consume multiple rounds per swing (`SPUR.COMBAT.S:98–101`)
- ✅ **Stray round / friendly fire** — missed ammo shot may hit ally or bystander; chance scales by weapon XP: GREEN 1-in-3, VETERAN 1-in-6, ELITE 1-in-10; 1–4 HP damage; ally killed if HP reaches 0 (`engine.py` `_stray_round()`)
- ✅ **Ammo recovery** — after killing a monster, bow/sling/blowgun weapons recover 1–max random rounds; message uses weapon-specific term (arrows/stones/darts) (`SPUR.MISC.S:427`, `engine.py` `_recover_ammo()`)
- ✅ **USE ammo command** — loads ammo into a readied ranged weapon; checks `used_with`; STORM refuses physical ammo (`SPUR.USE.S:147–162`, `commands/use.py`)
- ✅ **Missile: first strike** — when ammo is loaded and monster hasn't attacked yet, monster skips its first swing; "MISSILE: FIRST STRIKE!" message (`SPUR.COMBAT.S:219`, `engine.py`)
- ✅ **Pole weapon: first strike** — roll + (monster agility × 3) + 2 < player DEX → first strike; otherwise monster swings normally (`SPUR.COMBAT.S:221`, `engine.py`)
- ✅ **Fireball/energy weapon secondary damage** — 10% chance of secondary heat damage (`SPUR.COMBAT.S:143`, `resolution.py:511-514`)
- **LURK mode** — player fires over allies' shoulders; to-hit penalty; requires at least one living ally (`SPUR.COMBAT.S:87–96`)
- ✅ **Assassin critical hit** — class 8 (Assassin), 10% chance to double damage (`SPUR.COMBAT.S:135`, `resolution.py:435`)
- ✅ **Ease-of-use help message** — "(Ease of use helps!)" when roll barely misses and ease-of-use score would have made the difference (`SPUR.COMBAT.S:139`, `resolution.py:416`, `engine.py:541`)
- ✅ **Bad weapon choice warning** — "(bad weapon choice)" when `p2 < 3` (`SPUR.COMBAT.S:119`)
- ✅ **Zero-damage hit phrasing** — a landed hit that rolls 0 damage reads
  "You strike the TROLL, but inflict no damage!" (and the equivalent
  bystander/room broadcast and ally-swing message), not "...for 0
  damage!" — a TADA wording improvement, not from SPUR source
  (`combat/engine.py` `_narrate_player_swing()` and the ally-attack loop).

#### Defence
- ✅ **Shield** — blocks some incoming damage; degrades; can be destroyed; shield items usable via USE command (`SPUR.COMBAT.S`, `SPUR.USE.S:34–43`, `combat/resolution.py` `monster_attacks()`, `combat/engine.py`)
- ✅ **Armor** — degrades each hit; destroyed when it reaches 0; (`SPUR.COMBAT.S:289–302`, `combat/resolution.py` `monster_attacks()`, `combat/engine.py`)
- **Gauntlets** — absorb one hit (10% chance destroyed) when player takes a hit (`SPUR.COMBAT.S:210–217`, `SPUR.WEAPON.S:spec4`)
- **Wizard's glow** — item `zu$[7]` values 2/3 reduce incoming damage by 2 (`SPUR.COMBAT.S:266`)
- **Lazer shield** — energized shield variant; blocks laser fire at half damage (`SPUR.USE.S:86`)
- **Power armor** — specific item; halves blast damage (`SPUR.USE.S:124`)
- ✅ **Crystal Pendant** (item #82) — resolved once per encounter, not per round (`SPUR.MISC4.S` `mon.set`/`stone`, called when the monster is first set up): if the player carries it and the monster can `petrify`, 90% chance to permanently disable that monster's turn-to-stone for the rest of the fight ("The CRYSTAL PENDANT flashes, preventing TURN TO STONE by `<monster>`!"), 10% chance the monster "happens to see" it and dons anti-pendant glasses that one time (petrification remains possible for the rest of the fight either way) (`combat/engine.py` `CombatSession._check_crystal_pendant()`)

#### Monster abilities
- **Monster spellcasting** — monsters with `+` flag in `wy$` can cast spells when low HP (`SPUR.COMBAT.S` `lnk.msc4`)
- **Monster fire/laser** — monsters with `-` flag shoot fire; laser-equipped rooms use laser fire (`SPUR.COMBAT.S:240–248`)
- ✅ **Poison on hit** — monsters with `poisonous_attack` flag; 30% chance per hit (`SPUR.COMBAT.S:312–313`, `resolution.py:639`, `engine.py:603`)
- ✅ **Disease on hit** — monsters with `diseased_attack` flag; 30% chance per hit (`SPUR.COMBAT.S:315–316`, `resolution.py:641`, `engine.py:605`)
- ✅ **Experience drain on hit** — monsters with `experience_drain` flag; drains XP on hit (`SPUR.COMBAT.S:317`, `resolution.py:655`, `engine.py:611`)
- **Multiple guards** — if player is treacherous in a guard room, whistles summon more guards and monster HP multiplies (`SPUR.COMBAT.S mad.gd`)
- ✅ **Dexterity loss on heavy hit** — taking >4 damage reduces player DEX by 1 (`SPUR.COMBAT.S:318`, `engine.py:583`)
- ✅ **Dexterity gain** — dealing >4 damage has small chance to increase player DEX (`SPUR.COMBAT.S:143`, `engine.py:335`)
- ✅ **Wisdom gain on kill** — player `pw` increases by 1 on every non-ally kill (`SPUR.COMBAT.S:188`, `engine.py:676`)

#### UI / information display
- **Planned: hide monster HP by default** — the combat prompt bar
  (`_run_loop()`, `combat/engine.py:591`) currently always shows the
  monster's exact HP (`{mname} HP:{_monster_hp(self.monster)}`). Plan is to
  stop showing it by default — a player shouldn't know a monster's exact HP
  unless they've divined it via a specific spell or magic item (mechanic
  TBD, not yet designed). Until that spell/item exists, the bar should just
  show the monster's name without a number.
  - **Candidate spell: ESP** — proposed as the divining spell, but note SPUR
    already has a real spell of that exact name (`SPUR-data/spells.txt`:
    `ESP: Raises your intelligence`, type `I` per `SPELL.TYPE.TXT`'s
    Player/Intelligence coding) with no monster-HP-related purpose in the
    original game. Using this name for HP-divining would be a deliberate
    TADA repurposing, not a restoration of existing SPUR behavior — worth
    keeping in mind if the original INT-raising ESP is ever ported too
    (name collision to resolve one way or the other before implementing).
  - **Debug-mode exceptions** (gated on `PlayerFlags.DEBUG_MODE`, same flag
    as `dbg`/the `[DEBUG] Room flags` line): a `[DEBUG]`-prefixed line in
    the combat prompt still shows the monster's exact HP regardless of
    whether it's been divined, plus two new debug-only menu options on the
    same prompt bar: `[R]esurrect` and `[K]ill monster` (instant win/loss
    for testing combat flow without grinding out a real fight).

#### Status effects / survival
- ✅ **Hunger / thirst** — `food` and `drink` deplete every 10 commands; "VERY HUNGRY/THIRSTY", "FAINT" warnings; starvation death when both reach 0; `eat` and `drink` commands restore them (`survival.py`, `commands/eat.py`, `commands/drink.py`, `SPUR.COMBAT.S:12–19`)
- ✅ **Poison** — tick damage (−2 HP); 30% chance per tick (`SPUR.COMBAT.S:15`, `survival.py:41`); STR reduction if ring worn is not yet implemented
- ✅ **Disease** — tick damage (−1 HP); 30% chance per tick (`SPUR.COMBAT.S:16`, `survival.py:50`)
- **Ring of power weakening** — wearing the ring has a 10% per-tick chance to reduce STR/WIS (`SPUR.COMBAT.S:14`)
- ✅ **Strength drain on hit** — taking damage reduces player Strength by `damage/2` (`ps=ps-(a/2)`); `ps` = Player Strength, not food (`SPUR.COMBAT.S:307`)
- ✅ **Too weak to wield** — if player Strength < 4, weapon is automatically unreadied (`SPUR.COMBAT.S:321`, `engine.py:290`)
- **Dusk warning** — message when session time < 120 ticks remain (`SPUR.COMBAT.S:11`)

---

## Flee

### Implemented
- Basic flee command exists (`commands/flee.py`)

### Not Implemented
- ✅ **Monster blocks path** — if player HP > 7 and the monster is following, may block flee (`SPUR.COMBAT.S:75`, `combat/resolution.py` `flee_attempt()`, `combat/engine.py` — "`{mname} blocks your escape!`"). **Note**: the XP-scaling term in SPUR's formula (`random(1,10) < xp/3`) is currently hardcoded to `xp=1` (`resolution.py:800`, `# TODO: replace with derived xp_level`), so higher-level players don't yet get an easier time slipping past — the core block-or-not mechanic works, but the level scaling isn't wired up.
- ✅ **Energy cost** — fleeing costs 1 energy (`SPUR.COMBAT.S:76`, `engine.py` `flee()`)
- ✅ **Impassable rooms** — rooms flagged `@@` (water), `**` (snow), or `<<` (no_flee) cannot be fled from (`SPUR.COMBAT.S:74`, `resolution.py` `flee_attempt()`); flags parsed by `convert_from_gbbs_tool.py` and stored as `Room.flags`. **Note**: on level 6, `@@` doesn't mean water at all — see "Special room traversal requirements" below.

---

## Weapons & Readying

### Implemented
- **Ready command** — choose weapon from inventory; display class/weapon stats (`commands/ready.py`)
- **Battle experience tiers** — GREEN / VETERAN / ELITE thresholds displayed on ready (`commands/ready.py`)
- ✅ **STORM — howls in rage** — refuses to be switched away from; zaps player; disintegrates (`commands/ready.py`)
- ✅ **STORM — jealous rage** — unreadied STORM in inventory howls when player readies something else (`commands/ready.py`)
- ✅ **STORM — servant** — accepts player with good class/race affinity; grants +2 skill/damage (`commands/ready.py`, `combat/engine.py`)
- ✅ **STORM — YOU ARE NOT MINE** — rejects player with no class/race affinity (`commands/ready.py`)
- ✅ **Excalibur — Knight/honor gate** — readying weapon #17 requires Knight class + honor >= 1200; an unworthy player gets the same rejection blast as an unfit STORM ready, a worthy one gets unique "fiery sheen" flavor text (`SPUR.WEAPON.S:27`, `commands/ready.py`)
- ✅ **Death Amulet — readying gamble** — readying weapon #56 (matched by name) is a Y/N confirm with a 20% instant-death roll, reduced to 10% if carrying the Amulet of Life (#76) (`SPUR.WEAPON.S:31, 64-73`, `commands/ready.py`)
- ✅ **"Best targets" combat bonus** — the weapon-class-vs-monster-size table hinted at in the ready display's `[ Best targets ]` line is a real to-hit bonus/penalty during combat, not just flavor (`SPUR.COMBAT.S:110-118`, `combat/resolution.py` `hit_threshold()`); the `[ Best targets ]` hint itself only shows for non-expert players — experts get the terser "Weapon class: X" line alone (`commands/ready.py` `_weapon_class_line()`)
- ✅ **Archer bow accuracy bonus** — Archers (`pc=7`) wielding a weapon whose name contains "SBOW" or " BOW" get +2 to-hit / +2 damage; the same class gets a −1/−2 penalty with `bash/slash` or `pole/range` weapon classes (i.e. non-ranged weapons), and Assassins get a −1/−1 penalty with bows (`SPUR.WEAPON.S:134,137`, `item_system.py` `weapon_bonus()`, flows into `combat/engine.py` → `combat/resolution.py`'s hit-threshold roll like any other class/weapon modifier). Undocumented here until now, which is why it read as missing on a memory check.
- ✅ **UNREADY command** — clears readied weapon; "No weapon readied!" if nothing's equipped (`SPUR.MAIN.S:84-85`, `commands/unready.py`)

### Not Implemented
- ✅ **Battle experience accumulation** — `vp`/`weapon_experience` for the currently-readied weapon goes up by 1 only on landing the killing blow (not per swing -- `vp=vp+1` is only ever reached at SPUR.MISC.S:384 `p.a3`, confirmed by grepping every .S file); VETERAN at 40 kills, ELITE at 99 (`SPUR.MISC.S:384`, `player.py` `gain_weapon_experience()`, `engine.py` `_monster_dies()`). Corrected this session -- an earlier version incremented it after every swing (hit or miss) and even credited every other attacker in the room for the swinger's weapon; see `tests/test_battle_experience.py`.
- ✅ **ELITE damage scaling** — ELITE tier grants +XP damage instead of flat +1 (`SPUR.WEAPON.S`, `resolution.py` `battle_exp_bonuses()`)
- **Dexterity requirement** — weapons have a minimum DEX to wield (`ws+4`); player refused if below threshold (`SPUR.WEAPON.S:46`)
- **STORM — duel behavior** — deferred until duels are implemented

---

## Item USE

### Implemented
- ✅ **USE command** — item list + numbered picker; delegates to type-specific handlers (`commands/use.py`)
- ✅ **Ammo loading** — `USE <ammo item>` loads rounds into readied weapon; checks `used_with`; sets `player.ammo_rounds`/`player.ammo_damage`; STORM refuses physical ammo (`SPUR.USE.S:147–162`)
- ✅ **Shield use** — `USE <shield item>` adds to shield rating; class/race caps (Wizard 25, Thief/Assassin/Pixie 35, Hobbit/Gnome 50, others 100); Battle/Lazer shield +20 to all caps (`SPUR.USE.S:34–43`)
- ✅ **Compass** — toggle `player.compass_active`; "USE again to return to pack" hint (`SPUR.USE.S:44–50`)

### Not Implemented
- ✅ **Ring of invisibility** — USE toggles `ring_worn`; worn: CON−2, "hard to see", evil senses warning; remove: "returned to pack"; penalty persists (`SPUR.USE.S use4`, `commands/use.py`)
- ✅ **Grenade** — hurl at room monster; damage = 1d10 + 5 + (xp_level × 2); no monster: "harmlessly"; kills monster if HP reaches 0; item consumed (`SPUR.USE.S:91`, `commands/use.py`)
- **Potion** — restore HP or stats (`SPUR.USE.S`)
- **Rocket** — single-use ranged explosive; several variants (TOW, LAW, Redeye, plasma, nuclear) (`SPUR.USE.S:97–130`)
- **Scrolls / spellcasting** (`SPUR.MISC3.S`)
- **Spacesuit assembly** — combine parts 134 + 135 with tool into item 122 (`SPUR.USE.S:58–72`)
- **Communicator repair** — USE tool on item 141 produces item 66 (`SPUR.USE.S:70`)
- **Slippers of Galad** — location-specific item effect (`SPUR.USE.S:25`)
- **Palintar** — links to misc6 (`SPUR.USE.S:20`)
- **Crystal vial** — location-specific effect (`SPUR.USE.S:23–24`)
- ✅ **Ammo consumption in combat** — projectile/energy weapons check `player.ammo_rounds` before swinging; "NO AMMO READY" blocks attack; `ammo_damage` added to hit damage; one round decremented per swing (`SPUR.COMBAT.S:44,84,99,144`)

---

## Items (Examine / Look)

### Implemented
- **look \<item\>** — searches inventory, then room-floor items (`commands/look.py`, `SPUR.MISC3.S:316`)
- ✅ **Examine text lives in the data files** — objects.json/weapons.json/rations.json entries carry their own `"examine"` field (STORM weapons, named treasures like CRYSTAL PENDANT/ICE CRYSTAL/CROWN OF MIDAS/GOLD ROSE, potions, MOONSHINE, OLD HAMBURGER, etc.) instead of an if-chain keyed off item name/kind in `commands/look.py` (New in TADA — new items just need the field added, no code change)
- ✅ **Magical/cursed detection roll** — weapons.json `kind=="magic"` / objects.json `type=="cursed"` items without their own `"examine"` override go through a 1-100 roll (60% success, matching SPUR's `a=(random(999)/10)+1; if a>60 fail`) and a one-shot "already examined" memory (`player.last_examined`, mirrors SPUR's `xz$`); a failed roll re-fails even on a repeat examine, matching SPUR's roll-before-memory-check order (`SPUR.MISC3.S:295–307`)

### Not Implemented
- **"(You feel a bit smarter)" INT bump** — SPUR's `smarter` subroutine grants +2 INT (capped ~24) after examining cursed items, MOONSHINE, OLD HAMBURGER, or the suspicious-item trio (strange weapon/funny doll/Pandora's box) (`SPUR.MISC3.S:386–389`)
- **LOOT command** — search dead monster for items (`SPUR.MISC3.S`)

---

## Flee / Travel

### Not Implemented
- **Stealth / sneak** — player class affects how likely monsters are to lose sight of them (classes 6/8 get `z=50` instead of class-based roll, `SPUR.COMBAT.S:24–28`)
- ✅ **Room travel** — N/S/E/W/U/D movement between rooms (`commands/movement.py`, `simple_server.py` `_move()`)
- ✅ **Fixed bug: room lookups ignored the player's dungeon level** — nearly every
  room lookup across the codebase used `game_map.rooms.get(n)` (the level-1-only
  alias -- `Map.rooms` is just `Map.levels[1]`) instead of the multi-level-aware
  `game_map.get_room(level, n)`. Symptom: after taking the elevator to level 2+ and
  returning to the dungeon, the player appeared stuck on level 1 (wrong room shown,
  wrong monsters/exits resolved). Fixed across `simple_server.py`
  (`_describe_room()`, `_move()`), `ally_events.py`, and `commands/{drop,attack,
  give,movement,get,whereat,use,teleport}.py`. Left as-is (correctly): `simple_
  server.py`'s `_place_wild_horse()`, which is deliberately level-1-only. A second
  spot was missed in this same pass: `commands/teleport.py`'s room-existence check
  (`dest not in game_map.rooms`) and its name-search listing, fixed the same way.
- ✅ **Fixed bug: "Ye may travel:" never printed for full-word exit keys** — `Room.
  exits_txt()` looked up `compass_txts`, which is keyed by short direction forms
  (`n`/`s`/`e`/`w`) used for typed movement commands. Room *data*, however, stores
  exits under full words (`north`/`south`/`east`/`west` --
  `convert_from_gbbs_tool.py`'s `EXIT_KEYS`, used by every level 2-7 and by
  level_1.json since its reconciliation onto the modern schema), so the exit list
  was always empty and the line silently never printed. `exits_txt()` now
  normalizes full-word keys to short form before the `compass_txts` lookup
  (`base_classes.py`).
- ✅ **Fixed bug: real exits silently behaved like dead ends** — `commands/
  movement.py` always resolves typed directions to short forms (`n`/`s`/`e`/`w`/
  `u`/`d` — `_DIR_ALIASES`) before calling `Server._move()`, but every level's
  `exits` dict is keyed by full words (same `EXIT_KEYS` format as the "Ye may
  travel:" bug above). `exits.get(direction)` with a short-form direction
  against a full-word-keyed dict always returned `None`, so **every real exit,
  on every room, always failed to resolve** — masked in prior tests only
  because the hidden-exit `±1` fallback formula happened to produce the same
  destination room number in those specific fixtures. Added `Room.get_exit()`
  (`base_classes.py`), which checks both short and full forms; `Server._move()`
  and `commands/movement.py`'s bar-entry check now use it instead of a bare
  `.get(direction)`.
- ✅ **Fixed bug: rc/rt Up/Down connections with a real destination always
  went to the shoppe** — `rc`/`rt` on a room's `exits` dict is a separate
  transport system from compass exits: `rc=1` → Up, `rc=2` → Down, `rt=0` →
  the shoppe elevator, `rt>0` → a real same-level staircase to that room
  number (labyrinth ladders, pits, volcano-room lava tubes, etc. — display
  side already correct, see `Room.exits_txt()`'s "Up to #N"/"Down to #N" in
  `tests/test_rc_rt.py`). `commands/movement.py`'s `MoveCommand` checked only
  `rc`, never `rt`, so *any* room with `rc` set — real staircase or not — was
  unconditionally routed into the shoppe, silently swallowing every real
  rc/rt connection in the game (level 1 room 20 "Volcano Room" → room 23 was
  the one actually reported; the same bug affects at least 6 more rooms on
  level 1 alone, and others on levels 2–5). Fixed: `MoveCommand` now only
  intercepts to the shoppe when `rt==0`; a nonzero `rt` falls through to
  `Server._move()`, which now also resolves `rc`/`rt` as a destination when
  the normal exit/hidden-exit lookups come up empty. While auditing all
  `rc`/`rt` data across every level for this fix, found two also-broken `rt`
  targets on level 3 — room 39 (`rt: 100`) and room 86 (`rt: 141`) — that
  are a separate *data* problem, not a code one, and traced both back to
  SPUR's own original `ROOM.LEVEL3.TXT` database (see TODO.md's 7/10/26
  entry for the full trace): room 100 is a genuinely lost room (flagged as
  existing in `D.LEVEL3.TXT`'s header bitfield, but its message was never
  recoverable — only 90 of ~100 flagged rooms' data survived in the
  archive), while `rt: 141` is out of level 3's own numbering range
  entirely and looks like a bug already present in SPUR's original design.
  Neither is a conversion artifact, and neither has a confident fix without
  content that may simply no longer exist (an unproven "dropped trailing
  digit" theory for both — `rt: 10`/`rt: 14` — is written up in TODO.md,
  not applied).
- ✅ **Guard against moving into a room with no data** — `Server._move()`
  now checks that a resolved destination (normal exit, hidden exit, *or*
  rc/rt) actually has room data on the target level before committing the
  move, covering exactly the level 3 rooms 39/86 case above (and any other
  exit that turns out to point nowhere). Blocked instead of leaving the
  player stranded on a "You are nowhere" room they could only escape via
  teleport: logs a `logging.warning()` (so a real broken exit stays
  diagnosable) and shows one of a few in-character `_BLOCKED_ROOM_MESSAGES`
  — an invisible hand of SPUR gently pushing the player back, blaming his
  elves/crayon art skills/a "computer programming bug" rather than
  breaking immersion with a raw error.
- **Room flags** — monster blocking (`.`), no-flee (`@@`, `**`, `<<`), random encounter (`]`) — other flags (`+`, `#`, `-`, `*`, `@`, `&`, `E`/`G`, `;;`) belong to monsters, not rooms; see monster abilities in the Combat section above
- ✅ **Hidden exits** (`hidden_exit_east`/`hidden_exit_west`) — `SPUR.MISC.S:419`'s
  `"->"`/`"<-"` markers only set a boolean "exit exists" flag on the room; the
  original source never stores a target room number for them, so the real
  destination has to be traced per-room against the SPUR source. Data-driven:
  `Room.hidden_exit_east`/`hidden_exit_west` (`base_classes.py`) hold the
  *confirmed* destination once traced — a bare room number for a same-level
  exit, or `{"room": n, "level": n, "message_number": n}` for a cross-level
  one (`message_number` optional, a `server/messages.json` key printed via
  `messages.py`'s `send_message()`) — resolved by `Room.hidden_exit()` and
  `Server._move()`/`Server._teleport_to()`. All 12 currently-known
  hidden-exit rooms are now confirmed:
    - Level 1 room 89 "Teleport Room" → level 5 ("Land of the Wraiths") room
      41 — `SPUR.MISC.S:448`: `if (cl=1) and (cr=89) then a=18:gosub
      message:cl=5:cr=41:goto travel4`. Prints message #18 ("Suddenly, you
      are lifted bodily by a incredibly powerful gust of wind!..." —
      recovered from `SPUR-data/SPUR Messages.txt`, referenced by number
      (`"message_number": 18`) on room 89's `hidden_exit_east` field), then
      "You have entered Land of the Wraiths!". Note: `SPUR.MAIN.S:174`'s
      `if (cl=1) then if (cr=89) goto travel3` is a catch-all in the original
      that fires for *any* blocked direction out of the room, not just east;
      this port deliberately simplifies that to "only the flagged direction
      resolves the hidden exit," matching every other hidden exit — other
      directions out of room 89 just say "Can't go \<dir\>." now.
    - The other 11 rooms are ordinary same-level `cr ± 1` adjacency, derived
      from `SPUR.MAIN.S:169-171`'s row arithmetic (`cr=cr+1-((y=0)*ri)` for
      east, `cr=cr+((y=1)*ri)-1` for west, `y=cr mod ri`) using each level's
      real row width `ri` read straight from `D.LEVEL{2,5,6}.TXT`'s header
      (`225¬15` for level 2, `400¬20` for level 5, `900¬30` for level 6).
      Each is corroborated by the actual room data — a guarded room leads to
      an unguarded connector/reward room right next to it, often sharing a
      flag or holding the reward item:
      - Level 2: 155 "Burial Chamber" (monster 97) → 156 "Narrow Tunnel";
        157 "Mummy's Tomb" (monster 102) → 158 "Secret Chamber" (item 86)
        east, → 156 "Narrow Tunnel" west (both 155 and 157 flank the tunnel).
      - Level 5: 85 "Cold Cave" (monster 91) → 86 "Inner Cave".
      - Level 6: 45 "Engineering" (monster 109) → 46 "Access Tunnel"; 49
        "Engineering" → 48 "Equipment Locker" (item 134) west; 79 "Access
        Tunnel" → 80 "Vent Duct" (shared `radiation_extreme`); 99 "Main
        Reactor" (monster 118) → 100 "Storage Closet" (item 132); 109 "Main
        Reactor" (monster 110) → 108 "Security Bunker" (item 138) west; 115
        "Witches Coven" (monster 126) → 116 "Witches House"; 186 "A Strange
        Room" (monster 120) → 187 "Garden Of Eden" (shared `no_flee`).
      - Level 5 room 140 "Village" (monster 84, BIG CHIEF) → 141 "The
        Chief's Treasure Room" (item 78, weapon 57 — the documented
        Headhunter's Island quest reward) is the one exception worth
        flagging: room 140 sits exactly on a row boundary (`140 = 7×20`,
        the last column of its row), so the row-arithmetic formula would
        technically wrap it to room 121 ("The Ocean") instead of 141. Kept
        as `cr+1` anyway — 141's reward items and room 140's guarding
        monster are too strong a match to override with the formula, and
        every other one of these 12 rooms fits the "guarded room → very
        next room number" pattern with zero exceptions. Documented here as
        a known discrepancy rather than silently resolved either way.
  `Server._hidden_exit_target()`'s `room_number ± 1` guess remains in the
  code only as a fallback for any new hidden-exit room found later that
  hasn't been traced yet — see its docstring.
- ✅ **Hidden exit reveal message** — `SPUR.MISC.S:419-420`, right after
  `gosub rec.ammo` in the dead-monster routine (`p.a3`/`p.a4`/`no.robot`):
  killing any monster (except THE DWARF, which short-circuits earlier) in a
  room flagged `hidden_exit_east`/`hidden_exit_west` (legacy flag string *or*
  confirmed `Room.hidden_exit_east`/`west` field) unconditionally prints
  "A search reveals a secret hole, east!"/"...west!" — no other gate.
  `CombatSession._reveal_hidden_exit()`, called from `_monster_dies()`
  (`combat/engine.py`).
- Fixed data bug: `level_1.json` room 89's name carried a stray `"TELEPORT
  ROOM|->"` suffix — a leftover flag-recovery artifact from the level 1
  reconciliation (`parse_name_field()` used the `|->` marker to recover the
  `hidden_exit_east` flag, but the marker was never meant to display).
  Cleaned to plain `"TELEPORT ROOM"`; distinct from level 1's legitimate
  alignment symbols (`+`, `-]----`, `HQ`) which are intentionally kept visible.
- ✅ **Debug mode room-flags display** — when `player.is_debug` is true,
  `_describe_room()` appends a `[DEBUG] Room flags: ...` line listing the
  room's raw flags (e.g. `hidden_exit_east`) right after the "Ye may travel"
  exits line; omitted for non-debug players and for flagless rooms
  (`simple_server.py` `_describe_room()`).
- ✅ **`DBG` command** (`commands/dbg.py`) — shortcut for
  `player.toggle_flag(PlayerFlags.DEBUG_MODE)`; same underlying flag
  EditPlayer's flags menu already toggles, just without the menu hops.
- **Orator / Moderator player flag** — a player flag (name TBD — `Orator` or `Moderator`) that
  designates the speaker in an auditorium-type room.  While a flagged player is present, other
  players in the room cannot use `say`; instead they submit questions or comments via a `q` command
  which queues them for the Orator to address.  Good for town halls and structured announcements.
  Planned as one auditorium room per level for convenience; exact map placement TBD.

---

## Win/escape detection (`server/victory.py`)

- ✅ **Ported from `SPUR.MISC7.S`'s `win`/`win2`/`win5`/`nowin` labels.**
  Trigger: `SPUR.MISC.S:454`'s `travel3`/`no.shop` block intercepts an
  attempt to go "Up" (`di=5`) while on level 6 (`cl=6`), linking to the
  win check instead of a normal level transition. In this port that's
  room 117, "Shimmering Portal" (level 6, "A Brave New World") — the
  *only* room in the entire map data with `exits.rc==1` ("Ladder Up"),
  confirmed by scanning every level. `commands/movement.py` special
  -cases `direction=='u' and rc==1 and player_level==6` ahead of the
  generic rc/rt same-level-staircase fallthrough (which would otherwise
  just walk the player to room 117's `rt=1`, i.e. room 1, and do nothing).
  Old assumption from `SPUR.HELP.TXT`'s flavor text ("escape from level
  #1") was checked against `SPUR.CONTROL.S:578` and the actual room
  data and found wrong — room 1 is hardcoded to `rc=2` ("Ladder Down")
  in both the original source and this port.
- ✅ **Three gates**, checked in SPUR's order (`evaluate_victory()`):
  1. King of the Wraiths must be dead
     (`PlayerFlags.WRAITH_KING_ALIVE` false) — applies unconditionally,
     regardless of `victory_type`. Defaults `True` for every new player
     and nothing in this port currently clears it automatically (only
     manual admin/EditPlayer toggling) — the Wraith King boss encounter
     itself isn't implemented, so this gate is a hard blocker today.
  2. Objective item carried, only when `config.victory_type` is `item`
     or `both` — checks `player.inventory` for `config.victory_item_number`.
  3. Silver in hand, only when `victory_type` is `gold` or `both` —
     checks against `config.victory_gold_amount`. SPUR's actual gate here
     was a "riches of Tut" flag (`zu$` position 9), never wired up in
     this port (`player.tuts_treasure_looted` / `flags.py`'s
     `TutTreasure` dataclass are both dead code) — `config.py` deliberately
     generalized this into a plain silver threshold instead, predating
     `victory.py`.
- ✅ **On success** (`declare_victory()`): records the win
  (`winners.py`'s `record_win()` → `run/server/winners.json`), appends a
  `battle.log` entry, and posts a permanent news item ("A Winner!") —
  see "Merchant's Annex" below for the not-yet-built winners-list display.
  On failure: prints SPUR's own in-fiction refusal line and blocks the
  move (player stays put).
- Live-playtested against the running server (`tests/test_victory.py`
  covers all four gate combinations + the movement hook interception).
- **Not done**: no help topic documents this (see `TODO_HELP.md`); the
  Wraith King boss fight that would actually clear gate 1 in the normal
  course of play doesn't exist yet.

---

## Character Progression

### Implemented
- **Level-up** — XP threshold `999 + (xp_level × 100)` triggers level-up message (`SPUR.COMBAT.S:10`)
- **Stat rolling** — race/class bonuses applied at character creation (`characters.py`)
- ✅ **`xp_level` split from `map_level`** — these were conflated in one field (`player.map_level`), used correctly as the dungeon floor (SPUR's `cl`) by the elevator/shoppe but incorrectly reused as character level (SPUR's `xp`/`yn`) by combat level-up, the BHR stat formula, the XP-drain formula, Blue Djinn's hire pricing, and the bank transfer gate. `player.xp_level` is now the single source for character level; old saves migrate their `map_level` value into `xp_level` on load and reset `map_level` to 1 (`player.py`, `combat/engine.py`, `combat/resolution.py`, `commands/stats.py`, `bar/blue_djinn.py`, `shoppe/bank.py`)

### Not Implemented
- **Level-up stat grants** — what increases on level-up (HP, stats) (`SPUR.COMBAT.S lvl.msg`)
- **Time limit** — session clock `ev`; player is forced to quit when time expires (`SPUR.COMBAT.S tim.chk`)

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
- ✅ **Guilds** — three guilds (Claw, Sword, Iron Fist); bank, food locker, item locker, weapon box, chalk board, log (`SPUR.GUILD.S`; `guild_hq/main.py` — `_guild_bank()`, `_food_locker()`, `_item_locker()`, `_chalkboard()`; `guild_hq/state.py` for persistence)
- ✅ **Bar** — ally hiring, drink/food purchase, loans, gambling, hired hits (`SPUR.BAR.S`, `SPUR.BAR2.S`, `SPUR.BAR3.S`) — see **Bar** section below (only PvP brawling remains unimplemented there)
- **Ship / Space level** — space-themed level; confirmed as level 6 ("A Brave New World" per `shoppe/elevator.py`'s `_LEVEL_NAMES`; `level_6.json` has 86 rooms literally named "Outer Space" plus "Engineering"/"Between Dimensions" areas); `SPUR.SHIP.S` handles its specific mechanics (`SPACE SUIT` replaces `BOAT` for `@@`-flagged room traversal at level 6+, per `SPUR.MAIN.S:158` — see the flag-naming note under "Special room traversal requirements" below)
- **Gates** — zone gate travel (`SPUR.GATES.S`)
- **Annex** — visitor area (`SPUR.ANNEX.S`) — see **Annex** section below
- **Shop** — buy/sell items, ammo, shields (`SPUR.SHOP.S`) — see **Merchant Shoppe** section below
- **Bulletin board / news log** (`SPUR.MISC2.S`) — see expanded design in **News & Mail** and **Threaded Message Boards** sections below
- **Pray / Rest** — recover HP or stats out of combat (`SPUR.MISC2.S`)
- ✅ **READ command** — lists/reads book-type inventory items; item #69 "scrap of paper" is special-cased (see **Elevator Combination** section) (`commands/read.py`). **Not yet implemented**: the tips.txt claim that reading "increases your wisdom" — other books currently just print "there's nothing more to learn from it," per `read.py`'s own docstring (`SPUR.MISC3.S`; tips.txt: "READ books to increase your wisdom!")
- ✅ **QUOTE command** — player sets a short quote (60 char max) shown to others who see them in a room; `$` substituted with the *reading* player's name; View/Write/Quit menu (`SPUR.MISC2.S:488-503`; also wired into character creation, `SPUR.LOGON.S:410,618-624`) (`commands/quote.py`, `commands/new_player.py`)
- **LOOT command** — search an unconscious player's inventory; one item per session; Civilians barred from the Shoppe after looting (tips.txt); see also Items section above
- ✅ **The Dwarf** — wandering level-1 NPC; steals silver (or an item once broke) from players via a per-move roll, appears as a fightable encounter in his own room, awards his entire shared hoard to whoever kills him (`encounters/dwarf.py`; `SPUR.LOGON.S`/`SPUR.MAIN.S`/`SPUR.MISC5.S`). Per-player kill immunity and periodic relocation are this port's own additions, not from SPUR (original places him once at world-init and never moves him).
- **Special room traversal requirements** — snow/mountain rooms (`**` flag) require a Great Coat (item #78) or player freezes; water rooms (`@@` flag) require a Boat (levels 1–5) or Space Suit (level 6+); checks in `SPUR.MAIN.S:313–319` and `t_main.lbl`.
  **`@@`/`water` is a reused, misleading flag name on level 6**: SPUR's source
  literally swaps the requirement string at `SPUR.MAIN.S:158,179` --
  `i$="BOAT":if cl=6 i$="SPACE SUIT"` -- so the *same* `@@` room-condition token
  means "needs a Boat" on levels 1–5 and "needs a Spacesuit" on level 6. Confirmed
  against data: all 86 rooms named "Outer Space" in `level_6.json` (black-void
  vacuum descriptions) are flagged `water`/`water_with_rocks`, not some separate
  space-specific flag. There *is* a distinct `outer_space` `RoomFlag` (`=+` token,
  see `convert_from_gbbs_tool.py`), but it lands on unrelated rooms ("Engineering",
  "Between Dimensions") -- it does not mark the vacuum rooms.
  **TODO**: give this a level-aware label wherever it's surfaced to the player or
  used in game logic (e.g. a helper like `room_hazard_label(level, flags)` returning
  "water"/"Boat" below level 6 and "vacuum"/"Spacesuit" at level 6+), rather than
  hardcoding the string `"water"` in messages or comparisons. `commands/mount.py`'s
  MOUNT/auto-dismount water check (`_WATER_FLAGS`) is one place already doing a raw
  `water`/`water_with_rocks` flag check that would misfire (talk about a horse
  "refusing to go in the water") if a mount were ever brought aboard the ship level.
- ✅ **Wraith Master title** — players with `WRAITH_MASTER` flag get ", Wraith Master of Spur!" appended to their name at login (`commands/connect.py:251`)
- **WHO command** — lists currently online players; replaces the SPUR "last adventurer" login display (stubbed in `commands/connect.py:247`)
- **Guild follow** — player character automatically follows guild members to their location when logged off; toggle in settings (stubbed in `commands/connect.py:274`)
- **DIG command** — dig for buried items or gold (`SPUR.MISC7.S` `dig.a`
  onward, not `SPUR.MAIN.S`). SPUR's data model: one `bury.<level>` file per
  dungeon level (1-5 only — DIG refuses on level 6+), one record per room,
  five slots per room (North/South/East/West/Center) each holding what's
  buried there (gold amount or item number — a planted booby trap, see
  `shoppe/ollys.py`, is just an ordinary buried item; its A-I disarm code is
  fixed by which of the 9 "booby trap (code X)" items it is, objects.json
  #152-160, not stored again in the bury record). SPUR itself never records
  *who* buried something — anyone digging the right spot finds it.
  **Planned TADA deviations** (design notes only, nothing built yet — see
  `shoppe/ollys.py`'s `_help_section()` docstring): record the burying
  player per slot; a paid Olly "recall" service listing a player's own
  buried caches (level/room/position/code); possibly let Thieves disarm
  someone else's trap outright on dig-up (not confirmed in SPUR source —
  would be a new class perk, not a restoration).
- **WEAKEN command** — sysop-only stat reduction command (`SPUR.MAIN.S`)
- ✅ **GET command** — pick up items from the room; static room items and session-dropped items both handled (`commands/get.py`)
- ✅ **Fireball pickup burn** — non-Wizards picking up a fireball take 1–4 heat damage; gauntlets (item #68) absorb the hit with 10% chance of destruction (`SPUR.WEAPON.S:30`, `commands/get.py`)
- ✅ **Staff spellcasting hint** — Wizards picking up a staff see a reminder that it enhances spell casting (`SPUR.MISC3.S:47`, `commands/get.py`)
- ✅ **Monsters/players as GET targets** — live monster: "WON'T LET YOU!"; dead monster: hacked into `<name> MEAT` item placed in room; active player: "SKUTTLES OUT OF REACH!"; unconscious player: "WON'T FIT IN YOUR SACK.." (`SPUR.MISC.S get.b/get.plyr`, `commands/get.py`)
- ✅ **Monster meat** — eating `<name> MEAT` restores 2–6 food; monsters with `diseased_attack` flag have 30% chance to infect the eater (`SPUR.MISC3.S:369`, `commands/eat.py`)
- ✅ **Booby-trapped item pickup** — strange weapon (#70) / funny doll (#72): "BOOOMM!!" → INT−5, HP→5; Pandora's Box (#71): smoke → XP capped at 100, CON→5, INT−5, HP→5; Gold Rose (#41): DEX check, fail → −5 HP + poison; Fireplace (#81): "USE only" (can't be picked up); Obelisk (#139): too large (`SPUR.MISC.S get.itm`, `commands/get.py`)
- ✅ **Fireplace USE** — room 103 "East Hall"; `use` or `use fireplace` while in room: restores Strength to 20 and heals +4 HP if both were low; room message shown to bystanders (`SPUR.USE.S:187`, `commands/use.py`)
- ✅ **DROP command** — drop items into the room; water rooms (`@@` flag or keyword match on name/desc) show float/sink messages: metal weapons and heavy items sink and are lost, wooden weapons/food/books/darts/arrows float and remain retrievable; well rooms always lose the item; buoyancy inferred from category+name until a per-item flag exists (`SPUR.MISC.S`, `commands/drop.py`)
- ✅ **GIVE / TAKE** — `give <item> to <ally/player/monster>` transfers item to ally's carried list or co-located player's inventory; giving to a monster yields humorous responses (food eaten, gold kept by greedy types, etc.); `take [<item>] from <ally>` retrieves items ally is holding (`SPUR.MISC.S`, `commands/give.py`, `commands/take.py`)
- ✅ **ORDER command** — deploy up to 3 owned servants as Point Man / Flank Guard / Rear Guard; every owned servant must be placed somewhere (a slot can be left NONE if you own fewer than three), matching SPUR's "You didn't deploy ALL your servants!" retry loop; position persists across save/load (`bar.ally_data.Ally.position`, `party.py` to_json/from_json) (`SPUR.MISC2.S`, `commands/order.py`).
- ✅ **Tactical ambush** (SPUR.MISC4.S "tactical"/"desert") — once per encounter, before the first exchange, an ambush falls on a random ORDER slot (Point 50% / Flank 20% / Rear 30%). Whoever's deployed there shouts a warning and rolls to hold (an ELITE-flagged servant is always immune -- SPUR's literal "!" in the servant's name); failing that roll leaves the *player* caught off guard too (a bonus monster attack on the first swing, SPUR.COMBAT.S:31 "Surprise attack..") and a 1-in-10 chance the servant actually deserts (room-flavor text: ordinary/water/level-6+-vacuum). An empty slot puts the player alone at risk, rolled against Intelligence + character level plus a flat 10%. Skipped for a friendly encounter (same race/alignment affinity as the monster-quote greeting) and for any monster number already in `player.monsters_killed` (this port's equivalent of SPUR's xm$ rolling-kill-history gate) (`combat/engine.py` `CombatSession._check_tactical_ambush()`/`_ally_deserts()`, wired into `_run_loop()`).
- **Ally payment** — allies require weekly payment (gold) to remain loyal; non-payment triggers desertion (`SPUR.MISC2.S`)
- **Allies joining you** — conditions under which free allies in a room may voluntarily join the party (`SPUR.MISC2.S`)
- ✅ **Ally gold finding** — on each room move, any party ally has a 5% chance to find a gold sack (52–250 gp); fires at most once per day via `once_per_day` `'AYF'` tag; suppressed in water rooms (`SPUR.MISC6.S al.find`, `ally_events.py`, `simple_server._move()`)
- ✅ **Ally body building** — giving food/drink to an ally with strength < 11 raises their strength by 1; cursed rations poison the ally instead (strength −1, floor 1) (`SPUR.SUB.S hun.slv`, `commands/give.py _try_body_build()`)
- **Ally desertion / death** — allies may die or leave if unpaid, injured, or mistreated; status reverts to FREE (`SPUR.MISC6.S`)
- **Random events** — location-triggered events: little girl encounter, meteor strike, Enforcer arrival, Galadriel appearance (`SPUR.MISC6.S`)
- ✅ **Turn to stone attack** — a `petrify`-flagged monster (e.g. Medusa) has a
  20% chance per attack to attempt petrification instead of a normal swing, 10% chance to
  succeed once attempted; either way this replaces the normal hit/damage roll entirely for
  that round (`SPUR.COMBAT.S` "medusa" section, `combat/resolution.py` `monster_attacks()`)
- ✅ **Statue memorial file (turned-to-stone death)** — a successful petrification is a
  distinct death flow, not a normal kill: "...ARGG!! YOU ARE TURNED TO STONE!", not a
  player action, an automatic consequence of death. Creates/appends a file named after the
  killing monster (stripping a leading "THE "), one victim name per line — a permanent
  per-monster victim log (`SPUR.MISC6.S:113,123-126`, `combat/engine.py`
  `CombatSession._player_petrified()` / `_record_statue()`)
- ✅ **Statue display (`petrify` monster present)** — `#` in a monster's status string
  means it *can perform* petrification (the `petrify` flag), not that it has been turned to
  stone itself. Wherever a `petrify` monster is present in a room — alive or dead, not
  charmed away — SPUR's `statue` subroutine reads just the *first* name from that monster's
  own memorial file (the same one `_record_statue()` above writes) and shows it as a
  permanent room fixture: "There is a statue of `<victim>` here!", too heavy to pick up
  ("THE STATUE IS MUCH TOO HEAVY!"). Not a separate corpse/room-object system — the same
  monster showing up elsewhere on the map displays the same statue there too, exactly like
  SPUR (`SPUR.MAIN.S:386,532-536`, `SPUR.MISC.S:221,234`, `SPUR.MISC3.S:281,289`,
  `combat/engine.py` `first_statue_victim()`, `commands/get.py`, `commands/look.py`,
  `commands/read.py`, `simple_server.py` `_describe_room()`). LOOK/EXAMINE/READ show a
  plaque naming both the victim and the monster (Ryan's own wording, not a SPUR port — SPUR's
  own examine line was just "It is made of stone, and is kind of ugly.").
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

> **Naming note**: `shoppe/main.py`'s own entry flavor text says the player
> "follows the sloping passageway downward into the merchant's annex" — the
> Shoppe *calls itself* "the merchant's annex" in-fiction, which collides
> with the separate `annex/main.py` module ("The Annex" — bulletin board,
> guild standings, message boards, etc.). These are two distinct rooms/
> modules in SPUR (`SPUR.SHOP.S` vs `SPUR.ANNEX.S`) that happen to share
> very similar names. Worth renaming one of them for clarity eventually
> (e.g. `annex/` -> `bulletin/` or similar) -- not done here.

### Implemented
- ✅ **General Store** — sells rations 1–10 (safe food/drink); duplicate check; silver deduction; pack-full guard
- ✅ **Elevator** — travel between levels 1–5 (`shoppe/elevator.py`)
- ✅ **Player List** — browse online/offline players by wildcard pattern
- ✅ **Private Locker** (`shoppe/locker.py`) — personal item storage, reached
  by typing `LOCKER` at the Shoppe prompt (a free-text command, like
  SPUR.MISC6.S's `if i$="LOCKER" goto locker`, not one of the Shoppe's
  lettered menu options — checked ahead of the normal single-letter menu-key
  truncation so it doesn't collide with `L` = Player List). Ported from
  SPUR.MISC6.S:276-345's `locker`/`put.loc`/`tak.loc`/`look` subroutines
  (which itself returns to the Shoppe via `lnk.shop`, confirming the locker
  belongs here and not in the Annex): P)ut, T)ake, L)ook move items between
  `player.inventory` and a new `player.locker` (both `Inventory` instances),
  with a fixed 10-slot cap on the locker side (`inventory.LOCKER_CAPACITY`,
  matching SPUR's `if zt>9 ... "The locker is full!"`).
  - **Combination lock is a deliberate homebrew addition, not ported from SPUR** —
    the original `locker` subroutine has no access check at all; every player's
    locker record already exists from character creation and is opened directly by
    player number. This port adds a combination-lock layer mirroring the Elevator's
    guard (`shoppe/elevator.py`): a new character has no `CombinationTypes.LOCKER`
    entry (`player.set_up_combinations()` omits it, same as ELEVATOR), so the
    *first* visit is instead met by an attendant who assigns one, hands over a
    **brass claim tag** (objects.json #164) as a keepsake, and opens the locker
    directly that first time. Later visits must enter the combination (5 attempts,
    same shape as the Elevator guard) before P)ut/T)ake/L)ook is available.
  - The claim tag is a distinct item from the Elevator's scrap of paper (handed
    over by an NPC on first visit, not found in a room) so the two
    on-demand-combination mechanics don't get confused with each other, but is
    likewise `READ`-able (`commands/read.py`): it re-displays the player's own
    LOCKER combination, no flavor prompts needed since the combination already
    exists by the time the tag does.
    - **Bug fixed along the way**: `commands/read.py`'s book list only matched
      `ItemType.BOOK` (`item_system.Item`'s field), but items actually placed in
      `player.inventory` via `commands/get.py`/`shoppe/locker.py` are
      `items.Item`, which only sets `.category` (`ItemCategory`), never `.type`
      -- so a genuinely-picked-up scrap of paper was silently invisible to
      `READ` (only test doubles constructing `item_system.Item` directly ever
      exercised the `ItemType.BOOK` branch). Fixed by also special-casing known
      readable ids (`_READABLE_IDS = {69, 164}`) alongside the `ItemType.BOOK`
      check, rather than fixing the deeper two-Item-class split (a bigger,
      separate cleanup).
  - `player.locker` persists through `Player.save()`/`_load()` the same way
    `player.inventory` does (explicit `Inventory.to_json()`/`from_json()`
    round-trip alongside the generic `__dict__` dump).
- ✅ **Armory** — buy and sell weapons; max 6 weapons per player (`SPUR.SHOP.S`; `shoppe/armory.py`)
- ✅ **Protection** — buy armor and shields; max 5 items per player (`SPUR.SHOP.S`; `shoppe/armory.py`'s `protection()`)
- ✅ **Bank of SPUR** — deposit, withdraw, transfer gold; level 2+ required for transfers (`SPUR.SHIP.S bank`; `shoppe/bank.py`)
- ✅ **Wizard** — buy spells; Wizards pay half price, Druids two-thirds; max 10 spells (`SPUR.SHOP.S`; `shoppe/wizard.py`)
- ✅ **Clan / Guild office** — change guild affiliation (Claw, Sword, Iron Fist, Civilian, Outlaw); costs gold and honor (`SPUR.SHOP.S`; `shoppe/clan.py`)
- ✅ **Pawn Shop** — sell (not buy) items to the merchant; all found items are sellable (tips.txt) (`SPUR.SHOP.S`; `shoppe/pawn.py`)
- ✅ **Olly's Ammo** — buy ammo and ammo carriers; booby trap purchase; [H]elp explains ammo system and friendly fire. Reached in the original by typing `AMMO` (`SPUR.MISC5.S:16: if i$="AMMO" goto ammo`, `ammo` subroutine — "Olly greets you, 'Welcome, ...'"), not a separate ammo-count command (`shoppe/ollys.py`)

### Stubs (not yet implemented)
- None currently known — all `_MENU` entries in `shoppe/main.py` route to implemented modules.

---

## Elevator Combination (Scrap of Paper)

✅ Implemented. Mechanic traced from `SPUR.MISC2.S:296-352` (`elev` subroutine, triggered
by `READ`ing item #69) and `SPUR.SHIP.S:375-388` (`elevator`/`elev.1`, the actual
coordinate check at the Shoppe elevator).

- **Item #69 "scrap of paper"** (type `book`) is placed in level 1, room 64
  ("Labyrinth"); no placement/randomization work was needed.
- **Intelligence gate**: SPUR.MISC2.S's `read` subroutine opens with `if pi<6 print
  "Not smart enough to read!":goto advent` -- Intelligence below 6 blocks `READ`
  entirely, before even listing books. Ported as-is.
- **`commands/read.py`** (new) implements `READ`: lists book-type inventory items, or
  reads one by name/number. Item #69 is special-cased: the first read asks the two SPUR
  flavor prompts ("Art thou true of heart?" Y/N, "Good or Evil?" G/E -- answering Evil
  costs 2 honor if honor > 2, no other branching), generates a random `CombinationTypes.
  ELEVATOR` entry, and prints it. Subsequent reads just re-print the same combination
  rather than rerolling.
- **Deviation from source, on purpose**: the scrap of paper is **not** consumed on read
  (SPUR's item disappears after the one-time reveal, making a forgotten combination an
  unrecoverable dead end even in the original). It stays in inventory as a re-readable
  reference.
- **Shape fixed**: `player.combinations` is now a `dict[CombinationTypes, Combination]`
  (was a list), matching `commands/editplayer.py`'s existing usage.
  `player.set_up_combinations()` seeds CASTLE and LOCKER at character creation but
  deliberately omits ELEVATOR -- that key only appears once the scrap has been read, so
  `shoppe/elevator.py`'s guard correctly refuses access to anyone who hasn't found it
  (the old code auto-generated a default combination for everyone, silently defeating the
  guard).
- **Persistence fixed**: `Player._load()` now restores `combinations` from the save file
  (previously not in the restorable-field whitelist, so every login silently regenerated
  a fresh random combination). Restoration accepts both the current dict shape and the
  older list-of-dicts shape already written to disk by existing player saves, so no
  migration script is needed.
- **Known pre-existing issue, not fixed here**: `Inventory.remove()` matches by
  `id_number`, but `item_system.Item` (used for `objects.json` entries, including books)
  never sets that attribute -- so `inv.remove(item)` silently no-ops for these items
  today. This doesn't block the scrap of paper (which is intentionally never removed),
  but it likely also affects `commands/use.py`'s shield/grenade/ring/saddle consumption
  paths. Worth its own followup.

---

## Merchant's Annex (`server/annex/main.py`)

All sections are stubs. Source: `SPUR.ANNEX.S`. See the naming note under
"Merchant Shoppe" above -- this is a *different* room from the Shoppe (whose
own flavor text also calls itself "the merchant's annex"), and the Private
Locker belongs to the Shoppe (`shoppe/locker.py`), not here.

### Stubs (not yet implemented)
- **School info** — character class descriptions and stat bonuses
- **System message** — sysop broadcast message of the day
- **Tips** — in-game tips display (content from `SPUR-data/tips.txt`)
- **School spells** — list of spells available to the player's class
- **Recent news / Older news** — two-tier news log (ties into News & Mail design)
- **Guild standings** — ranking of guilds by kills/XP; SPUR source is
  `SPUR.DUEL2.S`'s `guild` label (~lines 316-336): after any guild-vs-guild
  duel, tallies a win/loss counter per guild to a `guild.standings` data
  file (`vv`/`yz` are the duelists' guild numbers, `zz`/`yw` the running
  win/loss counts, position-addressed by guild slot 1/2/3)
- **Personal records** — player's own stats history
- **Winners list ("Conqueror's list")** — SPUR.MISC7.S's `win5` label
  writes each victor to a `spur.winners` file after escaping via the
  level-6 "Ladder Up" (see "Win/escape detection" below); the persistence
  half exists (`winners.py`'s `record_win()`/`load_winners()`, backing
  `run/server/winners.json`) but nothing in the Annex displays it yet --
  a natural fit for this stub, listing name/class/race/level/date per winner.
- **System data view** — server-level statistics (total players, kills, etc.)
- **Message boards (×3)** — three separate threaded boards (ties into Threaded Message Boards design)
- **Player rosters** — separate lists for Civilians, Mark of the Claw, Mark of the Sword, Iron Fist, and Outlaws

---

## Bar (`server/bar/main.py`)

### Implemented
- ✅ **Fat Olaf** — slave/servant trader; buy allies; sell servant stub present (`bar/fat_olaf.py`)
- ✅ **Food/drink menu** — `food_menu()` helper exists; rations list rendered
- ✅ **Mundo escorts a debtor straight to Vinny** — `SPUR.BAR.S:16-18`:
  "Mundo checks your books.." / `if (g7>0) or (g8>0) ... "He 'escorts' you
  over to Vinney!" ... goto mundo.ck` (jumps straight to Vinny's tile and
  links into `spur.bar3` — no return to the normal move loop). Ported as:
  on every `enter_bar()` call, if `player.loan_amount > 0`, print the same
  two lines, place the player on Vinny's tile, and go straight into the
  Vinny interaction — skipping the help text and the normal movement loop
  entirely for that entry. Repeats on every subsequent entry until the loan
  is paid off (`bar/main.py` `enter_bar()`).
- ✅ **Bouncer** — Mundo throws the player out (with HP damage if it's a
  rough exit) (`bar/main.py` `_bouncer()`)
- ✅ **Vinny** — loan shark; apply for loans, pay back, store/withdraw gold
  in the bar (`SPUR.BAR.S`, `SPUR.BAR3.S`; `bar/vinny.py` — `_apply_loan()`,
  `_pay_loan()`, `_store_money()`, `_get_money()`)
- ✅ **Skip** — food/drink vendor (`SPUR.BAR2.S`; `bar/skip.py`)
- ✅ **Bar None** — Guss the barkeep; coin flips, blackjack (`SPUR.BAR2.S`; `bar/bar_none.py`)
- ✅ **Zelda** — reanimates monsters for players; studies and displays player stats (`SPUR.BAR.S`; `bar/zelda.py`)
- ✅ **Blue Djinn** — hire another player attacked; contract persisted to
  `hit_contracts.json` (`SPUR.BAR.S`; `bar/blue_djinn.py` `_hire()`,
  `add_contract()`/`pending_contracts()`). Hiring sets `PlayerFlags.THUG_ATTACK`
  on the target via `set_thug_flag_on_target()` — works whether the target is
  online (mutates their live `Player` directly) or offline (loads/edits/saves
  their save file). **Resolution** (`bar/thug_attack.py`
  `maybe_trigger_thug_attack()`, called from `simple_server.py`'s
  `_game_loop()` right before the room is shown): if the flag is set *or*
  there's a pending contract, a THUG (monster #60) ambushes the player via
  `combat.enter_combat()`, naming whichever hire's `attacker_display` is
  first pending; the flag is cleared and every pending contract against that
  player resolved (`resolve_all_pending_contracts()`) once the fight is
  over, win or lose. Either signal alone is enough to trigger — a mismatch
  (flag set with no contract record, or a contract with no flag, e.g. one
  placed by an older build before `set_thug_flag_on_target()` existed) logs
  a warning but still ambushes rather than leaving a contract unresolved
  forever or a flag stuck on. A player with `PlayerFlags.DEBUG_MODE` set
  gets an explicit Y/N to skip the ambush for testing — skipping leaves the
  flag/contracts pending so it can be retried on a later login.
  Also fixed while wiring this up: three spots in `blue_djinn.py` read
  `client.player` instead of `client.ctx.player` (`simple_server.py` sets
  `client.ctx = ctx` on connect; `Client` has no bare `.player` at all), so
  online-target detection for both hire pricing and the "* = online" matched
  -player list silently never worked — same bug class as
  `commands/messaging.py`'s `online_player_names()`, which already had it
  right.

### Stubs (not yet implemented)
- **Bar brawl / PvP** — fighting other players in the bar; stub message "combat not yet available" (`bar/main.py:280`)

### Street NPCs (not part of `bar/main.py`'s room grid)

Unlike the NPCs above, these two are reached via a hardcoded level/room/direction
interception in `commands/movement.py` — mirroring how SPUR itself hooks them into
`SPUR.MAIN.S`'s dispatch (`if cl=<level> if cr=<room> if di=3 ...`) rather than as a
normal data-driven room exit. Both target rooms have no east exit in their room data
for exactly this reason.

- ✅ **Allies' Guild** (Bubba, level 4 / room 42 "A Maze Of Alleys" / east) — pay gold to
  train an owned ally: Armor (600g → `AllyFlags.ARMORED`), Discipline (1,000g →
  `AllyFlags.ELITE`), Body building (incremental, level 1–8, +3 STR per level, cost scales
  with level), Combat training (800g → `AllyFlags.COMBAT_TRAINED`), Tracking (750g →
  `AllyFlags.TRACKING`, refused for MOUNT allies) (`SPUR.MISC8.S` `s.guild`, skip branch,
  `street/allies_guild.py`)
- ✅ **Jake's Stable** (level 5 / room 157 "The Ocean" / east) — buy Oats/Sugar Cube
  (rations.json), Lasso/Saddle/Horse Armor (objects.json, ×100 gold); Train Horse
  (2,000 gold, requires a MOUNT ally that is already SADDLED + ARMORED, applies
  `AllyFlags.ELITE`); Tips (`SPUR.MISC8.S` `jakes`, skip branch, `street/jakes.py`).
  Room 157's description hints at the stable before the player tries the hardcoded
  east interception — "You can see a faint trail sloping down to the east, where a
  horse paddock can be seen." (`level_5.json`, a TADA addition, not from SPUR).

---

## News & Mail

### News / Bulletin Board

#### Implemented
- ✅ **Startup display** — `commands/connect.py`'s `_login_news_lines()` shows applicable news
  items automatically at login, before the game loop starts.
- ✅ **`news` command** (`commands/news.py`) — `news` lists currently-active items, `news <id>`
  reads one in full, `news post` / `news edit <id>` / `news delete <id>` are admin-only.
- ✅ **Display lifetime** — each post (`news.py`) carries one of three lifetime modes:
  - *once* — shown once per player, then silently suppressed (tracked via `seen_by`).
  - *permanent* — always shown until manually deleted.
  - *range* — active only between `start_date` and `end_date`; invisible outside that window.
- ✅ **Storage** — posts stored as JSON (`run/server/news.json`); each record: `id`, `title`,
  `body`, `author`, `posted_at`, `lifetime` (`once` / `permanent` / `range`), optional
  `start_date` / `end_date`, and a `seen_by` list of player names.
- ✅ **Per-player display preference** — `command_settings.news_show_all` (PREFS key `N`)
  chooses between a full directory every login vs. just what's new since
  `player.last_connection`.

#### Future
- **Post editing via a real line editor** — admin authoring in `commands/news.py` currently uses
  a plain `END`-terminated multi-line prompt (same convention as `threaded_messages.py`'s
  `create_new_thread()`), not `text_editor.py` (the shared line-editor prototyped on the
  not-yet-merged `text_editor` branch). Swap it in once that branch lands.

### Mail / Paging

#### Implemented
- ✅ **`page` command** (`commands/page.py`) — sends an instant message to one or more online
  players (appears in their session immediately, same as `shout`), crossing rooms; supports
  comma/space-delimited target lists and `#groupname` (shared with `whisper`,
  `commands/groups.py`).
- ✅ **Combat courtesy queueing** — a page to a player who's an active combat participant
  (`commands.messaging.is_in_combat()`, checked against `server.active_combats[room].attackers`
  — a room *bystander* to someone else's fight still gets pages normally) isn't delivered
  immediately. Instead the sender gets a short "you sense you have a page waiting for you"
  notice, and the full message is queued on `player.pending_pages`; `network_context.py`'s
  `prompt()` (both `GameContext` and `PETSCIINetworkContext`) flushes it as `[PAGE] ...` lines
  the next time that player is prompted, so it surfaces after the fight's current prompt instead
  of interrupting a round mid-exchange.
- ✅ **`#ignore` / `#unignore`** — `page #ignore <name>` blocks a specific player from paging you
  (`command_settings.ignored_pagers`); their own page attempt is silently dropped and they're told
  "`<you>` is ignoring your pages." `page #unignore <name>` reverses it.
- ✅ **`#haven` / `#unhaven`** — `page #haven` blocks *all* incoming pages
  (`command_settings.haven`); senders are told you're "not accepting pages right now."
  `page #unhaven` reverses it. `#ignore`/`#unignore`/`#haven`/`#unhaven` are reserved words, so a
  saved group can't use those names.
- ✅ **Offline fallback** — if a target isn't online, `page` offers to leave the message as mail
  (declines silently if the player doesn't exist at all). Accepting appends a record to
  `run/server/mail/<name>.json` in the schema below.
- ✅ **Storage** — mailboxes stored per-player (`run/server/mail/<name>.json`); each message:
  `from`, `timestamp`, `body`, `read` flag (no `subject` yet — pages are one-liners).

#### Future
- **Mail inbox** — unread mail is shown at login (similar to news display); a `mail` command lets
  players read, reply to, and delete messages mid-session. Nothing reads `run/server/mail/*.json`
  yet — `page`'s offline fallback writes to it, but there's no way to read it back in-game.

---

## Horses

Source references: `text-listings/t_mount.lbl`, `t_charge.lbl`, `t_main.lbl`, `t_stat.lbl`,
`t_startup.lbl`, `t_ma_blacksmith.lbl`.

### Overview
A horse occupies **ally slot 4** (`a$(4)`).  The string `"---"` in that slot means no horse.
At login, if the player has a horse, it is announced: *"Your faithful steed `<name>` is here."*
`[MOUNTED]` is shown in the player status line when the mounted bit is set.

### Implemented

These pieces come from a different source generation than the `t_mount.lbl`/`t_charge.lbl`
listings above — the skip branch's `SPUR.USE.S` (`lasso`/`eq.horse`) and `SPUR.MISC8.S`
(`jakes`), where a mount is a regular party-slot ally flagged `MOUNT` rather than a
dedicated "ally slot 4". `MOUNT`/`DISMOUNT` (Phase 1 below) follow this same
party-slot-ally model; `CHARGE` is still unimplemented either way.

#### Acquiring a horse
- ✅ **LASSO capture** — during combat against a horse-named monster (e.g. `WILD HORSE`,
  added to `monsters.json` as a TADA extension — no canonical stats existed in the
  SPUR-data dumps), `lasso` captures it as a new `MOUNT`-flagged ally; player names it
  (4–12 chars, SPUR's own forbidden-character list); blocked by a full party or an
  existing mount (`SPUR.USE.S` `lasso`, `commands/lasso.py`, `engine.py`
  `CombatSession.lasso()`)
- ✅ **Jake's Stable** — level 5, room 157 ("The Ocean"), reached by moving east (same
  hardcoded level/room/direction interception as the Allies' Guild — see the **Bar**
  section below); sells Oats/Sugar Cube/Lasso/Saddle/Horse Armor and offers Train Horse
  (`SPUR.MISC8.S` `jakes`, `street/jakes.py`)

#### MOUNT / DISMOUNT — Phase 1 of 3 ✅
Implemented against the block-diagram plan traced from the skip branch's `SPUR.USE.S`/
`SPUR.MISC8.S` party-slot-ally model, not the `t_mount.lbl` bit-flag design above.
- ✅ **State tracking**: `PlayerFlags.MOUNTED` (already existed in `flags.py`, already
  wired into `commands/editplayer.py` and generic save/load via
  `flags.serialize_flags_for_save()`) — no new `Player` field needed.
- ✅ **`MOUNT`** (`commands/mount.py`) — refuses without a MOUNT-flagged ally
  (`bar.allies.find_mount()`), refuses if already mounted, refuses in a water room
  (`SPUR.COMBAT.S:74` — water needs a Boat, not a horse). Sets the flag and prints
  "You climb onto `<name>`."
- ✅ **Pixie exclusion** (design addition, not from SPUR source) — Pixies are too small to
  mount a horse; `MOUNT` refuses with "You're far too small to mount a horse!"
- ✅ **`DISMOUNT`** (`commands/dismount.py`) — unconditional while mounted; no-ops with a
  message otherwise.
- ✅ **Auto-dismount** (`commands/movement.py` `_auto_dismount_if_needed()`, called after
  every successful move) — clears the flag if the mount ally is gone from the party, or
  DEAD/UNCONSCIOUS but still in it (a combat loss leaves the corpse in `player.party` —
  see `combat/engine.py`), or if the destination room is flagged `water`/
  `water_with_rocks`.
- ⏸️ **Not implemented — half move-time while mounted**: the plan called for halving
  travel time on horseback, but this server has no move-time/tick system to halve
  (`player.moves_today` exists as a field but is never incremented anywhere; there's no
  session-elapsed-time tracking at all). Revisit if/when a real time budget exists;
  faking one just for this would be backwards.
- ⏸️ **Not implemented — mounting difficulty/saddle/strength checks**: the `t_mount.lbl`
  TODOs (character size, saddle requirement, strength vs. armor weight) weren't carried
  over; `MOUNT` only checks for a live MOUNT ally, water, and double-mounting.

#### CHARGE (`t_charge.lbl` design — NOT what was implemented; kept for reference)
- Requires horse in slot 4; fails with "You don't have a horse."
- Requires a live monster present; fails with a sarcastic message if nothing to charge toward.
- Water room: special joke message ("Clopping two coconut halves...").
- Horse strength gate: `peek(v1+119) < 5` → "Your horse is too weak to charge."
- Class attack bonuses: Fighter/Thief/Archer (cl 1/6/7): −25; Paladin (cl 3): +25; Assassin
  (cl 8): +35.
- Roll determines hit/miss; damage = `rnd(roll/4)`.
- TODOs in source: consider monster size (missing over its head); Knight lance bonus; player or
  horse taking return-attack damage; being unseated without a saddle on a heavy blow.

#### CHARGE — Phase 2 of 3 ✅
Implemented from the skip branch's `SPUR.COMBAT.S` (`m.attack`/`p.attack`), which has a
CHARGE mechanic entirely distinct from the `t_charge.lbl` design above (no water-room
joke, no horse-strength gate, no per-class attack bonus table) — the master branch's
`SPUR.COMBAT.S` has no CHARGE at all.
- ✅ **Eligibility roll** (`combat/engine.py` `_roll_charge_first_strike()`) — only checked
  on the first exchange (`monster_attack_count == 0`) while `PlayerFlags.MOUNTED`: d10
  roll, −4 for a projectile weapon or +4 otherwise, eligible if
  `roll + (monster_agility × 4) < player Dexterity`. Printed before the prompt each round
  ("MOUNTED- YOU MANAGE TO GET FIRST STRIKE! (CHARGE if you want)" / "...OOPS, DIDN'T GET
  FIRST STRIKE.."), and offered as `[C]harge` in the attack prompt when eligible.
  Independent of whether the player then picks CHARGE or a plain attack, achieving first
  strike skips the monster's retaliation this round (same effect as the existing
  missile/pole first-strike checks).
- ✅ **CHARGE bonus** (`combat/resolution.py` `player_attacks(is_charge=True)`) — +2 to the
  hit threshold and ×2 final damage (both the "ease of use" fast path and the normal hit
  roll), plus "YOU THUNDER DOWN UPON `<monster>`!" narration.
- ⏸️ **Known gap in `_WA` weapon-class lookup**: `combat/resolution.py`'s `_WA` dict keys
  (`'poke_jab'`, `'pole_range'`, `'hack_slash_bash'`) don't match the real
  `WeaponClass.value` strings (`'poke/jab'`, `'pole/range'`, `'bash/slash'` — punctuation
  differs), so `hit_threshold()` silently falls back to the hack/slash/bash formula for
  Poke/Jab and Pole/Range weapons instead of their own size-dependent formulas. Discovered
  while building CHARGE's projectile-vs-melee check (which is unaffected, since
  `'projectile'`/`'energy'`/`'proximity'` have no punctuation and match correctly) — a
  separate, pre-existing bug, not fixed here.

#### Mounted combat flavor & unseating — Phase 3 of 3 ✅
- ✅ **Miss over the top** (`combat/resolution.py` `player_attacks()`) — mounted with a
  melee weapon (hack/slash/bash, poke/jab, pole/range) can whiff clean over a small/agile
  monster: d10 roll vs. monster agility, independent of the normal hit roll. Doesn't apply
  to projectile/energy/proximity weapons or when not mounted.
- ✅ **Mount redirects a hit** (`combat/engine.py` `CombatSession._try_redirect_to_mount()`)
  — a monster's attack that would hit the player can instead strike the mount ally: d10
  roll vs. monster agility. **Narrative-only**: this port doesn't yet track meaningful
  mount HP (a freshly-lassoed mount's `hit_points` is seeded to 0 — see
  `CombatSession.lasso` — and Horse Constitution/HP display is still unported, see "Horse
  stats & equipment" below), so a successful redirect just means the player takes no
  damage from that hit rather than applying damage to the mount.
- ✅ **Unseat check** (`combat/engine.py` `CombatSession._charge_unseat_check()`) — risk of
  being thrown from the saddle after a CHARGE, win or lose (triggers whenever CHARGE was
  used this round, not on every hit). Formula: `d100 + HP + STR + CON + INT + EGY + DEX +
  (level × 3)`, +35 Knight / +25 Paladin / +25 Elf / −25 Ogre-Dwarf-Orc; score > 160 keeps
  the seat. Otherwise a Saddle gives one more (~40%) save roll; failing both throws the
  player, clears `PlayerFlags.MOUNTED`, and deals 2-11 fall damage (can kill).

#### Horse stats & equipment
- **Constitution & HP** — displayed on the stat screen alongside armor; "looks sick" / "looks
  weak" messages when low (same health-check loop as allies).
- **Armor** — horse has an armor rating; displayed in stat screen; no shield slot.
- **Race** — horse has a race (bits 6–0 of `v2+189`); cross-breeding possible by setting multiple
  bits (noted in source: "Thanks for the idea, DracoSilv").
- **Saddlebags** — bit 7 of `v2+189`; without saddlebags the horse carries no gold and no items;
  with saddlebags it can carry things (extra inventory).  Gold display routines explicitly check
  for this flag before showing horse gold.
- ✅ **Saddle / Horse Armor** — bought at Jake's Stable, then `USE`d on a mount ally to
  equip it (`AllyFlags.SADDLED` / `AllyFlags.ARMORED` — the latter shared with the
  Allies' Guild's Armor training, same "$" sigil in SPUR either way); refuses without a
  mount or on a duplicate (`SPUR.USE.S` `eq.horse`, `commands/use.py`)
- ✅ **Train Horse** — 2,000 gold at Jake's Stable; requires the mount already be
  `SADDLED` and `ARMORED`; applies `AllyFlags.ELITE` (`SPUR.MISC8.S` `train`,
  `street/jakes.py` `_train_horse()`)
- **Horseshoes** — listed as a TODO service at the Blacksmith (`t_ma_blacksmith.lbl:
  "todo: shoe horse"`); effect on speed or armor TBD.
- **Food** — horses presumably need feeding (appropriate food items TBD; ties into the
  food/ration system).

### Future
- Fix the `_WA` weapon-class string mismatch in `combat/resolution.py` (see CHARGE
  Phase 2 above) so Poke/Jab and Pole/Range weapons get their own hit-threshold formulas
  instead of silently falling back to hack/slash/bash's.
- Seed real mount Constitution/HP so "mount redirects a hit" can apply actual damage
  instead of being narrative-only.
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

#### `#version` / `#ver` — any command, Admin/Dungeon Master only
A command accepts a bare `#version`/`#ver` switch anywhere in its arguments
(e.g. `attack #version`) that reports when that command's own source file was
last changed, instead of actually running it — but only for a viewer with
`PlayerFlags.ADMIN` or `DUNGEON_MASTER` set (`command_processor._is_admin_or_dm()`).
For anyone else the switch is left alone and the command runs normally, same
as any other unrecognized `#`-token. Handled centrally in
`commands/command_processor.py`'s `process_command()` — right after the
command is resolved and mode-gated, before `execute()` is called — so no
individual command needs to implement it. `command_version.py`'s
`get_command_version()` resolves the date via one lazy `git log -1 --format=
%ad --date=short` call per command file (cached for the process's lifetime,
so each command is looked up via git at most once per run); falls back to the
file's own mtime, clearly labeled, if git isn't available (e.g. a production
deploy shipped without a `.git` directory) or the file isn't tracked yet.
Mentioned in `help commandline`'s concept topic, but only for privileged
viewers — see `Help.admin_notes` below.

#### `Help.admin_notes` — admin/DM-gated help text
`Help` (`commands/help.py`) has a second notes list, `admin_notes`, rendered
in the same "Notes:" section as `notes` but only when the viewer has
`PlayerFlags.ADMIN` or `DUNGEON_MASTER` set (`_is_privileged_viewer(ctx)`,
checked by both `_show_command_help()` and `_show_topic_help()` before
calling `format_help(..., is_privileged=...)`). Use it for admin-only
details that would just be noise (or an unwanted hint) for a regular
player — e.g. the `commandline` concept topic's mention of `#version`/`#ver`
above.

#### Player management
- **`editplayer` (`ep`)** — full in-game player editor: alignment, attributes,
  character names, combinations, flags/counters, hit points, inventory, money
  (In Hand / In Bank / In Bar), statistics, weapons (`commands/editplayer.py`).
  Changes are written on save/quit. Editing class or race warns (non-blocking)
  if the combination isn't normally valid, and always re-reports natural
  alignment — which depends only on race, per `SPUR.MISC5.S:196–199` (Ogre/Orc
  → Evil, Pixie/Elf → Good, else Neutral) — as "updated to X" or "unchanged
  (X)" (`characters.is_class_race_compatible()`,
  `characters.apply_natural_alignment()`; same table backs character
  creation's class/race validation in `commands/new_player.py`).
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

#### Development / ops
- ✅ **`reload <module> [module...]`** — hot-reload command/support modules
  without restarting the server. `CommandProcessor.discover()` re-imports via
  `importlib.import_module()`, which returns Python's cached module object
  unchanged even after the `.py` file on disk has changed — a new connection
  doesn't help either, same reason. This forces `importlib.reload()` on the
  named module(s), then calls `CommandProcessor.clear()` + `discover()` on
  every connected client's *existing* `CommandProcessor` object so the change
  takes effect immediately, no reconnect/restart needed. Mutating in place
  (rather than assigning a fresh `CommandProcessor` to `client.command_
  processor`) is required: `simple_server.py`'s per-connection game/login loop
  reads that attribute into a local variable once, at loop start, and keeps
  using that same reference for the connection's lifetime — reassigning the
  attribute is invisible to an already-running session, confirmed by testing
  against the actual live server. A bare name like `movement` expands to
  `commands.movement`; dotted names (e.g. `base_classes`) are used as-is.
  Caveat: only the named module(s) are re-executed — if a command module
  imports something else that also changed, name that too (`reload movement
  base_classes`) or the stale version stays in effect. Admin only
  (`commands/reload.py`).
- ✅ **`reload #list`** — lists every module under `commands/` (loaded vs. not
  yet imported) plus other first-party project modules currently loaded
  (stdlib/venv packages excluded) — a quick reference for what's a valid
  `reload` target.

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
- ✅ **Fix: age/birthday can disagree** — `editplayer`'s Age and Birthday fields
  (`commands/editplayer.py`) and character creation's age and birthday prompts
  (`commands/new_player.py`) used to set `player.age`/`player.birthday`
  independently, letting a birth year silently contradict the stated age.
  Birth year is now always derived as `current_year - age`
  (`characters.birthday_for_age()`), so only month/day is ever prompted;
  `editplayer`'s Age editor also recomputes an already-set birthday's year
  when age changes, keeping the two in sync. Along the way, fixed a real bug
  in `commands/new_player.py`'s age prompt: `elif ans > 50` compared the raw
  input string to an int, raising `TypeError` for every age entered as a
  digit — was `elif age > 50`.

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
