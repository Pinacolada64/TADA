# The Land of Spur — General Usage Variable Listing

Cross-reference for every scratch/global variable in `SPUR-code/*.S`. Classic
1980s BASIC: short 1-2-letter (+digit, +`$`) names get reused for unrelated
purposes across different subroutines, so the same variable can mean two (or
three) different things depending which label you're reading. **Check here
before assuming what a variable means from local context alone** — and when
porting work resolves a previously-uncertain entry, or turns up a variable
this file doesn't cover yet, add the finding back in, alphabetically, in this
same style, so the reference stays authoritative.

- Updated 2/Feb/2014 21:51 (Seahawks win Superbowl!)
- Updated 7/Mar/2016 16:03 — some corrections made
- Updated 2/Jul/2026 — ally name-string flag sigils, monster flag sigils
  (`wy$`), `b1`/`xu$` additions, and `*MNT` confirmed for `ys$`, all found
  while porting allies/mounts to the Python server. See `SPUR.MISC7.S`,
  `SPUR.MAIN.S`, `SPUR.COMBAT.S`, `SPUR.USE.S`, `SPUR.MISC2.S` (skip branch).
- Updated 31/Jul/2026 — converted from `spur variables.txt` to Markdown;
  resolved essentially every previously-"?"/"scratch variable" entry and
  added ~90 undocumented variables, via two full grep sweeps of every
  `.S` file (plus a `mac2unix` pass needed to read `SPUR.SYSOP.S` at
  all — see "Notes on working with the SPUR source" below). See the individual
  entries below for source citations.

---

## A

