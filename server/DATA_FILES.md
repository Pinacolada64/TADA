# DATA_FILES.md — what's in every loose JSON file, and how to touch it

TADA has grown a lot of JSON files. This is the map: what each one holds,
which code loads/saves it, and — if anything in-game can edit it — which
command to use and why you'd bother. If a file desyncs from what you
expect at runtime, this is where to start figuring out why.

Two categories:

- **Group A — content data** (`server/*.json`, git-tracked). Hand-authored
  game content: item/monster/room definitions, flavor text. Almost all of
  these are load-only at runtime — edit them with a text editor while the
  server is stopped, the same way you'd edit code.
- **Group B — save state** (`server/run/**/*.json`, gitignored). Written
  by the running server as players play. Never hand-edit these casually;
  if you do, do it with the server stopped and know what you're touching.

## Group A — content data (server/*.json)

| File | Holds | Loaded/saved by | In-game editor? |
|---|---|---|---|
| `objects.json` | Every non-weapon, non-food item (armor, treasure, misc, cursed items, books), one record per item number. | `items.py`'s `load_items()`/`Item.read()`; attached to `ctx.server.items` at startup. | No write path. Read by `get.py`/`examine.py`/`wear.py`/`use.py`/`read.py`, shops, and `editplayer.py`'s `_give_object()` (browse + grant to a player). |
| `weapons.json` | Weapon records: damage, to-hit, sound, ammo type, class restrictions. | `items.py`'s `load_weapons()`/`Weapon.read()`; attached to `ctx.server.weapons`. | No write path. Read by combat resolution, `shoppe/armory.py`, `ship/armory.py`, `editplayer.py` (grant a weapon). |
| `rations.json` | Food/drink/cursed consumables, mount feed. | `Rations.read_rations()` (`items.py`), cached in `inventory.py`. | No write path. Read by `cast.py` (CONJURE FOOD/DRINK), `give.py` (mount feed), `jakes.py`, shop code, `editplayer.py`. |
| `allies.json` | Static ally/mount roster template: name, gender, strength, to_hit, flags, `description` (LOOK flavor text), `comment` (dev-only research notes, never shown to players). | `bar/ally_data.py`'s `load_allies()` — merges `run/server/net/ally-roster.json` overrides on top at load time. | No write path — ownership/status changes go to `ally-roster.json`, not here (see Group B). Read by Fat Olaf's bar, `give.py`, `look.py`'s `describe_ally()`. |
| `ally_farewell_quotes.json` | Canned quote an ally says when it leaves the party. | `ally_events/farewell.py`. | No write path; pure content. |
| `books.json` | Book flavor text, keyed by `objects.json` item number. | `books.py`'s `load_books()`; attached to `ctx.server.books`. | No write path. Read by `read.py`. |
| `level_1.json` … `level_7.json` | Per-level room/map data: exits, names, alignment, monster/item placement. | `map_file_2.py`'s `read_map()`; attached to `ctx.server.game_map`. | No live command writes these. **Exception:** the offline cron script `tools/nightly_guild_maintenance.py` bakes SPORT DUEL turf captures back into the relevant level file nightly. |
| `little_girl_hints.json` | Hint dialogue for the little-girl/Evilyn encounter (monster #106). | `encounters/little_girl.py`. | No write path; pure content. |
| `messages.json` | Recovered SPUR numbered message-file text (intro/teleport/quest flavor). | `messages.py`'s `load_messages()`; attached to `ctx.server.messages`. | No write path. Read by `new_player.py`, `encounters/galadriel.py`, travel code. |
| `monster_quotes.json` | Combat taunt/quote text per monster number. | `monsters.py`'s `load_quotes()`; also read (display-only) by `monster_editor.py`. | No write path — the monster editor shows quotes next to a monster but never saves them. |
| `monsters.json` | Master monster template catalog: stats, flags, spells, size. | `monsters.py`'s `load_monsters()`/`save_monsters()`. | **Yes.** `editmonsters`/`em` (admin, `commands/editmonsters.py` → `monster_editor.py`) edits and saves live, no restart needed. |
| `server_config.json` | Server-wide settings: game name, session limits, victory condition, invite policy, ports, host, dwarf_silver, etc. | `config.py`'s `ServerConfig`. | **Yes.** `config`/`cfg` (admin/DM, `commands/config.py`) edits most settings live. Also editable offline via `setup/server_setup.py`. |
| `tips.json` | Rotating login/help tip strings. | `tips.py` — reloaded fresh on every call, no caching. | No in-game write command. "Reloaded fresh" just means a sysop's hand-edit while the server is running takes effect immediately, without a restart. Read by the `tips` command. |

## Group B — save state (server/run/**/*.json, gitignored)

| File | Holds | Loaded/saved by | Written when | Desync fix |
|---|---|---|---|---|
| `run/server/net/ally-roster.json` | Overrides on top of `allies.json`: who owns which ally (SERVANT), status (FREE/SERVANT/UNCONSCIOUS/DEAD), mutated strength/hit_points. | `bar/ally_data.py`'s `load_ally_roster()`/`save_ally_roster()`. | Buying/selling at Fat Olaf's (`bar/fat_olaf.py`), an ally dying/being captured in combat (`encounters/monster.py`, `combat/engine.py`), scripted ally events. | `editplayer.py`'s ally-management screens call `load_allies()`/`save_ally_roster()` directly so a sysop can fix an ally stuck showing SERVANT/owned by a player who no longer has it. |
| `run/server/board.json` | Bulletin board threads/posts, plus board-wide config. | `board.py`'s `load_board()`/`save_board()`/`load_config()`/`save_config()`. | `board`, `board_reply`, `board_edit` commands. | — |
| `run/server/dwarf_state.json` | Wandering DWARF encounter's current room and live state. | `encounters/dwarf.py`. | Automatically as the dwarf moves/acts. | No dedicated command — delete the file to force a re-roll/relocation. |
| `run/server/guild_control.json` | Nightly territory report: per-level, per-guild room counts/percentages. | Written only by offline cron `tools/nightly_guild_maintenance.py`; read by `guild_hq/main.py`'s `_territory_report()`. | Nightly cron run. | If missing, players are told to "ask the sysop to run the nightly maintenance job" — i.e. run the script, don't hand-edit. |
| `run/server/guild-fist.json`, `guild-sword.json`, `guild-claw.json` | Per-guild-HQ state: treasury, item/food lockers, weapons box, chalkboard, transaction log, ban list. | `guild_hq/state.py`'s `load()`/`save()`. | Normal in-game guild interactions (deposit/withdraw, chalkboard, bans) via `guild_hq/main.py`. | — |
| `run/server/hit_contracts.json` | Active bounty/hit contracts placed via the Blue Djinn. | `bar/blue_djinn.py`. | Taking out a contract at the Blue Djinn. | No admin command — hand-edit (server stopped) to cancel/inspect a stuck contract if it desyncs from a player flag (see comment in `bar/thug_attack.py`). |
| `run/server/news.json` | Server news/announcement posts. | `news.py`'s `load_news()`/`save_news()`. | The `news` admin command. | — |
| `run/server/winners.json` | Append-only victory log. | `winners.py`'s `load_winners()`/`save_winners()`/`record_win()`. | Automatically by `victory.py` on a win. | Historical record; hand-trim only if you really mean to. |
| `run/server/player-<name>.json` | Full serialized Player object — stats, inventory, locker, party, flags, settings, position. | `player.py`'s `Player._json_path()`/`Player.save()`. | Continuously, any time `player.unsaved_changes` is set. | `editplayer.py` (admin) is the direct tool for hand-fixing one player's file; it also globs all `player-*.json` to cross-check ally ownership for desyncs. |
| `run/server/mail/<name>.json` | A player's mailbox: oldest-first `{from, timestamp, body, read}` records. | `mail.py`'s `load_mailbox()`/`save_mailbox()`/`add_message()`. | `mail` command replies; `page.py`'s offline-page fallback. | — |
| `run/server/net/login-<name>.json` | Just the account's hashed password. | Written by `new_player.py` on account creation; read by `login.py`, `password.py`. | Account creation / password change. | Delete to manually purge an account's ability to log in. |
| `run/server/editor_recovery/<name>-<timestamp>.json` | Crash-recovery snapshot of an in-progress mail/news/board edit (shared `text_editor.py`, **not** the PETSCII art canvas editor — that's `petscii_editor/store.py`'s separate `.canvas` files). | `text_editor.py`'s `save_recovery_file()`/`load_recovery_file()`. | A player mid-edit when `Server.graceful_shutdown()` runs (a scheduled SHUTDOWN). | Player-facing self-service: bare `edit` command or the login-time "resume?" prompt picks it back up. A sysop can delete stale ones to tidy the directory. |

## The short version

Out of every Group A file, only **`monsters.json`** (via `editmonsters`/`em`)
and **`server_config.json`** (via `config`/`cfg`) are ever written by a
live in-game command — everything else in Group A is hand-edited content,
loaded once at startup (or, for `tips.json`, reloaded fresh each call).
`level_1.json`–`level_7.json` have one narrow exception: the offline
`tools/nightly_guild_maintenance.py` cron job rewrites them nightly.

Everything in Group B is the opposite: written continuously by the running
server as players play, never meant to be committed, and the closest thing
to a "database" this project has.
