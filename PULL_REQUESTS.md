# Pull Request Catalog

A running index of pull requests and feature branches: identifier (PR number
and/or tip commit), name, and a short summary of what the change adds or fixes.

- **PR data** comes from GitHub (`gh pr list --state all`); it is independent of
  which local branch this file lives on.

Sections: Open PRs → Merged PRs (newest first).

---

## Open PRs

#### [#61](https://github.com/Pinacolada64/TADA/pull/61) `128-client-swiftlink` → `128-client-keymap` — Commodore 128 client: SwiftLink connection, live server text, and keymap follow-ups
- **Tip:** `80dc99e` (3 commits on top of `128-client-keymap`). **Stacked** on #59.
- The C128 client over SwiftLink: `swiftlink.asm` shared with the C64 via `{def: c128}`
  (the 128 KERNAL's NMI entry saves the registers and `$FF00` itself, so the handler
  exits via `jmp $ff33`; handler + `rx_buf` below `$4000`). "Connecting..." or
  RUN/STOP for the offline demo; answers the 40/80 menu; server text shown while
  typing; prompts move to the input row; clock and login color/blink streams
  handled, popup streams skipped with a cancel reply.
- Keymap follow-ups: banner names the scrollback page keys from the live keymap,
  grey arrows named "Grey Up/Down/Left/Right", "Home"/"End" → "Line Start"/"Line End"
  (C64 and 128 popups). Also `make vice128` with an emulated SwiftLink and
  `server/tools/bot_crowd.py`.
- `80dc99e` is a content-neutral merge of `128-client-keymap` (the branch first carried
  #59's keymap work as copies) so the PR stacks cleanly.
- Tests: `vice128_swiftlink_test.py` 8/8, keymap 9/9, VDC 8/8, clock 4/4. Not yet tried:
  login color apply with a real account, Keymap Editor Save while online, real hardware.

#### [#60](https://github.com/Pinacolada64/TADA/pull/60) `feature/room-notify-movement` → `master` — Room notices: movement, level-aware rooms, and other visible actions
- **Tip:** `cd22500` (2 commits), up to date with `master`.
- **Conflicts with #54 (merged 2026-09-30)** in one hunk of `server/simple_server.py`:
  both insert code just before the player moves -- FOLLOW ME's `bring_followers()` and
  the departure notice. Needs `master` merged in and the order of the two decided.
- Movement tells the room left "Ryan moves north." / "Ryan and his party move north."
  and the room reached "Ryan enters from the south." (new `room_notices.py`, called
  from `_move()`; covers walked level changes and fleeing). Also announced now:
  transporter/communicator beaming (and malfunctions), mount/dismount/lasso,
  respawn, the bar and the Shoppe/Ship's Stores/Allies' Guild/Jake's Stable/guild
  halls, wear/unwear, eat/drink, read, pray, cast.
- **Fix:** `send_room()` (JSON and PETSCII) and the "X is here" list compared the
  room *number* only, so every broadcast leaked into the same-numbered room on
  every other level; they now compare `(level, room)`.
- Full suite 4702 passed, 2 skipped. Not yet live-tested with two clients.

#### [#59](https://github.com/Pinacolada64/TADA/pull/59) `128-client-keymap` → `feature/kernal-free-screen` — Commodore 128 client: 80-column VDC output, scrollback, built-in Keymap Editor
- **Tip:** `9660cd3` (23 commits), up to date with `feature/kernal-free-screen`.
  **Stacked** — base is `feature/kernal-free-screen`, which has no PR of its own.
  Contains #58's commit (`8ef87c8`).
- The whole 128 client line so far: `$1C01` BASIC stub, 40/80 detection, ESC-T/ESC-B
  window, ported line editor, IRQ task table, Hourglass clock; `vdc.asm` /
  `vdc_screen.asm` 80-column output with a 150-line scrollback; the Keymap Editor
  built in (`keymap_host_128.asm`, `KEYMAP.CFG` shared with the C64).
- **PR description is stale:** tip `9660cd3` (pushed after it was written) forks the
  popup into its own `keymap_menu_128.asm` and makes scrollback paging a rebindable
  Page Up/Page Down on Alt + the grey arrows, replacing the C= + CRSR paging and the
  Makefile `sed` build the description still mentions.
- #61 (`128-client-swiftlink`, SwiftLink) is stacked on this PR.

#### [#58](https://github.com/Pinacolada64/TADA/pull/58) `128-client-hourglass` → `128-client` — client-128: Hourglass clock on the status row; lowercase charset, locked
- **Tip:** `8ef87c8` (1 commit), up to date with `128-client`.
- Right-aligned clock on status row 23 with `clock_reset`/`clock_putc`/`clock_commit`
  for the server's `$0b` clock stream; lowercase charset at boot (CHR$(14)), locked
  with CHR$(11). `vice128_clock_test.py` 4/4. Also inside #59.

#### [#53](https://github.com/Pinacolada64/TADA/pull/53) `feature/keymap-editor` → `feature/help-popup` — Keymap editor: rebindable nav functions, macros, combo capture
- **Tip:** `5112cff` (46 commits on top of `feature/help-popup`). **Stacked** — base is
  `feature/help-popup`, which has no PR of its own yet (see Feature branches below).
- Client-side keymap editor for the C64 client, persisted to `KEYMAP.CFG`: 15-slot
  `keymap_table` with table-driven dispatch, Keymap/Macro Editor popup pages,
  combo capture, F7 as a rebindable entry, and `keyboard_rollover.asm` (3-key
  rollover scan replacing the stock KERNAL scan).

#### [#50](https://github.com/Pinacolada64/TADA/pull/50) `fix/switch-consistency` → `master` — Fix `#<switch>` consistency
- **Tip:** `50d58cf` (3 commits), **behind `master` and conflicting** (2026-09-30: 4 hunks in
  `server/commands/board/board.py` and `server/commands/news.py`, from the board rework
  that landed after it) -- needs `master` merged in and those spots redone.
- `board edit` accepted alongside `board #edit`; `map.py`/`teleport.py` moved onto
  `parse_args()`'s switch/positional split; `news.py`/`banner_edit.py` gain `#`-switch
  forms (`news #post`, etc.). `ban.py` deliberately left as-is. Two bot scripts
  updated to `news #post`.

---

## Feature branches (no PR)

| Branch | Tip | Status |
|--------|-----|--------|
| `feat/helpstaff` | `52b49ca` | WIP snapshot — `helpstaff` command (ask an available staffer for help: request → relay to `PlayerFlags.HELPSTAFF_AVAILABLE` players → first to `helpstaff accept <name>` is teleported in). 182-line command + 237-line test, recovered verbatim from tag `pre-30-cleanup` after the #30 mishap. **Not wired**: still needs the `HELPSTAFF_AVAILABLE` flag added to `flags.py`, `Server.pending_help_requests` init, command registration, and an editplayer toggle. Isolated test run: 5 pass / 9 fail (all on the missing flag). |
| `feature/help-popup` | `e5ce52f` | Native C64 help / keyboard-shortcuts / credits popup overlay (`help_menu.asm` + `commands/help_menu.py`, 8 commits). Pushed to `origin` 2026-09-09 as a backup — was local-only. Supersedes the two overlay commits on the now-deleted `dwarf-hoard-floor`. **Needs a live end-to-end retest** before a PR (see the `LOAD $05` history). #53 (`feature/keymap-editor`) is stacked on this branch. |

---

## Merged PRs

| PR | Merge commit | Branch | Title |
|----|--------------|--------|-------|
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
