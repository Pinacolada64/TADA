# Pull Request Catalog

A running index of pull requests and feature branches: identifier (PR number
and/or tip commit), name, and a short summary of what the change adds or fixes.

- **PR data** comes from GitHub (`gh pr list --state all`); it is independent of
  which local branch this file lives on.

Sections: Open PRs → Merged PRs (newest first).

---

## Open PRs

### Stacked set — allies (#34 → #35, #36)

`#35` and `#36` branched off `ready-ally-weapons`, so they target it rather than
`master`; merge `#34` first and GitHub retargets them.

#### [#34](https://github.com/Pinacolada64/TADA/pull/34) `ready-ally-weapons` → `master` — READY / UNREADY: ready & unready allies' weapons
- **Tip:** `7121e39`
- `GIVE <weapon> to <ally>` no longer auto-readies the weapon — it just stows it
  in the ally's pack. The player chooses when the ally wields it via `READY`
  (bare list or `ready <name>`), which toggles `ally.readied_weapon`;
  `UNREADY <ally>` is the mirror. Ammo still loads only into a readied ally
  weapon. Alpha-tester feedback: auto-readying on GIVE made no sense.

#### [#35](https://github.com/Pinacolada64/TADA/pull/35) `feature/ally-stat-caps` → `ready-ally-weapons` — cap ally strength / to-hit / HP to SPUR ceilings; SPUR-faithful Fat Olaf MAINTAIN
- **Tip:** `6e8e0cc`
- Ally stats had no ceiling and ran away to absurd values. Adds caps derived
  from the SPUR source — strength **25** (sysop max 20 + Fat Olaf's `+5` hire),
  to-hit **0–9**, HP **50** (SPUR has no ally-HP stat; the port's `strength × 2`
  is bounded by the strength cap). Clamps every growth path: Fat Olaf hire, the
  Allies' Guild body-building, and Fat Olaf MAINTAIN — rewritten from the port's
  uncapped `+random(1,3)` per visit back to SPUR's "repair up to catalog
  strength, refuse at the ceiling" behaviour. `load_allies()` and
  `Party.from_json()` re-clamp on load, so existing inflated saves self-heal on
  next login. editplayer's "Character Names" menu is renamed
  **"Character / NPC Stats"** and gains an `[E]dit stats` option on the ally and
  horse prompts.

#### [#36](https://github.com/Pinacolada64/TADA/pull/36) `feature/give-drink-polish` → `ready-ally-weapons` — give ally pick-list + drink pool confirmation line
- **Tip:** `ed9ed59` (2 commits)
- `2d7eb28` — bare `give <item>` with no `to <name>` now prints a numbered list
  of the player's allies and prompts for a choice instead of erroring out;
  falls back to the old "Give it to whom?" hint when the player has no allies.
- `ed9ed59` — drinking from a pool of water appends
  "(Your thirst has been quenched.)" for non-expert players, who previously got
  no confirmation that thirst was restored.

### Others

| PR | Branch | Title |
|----|--------|-------|
| [#33](https://github.com/Pinacolada64/TADA/pull/33) | `feature/say-verb-switch` | Add `say #verb` and `#split`/`#unsplit` switches — inline equivalents of the PREFS dialogue-splitting toggle. |
| [#32](https://github.com/Pinacolada64/TADA/pull/32) | `feature/ooc` | Add `OOC` command for out-of-character room asides. |
| [#31](https://github.com/Pinacolada64/TADA/pull/31) | `fix/news-date` | Render news header/listing dates in the player's PREFS date format. |
| [#30](https://github.com/Pinacolada64/TADA/pull/30) | `feature/buffered-more-prompt` | Buffered More Prompt: buffer a turn's output and decide pagination once per turn. |

---

## Merged PRs

| PR | Merge commit | Branch | Title |
|----|--------------|--------|-------|
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