- **`a`** — Time limit: initially 180. If caller's bps rate=300: 300.
- **`a1`** — Point man (ally 1)
- **`a2`** — Flank guard (ally 2)
- **`a3`** — Rear guard (ally 3)
- **`a1$`** — GBBS-Pro host global (caller's BBS handle), never assigned by
  SPUR itself — inherited across `LINK` from `main.seg`. Read-only: printed
  into the winners list (`SPUR.MISC7.S:28` `win5`,
  `"***[ "+a1$+"/"+n1$+" ]***"`) and paired with `un`/`n1$` in
  security/news-log lines (`SPUR.LOGON.S:496/497/560`). Careful:
  `spur.a1$` also appears as a **data file name** (bank gold/Vinny-debt/
  duel-record storage, keyed by `un` — `SPUR.MISC6.S:115`,
  `SPUR.DUEL2.S:357/363`) — that's a filename, not this variable, and is
  almost certainly what confused the original "can't find `a1$=`..." note
  (there genuinely is no assignment; it's host-supplied).
- **`a2$`** — Unused — does not appear anywhere in `SPUR-code/*.S` at all.
- **`a3$`** — GBBS-Pro host global (caller's real name?), same
  read-only/inherited nature as `a1$` above. Used in `SPUR.LOGON.S`'s
  news/security-log lines alongside `n1$` and `un` (e.g. `:560`
  `a3$+"/"+mid$(n1$,2)+": "+str$(ex/60)+" min."`).
- **`ac`** — Ally count (# in game)
- **`ai`** — # of ally inventory items
- **`ai$`** — Ally inventory in `xxx,yyy,[...]` format (xxx/yyy=object #)
- **`ar`** — main char ARmor percentage
- **`au`** — "Already found" / abort-scan flag while walking `spur.users`
  looking for an opponent (`SPUR.DUEL2.S:82`, `SPUR.MISC5.S:63`: `au=0`
  before the scan). `SPUR.MISC6.S:246` sets it fake-found (`au=0`, with
  the rest of the record synthesized) to build the Enforcer as if he'd
  been located normally.

## B

- **`b`** — Damage points for the current blow, player's or ally's
  (`SPUR.COMBAT.S:114-182` — base by race/class, then modified by weapon
  skill/damage, surprise bonus, ammo, LURK penalty, critical hits,
  EXCALIBUR, etc; reused at `:168-182` for an ally's swing). Also
  overlaid as: a file record-length constant passed to `reset` in
  `SPUR.CONTROL.S`'s data-file initializer (`:81-96`, e.g. `b=34` for
  weapons, `b=30` items, `b=26` rations, `b=40` spells, `b=26` allies,
  `b=32` monsters); and the spell-power divisor in `SPUR.MISC3.S:45`
  (`c2=c2/b`).
- **`b1`** — `SPUR.COMBAT.S` `m.attack`: mounted first-strike/CHARGE state
  for the current exchange (local to combat, likely reused elsewhere in
  the usual single/double-letter-variable way):
  - `0`: not mounted, or lost the first-strike roll
  - `1`: mounted, won the first-strike roll — CHARGE is allowed
  - `2`: mounted, first-strike roll not yet resolved this exchange
- **`bd`** — Bottom BBS screen mask display
- **`bh` / `bl`** — Banked gold, high/low (the exact analogue of `gh`/`gl`).
  `SPUR.MISC3.S:99` (deposit) `bh=bh+gh:bl=bl+gl:gh=0:gl=0`; `:102`
  (withdraw) `gh=gh+bh:gl=gl+bl:bh=0:bl=0`; `:105` carry `bl=>10000` into
  `bh`. `SPUR.SHOP.S:449/455-456` and `SPUR.SHIP.S:282-290` also
  deposit/withdraw. Persisted alongside the other core stats:
  `SPUR.LOGON.S:272` `input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp`.

## C

- **`c1$` / `c2`** — Decoded spell type and power, split out of the spell
  record's `q2$` field: `SPUR.MISC3.S:45` `c1$=left$(q2$,1):
  c2=val(right$(q2$,1)):c2=c2/b`. `c1$` dispatch table (`:48-55`):
  `S`=strength, `W`=wisdom, `D`=dexterity, `C`=constitution, `E`=energy,
  `I`=intelligence, `T`=transfer, `P`=player (heal). `c2` is boosted on a
  successful cast (`:127-128` `c2=c2+2+xp`, `+4` more with a `STAFF`
  readied) and feeds the aura's duration in moves (`:187`).
- **`cb$`** — Flag for something (`*`=non-existent object)
- **`cd`** — opponent's dexterity
- **`ce`** — opponent's energy
- **`cg`** — # of rations in game
- **`ch`** — Multi-purpose status flag for `ply.locD`, with an authoritative
  comment at `SPUR.MISC3.S:526-528`:
  ```
  ch=0 is call from LOOT. Return ch=1 if players present.
  ch=2 is call from Examine
     zt$="*" is examine ALL, zt$=NAME is examine NAME. Return ch=4 if success.
  ```
  Also overlaid as the duel win/lose flag: `SPUR.DUEL.S:251`
  `if h<=0 then ch=1:goto hell` (you won) vs `:255/:302`
  `if hp<=0 then ch=0:goto hell2` (you lost), read at `SPUR.DUEL2.S:310`
  to pick the news-log wording.
- **`ci`** — opponent's intelligence
- **`cl`** — current level on map
- **`cp`** — Compass in use (0/1). `SPUR.USE.S:48` `cp=not cp` toggles it;
  `SPUR.MAIN.S:323` gates the `[Reading COMPASS...]` room-description
  hint (level < 6 only); `SPUR.MAIN.S:162` combines with Ranger class
  (`pc=5`) for a bonus; `SPUR.COMBAT.S:320` has a small per-round chance
  of `COMPASS DAMAGED!` (`cp=0`) mid-fight. Cleared on death
  (`SPUR.MISC6.S:40`).
- **`cr`** — current room on map
- **`cs`** — opponent's strength
- **`cs$`** — Alignment-reaction parenthetical shown when a monster
  balks. `SPUR.MISC4.S:114/121` `cs$="(WHO IS AGAST AT YOUR GOODLY
  WAYS)"` / `"(WHO IS AGAST AT YOUR EVIL WAYS)"`, both paths also
  `ms=ms+(xp*5)`.
- **`ct`** — opponent's constitution
- **`cw`** — opponent's wisdom
- **`cw$`** — Opponent's readied weapon name (duel). `SPUR.DUEL.S:181`
  `if w2>w4 then w3=w1:w4=w2:cw$=w$`; `SPUR.DUEL2.S:153`
  `cw$=mid$(cw$,4)`; `:303` defaults to `"SOME WEAPON"` if blank; `:220`
  `if xx$="THE ENFORCER" then if cw$="SUN-SWORD" yb=1000`. Printed
  constantly (`xx$" STRIKES WITH THE "cw$"!"`).

## D

- **`d1$` / `d2$` / `d3$`** — Name of ally 1/2/3 — but really "name + flag
  sigils", format is `<name>|<sigils>`, e.g. `"STARDUST|=@$!"`. The `|`
  only appears once a sigil has been added; `cln.ally` strips everything
  from `|` onward before display. Sigils seen so far (same sigil means
  the same thing whether the ally was bought from Fat Olaf, trained at
  the Allys Guild, or lassoed/equipped at Jake's Stable):

  | Sigil | Meaning |
  |---|---|
  | `=` | MOUNT (only settable via LASSO) |
  | `@` | SADDLED (Jake's Stable: USE Saddle on a mount) |
  | `$` | ARMORED (Jake's Stable Horse Armor, or Allys Guild Armor training — same sigil either way) |
  | `!` | ELITE / Discipline trained (Allys Guild), or "trained mount" (Jake's Stable Train Horse — same sigil, same underlying flag) |
  | `&` | TRACKING trained (Allys Guild; refused for MOUNT) |
  | `%` | COMBAT trained (Allys Guild) |
  | `#N` | Body Build level 1-8 (Allys Guild; N is a digit; `cln.ally` reads N and multiplies by 3 — matches the Allys Guild's "+3 STR per level" wording) |
  | `(` | GOOD alignment |
  | `)` | EVIL alignment |
  | `>xx` | GOD (xx = message # from the MESSAGES file, printed when the ally is first found; also flags that the party may not hold two gods/goddesses at once — `SPUR.MISC2.S:no.fem`) |
  | `+xx` | GODDESS (same xx meaning as `>xx` above) |

  (from `programming-notes/file-formats.txt`'s ALLIES section, which has
  the full example `"PERSEPHONE|#3 >42 ( +"` and the `cln.ally` listing
  verbatim)
- **`d` / `d$` / `f` / `rl` / `dp$`** — The generic record-reader interface
  (`rd.file`). Callers set the file and record, e.g. `SPUR.MAIN.S:245`
  `dy$=dw$+"items":rl=30:d=i:gosub rd.file`; `:252`
  `dy$=dx$+"weapons":rl=34:d=wp:gosub rd.file:wp$=mid$(d$,2):wp=d:
  wt$=dp$:wv=f`. Returns: `d$` = name, `d` = record #, `f` = value,
  `dp$` = type letter (`SPUR.MAIN.S:275` `dp$=left$(d$,1):
  d$=mid$(d$,3):f=f mod 10`), and `if cb$<>"1" then d$="":d=0:f=0` for
  "not present".
- **`da$`** — Name of the weapon that's about to punish you, built right
  before a STORM-weapon rejection/rage message. `SPUR.WEAPON.S:26`
  `"THE "wr$" HOWLS IN RAGE!" … da$="THE "+wr$`; `:160` (an ignored
  STORM weapon), `:176` defaults to `"MYSTERIOUS WEAPON"`.
- **`dc$`** — Last command
- **`df`** — Dwarf room (0=dead)
- **`dh` / `dl`** — Dwarf gold, high/low amount (`dh*10,000+dl`)
- **`di`** — Direction chosen (N=1, S=2, E=3, W=4, U=5, D=6)
- **`dp`** — "Died in a duel" hand-off flag. `SPUR.DUEL2.S:353`
  `dp=1:if yx$<>"" goto linkflee`; cleared with the other post-death
  state at `SPUR.MISC6.S:40`.
- **`dy$`** — Usually a module name to LINK to

**Drive specifiers:** `dm$`=`g:` `ds$`=`a:` `dx$`=`j:` `dz$`=`a:` `dw$`=`j:`

Related file-path variables, not in the original drive-specifier block:
- **`du$`** — Which drive actually has a given file. `SPUR.LOGON.S:18`
  `du$=dx$`; `SPUR.MISC.S:462` `du$=dw$:dy$=dw$+i$:open #1,dy$:
  a=mark(1):close:if a du$=dx$` (fall back to `dx$` if not found on
  `dw$`), then `:463` `dr$=du$+i$:ready dr$`. Echoed in the sysop
  banner `SPUR.LOGON.S:23`.
- **`dr$` / `f1$` / `f2$`** — Per-level map and description file paths.
  `SPUR.CONTROL.S:385` `dr$=dx$+"room.level"+i$:f1$=dx$+"d.level"+i$`;
  `:705`/`:745` build the same pair for a level being created/edited.
- **`dt$`** — A second file handle's path, e.g.
  `dt$=dx$+"spur.weapons"` (`SPUR.UTIL.S:195`) or `dt$="k:users"`
  (`SPUR.CONTROL.S:327`).
- **`ln` / `lx`** — Level number being created/edited in
  `SPUR.CONTROL.S` (`ln=val(i$):if (ln<1) or (ln>lc) goto kl.lvl`;
  `ln=lc+1` for a brand-new level) and a room-index scratch read back a
  few lines later (`lx=x` … `if (rc=1) and (lx=1) then rt=x`).

## E

- **`e`** — East exit from room
- **`ep`** — experience points (reset each experience level increase)
- **`ev` / `ew` / `ex`** — The session clock:
  - **`ew`** = session start stamp (`SPUR.LOGON.S:15` `ew=clock(1)`).
    Rewound to *grant* time back — `SPUR.MISC6.S:465` `ew=ew-240` (a
    healing event), `SPUR.MISC7.S:182` `ew=ew-a` (digging charges time
    by moving the origin).
  - **`ex`** = seconds elapsed this session, always
    `ex=clock(1)-ew` (the `tim.chk` idiom, e.g. `SPUR.MAIN.S:348`).
    Logged as minutes played (`SPUR.LOGON.S:560`
    `": "+str$(ex/60)+" min."`).
  - **`ev`** = seconds *allowed* this session. `SPUR.LOGON.S` `tim.read`/
    `set.time` (`:480-495`): sysop path defaults to `3600`; user path is
    `mt-eu` (see `mt`/`eu` below), capped at time-left-on-BBS. Extendable
    in-game: `SPUR.MISC3.S:192` (Boots of Speed) adds 600 (`ev=ev+600`).
  - Seconds *remaining* (`ev-ex`) is computed inline wherever it's shown
    — the status-line clock (`SPUR.MAIN.S:67-70` etc, feeds into `yz`
    below), the "Dusk approaches…" warning (`<120`), duel/dig
    affordability checks, and the Hourglass display.
- **`eu` / `mt`** — BBS time budget, paired with `ev`/`ew`/`ex` above:
  **`mt`** = this session's maximum allowed seconds (`SPUR.LOGON.S:480`
  `mt=mv`, or the BBS's own remaining time if `mv=0`). **`eu`** = seconds
  already used *today*, read from the `spur.time` file keyed by `un`
  (`:484-485`, daily-reset on date change) and accumulated at logoff
  (`:544` `eu=eu+ex`). Author's own comment at `:546-553`:
  `;.. eu=mt: set time to full limit. Prevents multiple plays per day`
  — dropping carrier or suiciding burns your whole day's allowance.
  Sysop override: `SPUR.ANNEX.S:238`.

## F

- **`fd`** — Food in room
- **`fd$` / `ft$` / `sv`** — The room's ration: name / type / value (the
  ration counterpart of `wp$`/`wt$`/`wv`), set at `SPUR.MAIN.S:258`.

## G

- **`g$`** — Game name
- **`g1` … `g9`, `g0`** — The gold-arithmetic register file. `g1`/`g2` are
  the universal hi/lo pair passed to `prt.gold` / `spl.gold` /
  `add.gold` (`SPUR.MISC.S:52-57`), and get reused as scratch args for
  whichever gold pile is being formatted (`SPUR.BAR3.S:33-37`: `g1=g5,
  g2=g6` for bank balance display, `g1=g7,g2=g8` for Vinny debt,
  `g1=gh,g2=gl` for gold in hand). In the persistent `spur.a1$` record
  (`SPUR.MISC6.S:115-120`, `SPUR.DUEL2.S:357-364`) the fields are:
  **`g5`/`g6`** = bank gold hi/lo, **`g7`/`g8`** = gold owed Vinny hi/lo,
  **`g9`/`g0`** = duel record.
- **`gd$`** — Formatted 9-char gold string produced by `prt.gold`
  (`SPUR.MISC.S:57`
  `gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)`) and consumed as
  *input* by `spl.gold` (splits back into `g1`/`g2`). Also the raw input
  buffer for bank-amount prompts (`SPUR.BAR3.S:54`).
- **`gh` / `gl`** — Gold in hand, high/low (`gold=gh*10,000+gl`)
- **`go`** — Game objective: `1`=specific amount of gold, `2`=specific
  item, `3`=specific amount of gold & item
- **`gs`** — Cost of food
- **`gs$`** — Name of food

## H

- **`h`** — Opponent's hit points in a duel. `SPUR.DUEL.S:248-249`
  `print xx$" HIT! TAKES "w1" DAMAGE!":h=h-w1`; `:251`
  `if h<=0 then ch=1:goto hell` (you win).
- **`h1` / `h2` / `h3`** — HP for ally 1/2/3
- **`hh`** — currently in hand-to-hand combat? (0=no, 1=yes)
- **`hs`** — "Shield was topped up" latch, paired with `ra` below.
  `SPUR.USE.S:37` `if sh<100 then it=it*10:sh=sh+it:hs=1:if sh>100+a
  sh=100+a`; read once, in combat, to print the loss message exactly
  once: `SPUR.COMBAT.S:301` `if (sh<=0) and (hs) print "SHIELD
  GONE.":hs=0`.
- **`hp`** — hit points for main character

## I

- **`i`** — Item in room
- **`i$`** — General-purpose, but with one real convention: **`i$` is how
  modules pass a parameter across `LINK`/`gosub`**, because it survives
  the overlay swap. Examples: `SPUR.MAIN.S:192`
  `if zq>0 i$="CHARM":gosub lnk.msc5`; `:373` `i$="dead2":goto lnk.msc6`;
  `:383` `i$="AUTODUEL"`; `:348` `i$="QUIT":goto lnk.sub`; `:262`
  `i$="travel3":goto lnk.misc`; `SPUR.MISC.S:422`
  `if m=93 i$="wraith":link dy$`. Secondary uses: every menu's
  `input … i$`, and a temp message string for `gosub add.lg` /
  `gosub sys.log`.
- **`ic`** — Item count (# of items in game)
- **`it$` / `it` / `iv` / `i1$`** — The room's item: name / cost / value /
  type letter. `SPUR.MAIN.S:247` `it$=d$:i=d:i1$=dp$:iv=f`. Also built
  directly for a monster-drop treasure roll: `SPUR.MISC3.S:357-360`
  `i=16:it$="COIN":i1$="T":iv=1`, escalating to `"GOLD SACK"`,
  `"DIAMOND"`, `"SACK OF DIAMONDS"` by roll value. `it` separately is
  used as the shop price (`it=it*100`, `SPUR.SHOP.S:273`). Type letters
  (`i1$`/`dp$`, per `SPUR.SYSOP.S`'s editor): `T`=Treasure, `C`=Cursed,
  `B`=Book, `A`=Armor, `S`=Shield, `P`=Compass.

## L

- **`lc`** — Level count (# of map levels in game)
- **`lg$`** — last adventurer name
- **`lo$`** — Room location name (copied into `ww$`)
- **`l0$` / `rz$`** — The hand-rolled line-input routine. Identical copies
  in `SPUR.MAIN.S:601-626` and `SPUR.COMBAT.S:475-499` (label
  `tm.loop`): `l0$` accumulates the typed line, auto-uppercasing the
  first letter of each word; returns via `rz$=l0$`. `rz$` doubles as the
  mixed-case name formatter for the status line (`SPUR.MAIN.S:69`
  `rz$=n1$:gosub to.mixed`).

## M

- **`m$`** — Monster name
- **`m`** — The monster number occupying/approaching the current room.
  `SPUR.MAIN.S:214-216` sets it to a guild turf-guard number
  (65/66/67) or `70` (Ringwraith) under specific conditions, otherwise
  `:234` `m=random(mc):m=m+(m=0)`; `:240` `if m gosub rd.mons`. `m$` is
  the monster's *name* (documented above); plain `m` is the *index*
  actually used everywhere to look it up.
- **`ma`** — Monster's to-hit stat (`monsters.json` `'to_hit'` field) —
  confirmed via the Python port's `combat/resolution.py` ("SPUR ma",
  `hit_threshold()`'s `monster_size` param, line ~135/457/681). Read as
  the last field of the "monsters" data file record
  (`input #1,cb$\m$\ms,sw\ma`). Doubles as a size-word index in
  `SPUR.MISC4.S` `rd.mons`:
  ```
  zw$=" HUGELARGE  BIG  MANSHORTSMALLSWIFT"
  z=(ma-2)*5+1:zy$=mid$(zw$,z,5)     -- ma=2->HUGE ... ma=8->SWIFT,
                                         ma=5->"MAN SIZED"
  ```
  i.e. a monster's to-hit stat also drives the flavor-text size word
  shown on first sighting (higher to-hit = described as smaller/swifter).
  This is a *different* number from `yy` below, despite both loosely
  tracking "how big is this monster" — don't conflate them. Also used
  in the surprise-encounter roll (`rd.mons:86`): `z=10-ma`, so a
  low-to-hit ("huge") monster is easier to catch off guard than a
  high-to-hit ("swift") one.
- **`mc`** — # of monsters in game
- **`md`** — Monster dead (0=alive, 1=dead monster, 2=monster tracks)
- **`mf`** — Monster following (1=yes)
- **`mk`** — Monsters Killed
- **`mm`** — Lifetime move counter (rooms entered), saved with the
  character. `SPUR.MAIN.S:208` `mm=mm+1` on every room entry; `:227`
  `if not (mm mod 10) then pe=pe-1` (1 energy drained every 10 moves);
  `:229` wraps at 9999. Persisted alongside the other core stats
  (`SPUR.LOGON.S:272/346`), and `SPUR.SYSOP.S`'s player editor/listing
  shows it under the **"move"** column heading. Not the same thing as
  `tm` below, despite both once being guessed as "counter for Wizard
  Glow".
- **`ms`** — Monster strength?
- **`mt`** — see `eu` above.
- **`mv`** — Time limit in seconds (0=unlimited)
- **`mw`** — Monster waiting in room

## N

- **`n`** — North exit from room
- **`n1$`** — Character Name (leftmost character is either duel loss or
  guild)
- **`n2$`** — The *other* player's stored name (with its leading status
  digit), read in every `spur.users` scan: `SPUR.DUEL2.S:92`
  `xx$=left$(n2$,1):yz=val(xx$)` then `xx$=mid$(n2$,2)` strips it back
  off; `:394` writes the digit back after a duel changes someone's
  status.
- **`np`** — Number of players in game
- **`nr`** — Number of rooms on level?
- **`nw`** — Number of weapons currently in the game world (weapons file
  record 0). `SPUR.SYSOP.S` `weapon0` reads/writes it
  (`position #1,34,0`); adjusted by the armory shop on buy/sell
  (`SPUR.SHOP.S:152/216`).

## O

- **`og`** — Item number you must leave the game with
- **`oh` / `ol`** — Objective amount of gold, high/low
  (`amount=oh*10,000+ol`)

## P

- **`p1` / `p2` / `p3` / `p4`** — Probability variables (`SPUR.MAIN.S:357-
  359`, `SPUR.COMBAT.S:88-109`'s to-hit accumulator) — **but in the duel
  modules, a second, concrete meaning: the stat-derived attributes of
  bare hands (FISTS)**, built by `set.hh` (`SPUR.DUEL.S:332-345`,
  duplicated `SPUR.DUEL2.S:178-191`):
  ```
  p1=ps+pd+pt+pe:p1=p1/8      (yours, clamped 3-9)
  p2=cs+cd+ct+ce:p2=p2/8      (opponent's, clamped 3-9)
  p3=pw+pi:p3=p3/4            (yours, clamped 5-9)
  p4=cw+ci:p4=p4/4            (opponent's, clamped 5-9)
  ```
  consumed at `SPUR.DUEL2.S:173`
  `wr$="FISTS":cw$="FISTS":xu$="FISTS":gosub set.hh:wd=p1:w4=p2:ws=p3:
  w3=p4` and blended into an armed opponent's numbers
  (`SPUR.DUEL.S:113-114`/`SPUR.DUEL2.S:156-157`) — i.e. `p1`/`p3` = your
  unarmed damage/stability, `p2`/`p4` = the opponent's unarmed
  damage/to-hit.
- **`pa`** — Related to probability (`spur.main:set.prob`)
- **`pc`** — player class: 1) Wizard 4) Paladin 7) Archer · 2) Druid
  5) Ranger 8) Assassin · 3) Fighter 6) Thief 9) Knight
- **`pd`** — Player Dexterity
- **`pe`** — Player Energy
- **`ph$`** — BBS phone #? Checks for an `=` sign in it (must mean
  long-distance caller?)
- **`pi`** — Player Intelligence
- **`pn`** — Player Number (in SPUR.USERS?)
- **`pq`** — Printer **enabled** flag (0/1), not a device number.
  `SPUR.CONTROL.S:436-437` `if i$="ON" then pq=1` / `if i$="OFF" then
  pq=0`; used only as a boolean gate before offering to send a listing
  to the printer (`if pq gosub ptr.pmt`). `SPUR.ANNEX.S`'s admin display
  labels it "Printer device #", which is where the old note came from,
  but nothing ever treats it as a slot number.
- **`pr`** — player race: 1) Human 4) Elf 7) Dwarf · 2) Ogre 5) Hobbit
  8) Orc · 3) Pixie 6) Gnome 9) Half-Elf
