# Pull Request Catalog

A running index of pull requests and feature branches: identifier (PR number
and/or tip commit), name, and a short summary of what the change adds or fixes.

- **PR data** comes from GitHub (`gh pr list --state all`); it is independent of
  which local branch this file lives on.

Sections: Open PRs → Feature branches (no PR) → Direct commits to master → Merged PRs (newest first).

---

## Open PRs

| PR | Branch | Tip | Summary |
|----|--------|-----|---------|
| [#68](https://github.com/Pinacolada64/TADA/pull/68) | `feature/c128-video-settings` | `767aaf6` | C128 client: its own Video Settings popup (`video_menu_128.asm`), fields by screen -- 40 col border/background/blink; 80 col VDC background, blink, and the 8563 hardware cursor (Cursor Soft/Block/Line, Flash Slow/Fast/Solid, editor ROM's own ESC-S/U/E/F values, `TADA128.CFG` +3/+4); live preview; invisible-text guard (background skips the text colors; login apply too). `swiftlink.asm` `sl_hold`/`sl_release` around Video Settings', the Keymap Editor's and the drive picker's serial-bus I/O -- SwiftLink NMIs mid-transfer hung x128 at `$E3A4-$E3B4` (stress test: unfixed build hung in round 2, fixed passed 24). 80-col history 150 rows @`$6000` -> 140 @`$6800`. x128 suites pass; **real hardware untested.** |
| [#69](https://github.com/Pinacolada64/TADA/pull/69) | `feature/monster-initiative` | `f6ad1fa` | Combat, ported from master + skip `SPUR.MAIN.S` `advent` / `SPUR.COMBAT.S` `m.attack`: hostile monsters attack on sight and swing before the first prompt (not after a surprise, nor charmable/friendly monsters, turf guards, wild horse, dwarf); monster swings at the top of every round, so READY/skip/failed FLEE cost a turn; missile/pole/mounted first strike, beaten by an ambush; "lost sight of you" for Thief/Assassin/Ring; flee blocks work again (`xp=1` stub, tough only); USE/CAST/EAT/DRINK/WEAR/READY/QUIT mid-fight (INV/STATS/LOOK/HELP free); tactical ambush rolled once per encounter; `bye` mid-fight no longer reads as Attack. Full suite 4829 passed incl. e2e; **not tried on the live server.** |
| [#70](https://github.com/Pinacolada64/TADA/pull/70) | `fix/shared-monster-kill` → `feature/monster-initiative` | `b271a66` | Stacked on #69 (retargets to `master` once #69 merges). Two parties fighting one monster could each kill it: after one landed the kill, the other's next ATTACK/LURK opened a fresh full-HP fight. New `monster_gone_for()` check plus session-only `player.slain_here` (keeps a `re_animates` kill dead until you leave the room, SPUR `md=1`); ATTACK/LURK refuse "The TROLL is already dead.". 9 new tests; 58 related tests re-run; **not tried live with two parties.** |

---

## Feature branches (no PR)

| Branch | Tip | Status |
|--------|-----|--------|
| `feat/helpstaff` | `52b49ca` | WIP snapshot — `helpstaff` command (ask an available staffer for help: request → relay to `PlayerFlags.HELPSTAFF_AVAILABLE` players → first to `helpstaff accept <name>` is teleported in). 182-line command + 237-line test, recovered verbatim from tag `pre-30-cleanup` after the #30 mishap. **Not wired**: still needs the `HELPSTAFF_AVAILABLE` flag added to `flags.py`, `Server.pending_help_requests` init, command registration, and an editplayer toggle. Isolated test run: 5 pass / 9 fail (all on the missing flag). |

---

## Direct commits to master (no PR)

| Commit | Summary |
|--------|---------|
| `7ba59db` | Help text markup. New `\|heading\|` token, a fixed alias for yellow on ANSI and PETSCII, the color of help section titles; `_heading()` now emits it, so prose like "your \|heading\|Usage\|reset\| line" or "see Notes below" matches the heading it points at. Line editor `.h` Examples blocks are now headerless two-column tables (command column at its natural width, 2-space gap, explanations wrap under their own column). Unescaped `\|token\|` fixed in `.h h` and the `.j` usage message; the `commandline` help topic now explains `\|` between choices and wraps its command examples in `\|command\|` instead of backticks. Documented in the `colors` topic and `.h colors`. |

---

## Merged PRs

| PR | Merge commit | Branch | Title |
|----|--------------|--------|-------|
| [#65](https://github.com/Pinacolada64/TADA/pull/65) | `2869b2c` | `fix/gothic-reverse-digits` | C64 client Gothic charset: reverse-video `$B8`/`$B9` were a reverse **9** in the **8** slot (the drive picker's highlight turned "1581" into "1591"), now exact inverses of `$38`/`$39`; `$E0`/`$E1` now inverses of the down/right arrows at `$60`/`$61`. Every glyph checked against its `$80+` partner in the built `.prg`; **not yet checked visually in VICE or on hardware.** |
| [#62](https://github.com/Pinacolada64/TADA/pull/62) | `d52786e` | `feature/drive-scan` | C64/C128 clients: serial-bus drive detection (shared `disk.asm`: `probe_device`, `scan_serial_bus`, `select_drive`, hang-proof `read_error_channel`), so no drive gives DEVICE NOT PRESENT instead of a hang; `DRIVE.MNU` drive picker (F5) with model lookup (`drive_id.asm`) and a saved data drive (`config_settings` block, `CFG_DATA_DRIVE`); `POPUP_SCREEN` fix for the C64 overlays; build number on both clients' startup status line; SCRATCH `$D3` → `$53` fix (63, FILE EXISTS on re-save). Carried #64. VICE suites pass; **real hardware, C128 80-column untested.** |
| [#64](https://github.com/Pinacolada64/TADA/pull/64) | `1760a96` (via #62) | `feature/border-style` | C64 Video Settings Border style: Single (Gothic box glyphs) or Double (CP437 double lines), swapped live in the charset by resident `border_style.asm` (`run_under_io` banks I/O out NMI-safely); saved in `TADA64.CFG` byte +2 and reapplied at boot. `vice_border_style_test.py` 34/34. Merged into `feature/drive-scan`, reached master with #62. |
| [#63](https://github.com/Pinacolada64/TADA/pull/63) | `fe9423e` | `feature/128-40col-vdc-scrollback` | C128 client: 40-column scrollback in VDC RAM. `vdc_detect_ram` (Fred's 8563 DRAM-size test: R28 bit 4, `$55`/`$AA` at `$4200`, does `$4300` echo?) sizes the ring: 64K → 614 rows at `$4000`, 16K → 179 rows at `$0800`. New `vic_screen.asm`: `vic_putc` draws/scrolls 40-column dialogue itself (no CHROUT window), CRSR and Page Up/Down scroll back as in 80 columns. VICE suites pass both layouts; **64K confirmed on a real metal-case C128DCR**; 16K on a flat 128 still untested (VICE 3.8 can't: bug #1981). |
| [#50](https://github.com/Pinacolada64/TADA/pull/50) | `d64bf82` | `fix/switch-consistency` | `#<switch>` consistency: `board edit` accepted alongside `board #edit`; `map.py`/`teleport.py` on `parse_args()`'s switch/positional split; `news`/`banner` admin sub-actions `#`-only (`news #post`, `banner #list`, ...) with a "needs a '#'" hint for the bare form. Master merged in first (`50bfeac`): 7 hunks against #51/#52's help-text rework, kept master's `\|command\|` text with the `#` spellings. |
| [#61](https://github.com/Pinacolada64/TADA/pull/61) | `f0092cf` | `128-client-swiftlink` | The whole C64/C128 client stack in one merge (91 commits): C64 help popup (`feature/help-popup`), Keymap Editor (#53), KERNAL-free screen output + two-row input area + lost-lines fix + Hourglass clock (`feature/kernal-free-screen`); the native C128 client (#58 and earlier), its 80-column VDC output with scrollback and built-in Keymap Editor (`KEYMAP128.CFG`, Alt, Page Up/Down on Alt + grey arrows, #59), and SwiftLink play. All C64/x128 VICE suites pass; **real-hardware tests still pending** for both clients. |
| [#59](https://github.com/Pinacolada64/TADA/pull/59) | `80dc99e` (via #61) | `128-client-keymap` | C128 80-column VDC output, 150-line scrollback, built-in Keymap Editor (forked `keymap_menu_128.asm`). Landed inside #61. |
| [#58](https://github.com/Pinacolada64/TADA/pull/58) | `8ef87c8` (via #61) | `128-client-hourglass` | C128 Hourglass clock on the status row; lowercase charset, locked. Landed inside #61. |
| [#53](https://github.com/Pinacolada64/TADA/pull/53) | `5cba399` (via #61) | `feature/keymap-editor` | C64 Keymap Editor: rebindable nav keys, macros, combo capture, 3-key rollover scan, `KEYMAP.CFG`. Landed inside #61 (was still a draft). |
| [#60](https://github.com/Pinacolada64/TADA/pull/60) | `2d9badf` | `feature/room-notify-movement` | Room notices (`room_notices.py`): movement ("Ryan moves north." / "Ryan enters from the south."), beaming, mount/dismount/lasso, respawn, entering the bar/shops/guild halls, wear/eat/drink/read/pray/cast. FOLLOW ME groups move as one: "Rulan leaves north, with Frodo and Sam following." / "... arrives from the south, with ...", "Rulan carries Bilbo, who is unconscious."; followers get only "You follow ...". Fix: `send_room()` and the "X is here" list compared room number only, leaking across levels. Master (#54) merged in with the departure notice ahead of the followers. Live-checked by the new `tools/bot_follow_me.py` (7/7). |
| [#54](https://github.com/Pinacolada64/TADA/pull/54) | `c859099` | `feature/follow-me` | SPUR's FOLLOW ME / STAY guild followers (`guild_follow.py`, `commands/stay.py`): online guildmates follow live on every exit, logged-off ones are carried and dropped off by STAY or at logoff; carried followers add to duel guild support. Deferred (TODO.md): unconscious-carry, guild-leader gate, `#!`/`<<` markers, editplayer entry for `followed_leader_name`. |
| [#52](https://github.com/Pinacolada64/TADA/pull/52) | `5847aa2` | `feature/command-token-sweep-2` | `\|command\|...\|reset\|` markup swept into the remaining player-facing command mentions: help text in 19 command files, the pre-login menu and hints, and 61 more strings in 26 files. |
| [#57](https://github.com/Pinacolada64/TADA/pull/57) | `1c7aae7` | `fix/tips` | Tips run through `substitute_tokens()` (`%n`/`%o`/`%p`/`%r` name and pronouns instead of "your character"/"his"); Spur wording and typo fixes, Dwarf tip "gold" -> "silver". |
| [#47](https://github.com/Pinacolada64/TADA/pull/47) | `535fe60` | `fix/dwarf-hoard-floor` | Dwarf hoard resets to a 500-silver floor on kill (SPUR.MISC.S `dh=0:dl=500`), not zero. |
| [#56](https://github.com/Pinacolada64/TADA/pull/56) | `ba85c8d` | `fix/client-load-current-drive` | C64 client: `load_petscii_editor` / `load_config_menu` LOAD overlays from the drive the client was loaded from (KERNAL FA, `$ba`, via `setlfs_current_drive`; falls back to 8 if below 8) instead of hard-coded device 8. Same fix + help/keymap sites on `feature/keymap-editor` (#53: `df5d47a`, `cd777d4`). **Not yet live-tested in VICE from drive 9.** |
| [#55](https://github.com/Pinacolada64/TADA/pull/55) | `1e8a675` | `fix/dwarf-horse-collision` | Stop the Dwarf overwriting other monsters (`_place_dwarf()` no longer writes over an occupied room, e.g. the wild horse in rooms 30/52/68); session autouse `_isolate_dwarf_state` fixture keeps tests off the live `dwarf_state.json`. Follow-up: `room_alignment.py`, `winners.py`, `simple_server.py:737` share the hard-coded-path pattern. |
| [#49](https://github.com/Pinacolada64/TADA/pull/49) | `1bdc83a` | `feat/text-editor-split-join` | Line editor `.e s`plit / `.e j`oin subcommands (undo/redo-checkpointed); `.e` "show buffers" moved to `.e b`. Merged alongside #51, which carried the same commits. |
| [#51](https://github.com/Pinacolada64/TADA/pull/51) | `666e6c6` | `feature/command-color-tokens` | PREFS-configurable \|command\|...\|reset\| markup token for literal command syntax, swept into player-facing text; `.e split`/`.e join`; `board` "read new" rework (`rn`/`ra`/`sa`/`ld` folded into the listing's "Read which" prompt, `sn` added). |
| [#48](https://github.com/Pinacolada64/TADA/pull/48) | `fdae53b` | `feature/reply-target-token` | `page`/`whisper` `#reply`/`#r` (reply to your last correspondent) and `#last [N]` (recent-recipient history, 10-entry ring buffer); `command_settings.page`/`.whisper` namespaces. |
| [#46](https://github.com/Pinacolada64/TADA/pull/46) | `fe4c1ed` | `feature/pose` | `pose` / `emote` / `me` command with a bare `:` shortcut (wired like `say`'s `"`). Third-person action text shown to the room verbatim, de-conjugated to first person for the actor. |
| [#36](https://github.com/Pinacolada64/TADA/pull/36) | `8ccff36` | `feature/give-drink-polish` | Drinking from a pool appends "(Your thirst has been quenched.)" for non-expert players. (The branch's other commit — a `give` ally pick-list — was dropped before merge: `master` already had it via `inventory_select`.) |
| [#33](https://github.com/Pinacolada64/TADA/pull/33) | `44be439` | `feature/say-verb-switch` | `say #verb` (comma-based dialogue attribution) + `say #split` / `#unsplit` (inline equivalents of the PREFS 'Y' toggle), with in-game help coverage. |
| [#32](https://github.com/Pinacolada64/TADA/pull/32) | `cac3684` | `feature/ooc` | `OOC` command for out-of-character room asides — `[OOC] Name: …`, identical line for everyone in the room including the speaker. |
| [#31](https://github.com/Pinacolada64/TADA/pull/31) | `71ed2e0` | `fix/news-date` | Render news header / listing dates in the player's PREFS date format (`news.py` counterpart to #43's board-header date work). |
| [#45](https://github.com/Pinacolada64/TADA/pull/45) | `a43fa1b` | `fix/scuttles-test` | Fix stale `skuttles` → `scuttles` assertions in `test_get_unconscious.py` (the code was renamed in `09c0544`; last remaining unmerged change from the `prefs` branch, now deleted). |
| [#44](https://github.com/Pinacolada64/TADA/pull/44) | `57d98b8` | `feature/buffered-more-prompt-clean` | Buffered More-Prompt: `ctx.send()` buffers a turn's output and the pagination decision is made once on the combined total (`network_context.flush_turn`). Clean re-land of #30 — see note below. |
| [#43](https://github.com/Pinacolada64/TADA/pull/43) | `ae8d411` | `sig-editor` | Multi-SIG bulletin board (34-commit line): `board/` + `commands/board/` packages, structural SIG/board editor, two-level picker, `>`/`<`/`>>`/`<<` navigation, `player_can_access()` gating wired into every board command, `board ra`/`board sa` (Read/Scan All new), ImageBBS-style Stat column + freeze/unfreeze, per-SIG/board intro screens, and the PREFS date-format-preset / text-editor word-wrap changes developed alongside. |
| [#41](https://github.com/Pinacolada64/TADA/pull/41) | `701a9fc` | `feature/inventory-select` | `inventory_select`: shared "pick an item of type X" helper; `READY`/`UNREADY`/`USE`/`DROP` item selection moved onto it. |
| [#42](https://github.com/Pinacolada64/TADA/pull/42) | `7fed25e` | `feature/give-take-transfer` | GIVE / TAKE item selection onto the shared `inventory_select` picker; `TAKE` can reroute an item ally→ally (reroute step only on the browse forms). **Landed via a plain `git merge` (`7fed25e`) before the PR was reviewed — real position is here in history (between #41 and #40), not by number; PR closed 2026-09-09.** |
| [#40](https://github.com/Pinacolada64/TADA/pull/40) | `09e47e3` | `level-8` | Convert the 2014 Forest of Canolbarth (365 rooms) to `level_8.json` and load it. |
| [#39](https://github.com/Pinacolada64/TADA/pull/39) | `c65464e` | `maps-path-a` | `tools/gen_level_maps.py` — printable adventure-style per-level SVG maps (grid layout for 1–7, breadth-first walk for 8). |
| [#38](https://github.com/Pinacolada64/TADA/pull/38) | `9737f22` | `rename-ally-find-silver` | Rename the ally gold-find event to "silver" (moving-off-gold-standard convention). |
| [#35](https://github.com/Pinacolada64/TADA/pull/35) | `d8928af` | `feature/ally-stat-caps` | Cap ally strength / to-hit / HP to SPUR ceilings (**25 / 0–9 / 50**); clamp every growth path (Fat Olaf hire, Allies' Guild body-building); rewrite Fat Olaf MAINTAIN from the port's uncapped `+random(1,3)` back to SPUR's "repair to catalog strength, refuse at the ceiling". `load_allies()` / `Party.from_json()` re-clamp on load. editplayer's "Character Names" menu renamed **"Character / NPC Stats"** with an `[E]dit stats` option on ally/horse prompts. |
| [#37](https://github.com/Pinacolada64/TADA/pull/37) | `8b0b5bb` | `prompt-fixes` | Prompt/action-key display fixes for alpha testers — wrap long `ctx.prompt()` option text into `preamble_lines`, use `{ctx.player.return_key}` instead of hard-coded "Enter"/"blank", normalize action-key notation to `[X]word`, and fix a flaky e2e login-pagination race. |
| [#34](https://github.com/Pinacolada64/TADA/pull/34) | `9f65f71` | `ready-ally-weapons` | READY / UNREADY: ready & unready allies' weapons — `GIVE <weapon> to <ally>` stows instead of auto-readying; `READY`/`UNREADY <ally>` toggle `ally.readied_weapon`. |
| #29 | `394cf09f` | `fix/e2e-login-banner-pagination` | Fix e2e login helpers hanging on the paginated login banner. |
| #28 | `15ebe593` | `worktree-fix-baseline-test-failures` | Fix 14 pre-existing baseline test failures. |
| #27 | `7dda8ecd` | `worktree-editplayer-armor-shield-range` | Bound editplayer Armor/Shield to 0–100; note STR/DEX/armor-class TODOs. |
| #26 | `3fff6eb9` | `worktree-test-table-subcommand` | Add `test #table` sub-command: zebra striping + border styles. |
| #25 | `45ea49ec` | `board-reply-prompt-mode` | Interactive per-message board reader with quote preview and mail (PROMPT_MODE). |
| #24 | `99c93dd5` | `worktree-text-editor-port` | Add ctx-aware in-game text editor; wire into `news.py`. |
| #23 | `77c34d40` | `bot-dev` | Merge bot-dev: ORDER command, tactical ambush, ammo fixes, bot tooling. |
| #22 | `09900d57` | `worktree-ally-charm-encounter` | Port monster-encounter surprise/charm rolls; fix `.` flag mislabel. |
| #21 | `39c00c1f` | `worktree-modular-swimming-sunrise` | Add ORDER command: Point Man / Flank Guard / Rear Guard servant deployment. |
| #20 | `8e6029f3` | `worktree-enchanted-doodling-nebula` | Consolidate `net_admin.py` into `server_setup.py`; remove `old_server/`. |
| #19 | `1c74c6dd` | `monster-editor` | Monster editor: presence system, virtual areas, and NPC broadcasts. |
| #18 | `51615479` | `new_player` | Client-side colour. |
| #16 | `d6e14115` | `new_player` | Bug fixes. |
| #13 | `5484c9c6` | `mintish/new_player_stats` | Fix stat key lookup. |
| #12 | `cb745e54` | `new_player_fix_client` | Add `globals.py` to hold `client` and `flag` variables. |
| #11 | `0a1824eb` | `dev/turkey_day_refactor` | Turkey-day refactor. |
| #10 | `48e45da5` | `dev/server_refactor` | Server refactor (net server/client separation). |
| #9  | `a68f7691` | `dev/server_refactor` | Server error consistency; report error code on client. |
| #8  | `1995ca4c` | `dev/server_refactor` | Refactor net server/client — separate network aspects from the demo app. |
| #7  | `b041da72` | `dev/login_hardening` | Login hardening; refactor server flow. |
| #6  | `1545b307` | `dev/net_extra_fields` | Add message field `changes` beyond simple text lines. |
| #5  | `0dde87b0` | `dev/net_basics` | Improve the client/server demo. |
| #4  | `95a9b3bf` | `dev/net_basics` | Initial implementation of net client/server. |
| #3  | `d389e327` | `dev/exits_txt_2` | Exits text (round 2). |
| #2  | `f64c5de0` | `dev/exits_fix` | Fix exits initializer; dynamically get the list of exit directions. |
| #1  | `45c606f4` | `dev/json_refactor` | JSON refactor. |

_PRs #14, #15, #17 do not exist (never opened or deleted)._

_PR [#30](https://github.com/Pinacolada64/TADA/pull/30) (`feature/buffered-more-prompt`) was merged as `ea2f4d7` but then **force-reset off `master`**: its stale branch had ~4 MB of committed logs / hardcopies / screen dumps plus an unrelated `helpstaff` command that rode onto master in the merge. Re-landed clean as #44 with only the three feature files. GitHub still shows #30 as "Merged". The discarded commit is preserved locally as tag `pre-30-cleanup`; its salvageable contents have since been dispositioned:_
- _`helpstaff.py` + test → branch `feat/helpstaff` (see above)._
- _`client-128.asm`, `input_editor.asm` → already byte-identical on `origin/128-client`; nothing to recover._
- _`dotbasic-v2.2.zip` → kept locally, now covered by `.gitignore` (`assembly-language/client/dotbasic-*.zip`)._
- _The rest (`screenlog.0`, `client.log.*`, `hardcopy.*`, `tada_screen_dump*.txt`, `print.dump`, screenshots) was scratch — discarded._

_Branch cleanup, 2026-09-09: `prefs` deleted (its one useful change landed as #45); `dwarf-hoard-floor` deleted (its Dwarf commit → `fix/dwarf-hoard-floor` / #47, its two C64-overlay commits superseded by `feature/help-popup`)._

_Merged remote branches that can now be deleted: `feature/give-take-transfer` (fully in `master`, PR #42 closed), plus the branches of #31/#32/#33/#36/#46 (`fix/news-date`, `feature/ooc`, `feature/say-verb-switch`, `feature/give-drink-polish`, `feature/pose`)._