- **`ps`** — Player Strength
- **`pt`** — Player Constitution
- **`pw`** — Player wisdom

## Q

- **`q$` / `q2$` / `q3` / `q4`** — The spell record fields
  (`SPUR.MISC3.S:32/267` `input #1,cb$\q$,q2$,q3,q4`). Per
  `SPUR.SYSOP.S`'s editor: `q$`=name, `q2$`=type+point-determinator (see
  `c1$`/`c2` above), `q3`=success chance ×10% (`if a<q3 then b=1`),
  `q4`=gold cost (and, divided by 10, the aura's duration in moves).

## R

- **`rc`** — Room command (1=move up a level, 2=move down a level)
- **`ra`** — "Armor was topped up" latch, the `ar` counterpart of `hs`
  above. `SPUR.SUB.S:38` `if ar<100 then it=it*10:ar=ar+it:ra=1:if
  ar>100 then ar=100`; read once at `SPUR.COMBAT.S:302`
  `if (ar<=0) and (ra) print "ARMOR GONE.":ra=0`.
- **`ri`** — Level dimensions (RI x RI rooms)
- **`rt`** — Room exit transports you to room # (0=Shoppe)

## S

- **`s`** — South exit from room
- **`sc`** — Spell count? (# of spells in game)
- **`sc$`** — Screen Clear character (depends on terminal type)
- **`sd`** — Confirmed dead field: round-tripped through the `spur.data`
  header record (`SPUR.CONTROL.S:116/125`, `SPUR.ANNEX.S:365/427`,
  `SPUR.LOGON.S:36/541`, `SPUR.UTIL.S:299/304/472`) and displayed on
  ANNEX's `prnt.dat` page, but never read anywhere for a decision — no
  edit key, unlike the fields around it. **Bug worth knowing:**
  `SPUR.CONTROL.S` reads/writes the pair in the order `sd,pq` while
  every other module uses `pq,sd` — running the CONTROL initializer
  swaps the printer-enabled flag and this dead field.
- **`sh`** — Main character shield percentage
- **`sl`** — Level SPUR is residing on
- **`sn`** — Suicide? (If SN=1, don't write all stats to disk)
- **`sr`** — Room SPUR is residing in
- **`sw`** — Monster's special weapon to kill (number)
- **`sw$`** — Name of that special weapon, resolved from `sw`.
  `SPUR.MISC4.S:132` `if (not sw) then sw$="":return`, `:137`
  `close:sw$=mid$(sw$,4)`; consumed `SPUR.COMBAT.S:127`
  `if (sw$="") goto p.a0` and `:151` `if sw$<>"" then b=b+2` (the bonus
  damage bump for using the right weapon).
- **`sx`** — "This is the SPUR/boss duel" flag. `SPUR.DUEL.S:160`
  `xx$="SPUR":sx=1:wx$="random"`; consumed at `SPUR.DUEL2.S:227`
  `if sx then sr=0:sx=0` — kills SPUR's stored room so he isn't there
  next time. Cleared at the start of every normal duel.

## T

- **`ta$` `tb$` `tc$` `td$` `te$` `tf$` `tg$` `th$`** — Per-level "who is
  standing where" rosters, **not** "following characters" as the old
  note guessed. Built at logon (`SPUR.LOGON.S` `ply.loc`, `:585-608`) by
  scanning every `spur.users` record: each entry is
  `<room>=<name>:<playernum>:` appended to the level-keyed string for
  that player's level, capped at 220 chars. Level mapping, confirmed by
  the debug dump at `SPUR.LOGON.S:653`:

  | Level | 1 | 2 | 3 | 4 | 5 | 6 |
  |---|---|---|---|---|---|---|
  | String | `ta$` | `tb$` | `tc$` | `td$` | `te$` | `th$` |

  There is no level-keyed `tg$` — the sequence skips from `te$` to
  `th$`. **`tf$`** = the overflow/"Aux 1" bucket for level 1 only, used
  when `ta$` was already full. **`tg$`** = a scratch *copy* handed to
  `ply.locD` for the actual player-lookup (`tg$=ta$:gosub ply.locD`,
  repeated per-level in `SPUR.MAIN.S`, `SPUR.MISC.S`, `SPUR.MISC3.S`,
  `SPUR.DUEL2.S`). Default/empty value is `">:"`. Also written by
  `SPUR.MISC4.S`'s `stay` (parking a follower — guild members only) and
  `SPUR.MISC5.S`'s come/follow.
- **`td`** — Display BBS user stats on top of sysop screen
- **`tm`** — The move number (in `mm` units) at which the current
  protective-aura spell (Wizard Glow etc.) expires; `0` = no aura active.
  `SPUR.MISC3.S:187` (`cst.aura`) sets it to a *future* value of `mm`;
  `SPUR.MAIN.S:226` checks `if (tm<>0) and (tm<mm)` to expire it
  ("The aura protecting you is gone."); `SPUR.MISC.S:63` lets an active
  aura scare off the Thief. Cleared at login. Not the same counter as
  `mm` — it's only meaningful *relative to* `mm`.

## U

- **`un`** — User number on BBS (1=sysop)

## V

- **`vk`** — Honor
- **`vm`** — Ammo damage
- **`vn`** — Ammo left
- **`vo`** — Record index of the currently readied weapon in
  `misc.data` (for battle-experience `vp`). `SPUR.WEAPON.S:55`
  `vo=zp position #2,250,pn,17+(vo*3-3):input #2,vp:close`; `:54`
  flushes the *old* weapon's exp before loading the new one's.
- **`vp`** — Battle experience with weapon
- **`vq`** — Lurk flag
- **`vr`** — **Two documented meanings, plus a third found while porting:**
  guild.standings Sword victory points; a flag to do with
  single/burst/auto ammo fire; and the readied weapon's type code —
  `SPUR.WEAPON.S:29` `zz$=mid$(ws$,3,1):vr=val(zz$)*6+1` (`if(vr=43)`
  triggers the "10% chance of secondary heat damage" text).
- **`vs`** — Two meanings: Guild.standings Sword loss points; and, paired
  with `vx` below, half of the "already scanned this room" cache for
  `ply.locD` (`vs=cl:vx=cr`, consumed at `SPUR.MAIN.S:379`
  `if (vs=cl) then if (vx=cr) then if (dc$<>"LOOK") then return`).
- **`vt`** — # of duels per game?
- **`vu`** — Round counter in combat? / Flag for money owed to Vinny; also
  your initiative in a duel: `3`=Opponent has initiative, `4`=Neither
  has initiative, `5`=You have initiative.
- **`vv`** — Civilian/Outlaw flag:
  - `0`: Civilian
  - `1`: Outlaw
  - `2`: Outlaw (Autoduel on)
  - `3`: Sword
  - `4`: Sword (Autoduel on)
  - `5`: undefined
  - `6`: Claw
  - `7`: Claw (Autoduel on)
  - `8`: Fist
  - `9`: Fist (Autoduel on)

  Also gates `SPUR.MISC4.S:79-83`'s turf-guard check: monsters #65/66/67
  are each one guild's own guard (FIST/SWORD/CLAW), and a member of that
  guild (either `vv` value, autoduel on or off) gets saluted instead of
  a normal encounter. Ported as `encounters/monster.py`'s
  `_try_turf_guard()`, keyed off `player.guild` directly since this
  port has no separate autoduel-on/off axis on `vv` to match against.
- **`vw`** — Three unrelated overlays:
  1. **Duel initiative score** (`SPUR.DUEL.S:83-85`) — compared against
     the opponent's equivalent (`zr`) to set `vu` above.
  2. **Guild treasury honor delta** (`SPUR.GUILD.S:77-90/419-420`) —
     amount put into or taken from the guild treasury, in Honor terms.
  3. **Terminal mode in the Bar modules** — `SPUR.BAR.S:472-480`
     (`set.var`): `0`=ASCII, `1`=ANSI, `2`=ProTerm; gates every
     screen-addressed print in the Bar.
  4. Also abused as a flag-by-side-effect in `SPUR.MISC4.S`'s `wraith`
     routine — a leftover nonzero value from a delay loop
     (`for vw=1 to 2000:next`) doubles as "the Ringwraith recognized you
     and left, skip the encounter".
- **`vx`** — Room half of the `vs`/`vx` "already scanned" cache — see
  `vs` above.
- **`vy` / `vq` / `zm`** — see `zm` below.
- **`vz`** — "You were caught off guard" / surprise-in-the-monster's-favor
  flag. `SPUR.COMBAT.S:31` `if vz=1 vz=0:print "SURPRISE ATTACK..":
  gosub m.attack` grants the monster a bonus second swing. Set by
  `SPUR.MISC4.S:149-157`'s pre-fight ambush roll and by the ally-revolt
  ambush in `SPUR.SUB.S:408`. Also reused as a string-length scratch in
  `SPUR.MISC5.S:164`.

## W

- **`w`** — West exit from room
- **`w1`** — Damage of the current duel blow (the duel's counterpart of
  combat's `b`). `SPUR.DUEL.S:210` base roll, `:228-235` the modifier
  chain (level bonus, Assassin critical hit, tactic-matchup bonus,
  parry-halving), `:249` `print xx$" HIT! TAKES "w1" DAMAGE!":h=h-w1`.
- **`w3` / `w4`** — The *opponent's* weapon to-hit and damage.
  Self-documented at `SPUR.MISC6.S:242-243`:
  `;w4=weapon damage, w3=weapon 'to hit', xy=damage skill, xv= 'to hit' skill`.
  Chosen as the opponent's best weapon at `SPUR.DUEL2.S:151`; unarmed
  defaults set at `:173`. `w4` is also reused as the Death Amulet
  instant-death chance %, `SPUR.DUEL2.S:161-165`.
- **`wa`** — Weapon class armed
- **`wc`** — Weapon count (# in game)
- **`wd` / `ws` / `ws$` / `wz$` / `vr`** — Readied-weapon attributes
  (`SPUR.WEAPON.S:29` `input #1,ws$\ws,wd\wa`): `wd` = base damage,
  `ws` = stability → required Dexterity (`ws+4`; scaled up by level:
  `ws=((xp+2)*ws)/3` past level 1), `ws$` = the raw weapon record,
  `wz$` = the *previously* readied weapon, so ammo resets on a swap
  (`if wz$<>wr$ vn=0`). `vr` = weapon type code, see the `vr` entry
  above.
- **`wn`** — Game won flag
- **`wp`** — Weapon in room
- **`wp$` / `wt$` / `wv`** — The room's weapon: name / type / value, set
  at `SPUR.MAIN.S:252` and printed in the room description.
- **`wq`, `wk`** — Sysop-editor bookkeeping in `SPUR.SYSOP.S`'s weapon
  editor: `wk` = "this add increased the weapon count" flag, feeding
  `nw` above.
- **`wr$`** — Weapon readied
- **`ww$`** — Copy of room name (stuff before pipe)
- **`wx$`** — `>:x` (x=current room) — another flag for who's present in a
  room?
- **`wy$`** — Monster flags. Full sigil table (from the Python port's
  `monsters.py`, itself derived from parsing this field across the
  monster roster):

  | Sigil | Meaning | Sigil | Meaning |
  |---|---|---|---|
  | `;;` | heavy_armor | `++` | cast_multiple_spells |
  | `;` | light_armor | `+` | cast_one_spell |
  | `>>` | chance_find_gold_2x | `]` | double_attacks |
  | `>` | chance_find_gold | `:` | mechanical |
  | `.` | increase_strength | `E` | evil |
  | `G` | good | `<` | re_animates |
  | `#` | cast_turn_to_stone | `*` | poisonous_attack |
  | `@` | diseased_attack | `&` | experience_drain |
  | `%` | magic_resistant | `~` | appears_unaffected |
  | `-` | fire_attack | `X` | no_gold |
  | `$` | multiple_monsters | `?` | no_article (suppress "THE") |
  | `AC` | charmable | `!` | has_quote |

  `-` (fire_attack) detail, confirmed against `SPUR.COMBAT.S:239-243`:
  FIRE! (2 dmg) vs LAZER FIRE! (5 dmg) is decided by the dungeon
  **level** the fight is on (`cl>5`, the sci-fi levels), NOT by any flag
  on the monster. If the monster also has `;;` (heavy_armor), the
  attack is upgraded again to "IT'S PLASMA CANNON!" with a further +4
  damage. No monster flag selects fire vs. laser directly.

## X

- **`xa$`** — "Record number as `nnn,`" formatting temp, same idiom
  repeated in six modules (`SPUR.SHOP.S`, `SPUR.SHIP.S`, `SPUR.GUILD.S`,
  `SPUR.MISC5.S`): `xa$=right$("000"+str$(x),3)+","`, used to test
  membership in the `xi$`/`xw$`/`xf$` inventory strings without
  clobbering `a$`.
- **`xf`** — # of food items in char's inventory
- **`xi`** — # of inventory items
- **`xi$`** — inventory items `[xxx,yyy,zzz...]`
- **`xl$` / `xc`** — Sysop-editor plumbing (companions of `xn$` below):
  `xl$` names the list routine to dispatch to (`SPUR.CONTROL.S:454-462`,
  e.g. `"listally"`, `"listmons"`, `"listspel"`); `xc` is the highest
  valid record number for range checking (`SPUR.SYSOP.S` `getnum`:
  `if (x<1) or (x>xc) print xn$" from 1 to "xc" only."`).
- **`xm`** — # of monsters in `xm$`
- **`xm$`** — monsters killed so you don't encounter the same
  (non-re-animating) ones again `[xxx,yyy,...]`
- **`xn`** — copy of SN, or copy of UN if SN=0
- **`xn$`** — Not a scratch variable — the human-readable name of the
  data file currently being edited in `SPUR.SYSOP.S`/`SPUR.CONTROL.S`,
  paired with `xl$` (list-routine name) and `xc` (highest valid record
  #). `SPUR.CONTROL.S:465` `xn$="ROOMS"`; `SPUR.SYSOP.S` sets it to
  `"RATIONS"`, `"SPELLS"`, `"MONSTERS"`, `"ITEMS"`, `"WEAPONS"`,
  `"ALLIES"` per editor entry point. Used purely for prompt text
  (`"[ "xn$" ]"`, `"Kill "xn$" #"x`). Not used by the game proper.
- **`xo` / `xo$`** — Session history of rations *acquired*, so eaten food
  doesn't respawn — **not** "for ally use" as the old note guessed.
  Seeded from the carried-rations list at login (`SPUR.LOGON.S:198`
  `xo=xf:xo$=xf$`). A 20-entry ring buffer of ration numbers picked up
  this session (`SPUR.MISC.S:333-334`, `SPUR.GUILD.S:301-302`; oldest
  entry dropped once full). Consumed at `SPUR.MAIN.S:257`: a room's
  ration is suppressed from the description if it's in *either* `xf$`
  (still carried) or `xo$` (already taken and eaten this session).
- **`xp`** — Experience level
- **`xs`** — # of spells learned
- **`xs$`** — Spells main character has
- **`xt` / `xt$`** — Same ring-buffer mechanism as `xo`/`xo$`, but for
  **items** (60-entry, `nnn,` format). Appended in four places
  (`SPUR.MISC.S:321-322` pickup, `SPUR.MISC2.S:317-318` after a
  scroll/book is consumed, `SPUR.MISC7.S:289-290` digging). Consumed at
  `SPUR.MAIN.S:244`: an item already in `xi$+ai$` (current inventory) or
  `xt$` (already taken/consumed this session) is skipped when a room is
  described. The scroll-consumption case is why the old note guessed
  "scroll-related" — that's only one of the four append sites.
- **`xu`** — Guild.standings: Claw loss points. Also reused in
  `SPUR.MISC2.S`'s `elev` subroutine as a scratch numeric
  (`(random(890)/10)+10`, roughly 10-98) for building `xu$` — unrelated
  to the guild-standings meaning, just recycled.
- **`xu$`** — The scrap-of-paper elevator combination: three segments
  like `xu` built above, joined with `-` (e.g. `"45-72-33"`). Generated
  once when item #69 "scrap of paper" is READ, printed to the player,
  and written to a per-player-indexed record in the "elevator" file
  (`position #1, pn, 10`) so `SPUR.SHIP.S`'s elevator subroutine can
  check what the player types against it later. Never redisplayed after
  the initial reveal — forgetting it is a dead end even in the original
  game.
- **`xv`** — See `xy`/`xv` below (guild support / weapon skill).
- **`xv$`** — How allies are ORDERed?
- **`xw`** — # of weapons main char has / guild.standings: Fist victory
  points
- **`xw$`** — Main char weapon list
- **`xx$`** — Scratch string, but with one dominant meaning: **the duel
  opponent's display name**, set once and printed dozens of times
  (`SPUR.DUEL2.S:92-98` strips the leading guild/status digit off the
  stored `n2$`). Named-boss overlays: `SPUR.DUEL.S:160`
  `xx$="SPUR"` (the endgame boss fight); `SPUR.MISC6.S:240`
  `xx$="THE ENFORCER"`. Other unrelated overlays: a filename buffer
  (`SPUR.ANNEX.S:207/216/227`); the dig-direction letter
  (`SPUR.MISC7.S:170-176`); a guild-symbol label for the player list
  (`SPUR.MISC3.S:552-558`, e.g. `"OUTLAW"`, `"==[]"`); the news-log
  event verb (`SPUR.MISC4.S:161-168/223`, e.g. `"FLEE"`, `"CHARM"`); one
  entry of a `ta$`-style room roster (`SPUR.LOGON.S:612`); the DIE
  confirmation input (`SPUR.MAIN.S:80`); and, per `SPUR.BAR.S:468`'s own
  comment block, the terminal's clear-to-EOL escape sequence in the Bar
  modules.
- **`xy$`** — Activity-log message text in `SPUR.GATES.S`, unrelated to
  numeric `xy` below. `:25` `xy$="Spur Annex":gosub log`; `:27`
  `xy$="Invalid Command: "+chr$(34)+i$+chr$(34)`; `:57`
  `xy$="[ShowFile]: "+f$+" viewed"`; `log` appends it to `h:sys.log`.
  Distinct from `zs$`, which writes `c:spur.log` from inside the game
  proper.
- **`xy` / `xv`** — Guild support count (how many fellow guild members are
  backing you in a duel), and, per the `SPUR.MISC6.S:242-243` comment,
  double as **damage skill** (`xy`) and **'to hit' skill** (`xv`) once a
  fight starts. `SPUR.DUEL2.S:99-107` counts supporters (capped at 5:
  "Only 5 Guild members can lend support"); `SPUR.DUEL.S:65` gives +2 to
  `xy` for being in your own guild's HQ. `xv` separately is the count
  feeding `xv$`.
- **`xz` / `xz$`** — The character-position cursor while walking the
  `ta$`-style roster strings (`ply.loc2`: `xz=xz+1:if
  mid$(xu$,xz+yw,1)=":" goto ply.loc3`). Also the ally slot index in
  `SPUR.MISC2.S:48-51`. Note `SPUR.DUEL.S:9`'s own warning comment:
  `;... yz, xz$, zu must be preserved for spur.duel2, don't use`.

## Y

- **`yg`** — Copy of PC
- **`yi`** — Copy of PR
- **`yn` / `yf` / `yj` / `yc` / `yd` / `yh`** — The opponent's mirrored
  stats (level / armor / experience / …), loaded as a block —
  `SPUR.MISC6.S:248` builds the Enforcer as a clone of you:
  `ya=0:yb=0:yc=0:yd=0:yf=ar:yg=pc:yi=pr:yj=ep:yn=xp`. `yn` = opponent
  level, compared against `xp` for a duel bonus/penalty
  (`SPUR.DUEL.S:229/280`). `yh` = opponent HP, read from `spur.users`
  (`SPUR.DUEL2.S:87`) or set directly for a scripted fight
  (`SPUR.MISC6.S:227` `yh=15`).
- **`ya` / `yb`** — Duel prize gold, high/low. `SPUR.DUEL2.S:218-223`
  builds it up (base 250, +250 outlaw bounty, +250 for an active
  contract, 1000 flat for beating the Enforcer with the Sun-Sword),
  carries `yb=>10000` into `ya`, then pays out via `g1=ya:g2=yb:
  gosub prt.gold`.
- **`yc` / `yd`** — Looted gold, high/low — the same accumulator idiom as
  `ya`/`yb` but for taking a dead opponent's purse: `SPUR.DUEL2.S:235`
  `yc=yc+gh:yd=yd+gl:if yd=>10000 then yd=yd-10000:yc=yc+1`; reused
  identically in `SPUR.SHOP.S:531` and `SPUR.SHIP.S:365`.
- **`ys` / `yp` / `yl` / `yr` / `yh`** — The `spur.users` fields as read by
  `ply.loc`'s scan (`SPUR.LOGON.S:591`
  `input #1,n2$,ys,yp,yl,yr,yh`): name, BBS id, player #, **level**,
  **room**, hp. `SPUR.MISC6.S:246` fakes them for the Enforcer
  (`ys=1:yp=1:yl=cl:yr=cr:yh=hp+1`). Careful: `ys$` (session-event
  flags, documented below) is a completely different variable from
  numeric `ys`.
- **`ys$`** — What events have occurred this session (not strictly
  "once-per-session" flags as thought previously). Strings are
  surrounded by `*` (`"*GI*"` for example) so `INSTR()` can isolate just
  that sub-string from the whole string. `*` characters are omitted
  below:

  | Flag | Meaning |
  |---|---|
  | `AD` | AutoDuel flag |
  | `ayf` | Ally finds something |
  | `bo` | Boots of Speed used |
  | `CM` | Communicator used |
  | `ENF` | Enforcer |
  | `gal` | Galadriel's test |
  | `gd` | Guardian seen |
  | `gd2` | Guardian waiting |
  | `GI` | Little girl |
  | `LAZ.SH` | Lazer Shield used |
  | `LOOT` | Looted character |
  | `me` | meteor |
  | `MNT` | Mounted (`SPUR.MISC7.S` mount/dismount; `SPUR.MAIN.S` checks it every move for auto-dismount/water-room block, and halves move-time-cost while set) |
  | `OUTLAW` | Outlaws can LOOT twice |
  | `pr1` | Can only pray once per session |
  | `pr2` | Can pray twice (pc=2 or 4) |
  | `prd` | Prayed |
  | `PS` | Pawn Shop visited |
  | `PWR.AR` | Power Armor energized |
  | `sk` | Visited Skip in Bar |
  | `SS` | Salvage computer used |
  | `TR+` | Transporter used |

- **`yt$`** — Characters following, `*` if none
- **`yw` / `yx` / `yy` / `yz` (Bar modules only)** — 2-D map coordinates
  in `SPUR.BAR.S`, a completely separate overlay from every other
  meaning of these letters listed elsewhere in this file: `yw`=column,
  `yy`=row, `yx`/`yz`=previous column/row (for "restore on blocked
  move"). `SPUR.BAR.S:8` inits all four to `(7,7,1,1)`; `:36-39` move
  them by direction letter; `:46-50` is the destination table mapping
  `(yw,yy)` pairs to sub-rooms (Vinny, Skip, Zelda, the Slave Trade,
  etc).
- **`yx$`** — `*`
- **`yx` (outside the Bar)** — The duel tactic-matchup outcome code.
  `SPUR.DUEL.S:410-419` cross-references your tactic (`zw`) against the
  opponent's (`zz`) to set a numbered outcome (e.g. `yx=13`/`14` "HAS
  AUTO-STRIKE", `yx=15` "YOU TRIP OVER"), read back for damage/hit
  modifiers. Also the special-weapon bonus out-param
  (`SPUR.WEAPON.S:44` `gosub special:zv=yz:zu=yx`) and an ally-HP
  scratch in `SPUR.MISC2.S:48-51`.
- **`yy` (outside the Bar)** — Reused scratch variable, TWO unrelated
  meanings depending on where you are in `SPUR.MISC4.S`'s `rd.mons`
  routine:

  1. Temporarily, a string `INSTR()` index while splitting the monster's
     flag suffix off its name (`rd.mons:53` `yy=instr("|",m$)`) — just a
     slice-position number, discarded immediately after use.

  2. Then reassigned (`rd.mons:62` `zx$=left$(m$,1):yy=val(zx$)`) to the
     monster's SIZE digit: an optional leading digit on the monster's
     NAME field in the "monsters" data file (e.g. `"M.7RATTLESNAKE"` →
     name digit 7), 1–7, matching the Python port's `monsters.py`
     `monster_sizes` table (1=huge ... 7=swift; `monsters.json`'s
     `'size'` field is this exact digit, already parsed by
     `convert_monster_data_fixed.py`). `yy=0` means the monster's name
     had NO leading digit at all (`monsters.json` `'size': null`).

     Confirmed by reading `monsters.txt` directly (fixed-width/light-
     compression format, `RECORD_SIZE=32`) — e.g. `"M.1TINMAN|!55ACG"`,
     `"M.3DRAGON! |~>>-."` all carry the digit; `"M.OLD MAN|!53AC<"`
     does NOT, despite being AC (charmable) — see the quirk below.

     This SIZE digit is NOT the same number as `ma` above (`ma` is the
     monster's to-hit stat, read as a separate CSV field) — they're both
     small integers describing "how big/tough" a monster is, and easy to
     conflate, but they come from different source columns and are used
     for different things:

     `yy`'s (2nd meaning's) actual uses, all in `rd.mons`:
     - Gates the ENTIRE spontaneous-charm check (`d.charm`,
       `rd.mons:100`): `if (yy=0) or (zs=998) goto rd.mon2` — monsters
       with no leading digit skip the charm roll entirely, INCLUDING the
       AC/charmable forced-join override (`rd.mons:128`
       `if instr("AC",wy$) zq=1`), because execution jumps past it.
       Confirmed real-data quirk: OLD MAN (`monsters.txt`) is
       AC-flagged but has `yy=0`, so it can never actually be
       spontaneously charmed/recruited by this routine — whether that's
       an intentional design choice or an authoring oversight in the
       original game isn't clear from the source alone.
     - Gates the "whole encounter flees in terror" branch of the
       surprise roll (`rd.mons:96`): `if zs=998 then if yy>0 ... WHO RUN
       AWAY SCREAMING!` — also requires a nonzero size digit.
     - Two specific charm-bonus modifiers keyed to an exact `yy` value:
       `if pc=9 if yy=1 z=z+20` (Knight, vs. huge/yy=1 monsters) and
       `if pr=3 if yy=2 z=z+40` (Pixie, vs. large/yy=2 monsters).

     Ported (with these exact gates) in the Python port's
     `encounters/monster.py` `try_monster_encounter()`.
- **`yz$`** — Which module to return to after the sysop editor.
  `SPUR.ANNEX.S:16` `if i$="S" gosub view.dat:yz$="d:spur.annex":
  dy$=ds$+"spur.sysop":link dy$`; consumed by `SPUR.SYSOP.S`'s `quit`:
  `if yz$="spur.gates" link "a:spur.gates"` / `if yz$="spur.annex"
  i$=yz$:yz$="":link dz$+i$`.
- **`yz` (outside the Bar)** — `EV-EX` — seconds remaining this session
  (`spur.main`), computed for the status-line clock — see `ev`/`ew`/`ex`
  above. Elsewhere an unrelated scratch: an `INSTR()` index
  (`SPUR.MAIN.S:246`), a guild `flag()` number
  (`SPUR.MAIN.S:590-594`/`SPUR.GUILD.S:13-16`, see `zm` below), the
  opponent's status digit (`SPUR.DUEL2.S:58-103`), and the special-
  weapon bonus out-param (`SPUR.WEAPON.S:44`).

## Z

- **`z`** — Random-roll output register (the `…z`-suffixed `rnd`
  subroutines return here, e.g. `rnd.10z`, vs. the `…a`-suffixed ones
  returning in `a`). Also, separately, the **cause-of-death code**, set
  at the death site and consumed by `SPUR.MISC6.S`'s `dead2b`
  (`:87-105`) to pick the epitaph:

  | `z` | Cause |
  |---|---|
  | 1 | Starvation |
  | 2 | Suicide (also `goto win`) |
  | 3 | Picked up a cursed object |
  | 4 | Killed while battling a monster |
  | 5 | Killed by your own readied weapon |
  | 6 | Turned to stone by a monster (→ `gosub statue`) |
  | 7 | Poisoned |
  | 8 | Diseased |
  | 9 | Killed by the Death Amulet |
  | 10 | Drowning |
  | 11 | Freezing |
  | 12 / 0 | Killed in a duel |
  | 13 | Zapped by the Spirit of the Dungeon |
  | 14 | Killed by a monster's magic |
  | 15 | Decompression |
  | 16 | Radiation |
  | 17 | Concussion |
  | 18 | Passed through the Portal of Spur (→ `goto win`, becomes immortal) |
  | 19 | Killed by a booby trap |

- **`zm` / `vy` / `vq`** — Three guild-member tallies while scanning who's
  in the room for duel support (`SPUR.DUEL2.S:59-61`, cleared together
  at several duel-init sites): `zm`=Sword count, `vy`=Claw count,
  `vq`=Fist count (matching the `vv` guild-ID scheme). `zm` is *also*
  reused for which guild HQ you're standing in
  (`SPUR.GUILD.S:13-16`/`SPUR.MAIN.S:590-594`: `1`=Sword, `2`=Claw,
  `3`=Fist, `0`=not in any HQ → "A gruff guard informs you that you are
  not a member..."), and, in `SPUR.BAR2.S`, blackjack's soft-ace
  counter. `vy` is *also* the deployed-ally slot number in
  `SPUR.MISC4.S:143-146` (1=front/point, 2=flank, 3=rear).
- **`zn`** — Three meanings:
  1. **Duel: consecutive-ATTACK counter**, the third leg of the
     `xu`(parry)/`zp`(bash)/`zn`(attack) pattern-prediction trio —
     `SPUR.DUEL.S:31/33/36` sets exactly one of the three and zeroes the
     other two each round; a high count feeds the AI's own tactic choice
     and prints "Predicts you will attack, -N%!".
  2. **"Ringwraith already dealt with" marker** —
     `SPUR.MISC4.S:226` sets `zn=70` at the end of the `wraith`
     encounter; `SPUR.MAIN.S:217` checks it to suppress the "Something
     evil stalks…" wandering-guard roll on later moves.
  3. **Monster hand-off across LINK** — `SPUR.MISC.S:422`
     `zn=m:if m=93 i$="wraith":link dy$`.
- **`zo`** — Carrying capacity
- **`zp`** — Consecutive-BASH counter in duels (see `zn` above). Other
  overlays: the weapon slot number in `SPUR.WEAPON.S:23-25`; the Bar's
  cached HP for change-detection on the status window (documented in
  the source itself, `SPUR.BAR.S:471` `;(zp used to detect difference in
  HP)`); the thug's motive in `SPUR.MISC7.S:78-80` (`0`=hired to attack,
  `1`=return the compliment, `2`=wants gold); a stat-roll scratch in
  `SPUR.MISC2.S:452-454`.
- **`zq`** — "Quite charmed" flag — set by `SPUR.MISC4.S` `rd.mons`'s
  spontaneous charm-on-encounter roll (`d.charm`, confirmed
  `rd.mons:118/127/128`) or a turf-guard recognizing the player
  (`rd.mons:41-44`). Read back in `SPUR.MAIN.S:192`
  (`if zq>0 i$="CHARM":gosub lnk.msc5`) to send the monster through the
  exact same join-the-party offer flow as the CHARM POTION — see the
  Python port's `spells/charm.py` `try_charm_join_offer()`, reused
  verbatim for both triggers, and `encounters/monster.py` for the
  spontaneous-roll side. Also a commentary flag in duel.
- **`zr`** — # to remove from stats. Also the opponent's initiative score
  in a duel, compared against `vw` — see `vw` above.
- **`zs`** — Surprise-encounter state, set by `rd.mons` and consumed by
  `SPUR.COMBAT.S` once a fight actually starts:
  - `999`: `m$` lost sight of you
  - `998`: `m$` is surprised (set by `rd.mons`'s surprise roll,
    `SPUR.MISC4.S:94` — the player caught the monster off guard) —
    consumed on the first combat exchange (`SPUR.COMBAT.S:23`
    `if zs=998 zs=997`)
  - `997`: SURPRISE ATTACK! — to-hit +2 (`p2=p2+2`, `SPUR.COMBAT.S:124`)
    and damage +3 (`b=b+3`, `SPUR.COMBAT.S:143`) on the player's swing.
    Never reset back to 0 mid-fight, so per SPUR's own code this bonus
    actually applies to every swing of the fight, not just the first.
    Ported as `CombatSession.is_surprise` in the Python port's
    `combat/engine.py`, feeding `combat/resolution.py`'s `is_surprise`
    param (which existed before this was wired up, but nothing set it
    until `encounters/monster.py`'s surprise roll did).
  - `<990`: `m$` powers down/snarls and waits
  - `>989`: ignores you/looks around uneasily
  - `0`: (no state)
- **`zs$`** — The opponent's tactic message string in a duel (paired with
  `zz`): `SPUR.DUEL.S:379-404` sets it to `"STANDS UP.."`,
  `"ROLLS ON THE GROUND.."`, `"SHIELD BASHES!"`, `"PARRIES WITH THE
  "+cw$+"!"`, or `"ATTACKS!"`, printed at `:408`
  `print xx$" "zs$\"YOU "zy$` (so `zy$` is *your* tactic message — see
  `zy$` below). Also the security-log line builder in
  `SPUR.LOGON.S:496/560` (`gosub log` writes `zs$`).
- **`zt` / `zs` (duel weapon-affinity context)** — In the guild-standings
  sense, documented below/above respectively. But inside
  `SPUR.DUEL2.S`'s opponent-weapon-selection scan (`:146-151`,
  `for e=1 to c`), `zt` = weapon damage-skill bonus and `zs` = weapon
  to-hit-skill bonus, accumulated by the `special` subroutine per
  candidate weapon from the opponent's class (`yo`) and race (`yq`)
  affinity tables (`:407-413` by class, `:424-430` by race — e.g. Wizard
  favors BALL/STAFF/BOLT weapons, Ogre favors CLUB/HAMMER/KLES). The
  best-scoring weapon so far is tracked in **`yt`**
  (`if (zt+zs)>yt then yt=zt+zs:cw$=w$:w3=w1:w4=w2:wa=w5`) — `yt` isn't
  used anywhere outside this one scan.
- **`yo` / `yq`** — Opponent's class/race, copied from `yg`/`yi` at
  `SPUR.DUEL2.S:139` specifically to drive the weapon-affinity scan
  above.
- **`zt`** — Guild.standings: Claw victory points
- **`zt$`** — Copy of `xv$` (from spur.misc2)
- **`zu`** — Skill with currently readied weapon
- **`zu$`** — 10 characters:
  1. Room description — `A`/`B`=off (`spur.logon.s`; `SPUR.ANNEX.S`'s
     `status1` says 1=descs off); `B`/`C`=Shield training
     (`spur.combat.s`, `spur.misc.s`)
  2. The Ring worn
  3. Poisoned
  4. Diseased
  5. Thug attack
  6. Gauntlets worn
  7. `0`=no spell active? / `1`|`2`=Wraith Master of Spur / `>2`=Wizard
     Glow spell active
  8. Amulet of Life
  9. Tut's Treasure — `0`=not examined, `1`=examined
  10. Guild Follow
- **`zv`** — Damage with currently readied weapon
- **`zv$`** — The duel entry mode (`"autoduel"`, `"abortduel"`, or a
  contract flag whose non-blank value adds 250 to the duel prize — see
  `ya`/`yb` above). Also the Center square in the dig/bury compass
  (`SPUR.MISC7.S:176/264`).
- **`zw`** — Opponent weapon class (from `spur.duel2.s:opnt.wp`). Also
  reused in `SPUR.COMBAT.S`'s CHARGE branch as a one-shot "this attack
  is a charge" flag (`zw=1` set right before falling through to
  `p.attack`) — unrelated to the duel meaning above, just the same two
  letters recycled in a different overlay.
- **`zw$`** — Temp for class/race display
- **`zx$`** — Class/race name slice (`SPUR.LOGON.S:103-107`) and the
  `":"+str$(cr)+"="` search key used in every `ply.locD` room-roster
  lookup.
- **`zy$`** — Your own tactic message in a duel (the mirror of `zs$`
  above), set alongside `zn`/`zp`/`xu` at `SPUR.DUEL.S:31/33/36`
  (`"PARRY WITH THE "+xu$+"!"` / `"Shield BASH!"` / `"aTTacK!"`). Also
  the monster size word in `SPUR.MISC4.S` (`zy$=mid$(zw$,z,5)` — see
  `ma` above).
- **`zy`** — Sysop/debug verbosity switch. Guards every debug print in the
  game: `SPUR.LOGON.S:653` `if zy=1 print "1]"ta$\"2]"tb$…` (the `ta$`…
  `th$` roster dump), `SPUR.MISC2.S:399` `if zy=1 print "zu$="zu$`,
  `SPUR.DUEL2.S:463/469`, `SPUR.SHOP.S:196`, `SPUR.SHIP.S:240`. Distinct
  from `zy$` immediately above.
- **`zz`** — General numeric scratch, with one real named meaning: **the
  duel opponent's chosen tactic this round**, the mirror of your `zw`.
  Set by the opponent-AI routine `SPUR.DUEL.S:379-404`
  (`1`=stand up, `2`=attack, `3`=parry, `4`=shield bash, `5`=roll on the
  ground), consumed all through the resolution table. Elsewhere a plain
  temp: a guild number in `SPUR.ANNEX.S:169`, the sysop player-editor
  input buffer, a level-difference bonus in `SPUR.DUEL.S:229`.
- **`zz$`** — Almost always the **RNG reseed** performed immediately
  before any `random()` call — `zz$=rnd$` — whose *value* is thrown
  away (`SPUR.MAIN.S:471/473/475`, `SPUR.COMBAT.S:126/386-390`,
  `SPUR.CONTROL.S:727-730`, `SPUR.SYSOP.S`). Otherwise a general string
  scratch: status-line assembly, pluralization ("IS"/"ARE"), the
  fire/laser attack text, one `zu$` character being tested, the
  news-log line, the compass room string, and a temp variable to output
  to the news log.

---

## Notes on working with the SPUR source

- **`SPUR.SYSOP.S` is stored as a single ~24 KB line** (old Mac-style
  CR-only line endings, no LF) — a normal line-numbered `grep`/`Read`
  against it is meaningless until it's converted. Use **`mac2unix`**, not
  `dos2unix`, and convert **only this one file** — running `dos2unix`
  across the whole `SPUR-code/` directory would also rewrite the CRLF
  files, and `SPUR.BAR.S` contains 8-bit ANSI/ProTerm escape bytes (why
  `file` reports it as `data`), which `dos2unix` will refuse or mangle
  unless forced. Before converting, `tr '\r' '\n' < SPUR.SYSOP.S |
  grep -n …` works as a one-off substitute. For whole-tree sweeps across
  `SPUR-code/*.S`, use `grep -a` — plain `grep` can silently skip
  `SPUR.BAR.S`'s high-bit bytes as "binary".
- **Labels can look exactly like variables and will pollute a naive
  grep.** e.g. `a1$.a`, `a1$.b`, `read.a1$`, `writ.a1$`
  (`SPUR.ANNEX.S`/`SPUR.DUEL2.S`), `tm.loop` (`SPUR.MAIN.S:615`,
  `SPUR.COMBAT.S:489`), and the filename `spur.a1$` are all labels/paths,
  not the variables `a1$`/`tm`. Short tokens like `z`, `a`, `i$` will
  also match inside unrelated string literals and longer identifiers —
  search for the variable at a real assignment/read boundary (`\bz=`,
  `\bz,`, `(z)`, etc.), not just the bare substring.
- **The `sd`/`pq` field order is a live, confirmed bug**, not just an
  inconsistency to note: `SPUR.CONTROL.S` reads/writes the pair as
  `sd,pq` while `SPUR.ANNEX.S`, `SPUR.LOGON.S`, and `SPUR.UTIL.S` all use
  `pq,sd` — running the CONTROL initializer swaps the printer-enabled
  flag and the (otherwise dead) `sd` field. See the `sd` entry above.

---

## Player flags (`FLAG(n)`)

| Flag | Meaning |
|---|---|
| `FLAG(3)` | Has access to Sword Guild HQ |
| `FLAG(6)` | Has access to Claw Guild HQ |
| `FLAG(7)` | Immortal player? |
| `FLAG(13)` | Has access to Fist Guild HQ |
| `FLAG(15)` | Involuntary Outlaw |
| `FLAG(25)` | Game Master |
| `FLAG(26)` | No Spur access |
| `FLAG(27)` | SPUR.GUILD: Member of Sword Guild |
| `FLAG(28)` | SPUR.GUILD: Member of Claw Guild |
| `FLAG(29)` | SPUR.GUILD: Member of Fist Guild — **also** reused by BAR.S as "Caller in ANSI mode?" |
| `FLAG(30)` | BAR.S: Caller in ProTerm mode (Atari graphics)? |
| `FLAG(35)` | Pause mode on BBS enabled |

(Unlisted flag numbers in this range have no known meaning recorded here.)

---

## Minor locals not individually documented

A full sweep also turned up a tail of single/double-use locals confined to
one routine — mostly `SPUR.CONTROL.S`'s map editor, `SPUR.UTIL.S`'s file
maintenance, and `SPUR.GATES.S`'s `show.file`. Below documentation
threshold for a full entry each, but noted here so the sweep is known to
be complete and so nobody re-derives them from scratch:

- **`t1`/`t2`** — gold-totalling pair in `SPUR.CONTROL.S:370-373`.
- **`vl`** — ammo count backup, `SPUR.USE.S:157`
  `vn=val(left$(i$,2)):vl=vn:vm=val(mid$(i$,3,1)`.
- **`wq`** — "already printed 'an' for this item" article flag,
  `SPUR.MISC3.S:610-612`.
- **`mn`** — allocation cursor, `SPUR.MISC7.S:50` `x=mn:mn=mn+1`.
- **`tt`/`tl`** — `clock(2)`/`clock(1)` snapshot, `SPUR.ANNEX.S:536`.
- **`ed`** — edit-buffer address, `SPUR.CONTROL.S:764`.
- **`ii`** — inner delay-loop index, e.g. `SPUR.MISC2.S:527` (paired with
  **`k0$`**, the per-character scream builder:
  `k0$=mid$("AARRGGGHHH!!!!",i,1):for ii=1 to 4`).
- `f0$`–`f4$`, `og$`, `wl`, `ae`, `aa` — single-routine locals in the
  editor/maintenance modules (e.g. `ae` = `SPUR.GATES.S`'s "fancy
  header" flag, `aa` = `SPUR.SYSOP.S`'s comma-formatter working length).

Also the sysop-editor player-record field temps `b1`-`b4`, `g0`,
`m1`-`m4`, `n1`-`n8`, `z1`, `z2`, `x1`-`x3`, `x1$` (all just
`SPUR.SYSOP.S` `pull`/`rd.plr`/`wr.plr` staging for `spur.users` fields —
confirmed post-`mac2unix` at `SPUR.SYSOP.S:113`
`sh=s:ar=a:gh=g3:gl=g4:bh=g5:bl=g6:ep=m1:mk=m2:mm=m3:xp=m4`, which also
pins down `mm`'s field position in that record). And the Bar-module doc
block at `SPUR.BAR.S:465-471`, straight from the source's own comments:
`sc$`=screen clear, `xx$`=clear to end of line (Bar-local overlay),
`d4$`=message line 1, `d5$`=message line 2, `d6$`=return message from
routines (deferred message a sub-room hands back to the main loop).

**False positives to ignore** if they turn up in a future grep: `ag`
(tail of `flag=z1`), `ng` (tail of string literals like
`"…rvng="`/`"…wng="`), and `es`/`er`/`rn`/`us`/`os`/`st` (no real
assignments anywhere — likely mis-parsed substrings of other tokens).
