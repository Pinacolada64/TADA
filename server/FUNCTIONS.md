# FUNCTIONS.md
## Roadmap of functions across the TADA server codebase

Last updated: 2026-08-11 — manually maintained; update the date above when adding, moving, or removing functions.

## Refactor progress
| Step | Status | Description                                                                         |
|------|--------|-------------------------------------------------------------------------------------|
| 1    | ✅ Done | Fix `prompt_client()` and async bugs in `tada_utilities.py`                         |
| 2    | ✅ Done | Write `TerminalContext` — local terminal stand-in for `GameContext`                 |
| 3    | ✅ Done | Refactor `menu_system.py` to take `ctx` instead of `reader, writer, client, player` |
| 4    | ✅ Done | Wire `monster_editor.py` into the `ctx` pattern                                     |

## network_context.py
*(renamed from `context.py`)* Core context object hierarchy passed to all
commands and editor functions.

| Function / Class                                  | Notes                                                                               |
|---------------------------------------------------|-------------------------------------------------------------------------------------|
| `BaseContext`                                      | Interface layer — `send()`, `send_room()`, `prompt()`                              |
| `GameContext(BaseContext)` (dataclass)             | Holds `player`, `reader`, `writer`, `server`, `client`                              |
| `PETSCIINetworkContext(GameContext)`               | Commodore/PETSCII wire-protocol variant                                             |
| `GuestPlayer`                                      | Stub player for unauthenticated/guest sessions                                      |
| `GameContext.send(*lines)`                        | async — send text to this player only                                               |
| `GameContext.send_room(*lines, exclude_self)`     | async — send to all players in same room                                            |
| `GameContext.prompt(prompt_text, preamble_lines)` | async — send prompt, await single-line response; mirrors `terminal_context.py`'s `GameContext.prompt()` |

---

## terminal_context.py
*(STALE — confirmed this pass to be an actual stale FORK of
`network_context.py`, not just a renaming issue)* Despite its module
docstring's claim ("`TerminalContext` — local terminal (print/input), in
terminal_context.py"), the file defines **no `TerminalContext` class at
all** — never has, under the names below or any other. What it actually
contains is a second, older copy of `network_context.py`'s
`BaseContext`/`GameContext`/`PETSCIINetworkContext`/`GuestPlayer` classes
(same names, same dataclass fields, same `send`/`send_room`/`prompt`
signatures) that has since fallen behind: read side-by-side this pass,
this file's `GameContext`/`PETSCIINetworkContext` are missing
`network_context.py`'s pagination (`_wants_pagination`/`_paginate`/
`_send_formatted`, the `PlayerFlags.MORE_PROMPT` screenful-at-a-time
reader), `_pop_pending_pages()` (queued-page delivery, see
`commands/page.py`), and `PETSCIINetworkContext.send_raw()` (the sid_engine
raw-byte passthrough) -- none of which exist in `terminal_context.py`'s
copies. `simple_server.py` (the live server) imports its context classes
from `network_context.py`, confirmed via `grep -n "^from network_context"
simple_server.py`; `terminal_context.py`'s classes are only reachable
through `tada_utilities.py`, `encounters/droid_salvage.py`, and
`monster_editor.py` (imported there as `from terminal_context import
GameContext as TerminalContext` -- the alias masks that it's the same
class name as network_context.py's, not a distinct terminal-only context).
`run_local(coro)` is the one function that matches its documented purpose:
a plain `asyncio.run()` wrapper for editor entry points, still present and
correct.

**terminal_context.py vs terminal.py -- clarified this pass:** these are
genuinely unrelated modules that happen to share a name prefix, not the
same file under two names. `terminal.py` (546 lines, see its own section
below) is client-display/settings data -- `ClientSettings`, `ColorName`,
`Translation`, keyboard/color code enums -- with no context/ctx classes in
it at all. `terminal_context.py` is entirely GameContext-shaped
network-context code, with no terminal-*settings* content in it. No
overlap, no risk of confusing one for the other once you've opened both.

| Function / Class (current, real names)                 | Notes                                                                                         |
|----------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `GuestPlayer`                                           | Pre-login stub -- near-identical to `network_context.py`'s copy                                |
| `_GuestSettings` (dataclass)                            | `ClientSettings`-compatible stub for `GuestPlayer`                                             |
| `BaseContext`                                           | `send()`/`send_room()`/`prompt()` interface stubs -- no `_pop_pending_pages()` (network_context.py's copy has it, this one doesn't) |
| `GameContext(BaseContext)` (dataclass)                  | `player`/`reader`/`writer`/`server`/`client`; `send()`/`send_room()`/`prompt()`/`set_prompt()`/`for_guest()` -- no pagination, no pending-page popping |
| `PETSCIINetworkContext(GameContext)`                    | Raw-PETSCII-byte variant; `send()`/`prompt()`/`send_room()`/`for_guest()` -- no `send_raw()`   |
| `run_local(coro)`                                       | Convenience wrapper around `asyncio.run()` for editor entry points; matches its doc, still correct |

---

## net_common.py
Wire-protocol primitives, password hashing, and the shared `Message`/`Mode`/
`MessageType` types used across the network layer -- not a "common utils
grab-bag" so much as the load-bearing definitions everything else (`net_client.py`,
`net_server.py`, `network_context.py`, `terminal_context.py`, dozens of
`commands/*.py`) imports as `net_common as nc`. Actively touched
(`append_battle_log` -- collapsed ~10 duplicated `_append_battle_log`/
`_append_capture_log` copies into this one shared helper).

| Function / Class                                       | Notes                                                                                          |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `run_server_dir` (module global)                          | `str \| None`; read dynamically (not import-time) by `user_dir()`/`Player._json_path()` so tests can isolate it to a `tmp_path` after import |
| `user_dir()`                                               | Returns `Path` to per-account `login-<username>.json` credential directory                    |
| `append_battle_log(entry)`                                 | Appends one UTC-timestamped line to `battle.log`; shared by monster kills, ally desertion/recruitment, guild duels, thefts, prayers, mount captures, etc. |
| `hash_password(password)` / `verify_password(password, stored)` | bcrypt hashing; passwords always compared lowercased (C64 keyboards send uppercase by default); `verify_password` transparently upgrades a legacy plaintext match to a bcrypt hash via its `rehashed` return value |
| `K` (StrEnum)                                              | Credential-file JSON key names (`id`, `password`, `code`, `hash`, `salt`, `invite`, `user`, `translation`) |
| `Mode` (StrEnum)                                            | Connection state machine: `init`, `guest`, `new_player`, `login`, `app`, `bye`                 |
| `MessageType` (Enum)                                        | `INIT`, `SYSTEM`, `ANNOUNCEMENT`, `REGULAR`, plus lowercase player-communication members `shout`/`page`/`say`/`mumble`/`emote`/`whisper` (inconsistent casing vs. the uppercase members above, not resolved this pass) |
| `_default_serializer(o)`                                    | Private -- JSON default hook: Enum by name, dataclass via `asdict`, else `__dict__`/`str()`   |
| `to_jsonb(obj)` / `from_jsonb(b)`                            | Serialize to/from JSON bytes for the wire; `from_jsonb` returns `None` on empty/invalid input  |
| `Message` (dataclass)                                       | The wire envelope: `lines`, `changes`, `choices`, `prompt`, `error`, `error_line`, `mode`, `type`; `__post_init__` normalizes a bare string `lines` into a one-item list |
| `ClientInfo` (dataclass)                                     | `user_id`, `handler`, `connected_time`, `last_active` -- used by `ClientManager` below         |
| `ClientManager` (class)                                     | *(new, undocumented until now -- appears unused by the live game; see note below)* `add_client`/`remove_client`/`update_activity`/`get_online_client_info`/`broadcast`, thread-lock-guarded |
| `client_manager` (module-level `ClientManager()` instance)  | *(new, undocumented until now)*                                                                |

`ClientManager`/`client_manager` are exercised only by `new_server.py` (see
below, itself unreferenced by the live game) and are not the mechanism
`simple_server.py` actually uses for tracking connections (`Server.clients`,
a plain dict keyed by `addr`) -- so this class, while real code, is not on
the live server's path today.

---

## net_client.py (916 lines)
A synchronous, blocking-socket TCP client with its own handshake/receive-thread/
`cmd`-style dispatch loop -- written for a standalone CLI/bot client, not
for the live async server. Confirmed this pass: **only the `Client`
dataclass itself is used by the live game**, and only as a plain per-connection
data container (`client.mode`, `client.translation`, `client.room`, etc.)
attached to `ctx.client` by `network_context.py`/`simple_server.py`/
`terminal_context.py`/`new_server.py` -- none of those call sites use
`Client.connect()`/`.default()`/`._send_data()`/`._receive_messages()` or
any of this file's other socket-I/O machinery; that machinery is only
exercised by this module's own `main()` when run standalone. `main()` itself
is broken as written -- it references an undefined `server` and `Mode.APP`
(no such member; `net_common.Mode`'s app-mode value is lowercase `Mode.app`)
that would raise `NameError`/`AttributeError` immediately if actually run.

| Function / Class                                            | Notes                                                                                            |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| `Init` (dataclass)                                            | Handshake payload: `id`, `key`, `mode`, `protocol`; `__post_init__` forces `mode=Mode.init`, `translation=Translation.ANSI` |
| `Client` (class)                                               | Per-connection state; live usage is purely as a data container (see note above). ~14 methods, below |
| `Client.set_user(user_id)` / `.set_password(password)`         | Trivial setters                                                                                    |
| `Client.connect(host, port, server_id, server_key, protocol_version, translation)` | Blocking-socket handshake + starts a background `_receive_messages` thread; standalone-CLI-only in practice |
| `Client.default(command)`                                     | `cmd`-style command dispatch -- formats guest/login/plain commands and sends via `_send_data()`    |
| `Client._send_data(data)` / `Client._receive_messages()`      | Private -- raw socket write / threaded receive loop with `select()`                                |
| `Client.init_success_lines(request)` / `._process_mode(request)` | Response handling for the standalone CLI: prints lines, tracks mode, dispatches to `_handle_*`  |
| `Client._handle_command_result(result)` / `._handle_room_change(data)` / `._handle_room_data(room_data)` | Private -- CLI-side response formatting for those message shapes                    |
| `Client.close()` / `Client._cleanup()`                         | Socket teardown                                                                                    |
| `Client.process_request(request)`                              | Blocking `input()`-based request/response helper for the CLI loop                                 |
| `CommodoreClient(Client)`                                      | "Client that sends just lines of text for Commodore clients" -- overrides `_send_data`/`_receive_data` |
| `get_input(prompt, hidden=False)`                              | Wraps `input()`/`getpass.getpass()`                                                                |
| `main()`                                                       | Standalone CLI entry point -- **broken as written**, see note above; not exercised by any test or the live server |

---

## net_server.py (515 lines)
*(superseded/dead — confirmed this pass)* A `socketserver.ThreadingMixIn` +
inner-asyncio-`Server.Server` alternate server implementation, predating
(or an abandoned parallel to) `simple_server.py`, which is the actual live
server (see `simple_server.py`'s own section above and `player.py`'s
`_ss`-preferred-over-`_ns` fallback logic). **Nothing in the live game path
imports this module.** It's reachable only from: `player.py` (a
try/except fallback -- `import net_server as _ns`, used only if `import
simple_server as _ss` itself raises, which it doesn't in production),
`new_server.py` (itself unreferenced anywhere, see below),
`create_character.py` (itself unreferenced anywhere, see below), and one
test file (`tests/social/test_message_handling.py`). The module docstring
literally embeds a comment attributing its design to "simple_server.py",
suggesting this was an earlier/alternate draft of that server rather than
something meant to run alongside it.

| Function / Class                                              | Notes                                                                                             |
|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `Init` (dataclass)                                                | Local handshake payload -- separate definition from `net_client.py`'s `Init`                        |
| `connected_users` (module global `set`) / `server_lock` (module global `threading.Lock`) | Legacy globals -- see `player.py`'s fallback wiring to these under the `_ns` name          |
| `Error` (StrEnum)                                                 | `server1`, `server2`, `user_id`, `login1`, `login2`, `multiple`                                      |
| `Message` (module alias)                                          | `= nc.Message`, i.e. `net_common.Message`                                                            |
| `Server(socketserver.ThreadingMixIn, socketserver.TCPServer)`     | Outer class; its body is almost entirely a **nested inner class also named `Server`** (`Server.Server`) that does the real work via asyncio -- an unusual/confusing double-`Server` shape, not cleaned up this pass |
| `Server.Server.__init__(host, port)`                              | Builds `server_init_object`, loads `level_<n>.json` map files 1-7 into a `Map`                       |
| `Server.Server.send_message(writer, obj)` / `.receive_message(reader)` | async JSON-over-newline read/write                                                             |
| `Server.Server.handle_connection(reader, writer)`                 | async -- per-client lifecycle: handshake, login, then a `Mode.login`/`Mode.app` dispatch loop         |
| `Server.Server._perform_handshake(reader, writer, addr)`          | async -- checks `server_id`/`server_key`, warns (doesn't reject) on protocol-version mismatch         |
| `Server.Server.start()`                                           | async -- `asyncio.start_server` + `serve_forever()`                                                   |
| `Server.Server._handle_login(reader, writer, addr, client)`       | async -- sends the hardcoded "Totally Awesome Dungeon Adventure" login banner                         |
| `Server.Server.handle_login_command(writer, username=None)`       | async -- mock login handler (`await asyncio.sleep(1)` "simulated processing delay"), not real auth   |
| `Server.Server.handle_login_mode(client, in_message, writer)`     | async -- parses `connect`/`guest`/`new` commands out of raw message lines                             |
| `Server.Server.handle_app_mode(client, in_message, writer, addr)` | async -- lazily creates a `CommandHandler`/`command_processor` and dispatches text through it        |
| `Server.Server._save_client_state(client)`                        | async -- dumps `client.__dict__` (JSON-safe subset) to `player_data/<username>.json`; separate/incompatible persistence path from `player.py`'s real `Player.save()` |
| `Server.error_ban()` / `.error_login_failed(message)`              | Return canned `Message` objects                                                                       |
| `Server.init_success_lines()` / `.login_fail_lines()` / `.process_login_success(user_id)` / `.process_message(data)` | Docstrings say "OVERRIDE in subclass" -- base-class stub behavior, not itemized further |
| `handle_new_connection(self, reader, writer)`                     | Module-level (not a method despite `self` -- orphaned/dead code smell), body is just `pass`           |
| `start(host, port, _id, key, protocol, handler_class)`            | Module-level entry point -- spins up `Server.Server` on a dedicated background thread                 |

---

## tada_utilities.py
General-purpose utilities. Mix of async (ctx-aware) and pure sync functions.

### Async / ctx-aware
| Function                                                                                | Status     | Notes                                          |
|-----------------------------------------------------------------------------------------|------------|------------------------------------------------|
| `prompt_client(ctx, preamble_lines, prompt_text)`                                       | ✅ Fixed   | Correctly uses `ctx.reader`/`ctx.writer` now   |
| `input_string(ctx, default='', prompt='', allow_empty=True, keep_msg=True, reminder='Please enter something.')` | ✅ OK | Loops on `prompt_client(ctx, ...)`; empty/`default` input returns `default` (or reprompts with `reminder` if `allow_empty=False`, unless expert mode, which just keeps `default`) |
| `input_number_range(ctx, default=None, prompt_msg='', min_value=1, max_value=10, out_of_bounds_msg=None)` | ⚠️ Bug | **Real bug, confirmed this pass:** line calls `await ctx.prompt(ctx, prompt_text=f'...')` — passes `ctx` itself as the positional `prompt_text` argument *and* `prompt_text=` as a keyword, which raises `TypeError: prompt() got multiple values for argument 'prompt_text'` the instant this runs. Not currently reached by any live ctx-based caller — `grep` across `commands/`, `bar/`, `shoppe/` finds zero call sites; the only callers are `terminal.py`/`create_character.py` (both stale pre-ctx-refactor files, calling with `player=`/positional args and no `await` — already broken independently) and `tada_utilities.py`'s own `__main__` demo block (also broken — references an undefined `ctx`). Latent/dead-code bug, not exercised in production. |
| `set_logging_level(ctx)`                                                                | ✅ OK | async — shows current root logger level, prompts via `input_string`, applies D/I/W/E/C choice |
| `text_pager(ctx, text_lines)`                                                           | GONE | Confirmed this pass: no longer exists anywhere in `tada_utilities.py`. Only references left in the tree are a commented-out import in `threaded_messages.py` and one live call `tada_utilities.text_pager(text, p)` in `create_character.py` (line 740) that would raise `AttributeError` if ever reached — but `create_character.py` is itself stale/pre-refactor (see backlog section) and not part of the live ctx pipeline. |
| `header(ctx, header_text)`                                                              | ✅ OK       | async, sends underlined header                 |
| `format_quote(quote_text, reader_name)`                                                 | *(new, undocumented)* | Not in original doc                 |

### Pure / sync (no ctx)
| Function                                           | Status | Notes                                      |
|----------------------------------------------------|--------|--------------------------------------------|
| `oxford_comma_list(items)`                         | ✅ OK   | Pure string utility                        |
| `grammatical_list(item_list)`                      | ✅ OK   | Pure string utility                        |
| `a_or_an(string, capitalize)`                      | ✅ OK   | Pure string utility                        |
| `get_article_and_quantity(item_name)`              | ✅ OK   | Pure string utility                        |
| `list_players_in_room(player_list)`                | ✅ Fixed | Correctly calls `oxford_comma_list(player_list)` now |
| `make_random_id()`                                 | ✅ OK   | Returns random int 1-65536                 |
| `input_yes_no(ctx, prompt, ...)`                   | ✅ Changed | Now `async`, takes `ctx` (was sync/no-ctx) |
| `get_pronoun(character, pronoun_type, capitalize)` | ✅ OK   | Player-aware, pure output                  |
| `frame_text(p, text, title, width)`                | ✅ OK   | Returns list[str], no I/O                  |
| `tip(p, title, message)`                           | ✅ OK   | Returns list[str], respects EXPERT_MODE    |
| `bulleted_list_format(text, width, ...)`           | ✅ OK   | Pure formatting                            |

---

### Needs full rewrite
| Function                       | Notes                                                        |
|--------------------------------|--------------------------------------------------------------|
| `fileread(ctx, filename)`      | ✅ Rewritten — now takes `ctx` as documented goal (was `fileread(self, filename, p)`) |
| `game_help(self, player, arg)` | REMOVED — no longer exists in the file at all                |

---

## menu_system.py
Hierarchical menu system. All functions now take `ctx` (GameContext or TerminalContext).

| Function / Class                          | Notes                                                                                |
|-------------------------------------------|--------------------------------------------------------------------------------------|
| `MenuItem` (dataclass)                    | `text`, `shortcuts`, `dot_leader_handler`, `submenu`, `action`; `is_header` property |
| `Menu` (dataclass)                        | `title` (str or callable, re-evaluated per redraw), `columns`, `menu_items`; `selectable`/`rendered_title` properties |
| `_vis_len(s)`                              | *(new, undocumented)* visible-width helper (strips `\|token\|` markup)               |
| `_InvalidChoice` / `INVALID_CHOICE`       | *(new, undocumented)* sentinel — distinguishes "bad input, redisplay menu" from "cancel" |
| `format_menu_lines(ctx, menu)`            | Returns `list[str]`; reads screen width from `ctx.player.client_settings`            |
| `print_menu(ctx, menu)`                   | async — formats and sends menu via `ctx.send()`                                      |
| `get_user_choice(ctx, menu, stack_depth)` | async — prompts via `ctx.prompt()`, returns `MenuItem`, `None` (cancel), or `INVALID_CHOICE` |
| `navigate_menu(ctx, menu_stack)`          | async — interactive loop; pushes submenus, pops on cancel, redisplays on `INVALID_CHOICE` |
| `run_menu(ctx, menu_hierarchy)`           | async entry point; accepts single `Menu` or `list[Menu]`                             |

---

## formatting.py
Pure text formatting functions. No I/O, no ctx — strings in, strings out.
Called by `ctx.send()` before writing to wire or terminal.

| Function / Class                                       | Notes                                                                                                                      |
|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `HasClientSettings` (Protocol)                         | Minimum interface needed from a settings object: `screen_columns`, `screen_rows`                                           |
| `ColorCodec` (Protocol)                                | Pluggable color translation: `highlight_on()`, `highlight_off()`, `reset()`                                                |
| `ANSICodec` (dataclass)                                | ANSI color codes via colorama                                                                                              |
| `PlainCodec` (dataclass)                               | No color — plain ASCII output                                                                                              |
| `PETSCIICodec` (dataclass)                             | Commodore reverse-video highlighting for `[bracket]` text; full 16-color palette is separately available via `\|token\|` substitution (see `PETSCII_CONTROL_CODES` below)                                                |
| `codec_for_settings(settings)`                         | Returns appropriate `ColorCodec` for a `ClientSettings` object                                                             |
| `highlight_brackets(text, codec)`                      | Wraps `[bracketed text]` with codec color codes                                                                            |
| `wrap_text(text, width, ...)`                          | Word-wraps a string, returns `list[str]`                                                                                   |
| `format_bullet(text, width)`                           | Formats a bullet point with hanging indent                                                                                 |
| `format_line(text, width, codec)`                      | Highlights + wraps one logical line, returns `list[str]`                                                                   |
| `format_lines(lines, settings, codec)`                 | Formats a list of lines for a player's terminal                                                                            |
| `COLOR_NAME_TO_TOKEN` (dict)                           | Maps `terminal.ColorName` enum values to `{token}` names; bridge between player-facing color names and the encode pipeline |
| `ANSI_COLOR_CODES` (dict)                              | `{token}` name → colorama ANSI escape string; token names match `PETSCII_CONTROL_CODES`                                    |
| `ansi_encode(text)`                                    | Replaces `{token}` sequences with ANSI escape codes; unknown tokens left as-is                                             |
| `ansi_encode_lines(lines)`                             | Applies `ansi_encode()` to each line in a list; use after `format_lines()` in `GameContext.send()`                         |
| `PETSCII_CONTROL_CODES` (dict)                         | `{token}` name → raw Commodore control byte value (colors, cursor, case)                                                   |
| `PETSCII_CODE_NAMES` (dict)                            | Reverse lookup: raw byte → token name, for debugging                                                                       |
| `petscii_encode(text, codec_name)`                     | Encodes a string for Commodore: text via cbmcodecs2, `{tokens}` as raw control bytes spliced in after                      |
| `petscii_encode_lines(lines, codec_name, line_ending)` | Encodes a list of formatted strings, joined with CR for Commodore line endings                                             |
| `flatten_send_args(*args)`                             | Flattens `ctx.send()` args into `list[str]`; shared by both context classes                                                |
| `make_header(text, char)`                              | Returns `[text, underline]` as `list[str]`                                                                                 |
| `make_rule(width, char)`                               | Returns a horizontal rule string                                                                                           |
| `make_box(lines, title, width)`                        | Wraps lines in an ASCII box, returns `list[str]`                                                                           |
| `make_box_for_settings(...)`                           | *(new, undocumented)*                                                                                                      |
| `plain_encode(text)` / `plain_encode_lines(lines)`     | *(new, undocumented)* strips `{token}` markup for ASCII/screenreader mode                                                  |
| `_visible_len(s)`                                      | *(new, undocumented)* visible-width helper (mirrors `menu_system.py`'s `_vis_len`)                                         |
| `border_style_for_ctx(ctx)`                             | *(new, undocumented)*                                                                                                      |
| `hrule_char(ctx)`                                      | *(new, undocumented)*                                                                                                      |
| `guild_sigil_for(ctx, alignment)`                       | *(new, undocumented)* colorized/terminal-appropriate guild sigil                                                           |
| `underline(text)`                                      | *(new, undocumented)*                                                                                                      |
| `_build_color_name_to_token()` / module `__getattr__`  | *(new, undocumented)* — the dunder is unusual, worth a closer look during the full rewrite                                |
| `_MockSettings`                                        | *(new, undocumented)* test helper                                                                                          |

Resolved this pass: the "PETSCII full palette TODO" note is **stale — the palette is complete**. `PETSCIICodec`'s own docstring now states plainly: "Full 16-color palette is available via `\|token\|` substitution in `petscii_encode()` — see `PETSCII_CONTROL_CODES` below." `PETSCII_CONTROL_CODES` contains all 16 CBM color codes (`black`, `white`, `red`, `cyan`, `purple`, `green`, `blue`, `yellow`, `orange`, `brown`, `light_red`, `dark_gray`, `mid_gray`, `light_green`, ...) plus cursor/case control tokens. No TODO remains in the source.

## monsters.py
Monster data and flag definitions. Shared by editor and game server.

| Function / Symbol               | Notes                                 |
|---------------------------------|---------------------------------------|
| `monster_flag_labels` (dict)    | Snake_case key → human-readable label |
| `load_monsters(path)`           | Returns `list[dict]` from JSON        |
| `save_monsters(monsters, path)` | Writes `list[dict]` to JSON           |
| `get_monster(monsters, number)` | *(new, undocumented)* look up one monster dict by number |
| `monster_flags` (list)          | *(new, undocumented)* raw symbol/key tuples `monster_flag_labels` is derived from |
| `monster_sizes`                 | *(new, undocumented)*                 |
| `all_monster_keys`              | *(new, undocumented)*                 |

---

## monster_editor.py
*(HEAVILY STALE — see FUNCTIONS.md full-rewrite plan)* The "will eventually be
wired into ctx pattern" note is now true — refactor progress step 4 (top of
this file) is done — but every function below has been replaced. Current file
is fully async/`ctx`-based, using `menu_system.Menu` objects instead of a
custom numbered-menu loop.

| Function (OLD — none of these exist anymore) | Notes                                                             |
|-----------------------------------------------|-------------------------------------------------------------------|
| `prompt(msg, default)`                        | GONE                                                               |
| `confirm(msg)`                                | GONE                                                               |
| `pause()`                                     | GONE                                                               |
| `header(title)`                               | GONE                                                               |
| `numbered_menu(items, title, extra_inputs)`   | GONE — replaced by `menu_system.Menu`/`MenuItem`                   |
| `load_monster_locations(level_files)`         | still present                                                      |
| `load_quotes(path)`                           | GONE from this file (lives in `monsters.py` now)                   |
| `load_weapons(path)`                          | still present                                                      |
| `active_flags(monster)`                       | still present                                                      |
| `show_monster(m, quotes, weapons, locations)` | renamed to `format_monster(...)`; `show_monster(ctx, ...)` now sends via ctx |
| `list_quotes(quotes)`                         | GONE — replaced by `build_quote_menu(...)`                         |
| `edit_basic(m, quotes, weapons)`              | GONE — replaced by `build_edit_menu(...)`                          |
| `edit_flags(m)`                               | GONE — replaced by `build_flags_menu(...)`                         |
| `edit_monster(m, quotes, weapons, locations)` | GONE — replaced by `build_monster_menu(...)`                       |
| `search_by_attribute(monsters, weapons)`      | still present                                                      |
| `main()`                                      | now `main(ctx=None)`                                               |

**Current functions (not previously documented):** `build_quote_menu`,
`build_flags_menu`, `build_edit_menu`, `build_monster_list_menu`,
`build_monster_menu`, `search_by_name`, `search_by_flag`,
`show_special_weapons`, `format_monster`.

---

## gbbs_io.py
Binary file reader for SPUR/GBBS/ACOS data files.

| Function / Symbol                             | Notes                                                    |
|-----------------------------------------------|----------------------------------------------------------|
| `RecordInfo` (dataclass)                      | `record_size`, `field_count`, `description`              |
| `RECORD_INFO` (dict)                          | Known record sizes keyed by filename stem                |
| `read_file(path)`                             | Reads binary, strips high bits, replaces 0xAC separators |
| `normalize(data)`                             | Auto-detects and strips Apple II high bits               |
| `strip_high_bits(data)`                       | Strips bit 7 from all bytes                              |
| `iter_records(data, record_size, skip_first)` | Yields `(record_num, fields)` tuples                     |
| `read_count(data, record_size)`               | Reads record count from record 0                         |
| `record_size_for(filename)`                   | Looks up record size from `RECORD_INFO`                  |
| `_has_high_bits(data)`                        | *(new, undocumented)*                                     |
| `_split_record(...)`                          | *(new, undocumented)*                                     |

---

## convert_monster_data.py
Converts `monsters.txt` binary to `monsters.json`.

*(STALE — diverged)* The dataclass-based API below does **not** match the
current `convert_monster_data.py`, which is a simpler old-style script
(`class Monsters(object)`, `read_stanza`, `diskin`, `convert`). The API
documented below now actually lives in a sibling, undocumented file:
**`convert_monster_data_fixed.py`**.

| Function / Symbol                      | Notes                                      |
|----------------------------------------|--------------------------------------------|
| `MONSTER_FLAGS` (list)                 | `(symbol, key)` pairs, longest-match-first |
| `ALL_FLAG_KEYS` (list)                 | Derived from `MONSTER_FLAGS`               |
| `MONSTER_SIZES` (dict)                 | `int → str` size names                     |
| `EMPTY_FLAGS` (dict)                   | All flags set to False                     |
| `Monster` (dataclass)                  | Full monster schema                        |
| `parse_flags(flag_str)`                | Returns `(flags_dict, quote_number)`       |
| `parse_monster(record_num, fields)`    | Returns `Monster` or `None`                |
| `convert(txt_filename, json_filename)` | Main conversion entry point                |

---

## convert_weapon_data.py
Converts `weapons.txt` binary to `weapons.json`.

*(STALE — diverged, same pattern as convert_monster_data.py above)* Current
file uses old-style `class Weapons(object)`/`read_stanza`/`diskin`. The
dataclass-based API below now lives in a sibling, undocumented file:
**`convert_weapon_data_new.py`**.

| Function / Symbol                                 | Notes                                |
|---------------------------------------------------|--------------------------------------|
| `WEAPON_KINDS`, `WEAPON_CLASSES`, `WEAPON_SOUNDS` | Lookup tables                        |
| `Weapon` (dataclass)                              | Full weapon schema incl. `sfx_index` |
| `parse_weapon(record_num, fields)`                | Returns `Weapon` or `None`           |
| `convert(txt_filename, json_filename)`            | Main conversion entry point          |

---

## convert_item_data.py
Converts `items.txt` binary to `items.json`.

| Function / Symbol                                   | Notes                           |
|-----------------------------------------------------|---------------------------------|
| `ITEM_TYPES` (dict)                                 | Type letter → name              |
| `AMMO_CARRIER_NUMBERS` (set)                        | Hard-coded carrier item numbers |
| `AmmoInfo` (dataclass)                              | `rounds`, `damage`, `used_with` |
| `Item` (dataclass)                                  | Full item schema                |
| `parse_ammo(name_raw, after_pipe)`                  | Parses `\|` ammo spec           |
| `parse_item(record_num, fields)`                    | Returns `Item` or `None`        |
| `convert(txt_filename, json_filename, record_size)` | Main conversion entry point     |

---

## convert_quotes.py
*(MODULE GONE — no file, no renamed equivalent found anywhere in the tree)*
`monster_quotes.json` itself still exists; its converter script is simply
missing now.

| Function                               | Notes                                     |
|----------------------------------------|-------------------------------------------|
| `is_allcaps(text)`                     | Returns True if >80% uppercase            |
| `sentence_case(text)`                  | Converts all-caps string to sentence case |
| `normalize(text)`                      | Applies sentence_case if needed           |
| `convert(txt_filename, json_filename)` | Main conversion entry point               |

---

## ammo_cross_reference.py
*(renamed from `cross_reference.py`)* Cross-references ammo items against weapons.

| Function                                          | Notes                                                                 |
|---------------------------------------------------|-----------------------------------------------------------------------|
| `find_weapon(used_with, weapons)`                 | Substring match, returns list of matching weapons                     |
| `cross_reference(items, weapons, unmatched_only)` | Prints full cross-reference report                                    |
| `main()`                                          | CLI entry point with `--items`, `--weapons`, `--unmatched-only` flags |

---

## show_sfx.py
Displays and edits weapon sound effect indices.

| Function                 | Notes                                                 |
|--------------------------|-------------------------------------------------------|
| `sfx_strings(sfx_index)` | Returns `(miss_sfx, hit_sfx)` for a given index       |
| `print_sfx_table()`      | Prints full SFX index reference                       |
| `print_weapons(weapons)` | Prints all weapons with sfx info                      |
| `edit_sfx(weapons)`      | Interactive sfx_index editor, returns True if changed |
| `main()`                 | CLI entry point                                       |

---

## patch_monster_descriptions.py
*(renamed from `patch_descriptions.py`)* One-shot script to patch descriptions into monsters.json.

| Symbol                | Notes                                 |
|-----------------------|---------------------------------------|
| `DESCRIPTIONS` (dict) | `monster_number → description string` |

---

## presence.py
Virtual-location occupancy tracker for non-room areas (shoppe, elevator, bar).
Sets `client.virtual_location` so `_describe_room` can skip in-area players.

| Function                              | Notes                                                                             |
|---------------------------------------|-----------------------------------------------------------------------------------|
| `occupants(server, area)`             | Returns list of all clients with `virtual_location == area`                       |
| `others_present(ctx, area)`           | Returns names of other players in *area*, excluding the caller; used for "Also here:" display |
| `broadcast_area(ctx, area, message)`  | async — sends *message* to every co-occupant of *area* except the sender          |
| `enter_area(ctx, area)`               | async — sets `client.virtual_location`, notifies existing occupants               |
| `leave_area(ctx, area)`               | async — clears `client.virtual_location`, notifies remaining occupants            |
| `broadcast_open_room(ctx, message)`   | *(new, undocumented)* async — sends to players in the same physical room who are NOT in any virtual sub-area (e.g. "X steps up to the elevator") |

Usage pattern: call `enter_area` before the interaction loop, `leave_area` in a `finally` block.

---

## shoppe/main.py
Merchant's annex interaction loop. Entry point: `main(ctx)`.

| Function / Symbol              | Notes                                                                                      |
|--------------------------------|--------------------------------------------------------------------------------------------|
| `main(ctx)`                    | async — broadcasts `send_room` entry message, calls `enter_area('shoppe')`, runs session  |
| `_shoppe_session(ctx, player)` | async — inner loop: shows menu, dispatches keypress to sub-function, exits on `x`/EOF      |
| `_show_menu(ctx)`              | async — lists shoppe options + "Also here:" names from `others_present()`                  |
| `_MENU` (tuple)                | Dispatch table: `(key, label, async_fn)` entries; `x`/exit handled separately             |
| `_armory`, `_bank`, `_wizard`, `_clan`, `_pawn_shop` | ✅ No longer stubs — thin dispatchers to full sub-modules: `shoppe/armory.py` (349 lines), `shoppe/bank.py` (162), `shoppe/clan.py` (196), `shoppe/pawn.py` (100), `shoppe/wizard.py` (247) |
| `_general_store`, `_player_list`, `_protection` | ✅ Fully implemented now (not stubs) — `_player_list` is a wildcard-pattern player browser |
| `_elevator(ctx)`               | async — delegates to `shoppe.elevator.main(ctx)`                                          |

**New, undocumented shoppe sub-modules:** `shoppe/ollys.py` (302 lines — Olly's,
booby-trap items), `shoppe/locker.py` (249 lines — Private Locker).

---

## shoppe/elevator.py
Elevator car: floor selection, combination lock, travel between dungeon levels.

| Function / Symbol                                  | Notes                                                                                             |
|----------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `main(ctx)`                                        | async — broadcasts `send_room` entry/exit messages, calls `enter_area('elevator')`, runs session |
| `_elevator_session(ctx, player)`                   | async — inner loop: look, go, quit commands                                                       |
| `get_combination(ctx, *, kind, prompt_text)`       | async — prompts for floor/level combination; validates against player's stored combination        |
| `_travel_to(ctx, target)`                          | async — moves player to target level, checks level bounds and obstacles                           |
| `_find_combination(player, kind)`                  | Pure — looks up player's combination for *kind* (`CombinationTypes`)                             |
| `_wrong_combination_msg()`                         | Pure — returns a random wrong-combination message                                                 |
| `_out_of_range(obstacle)`                          | Pure — returns error text for out-of-range floor                                                  |
| `CombinationTypes` (Enum)                          | `ELEVATOR`, `DUNGEON_DOOR` — selects which combination field to check                            |

---

## bar/main.py
Wall Bar & Grill interaction loop. Entry point: `enter_bar(ctx)`.

| Function / Symbol          | Notes                                                                                                        |
|----------------------------|--------------------------------------------------------------------------------------------------------------|
| `enter_bar(ctx)`           | async — entry `send_room` broadcast, `enter_area('bar')`, movement/location/obstacle loop, exit broadcast    |
| `Bar` (dataclass)          | Runtime state: `pos_x`, `pos_y`, `can_go_here`, `valid_move`, `go_routine`; `bar_map` and `locations` class attrs |
| `Bar.bar_map` (dict)       | `'ascii'`/`'ansi'`/`'petscii'` variants of the 6-row bar floor map                                          |
| `Bar.locations` (list)     | `(row, col, display_name, routine_key)` — interactive spots on the map                                       |
| `_render_map(bar, bar_map, debug)` | Pure — inserts player marker `X` at `(pos_y, pos_x)`; adds row/col rulers in debug mode           |
| `_pick_map(ctx)`           | Pure — selects ascii/ansi/petscii map based on `client_settings.translation`                                 |
| `_show_menu(ctx, bar)`     | async — prints movement menu; includes `[G]o here` when `bar.can_go_here`                                    |
| `_bar_help(ctx)`           | async — prints bar help text                                                                                  |
| `food_menu(p, foodstuffs)` | Pure sync — builds sorted `list[Rations]` (drinks then food) from raw dicts                                  |
| `_bouncer(ctx, bar)`       | async — Mundo ejects player (HP penalty + move to exit)                                                       |
| `_vinny(ctx, bar)`         | ✅ No longer a stub — delegates to full `bar/vinny.py` (362 lines: loan shark, apply/pay loan, store/get money) |
| `_blue_djinn/_skip/_bar_none/_fat_olaf/_zelda` | async — delegates to respective sub-module `main(ctx, bar)`             |
| `_ROUTINES` (dict)         | Maps routine key strings to async callables for dispatch                                                      |
| `_DIRECTION_NAMES` (dict)  | `'n'→'north'` etc.; used in movement broadcast messages                                                       |

---

## bar/blue_djinn.py
*(STALE — entirely different feature now)* Doc used to describe "drinks,
gambling, combat challenge" — that content apparently moved to
`bar_none.py`. The Blue Djinn is now a **thug-hire/contract system**: pay to
have another player attacked; resolved at their next login via
`bar/thug_attack.py`.

| Function                            | Notes                                                                     |
|--------------------------------------|-----------------------------------------------------------------------|
| `main(ctx, bar)`                     | async — approach `broadcast_area`, interaction loop, ejection via Mundo or leave broadcast |
| `_hire(ctx)` / `_insult(ctx)`        | *(new)* hire flow / insult-the-Djinn flow                             |
| `add_contract`, `pending_contracts`, `resolve_contract`, `resolve_all_pending_contracts` | *(new)* contract persistence (`hit_contracts.json`) |
| `set_thug_flag_on_target`           | *(new)* sets `PlayerFlags.THUG_ATTACK` on the hire target              |
| `_load_contracts` / `_save_contracts` | *(new)* JSON persistence helpers                                     |

---

## bar/skip.py
Skip's Eats: once-per-day meal counter.

| Function         | Notes                                                                                              |
|------------------|----------------------------------------------------------------------------------------------------|
| `main(ctx, bar)` | async — once-per-day gate; approach `broadcast_area` fires only after gate passes; leave broadcast |
| `_improve_stat(player, stat, rng)` | *(new, undocumented)* stat-training mechanic |

---

## bar/bar_none.py
*(HEAVILY STALE — 560 lines now, doc only described a "drinks menu")*
Bar None (Mae the Bartender): drinks menu, **plus an entire undocumented Guss
blackjack minigame**.

| Function         | Notes                                                                              |
|------------------|------------------------------------------------------------------------------------|
| `main(ctx, bar)` | async — approach `broadcast_area`; leave broadcast on empty input only (not on EOF) |
| `Bartender(Ally)` | *(new, undocumented)* |
| `_guss_talk(ctx, ...)`, `_scan_chat(text, ...)` | *(new)* Chat with Guss: scans player input for keywords (profanity caught/filtered) and returns a matching, possibly-random reply |
| `_guss_flip`, `_guss_blackjack`, `_draw_card`, `_hand_total`, `_fmt_hand`, `_guss_session` | *(new, undocumented)* Guss blackjack minigame |

---

## bar/fat_olaf.py
Fat Olaf's Servant Trade: buy/sell party allies.

| Function                              | Notes                                                                    |
|---------------------------------------|--------------------------------------------------------------------------|
| `main(ctx, bar)`                      | async — approach `broadcast_area`, buy/sell loop, leave broadcast        |
| `_buy_servant(ctx, allies)`           | async — numbered menu to select and purchase a servant                   |
| `_sell_servant(ctx)`                  | ✅ No longer a stub — fully implemented                                  |
| `filter_allies(ally_list, status)`    | Pure — returns allies matching `AllyStatus`. **Confirmed this pass: still duplicated, byte-for-byte identical** (same signature, same docstring, same body) in both `bar/fat_olaf.py:41` and `bar/allies.py:14`. Not a live bug — `fat_olaf.py` doesn't import the `bar/allies.py` copy (it only imports `pick_ally` from there), so there's no shadowing/override conflict, just dead duplication that should be collapsed to one definition. |
| `_maintain_servant`, `_owned_allies`, `_purchased_allies`, `_sync_to_roster`, `_free_allies_for_sale`, `_ally_price`, `_ally_sellback`, `_is_elite` | *(new, undocumented)* |

---

## bar/zelda.py
Madame Zelda's: spy on player stats or resurrect monsters.

| Function                   | Notes                                                                    |
|----------------------------|--------------------------------------------------------------------------|
| `main(ctx, bar)`           | async — approach `broadcast_area`, command loop, leave broadcast         |
| `_study_player(ctx)`       | async — prompts for target player name, charges 1,000 silver, shows stats from disk |
| `_resurrect_monsters(ctx)` | ✅ TODO resolved — now writes via `_append_battle_log` (new, undocumented) |
| `get_player_info(stats, id_pattern)` | Pure sync — reads player JSON from `run/server/player-<id>.json` |
| `_zelda_menu(ctx)`         | async — prints available options                                          |
| `_tell_fortune`, `_clear_monsters_killed_offline`, `_find_online_player`, `_player_json_path` | *(new, undocumented)* |

---

## bar/ally_data.py
Ally/servant data definitions used by Fat Olaf.

| Symbol / Function                        | Notes                                         |
|------------------------------------------|-----------------------------------------------|
| `AllyFlags`, `AllyStatus` (Enum)         | Flags and lifecycle states for allies         |
| `Ally` (dataclass)                       | `name`, `strength`, `status`, `flags`, `breed`/`color` *(new, undocumented — `Optional[HorseBreed]`/`Optional[HorseColor]` from `base_classes.py`, only meaningful when `AllyFlags.MOUNT` is set)* |
| `load_allies()`                          | Returns `list[Ally]` from JSON                |
| `assign_random_statuses(allies)`         | Pure — randomly assigns `SERVANT`/`IN_PARTY`  |
| `AllyPosition` (Enum)                     | *(new, undocumented)*                         |
| `load_ally_roster()` / `save_ally_roster(...)` | *(new, undocumented)*                    |
| `find_duplicate_allies(...)`             | *(new, undocumented)*                         |
| `print_allies(...)`                      | *(new, undocumented)*                         |

**New, related module — `bar/allies.py`** (separate from `ally_data.py`):
`filter_allies`, `owned_allies`, `purchased_allies`, `find_mount`, `pick_ally`.
`filter_allies` is defined independently — and identically — in *both*
`bar/allies.py` and `bar/fat_olaf.py`; see the note in the `bar/fat_olaf.py`
section above (confirmed still duplicated this pass, not fixed, not a live
bug since `fat_olaf.py` doesn't import the other copy).

---

## ally_events/
Package (not a flat module) of ally-triggered game events — random
per-move mechanics plus one quit-time mechanic. Sibling package to
`encounters/` but kept separate since these are ally-specific rather
than room/NPC events (see `starvation.py`'s and `capture_horse.py`'s
docstrings for the rationale). All four files ported from SPUR
`MISC6.S`/`SUB.S`/`MISC9.S`/`COMBAT.S`, except `capture_horse.py`
(new-to-TADA mount mechanic) and `capture_horse.py`'s breed/color
flavor.

### `__init__.py`
| Function                                              | Notes                                                                                                       |
|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `try_ally_find_gold(ctx)`                             | async — ~5% per-move chance a SERVANT ally hands the player 52-250 gp; skips water rooms, once-per-day gated (`AYF` tag), no-op if no owned allies (SPUR `MISC6.S al.find`) |
| `try_hungry_ally(ctx, item, kind)`                    | async, returns `bool` — intercepts a player eat/drink to let the weakest hungry ally (strength < 11, non-`ELITE`) claim the item first; `Y/n` prompt, honor -2 on refusal / +2 or +5 on feeding; call BEFORE removing the item from inventory (SPUR `SUB.S hun.slv`) |
| `_free_ally_in_roster(name, status, owner)`           | private — syncs one ally's status/owner into the persisted roster JSON (mirrors `bar/fat_olaf.py`'s `_sync_to_roster`); also imported directly by `starvation.py` |
| `try_ally_death_save(ctx, incoming_damage)`           | async, returns `bool` — gives allies a chance to intervene before a killing blow, tried in party order; `GOD`/`GODDESS` allies always save the player (teleport away, return `True`) and depart for good, others make a courage-vs-honor roll and either flee (`AllyStatus.FREE`) or "take the blow" (`AllyStatus.DEAD`) as flavor only — per SPUR only a divine save actually cancels the damage, so a non-divine "save" still returns `False` and the hit lands (SPUR `COMBAT.S` "dragon" label / skip's `MISC9.S sac.ally`) |

### `starvation.py`
| Function                     | Notes                                                                                                                     |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| `_weakened_ally(player)`     | private — first owned ally with `0 < strength < 8`, in party order                                                          |
| `_is_divine(ally)`           | private — `True` if `AllyFlags.GOD`/`GODDESS`                                                                               |
| `_is_elite(ally)`            | private — `True` if `AllyFlags.ELITE`                                                                                       |
| `try_encounter(ctx)`         | async — the package's per-move random-event entry point (called from `simple_server.py`'s world-event roll alongside `encounters/*.py`, not from this file); 0.3% composite chance, no water/vacuum gate and no once-per-day gate (deliberate — matches SPUR, can fire every move); elite allies get a flavor-only immunity line, divine allies desert (`AllyStatus.FREE`) instead of dying, mortal allies die (`AllyStatus.DEAD`); either way applies Honor -20/Wisdom -5/Intelligence -5 (floored) and writes to the battle log via `net_common.append_battle_log` |

### `farewell.py`
| Function                                                     | Notes                                                                                                                 |
|-----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| `_load_quotes()`                                                | private — loads `ally_farewell_quotes.json` (`server/` root, i.e. `Path(__file__).parent.parent`), keyed by tier |
| `_tier_for(ally)`                                               | private — `'god'`/`'goddess'`/`'mortal'` from `AllyFlags`                                                                 |
| `_display_name(ally, tier)`                                     | private — prefixes `"THE GOD "`/`"THE GODDESS "` for divine tiers (mirrors SPUR's `cln.ally`)                            |
| `_substitute(quote, player_name, ally_display_name, ally)`      | private — replaces `$`→player name, `%n`→ally display name, `%s`/`%o`/`%p`/`%P`/`%r`→gendered pronoun via `tada_utilities.get_pronoun()` |
| `farewell_lines(player)`                                        | sync, returns `list[str]` — one farewell line per party member (in party order); a `'mortal_exchange'` pair (30% chance, ≥2 mortal allies) can bind the first two mortals to a scripted back-and-forth instead of independent random lines; called from `commands/quit.py`, not the world-event roll |

### `capture_horse.py`
*(new 8/1/26, extracted out of `combat/engine.py`'s `CombatSession` —
see that section's note on `_charge_unseat_check`/`_try_redirect_to_mount`)*

| Function                                       | Notes                                                                                                                          |
|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `_random_horse_name(gender)`                    | private — random pick from a hardcoded male/female name pool                                                                  |
| `_monster_hp(monster)`                          | private — `monster['strength']` or `['hit_points']`, default 5                                                                |
| `prompt_horse_name(ctx, gender='m')`            | async, returns `Optional[str]` — prompts for a 4-12 char name (no symbols), `'R'` for a random gender-appropriate name, `None` on cancel |
| `mount_slot_available(ctx, *, verbose)`         | async, returns `bool` — true if the player has room for a new `MOUNT` ally; the 3-ally cap only counts non-`MOUNT` allies (a mount is a 4th slot, confirmed against original gameplay), only 1 mount allowed; `verbose` controls whether a refusal message is sent (LASSO command wants it, passive Druid/Ranger taming check stays silent) |
| `capture_mount(ctx, monster)`                   | async, returns `Optional[Ally]` — prompts for a name and, if given, rolls gender/breed/color (breed/color are new-to-TADA display flavor, no SPUR precedent), builds and adds a `MOUNT`-flagged `Ally` via `player.party.add_member()` (not `.append()` — party isn't a plain list), writes to the battle log; returns `None` on name-prompt cancel; called from both `CombatSession.lasso()` (guaranteed capture) and `CombatSession._try_class_tame()` (passive per-round chance, no SPUR precedent) |

---

## commands/
All commands are `Command` subclasses auto-discovered by `command_processor.py`.

*(HEAVILY STALE — doc previously listed only 8 commands, one of them
misnamed)* There are now **52** `Command` subclasses. `StatsCommand` never
existed under that name — the real class in `commands/stats.py` is
**`StatCommand`** (singular). **The previously-flagged `BanCommand` duplicate
is resolved — confirmed fixed this pass, not just re-flagged:** `grep -n
"class BanCommand" commands/admin.py commands/ban.py` now matches only
`commands/ban.py:163`. `commands/admin.py` no longer defines a `BanCommand`
at all (it still has `UnbanCommand` and others). Whoever fixed this did so
since the last FUNCTIONS.md pass; no duplicate-class-name bug remains here.

Grouped by rough category (module name in parens where it's not obvious
from the class name):

**Movement/navigation:** MoveCommand (`movement.py` — handles n/s/e/w/u/d
and `go`), TeleportCommand, WhereatCommand, LookCommand, DismountCommand,
MountCommand, LassoCommand

**Inventory/items/economy:** GetCommand, DropCommand, TakeCommand,
GiveCommand, InvCommand, ReadyCommand, UnreadyCommand, UseCommand,
DrinkCommand, EatCommand

**Combat:** AttackCommand, FleeCommand, DieCommand

**Character/stats:** StatCommand (`stats.py` — not "StatsCommand"), PrefsCommand

**Communication:** SayCommand, ShoutCommand, WhisperCommand, PageCommand,
QuoteCommand, GroupsCommand

**Reading/news/help:** ReadCommand, NewsCommand, HelpCommand

**Session/auth/connection:** LoginCommand, PasswordCommand, GuestCommand,
ConnectCommand, NewPlayerCommand, QuitCommand, WhoCommand, MorePromptCommand

**Admin / editplayer / moderation:** ExampleAdminCommand, RestartCommand,
ShutdownCommand, BootCommand, UnbanCommand, BanCommand (`ban.py` — sole
definition, see note above), EditPlayerCommand, EditMonstersCommand,
DbgCommand, ReloadCommand

**Dev/example/misc:** TestCommand (its 'colors' functionality moved to
'test #colors' -- freed up the 'colors' name for the 'help colors'
concept topic), TableCommand

`commands/messaging.py` is a support module of plain functions used by
say/shout/whisper/page — no `Command` subclass of its own, despite the name.

**Original 8 commands, status check:**

| Class            | Keyword(s)                | Notes                                                                                  |
|-------------------|----------------------------|-----------------------------------------------------------------------------------------|
| `GetCommand`      | `get`, `g`                | Pick up items from current room; tracks per-player pickup in `player.ration_history`/`item_history` session-scoped ring buffers (replaced the old unbounded `picked_up_items` list 7/31/26) |
| `DropCommand`     | `drop`                    | Drop inventory item into current room                                                  |
| `ReadyCommand`    | `ready`, `wield`, `equip` | Select and ready a weapon from inventory; shows weapon class/race bonuses          |
| `WhereatCommand`  | `whereat`, `wa`           | Show all connected players with room/virtual-location; restricted to privileged players |
| `TeleportCommand` | `teleport`, `tp`          | Move player to target room; flash-of-light `send`+`send_room` at origin and destination |
| `StatCommand`     | `stats`, `st`             | ⚠️ Doc previously said `StatsCommand` (wrong name) — real class is `StatCommand`; uses `characters.py` race/class bonus tables |
| `InvCommand`      | `inv`, `i`                | Show inventory; persisted across save/load via `player.inventory`                      |
| `LookCommand`     | `look`, `l`               | Describe room; skips players whose `virtual_location` is set (ghost-player fix)        |

---

## item_system.py
Weapon and item data layer: loading from JSON, class/race bonuses, async display helpers.

| Symbol / Function                              | Notes                                                                                   |
|------------------------------------------------|-----------------------------------------------------------------------------------------|
| `WeaponKind` (StrEnum)                         | `SWORD`, `AXE`, `BOW`, etc.                                                             |
| `WeaponClass` (StrEnum)                        | `FIGHTER`, `MAGIC_USER`, etc. — who can use the weapon                                  |
| `ItemType` (StrEnum)                           | `WEAPON`, `ARMOR`, `MISC`, etc.                                                         |
| `Weapon` (dataclass)                           | Full weapon schema: `name`, `kind`, `damage`, `sfx_index`, `class_bonuses`, `race_bonuses` |
| `Item` (dataclass)                             | Full item schema: `name`, `item_type`, `flags`, `value`                                 |
| `load_weapons(path)`                           | Returns `list[Weapon]` from JSON                                                        |
| `load_items(path)`                             | Returns `list[Item]` from JSON                                                          |
| `weapon_sfx(weapon)`                           | Pure — returns `(miss_sfx, hit_sfx)` strings                                            |
| `weapon_bonus(weapon, player_class, player_race)` | Pure — returns `(attack_bonus, damage_bonus)` from class/race bonus tables          |
| `active_item_flags(item)`                      | Pure — returns list of active flag key names                                            |
| `show_weapon(ctx, weapon)`                     | async — formatted weapon stat display                                                   |
| `list_weapons(ctx, weapon_list)`               | async — table of weapons                                                                |
| `ready_weapon(ctx, player, weapons_data)`      | async — interactive weapon selection; sets `player.readied_weapon`                      |
| `show_item(ctx, item)`                         | async — formatted item display                                                          |
| `list_items(ctx, item_list)`                   | async — table of items                                                                  |

---

## items.py
Runtime item classes used in player inventory and room contents.

| Class / Symbol       | Notes                                                                                  |
|----------------------|----------------------------------------------------------------------------------------|
| `ItemCategory` (StrEnum) | `WEAPON`, `ARMOR`, `RATIONS`, `SPELL`, etc.                                        |
| `IDNumber` (dataclass) | Wraps item number with validation                                                    |
| `BoobyTrap` (dataclass) | Trap definition attached to an item                                                 |
| `BaseItem` (dataclass) | Common fields: `number`, `name`, `category`, `booby_trap`                           |
| `Item(BaseItem)`     | General item; adds `quantity`, `picked_up` tracking                                   |
| `Weapon(BaseItem)`   | Weapon item; adds `damage`, `sfx`; `read_weapons(path)` class method                 |
| `Rations(BaseItem)`  | Food/drink; adds `kind`, `price`; `read_rations(path)` class method                  |
| `Spell(BaseItem)`    | Spell; adds `cast_chance`, `effect`                                                   |

---

## characters.py
Race and class stat bonus tables, and character-creation helpers.

| Function / Class                         | Notes                                                                             |
|------------------------------------------|-----------------------------------------------------------------------------------|
| `BaseCharacter` (dataclass)              | Common fields: `name`, `race`, `character_class`, `stat` (dict of `PlayerStat`)  |
| `Pixie`, `Ally`, `Monster`               | Concrete character subclasses. `Horse` (dead, never-wired stub) deleted 8/1/26 — a mount is an ordinary `bar/ally_data.Ally` flagged `AllyFlags.MOUNT`, not a separate class |
| `race_bonuses(race)`                     | Pure — returns `dict[PlayerStat, int]` bonuses for a race                         |
| `class_bonuses(char_class)`              | Pure — returns `dict[PlayerStat, int]` bonuses for a class                        |
| `base_stats_for(race, char_class)`       | Pure — merges race + class bonus dicts                                            |
| `apply_race_class_deltas(player)`        | Mutates player stats in-place by applying race+class bonuses                      |
| `apply_creation_bonuses(player)`         | Mutates player stats in-place from character-creation rolls; returns bool success |

---

## table.py
Terminal-safe table renderer. Pure — no I/O, no ctx.

| Symbol / Function                   | Notes                                                                               |
|-------------------------------------|-------------------------------------------------------------------------------------|
| `Align` (Enum)                      | `LEFT`, `RIGHT`, `CENTER`                                                           |
| `Border` (dataclass)                | Full border spec: corners, edges, intersections; includes `ascii`, `ansi`, `petscii` presets |
| `Column` (dataclass)                | `header`, `width`, `align`                                                          |
| `Table` (dataclass)                 | `columns`, `rows`, `border`, `title`; `render()` returns `list[str]`               |
| `make_table(columns, rows, ...)`    | Convenience constructor: accepts plain dicts/lists, returns `list[str]`             |
| `_fit(text, width, align)`          | Pure — pads/truncates a cell value                                                  |
| `_wrap_cell(text, width)`           | Pure — wraps long cell text across multiple lines                                   |

---

## simple_server.py
Async TCP server. Manages client connections and room broadcasting.

| Key change (monster-editor branch)    | Notes                                                                                |
|---------------------------------------|--------------------------------------------------------------------------------------|
| `_describe_room` ghost-player fix     | Skips clients with `virtual_location` set — prevents in-area players appearing in room `look` output |

---

## player.py
Core live `Player` runtime class (~1717 lines) — identity, stats, flags,
inventory, party, silver/rulan, client settings, save/load. Actively
touched (5 of last 5 commits landed in the last two weeks: ammo persistence,
GIVE/DROP unready fixes, EXAMINE expansion, armor durability). Distinct from
`players.py` below, which is a stale, explicitly-marked-for-deletion
predecessor.

| Function / Class                                                                       | Notes                                                                                     |
|------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `set_up_flags()` / `set_up_client_settings()` / `set_up_combinations()` / `set_up_rulan()` / `set_up_silver()` / `set_up_stats()` | Module-level factory functions for `Player.__init__` field defaults          |
| `make_random_id()` / `make_random_stat()`                                              | Pure — new-player default generators                                                        |
| `longest_flag_name()`                                                                   | Pure — column-alignment helper for flag listings                                            |
| `Player` (class)                                                                        | Core player object; ~40 public methods (below); private helpers not itemized                |
| `Player.set_stat(ctx, stat, adj, verbose=False)` / `.set_stat_absolute(stat, value)` / `.get_stat(stat)` / `.get_one_stat(stat)` / `.print_stat(stat, abbreviated)` / `.print_multiple_stats(stat_list, ...)` | Stat read/write/display                                          |
| `Player.get_flag(flag_name)` / `.set_flag(flag, verbose=False)` / `.clear_flag(flag, verbose=False)` / `.toggle_flag(flag, verbose=False)` / `.query_flag(flag)` | Thin wrappers delegating to `flags.py` module functions of the same name |
| `Player.get_silver(kind)` / `.set_silver_absolute(kind, amount)` / `.subtract_silver(kind, amount)` | Money accessors (`PlayerMoneyTypes`)                                        |
| `Player.gain_weapon_experience(weapon_id_number)` / `.gain_shield_proficiency(shield_id_number)` | Combat skill-progression, returns new proficiency int                          |
| `Player.has_item(*, name=None, item_id=None, ...)`                                      | Inventory lookup                                                                             |
| `Player.record_ration_pickup(item_id)` / `.record_item_pickup(item_id)` / `.record_command(text)` | Appends to session-scoped ring-buffer history (`ration_history`/`item_history`, 7/31/26 redesign) |
| `Player.look_at(item)`                                                                   | Sets `last_examined`                                                                         |
| `Player.get_birthday()` / `.get_age()`                                                  | Pure                                                                                          |
| `Player.connect()` / `.move(destination_room, direction=None)` / `.quit()`             | Session lifecycle                                                                             |
| `Player.save(force=False)` / `Player._load()` / `Player._json_path(user_id)` (staticmethod) | JSON persistence; `_load` is the single largest method in the file (~440 lines)     |
| `Player.__str__` / `.__repr__`                                                           |                                                                                                |
| `Player.is_expert` / `.is_debug` / `.return_key` / `.is_future_expansion` / `.monsters_killed` (properties) |                                                                                 |
| `equipped_entry(player, slot)` / `refresh_equipped_rating(player, slot)` / `unequip_if_worn(player, item)` / `unworn_if_given_away(player, item)` / `unworn_notice(slot, name)` / `apply_equipment_degradation(player, slot, degraded, destroyed)` | Module-level (not `Player` methods) — armor/shield equip-slot bookkeeping, from the 8/8/26 per-item durability work |

---

## players.py
*(STALE — self-flagged dead code, confirmed unused this pass)* File's own
first line: `# FIXME: PLAYERS.PY IS OUTDATED. MIGRATE BETTER CODE TO
PLAYER.PY, THEN DELETE IT.` Confirmed this pass: nothing else in the tree
imports it (`grep -rl "from players import\|import players\b"` outside the
file itself returns no hits) — fully orphaned. Superseded by `player.py`
above.

| Function / Class                                              | Notes                                                                    |
|-----------------------------------------------------------------|---------------------------------------------------------------------------|
| `Character` (dataclass)                                        | `name`, `flags` — small stub, superseded by `player.py`'s `Player`        |
| `Player` (dataclass)                                            | Old, incompatible predecessor of `player.py`'s `Player`; own inline comment says "THIS DOES NOT WORK ANYMORE" |
| `Player.get_flag/show_flag/show_flag_line_item/show_flag_status/toggle_flag/put_flag/query_flag` | Old flag API, superseded by `flags.py`'s module functions |
| `Player.show_stat/adjust_stat/get_stat/put_stat`                | Old stat API, superseded                                                  |
| `TodoPlayer(Character)`                                         | Another stub subclass: `__str__`, `set_stat`, `get_stat`, `print_stat`, `print_all_stats`, `get_silver`, `set_silver` |
| `transfer_money(receiver, giver, kind, adj)`                    | Standalone module-level function                                          |
| `Ally` (class)                                                   | Old Ally stub — separate from, and superseded by, the live `bar/ally_data.Ally` used everywhere else |

---

## combat/engine.py
`CombatSession` — the live wandering-monster combat loop (~2145 lines).
Actively touched (gendered death messages, desert/labyrinth mechanics,
tactical-ambush shouts, armor durability all landed recently).

| Function / Class                                              | Notes                                                                    |
|-----------------------------------------------------------------|---------------------------------------------------------------------------|
| `first_statue_victim(monster_name)`                             | Public — first player turned to statue by a given monster (Medusa-type Easter egg) |
| `load_all_statues()`                                             | Public — returns `dict[str, list[str]]`                                   |
| `CombatSession` (class)                                          | One combat encounter's full state/loop; ~30 methods, all but `start`/`join`/`flee`/`lasso` are `_`-prefixed private and not itemized individually |
| `CombatSession.start(ctx)` / `.join(ctx, is_lurking=False)`     | async — begin a new fight / join an in-progress one                       |
| `CombatSession.flee(ctx)` / `.lasso(ctx)`                        | async — public player actions during combat                               |
| `enter_combat(ctx, monster)`                                     | async — top-level entry point; creates and starts a `CombatSession`       |
| `join_combat(ctx)`                                                | async — joins the room's already-running `CombatSession`, if any; returns bool |
| 18 private module-level functions and ~26 private `CombatSession` methods | Not itemized — notably `_run_loop` (main turn loop), `_swing`/`_ally_swings` (attack resolution), `_monster_dies`/`_player_dies` (outcome handling), `_charge_unseat_check`/`_try_redirect_to_mount` (mount combat, 8/1/26 extraction point for `ally_events/capture_horse.py`) |

---

## combat/resolution.py
Pure combat math — dataclasses + functions, no ctx/I-O (~1000 lines).

| Function / Class                                                            | Notes                                                        |
|--------------------------------------------------------------------------------|-----------------------------------------------------------------|
| `battle_exp_bonuses(vp, xp_level)`                                            | Pure                                                             |
| `tier_label(vp)`                                                               | Pure — victory-point tier display string                        |
| `shield_exp_bonus(shield_proficiency)`                                        | Pure                                                             |
| `assemble_zu_zv(weapon, player_battle_exp, xp_level, ...)`                    | Pure — builds to-hit/damage input values                        |
| `hit_threshold(weapon_class_str, monster_size, ...)`                          | Pure                                                             |
| `SpecialWeaponResult` / `AttackResult` / `MonsterAttackResult` / `AllyAttackResult` / `FleeResult` (dataclasses) | Structured return types for the resolver functions below |
| `check_special_weapon(...)`                                                    | Special-weapon effect roll                                       |
| `player_attacks(...)`                                                          | Main player-attack resolver → `AttackResult`                     |
| `monster_attacks(monster, player, *, stone_blocked=False, ...)`               | Main monster-attack resolver → `MonsterAttackResult`             |
| `ally_attacks(ally_name, ally_strength, monster, ...)`                        | → `AllyAttackResult`                                             |
| `flee_attempt(player, monster, monster_is_following=True, ...)`               | → `FleeResult`                                                   |
| `_apply_special_weapon_damage` / `_scare_check` / `_calc_player_damage`       | Private helpers                                                  |

---

## combat/duel.py
PvP duel system — challenge, tactics, round resolution, guild-turf capture
(~1263 lines). Actively touched (ammo-penalty rules, guild support headcount
bonus, initiative/Wizard-cast/Druid-heal all landed recently).

| Function / Class                                                             | Notes                                                       |
|----------------------------------------------------------------------------------|------------------------------------------------------------------|
| `DuelTactic` (StrEnum)                                                          | Selectable duel tactics                                          |
| `_DuelSide` (dataclass)                                                          | Per-combatant duel state                                         |
| `DuelOutcome` (dataclass)                                                        | Result summary                                                   |
| `DuelSession` (class, ~480 lines)                                               | One duel's state/loop                                            |
| `DuelSession.side_for(player)` / `.other(player)`                               | Look up the matching `_DuelSide`                                 |
| `DuelSession.submit(player, tactic)`                                            | async — records a player's chosen tactic for the round           |
| `DuelSession.forfeit(disconnected_player)`                                      | async — handles a disconnect mid-duel                            |
| `_send_challenge` / `_resolve_challenge` / `_resolve_grovel` / `_submit_tactic` / `_toggle_verbose` / `_show_standings` (all `(ctx, ...)`, async) | Command-handler-style functions wired to `DuelCommand` |
| `DuelCommand(Command)`                                                           | Player-facing `duel`/`grovel`/etc. command class                 |
| ~16 private `DuelSession`/module helpers                                        | Not itemized — notably `_resolve_round`, `_resolve_swing`, `_resolve_bash`, `_apply_final_damage`, `_end`, `_try_capture_turf`, `_compute_initiative`, `_absorb_shield_armor`/`_apply_degradation` (armor/shield durability) |

---

## combat/rewards.py
Tiny module (61 lines) — gold and exp-per-swing reward math. Added 8/8/26,
wired into `combat/engine.py`.

| Function                      | Notes                                  |
|--------------------------------|-------------------------------------------|
| `gold_from_monster(monster)`  | Pure — gold dropped by a monster           |
| `exp_per_swing()`              | Pure                                       |

---

## party.py
`Party` class — a player's group of allies/mounts, wrapping a list with
JSON (de)serialization. Extracted from `players.py`/inline logic on
7/26/26; actively touched since (ORDER command, item persistence, GIVE
auto-wear).

| Function / Class                                     | Notes                                                              |
|---------------------------------------------------------|------------------------------------------------------------------------|
| `Party` (class)                                          | Wraps a `members` list; `__iter__`/`__len__`/`__bool__`/`__contains__`/`__getitem__`/`__repr__` dunders |
| `Party.add_member(owner, member)`                        | Returns `(bool, str \| None)` — success flag + optional error message |
| `Party.is_member(member)` / `.remove(member)`            |                                                                          |
| `Party.to_json()` / `Party.from_json(data, weapons_data=None)` (classmethod) | Persistence                                          |
| `Party.add(ctx, owner, member)`                          | async wrapper around `add_member`                                      |
| `Party.list_members(ctx, owner_name)`                    | async — displays party roster via `ctx.send`                           |

---

## group_management.py
`Group` class — named player groupings for social/admin purposes; distinct
from `Party` (combat allies) above.

| Function / Class                                                             | Notes                                          |
|-----------------------------------------------------------------------------------|-----------------------------------------------------|
| `Group` (class)                                                                    | `__init__(name)`                                     |
| `Group.group_add(group_name)` / `.group_delete(group_name, force=False)` / `.group_rename(new_name)` | Returns `str \| None` error message on failure |
| `Group.group_list(verbose=True)`                                                   | Returns `list[str]`                                   |
| `Group.player_add(player)` / `.player_remove(player)`                             |                                                        |
| `Group.move_player_between_groups(move_from, move_to, player)`                    |                                                        |
| `Group.is_empty()` / `.show_members()`                                            |                                                        |

---

## inventory.py
`Inventory` class — stacking, capacity, category sort; used for both player
packs and ally item lists. Actively touched (stacking-across-categories fix,
Merchant's Annex pack management, armor/shield durability).

| Function / Class                                                              | Notes                                                    |
|-------------------------------------------------------------------------------------|---------------------------------------------------------------|
| `class_inventory_limit(char_class)`                                                | Pure — capacity by player class                                |
| `InventoryEntry` (dataclass)                                                        | One stack: item + quantity                                     |
| `Inventory` (class)                                                                 | Backed by a list of `InventoryEntry`                            |
| `Inventory.add(item, quantity=1)` / `.remove(item, quantity=1)`                    | Returns bool success                                            |
| `Inventory.find(*, name=None, item_id=None, ...)`                                  | Lookup                                                          |
| `Inventory.entries(category=None)`                                                 |                                                                  |
| `Inventory.sort(category_order=None)`                                              |                                                                  |
| `Inventory.is_full()` / `.slot_count()`                                            |                                                                  |
| `Inventory.to_json()` / `Inventory.from_json(data, capacity=None, ...)` (classmethod) | Persistence                                                  |
| `Inventory.__len__` / `.__iter__` / `.__bool__`                                    |                                                                  |
| `_rations_by_number()` / `_objects_by_number()` / `_remove_at(index, quantity)` / `_prune()` | Private helpers                                        |

---

## flags.py
`PlayerFlags` enum, display metadata, and module-level flag get/set/clear/
toggle functions — `player.py`'s `Player.get_flag`/etc. are thin wrappers
around these.

| Function / Class                                                             | Notes                                                     |
|-------------------------------------------------------------------------------------|------------------------------------------------------------------|
| `PlayerFlags` (StrEnum)                                                            | All player flags                                                  |
| `FlagDisplayTypes` (Enum)                                                          | How a flag renders in flag-listing UI                              |
| `TutTreasure` (dataclass)                                                          |                                                                     |
| `Flag` (dataclass)                                                                 | One flag instance: value + display metadata                       |
| `ensure_player_flags(player)`                                                      | Backfills missing flags with defaults (e.g. after a schema change) |
| `set_flag(player, flag)` / `clear_flag(player, flag)` / `toggle_flag(player, flag)` / `query_flag(player, flag)` | Module-level flag mutators               |
| `serialize_flags_for_save(player)`                                                 | Returns dict for JSON persistence                                  |
| `_make_flag_from_tuple(tup)`                                                       | Private                                                            |

---

## base_classes.py
Grab-bag of shared enums/dataclasses used across the codebase: races,
classes, rooms, map, combinations, money (~846 lines). Actively touched
(gendered class-name display, HQ-territory room fix, race-based Honor).

| Function / Class                                                                     | Notes                                                            |
|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `Guild`, `Size`, `Alignment`, `CombinationTypes`, `PlayerMoneyTypes`, `PlayerMoneyCategory`, `WeaponClass`, `Gender`, `PronounType`, `PlayerClass`, `PlayerClassText`, `PlayerRace`, `HorseBreed`, `HorseColor`, `PlayerRaceText`, `PlayerStat`, `PlayerRaceBonuses`, `PlayerRaceMaxHonor`, `PlayerClassBonuses`, `RoomAlignment` (Enums/StrEnums) | Core game-vocabulary enums          |
| `BaseCharacterRace` (dataclass)                                                            |                                                                         |
| `class_and_race_combinations(ctx)`                                                         |                                                                         |
| `room_alignment_label(alignment)` / `strip_legacy_alignment_suffix(name)`                 | Pure                                                                   |
| `HiddenExitTarget` (NamedTuple)                                                            |                                                                         |
| `Room` (dataclass/class)                                                                   | `__str__`, `hidden_exit(direction, current_level)`, `get_exit(direction)`, `exits_txt(ctx)` |
| `guild_hq_key_for_room(room)`                                                              |                                                                         |
| `_parse_room_alignment(value)`                                                             | Private                                                                |
| `Map` (class)                                                                              | `__init__()`, `read_map(filename, level=1)`, `get_room(level, room_number)` |
| `Combination` (class)                                                                      | `__init__(name)`, `__str__`, `has_single_digit()`, `from_string(ans, combination_type)` (classmethod), `valid_combination(ans)` |
| `VinneyLoan` (class)                                                                       | `__init__(due_date, amount_due)`                                       |
| `InventoryItem` (class)                                                                    | `__init__(item, quantity=1)`, `find_item`, `remove_item`; private `__increment_quantity`/`__decrement_quantity` |

---

## terminal.py (546 lines)
Client-display/settings data: keyboard/color code enums, `ClientSettings`
(the object every player's `player.client_settings` actually is), and a
second half of legacy menu-driven settings-editor functions that appear to
predate the `ctx`/`menu_system.py` refactor and are **not wired into the
live `prefs` command** (confirmed this pass -- `commands/prefs.py` never
imports from `terminal.py` at all; it edits `player.client_settings`
fields directly). Distinct from `terminal_context.py` -- see that
section's clarifying note above; no naming confusion once both are read.

### Live / actively used
| Symbol                                                     | Notes                                                                                              |
|-----------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `KeyboardKeyName` (StrEnum) / `KeyboardKeyCodes` (Enum) / `KeyCodes` (Enum) | Key-name/code tables                                                              |
| `CommodoreKeyCodes`                                          | C64/128 keyboard code constants                                                                     |
| `ANSIGraphicsChars` (StrEnum) / `CommodoreGraphicsChars` (StrEnum) | Box-drawing glyph tables, one per translation mode -- `formatting.py` looks up `{NAME}` glyph tokens from `CommodoreGraphicsChars` |
| `LineEnding`                                                 | Line-ending constants                                                                                |
| `ColorName` (StrEnum)                                        | Abstract color-token names; `formatting.py`'s `COLOR_NAME_TO_TOKEN` maps these to `\|token\|` names |
| `ANSIColors` (Enum) / `CBMColors` (Enum)                      | Concrete per-translation color code tables                                                          |
| `Translation` (Enum)                                          | `PETSCII`/`ASCII`/`ANSI` (or similarly-named members) -- the single most-imported symbol in this file, used by `player.py`, `formatting.py`, `network_context.py`, `net_client.py`, `net_common.py`'s `Init`, etc. |
| `TabSettings` (class)                                         | `to_dict()`/`from_dict()` persistence                                                               |
| `TerminalColors` (class)                                      | `to_dict()`/`from_dict()` persistence                                                               |
| `ClientSettings` (class)                                      | The real, live object behind `player.client_settings` (screen size, translation, colors, return key, etc.); `to_dict()`/`from_dict()` persistence |
| `Commodore64(ClientSettings)` / `Commodore128_40Col(Commodore64)` / `Commodore128_80Col(Commodore64)` | Preset `ClientSettings` subclasses for specific hardware profiles |

### Legacy menu-driven settings editor -- confirmed unreferenced by `commands/prefs.py` or anywhere else this pass
| Function / Class                                            | Notes                                                                                               |
|--------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `settings_menu(player)` / `tab_edit(player)`                  | Old numbered-menu-loop settings editors, pre-`ctx`/`menu_system.py`                                  |
| `edit_screen_columns(player)` / `edit_screen_rows(player)`    | Nested inside `tab_edit`/module scope                                                                |
| `horizontal_ruler(player)`                                     | Renders a column-width ruler for the old editor                                                      |
| `keyboard_settings(player)` / `color_settings(player)` / `test_graphics_output(player)` | Further old menu-driven editor screens                                                  |
| `CommodoreClient` (dataclass)                                  | *(new, undocumented)* -- distinct from, and not to be confused with, `net_client.py`'s `CommodoreClient(Client)` |
| `Output` (class)                                                | `__init__(player)`, `.output(message)`, `.process_message(player, message)` -- old direct-print output helper, superseded by `ctx.send()` |

No behavior was invented here -- `grep -rn "terminal\.settings_menu\|terminal\.tab_edit\|terminal\.Output"` across the tree (outside `terminal.py` itself) returns nothing, confirming these are dead in the current game, not merely undocumented.

---

## create_character.py (1115 lines)
*(STALE — confirmed orphaned this pass, not merely undocumented)* A
complete pre-`ctx` character-creation flow (`choose_gender`/`choose_name`/
`choose_client`/`choose_class`/`choose_settings`/`choose_race`/`choose_age`/
`choose_guild`/`roll_stats`/`main(player)`/`debug_menu`, ~22 top-level
functions total). Imports `net_server` (itself dead, see above) and calls
into `tada_utilities.py` functions (`header`, `input_number_range`,
`input_yes_no`, `a_or_an`, `set_logging_level`) using old positional/`player=`
calling conventions that predate the `ctx`-based signatures those functions
have today. Confirmed this pass: the only reference to this module anywhere
in the tree is a **commented-out** `# import create_character` plus a
commented-out call in `future/main.py` (itself an untracked-scratch-turned-
`future/` holding-pen file, not live) -- so `create_character.py` has zero
live importers. The actual, live new-character flow is
`commands/new_player.py` (1580 lines, ctx-based, its own `Command`
subclass), which does not use this file at all.

| Function                                                     | Notes                                                                                                |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `choose_gender(char)` / `edit_gender(char)`                     |                                                                                                       |
| `choose_name(char)` / `edit_name(char)` / `enter_name(p, edit_mode)` |                                                                                                  |
| `choose_client(p)`                                               | Old client-type/settings selection, pre-`ClientSettings` negotiation flow                            |
| `choose_class(p)` / `display_classes(p)` / `edit_class(p)` / `validate_class_race_combo(p)` |                                                                                        |
| `choose_settings(p)`                                             |                                                                                                       |
| `choose_race(p)` / `display_races(p)` / `edit_race(p)`           |                                                                                                       |
| `choose_age(p)` / `validate_age(age, p)`                         |                                                                                                       |
| `final_edit(p)`                                                  |                                                                                                       |
| `choose_guild(p)`                                                |                                                                                                       |
| `roll_stats(p)` / `preview_stats_with_bonuses(p, class_bonuses, race_bonuses)` |                                                                                          |
| `getnum()`                                                       |                                                                                                       |
| `main(player) -> Player`                                         | Old top-level entry point, superseded by `commands/new_player.py`                                    |
| `debug_menu(p)`                                                  |                                                                                                       |

---

## new_player_2.py (553 lines)
*(STALE — confirmed orphaned this pass, not merely undocumented)* Another
pre-`ctx` character-creation prototype, with its own **third** independent
`Player` class definition (alongside `player.py`'s live one and
`players.py`'s self-flagged-dead one -- see those sections above), plus a
local `Client` dataclass and `Color` enum unrelated to `net_client.Client`/
`terminal.ColorName`. Confirmed this pass: `grep -rl "import new_player_2\|
from new_player_2"` across the tree (outside the file itself) returns
nothing -- zero live importers, same as `create_character.py`.

| Function / Class                                                | Notes                                                                                                |
|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| `Color` (Enum)                                                    | `BLACK`/`WHITE` -- unrelated to `terminal.ColorName`                                                  |
| `Client` (dataclass)                                              | `name`, `rows`, `columns`, `translation`, `text`/`highlight`/`background`/`border` (`Color` fields) -- unrelated to `net_client.Client` |
| `make_random_id()` / `make_random_stat()`                        | Old duplicates of the same-named live helpers in `player.py`                                         |
| `set_up_combinations()` / `set_up_flags()` / `set_up_silver()` / `set_up_stats()` / `set_up_rulan()` / `set_up_terminal()` | Old `Player.__init__` field-default factories -- predecessors of `player.py`'s same-named live functions |
| `Player` (class)                                                  | Old, independent `Player` implementation; `__init__(**kwargs)` with a large FIXME/TODO-laden docstring about eventually using dataclasses; not compatible with the live `player.py` `Player` |

---

## wild_horse_events.py (96 lines)
Wild-horse encounter triggers beyond the random-room placement
`Server._place_wild_horse()` does at boot. Live -- imported by
`simple_server.py` and `commands/drop.py`. Ports SPUR `MAIN.S "horse"` and
`MISC.S "d.sugar"`.

| Function                                             | Notes                                                                                                              |
|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `_room_is_grassy(room)`                                 | Private -- `True` if `'grassy'` is in `room.flags`                                                                  |
| `_current_room(ctx)`                                    | Private -- resolves `ctx`'s current `Room` via `ctx.server.game_map`                                                |
| `try_wandering_horse_encounter(ctx)`                    | async -- per-move d100 roll in grassy rooms only; +15 Ranger / +10 Knight; >70 shows a tracks hint, >93 spawns the horse (both checks independent, matching SPUR) |
| `try_sugar_cube_drop(ctx, room)`                        | async, returns `bool` -- always returns `True` ("fully handled"); outside a grassy room the cube just fails silently; in a grassy room, 50% chance nothing happens, else spawns the wild horse |

`_WILD_HORSE_MONSTER_NUMBER = 136` is duplicated (not imported) from
`simple_server.py`'s own constant of the same value, deliberately, to avoid
a load-time circular import -- documented directly in the module's own
comment.

---

## survival.py (115 lines)
Hunger/thirst/poison/disease tick mechanics, ported from SPUR
`COMBAT.S`/`MAIN.S`. Live -- imported by `simple_server.py`,
`ally_events/starvation.py` (transitively, via shared conventions), and
several `commands/*.py` (`eat.py`, `examine.py`, `drink.py`, `get.py`).

| Function                                  | Notes                                                                                                                       |
|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `survival_tick(player) -> list[str]`         | Call once per command; decrements food/drink on a `config.survival_tick_interval` schedule (`-1` disables depletion entirely), applies ring-of-invisibility stat drain, poison (-2 HP, 30% chance), disease (-1 HP, 30% chance), and starvation (both at 0 → death); Admins/DMs are fully immune (no depletion, no damage, no starvation); keeps `PlayerFlags.HUNGER`/`THIRST` in sync with the `< 7` threshold |
| `restore_food(player, amount)` / `restore_drink(player, amount)` | Add to food/drink, capped at `config.survival_max`                                                              |
| `ration_restore(item) -> int`                | Pure -- derives a 1-9 restore quantity from `item.price` (mirrors SPUR's `gs` quality variable; `rations.json` has no explicit quality field) |
| `apply_poison(player)` / `cure_poison(player)` | Sets/clears `player.poisoned` + `PlayerFlags.POISON`                                                                       |
| `apply_disease(player)` / `cure_disease(player)` | Sets/clears `player.diseased` + `PlayerFlags.DISEASE`                                                                    |

---

## books.py
SPUR book-text emulation (`server/books.json`), same shape/pattern as
`messages.py` below. Live -- imported by `simple_server.py` and
`commands/read.py`.

| Function                                                | Notes                                                                                                    |
|-------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| `load_books(path) -> dict[int, list[str]]`               | Loads `books.json` into `{item_number: [paragraph, ...]}`; logs and returns `{}` on `FileNotFoundError` |
| `get_book_text(ctx, item_number) -> Optional[list[str]]` | Looks up `ctx.server.books.get(item_number)`                                                            |

---

## messages.py
SPUR numbered-message-file emulation (`server/messages.json`, 54 recovered
entries from `SPUR-data/SPUR Messages.txt`). Live -- imported by
`simple_server.py`, `commands/new_player.py`, `encounters/galadriel.py`,
`street/jakes.py`.

| Function                                                    | Notes                                                                                                                  |
|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `load_messages(path) -> dict[int, list[str]]`                  | Same load pattern as `books.py`'s `load_books`                                                                          |
| `get_message(ctx, number) -> Optional[list[str]]`               | Nested `getattr()` so a `ctx` without a `.server` (lightweight test fixture) doesn't raise before the fallback applies |
| `send_message(ctx, number, **context) -> bool`                  | async -- prints message `number` if loaded; supports `{PLACEHOLDER}`-style `str.format()` substitution via kwargs (e.g. gendered pronouns), deliberately not a mini-expression-language -- messages with no placeholders are unaffected |

**`messages.py` vs `message_handlers.py` -- confirmed both files exist,
confirmed neither was merged into the other.** They are unrelated in
purpose despite the similar name: `messages.py` (above) is the live
SPUR-message-lookup module. `message_handlers.py` is a separate, much
smaller (91-line) file whose own module docstring says outright: *"Minimal
message handlers module used by tests."* It defines a toy
`MessageRouter`/`Handler` pair and five `handle_*` example callbacks
(`handle_notification`, `handle_page`, `handle_system`, `handle_new_player`,
`handle_player_created`) operating on a different, simpler `{'type': ...}`
dict shape than `net_common.Message`. Confirmed this pass: its only
importer anywhere in the tree is `tests/social/test_message_handlers.py` --
it is test-support scaffolding, not part of the live message pipeline.

| Function / Class (message_handlers.py)                        | Notes                                                                    |
|-------------------------------------------------------------|--------------------------------------------------------------------------|
| `Handler` (class)                                               | `message_type`, `func`                                                    |
| `MessageRouter` (class)                                         | `register_command(message_type)` decorator, `handle_message(message, client)` |
| `handle_notification` / `handle_page` / `handle_system` / `handle_new_player` / `handle_player_created` | Example handlers, print-based                          |
| `message_router` (module-level `MessageRouter()` instance)      | Pre-registered with the five handlers above                              |

---

## command_settings.py
Per-player command-preference settings (`player.command_settings`),
distinct from `PlayerFlags` (game state) -- for player-controlled UI/behavior
toggles. Live -- imported by `player.py` and several `commands/*.py`.

| Function / Class                                          | Notes                                                                                                             |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `TipsSettings` (dataclass)                                  | `enabled` (auto-show on login), `tip_number` (last-shown cursor) -- `commands/tips.py`                          |
| `BoardSettings` (dataclass)                                 | `last_date` (ISO string) -- only `'board ld'` advances it; `None` means "everything is new" -- `board.py`/`commands/board.py` |
| `TeleportSettings` (dataclass)                              | `destinations: dict` -- name-as-typed → `(level, room)` tuple, via `'teleport #learn <name>'` -- `commands/teleport.py` |
| `CommandSettings` (dataclass)                               | Aggregate: `whereat_hidden`, `groups` (dict, whisper/page group names), `news_show_all`, `haven`, `ignored_pagers`, `tips`, `board`, `teleport`, `wasd_movement` |
| `CommandSettings.to_dict()` / `.from_dict(data)` (classmethod) | Persistence; `from_dict` reconstructs the three nested dataclasses (`tips`/`board`/`teleport`) from plain dicts, and round-trips `teleport.destinations`' JSON-serialized-as-lists back into tuples |

*(New per-player settings added here should get an `editplayer.py` entry
per this file's own CLAUDE.md convention -- not verified field-by-field
against `commands/editplayer.py` this pass; flag for a future check.)*

---

## user_settings.py
*(STALE — confirmed orphaned this pass)* A tiny (33-line) file of three
enums with a literal `# TODO: client settings editor here, pull stuff from
terminal.py` comment at the top -- reads as an abandoned starting sketch
for a client-settings editor that was apparently built directly into
`terminal.py`/`commands/prefs.py` instead. Confirmed this pass: `grep -rl
"import user_settings\|from user_settings"` across the tree (outside the
file itself) returns nothing -- zero importers anywhere.

| Symbol                              | Notes                                                                                            |
|-------------------------------------|----------------------------------------------------------------------------------------------------|
| `ClientSettingsNames` (StrEnum)        | Display-label strings (`"Name"`, `"Screen rows"`, `"Text color"`, etc.) -- overlaps in concept with, but is a separate/unused definition from, `terminal.ClientSettings`'s real fields |
| `Translation` (StrEnum)                | `PetSCII`/`ASCII`/`ANSI` -- separate, unused duplicate of `terminal.Translation`                  |
| `ClientValues` (Enum, `int`)           | Odd hybrid: an `IntEnum`-style class body that's actually just type-annotated attribute stubs (`name: str`, `rows: int`, ...) with no actual enum members -- dead/non-functional as written |

---

## new_server.py (257 lines)
*(STALE — confirmed orphaned this pass)* Yet another alternate server
entry point, built around a `GameServer` class (distinct from
`net_server.py`'s `Server`/`Server.Server`). Handles PID-file locking,
logging setup, graceful-shutdown signal handling, and `load_game_data()`
(map/items/weapons/rations/monsters loading) -- yet none of it is reachable
from the live game. Confirmed this pass: `grep -rl "import new_server\|from
new_server"` across the tree (outside the file itself) returns nothing --
zero importers anywhere, including from `net_server.py` or `player.py`
(both of which reference `net_server.py`, not this file, despite the
similar name). Distinct module from `net_server.py`, not a typo/duplicate
of it -- genuinely a third, separate, also-dead server prototype alongside
`net_server.py` and `create_character.py`'s abandoned pipeline.

| Function / Class                                                | Notes                                                                                                 |
|-------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Module-level PID-file / logging setup                              | Runs at import time -- writes `run/tada_server.pid`, configures `logging.basicConfig` to `logs/server.log`, registers an `atexit` cleanup |
| `Init` (class)                                                       | Yet another separate handshake payload class (third one across `net_client.py`/`net_server.py`/this file) |
| `GameServer` (class)                                                 | `__init__(host, port)`, registers `SIGINT`/`SIGTERM` handlers                                            |
| `GameServer._signal_handler(signum, frame)`                          | Schedules `_handle_shutdown` as an asyncio task                                                          |
| `GameServer._handle_shutdown(signum=None, frame=None)`                | async -- broadcasts a shutdown message, saves all players, closes connections, re-raises `KeyboardInterrupt` on `SIGINT` or `os._exit(0)` otherwise |
| `GameServer.load_game_data()`                                        | Loads `level_<n>.json` map files (1-7), `objects.json`, `weapons.json`, `rations.json`, `monsters.json` via `Item.read`/`Weapon.read`/`Rations.read_rations`/`Monster.read_monsters` |

---

## Not yet covered by this doc (full-rewrite backlog)

Significant modules/packages that exist in the codebase but this doc never
mentions at all. Not stale entries — just gaps. Tackle these during the
planned full rewrite (this pass only patched renamed/deleted modules and the
commands/ list, per explicit scope).

**Whole packages:**
- `combat/` — `engine.py` (1570 lines), `resolution.py` (809 lines —
  `AttackResult`/`MonsterAttackResult`/`AllyAttackResult`/`FleeResult`/
  `SpecialWeaponResult` dataclasses), `duel.py`, `rewards.py`. (A same-named
  top-level `combat.py` was never actually part of this package — it was an
  untracked scratch file, now moved to `future/combat_system.py`, see below.)

**`future/`** — holding pen for untracked scratch files with promising ideas,
not wired into the live game yet:
- `future/combat_system.py` (moved from a stray top-level `combat.py`)
- `future/main.py` (moved from a stray top-level `main.py`, 1312 lines)

**`experiments/`** — learning/tutorial scratch files, not project-specific:
- `experiments/custom_codec_registration.py` (moved from a stray top-level
  `custom_codec_registration.py`) — a generic Python `codecs.register()`
  tutorial example (reverse-string encode, "hello"→"world" decode demo).
  Not real `cbmcodecs2`/PETSCII work despite the name — the actual PETSCII
  encoding lives in `formatting.py`, using `cbmcodecs2`'s
  `petscii_c64en_lc` codec directly. Unused anywhere.

Same audit-caution applies to anything else found sitting at the top level
in the future: verify with `git ls-files --error-unmatch <path>` before
trusting any "new module" claim in this doc, since untracked scratch files
can look like real modules at a glance. (A same-named, similarly untracked
`message.py` was checked and deleted — a dead, unused,
incompatible early draft of what `net_common.py`'s real `Message`/
`MessageType` classes actually shipped as; nothing imported it.)
- `guild_hq/` — `main.py` (now **813 lines**, up from 631 at last pass —
  grew a `_can_manage_bans`/`_ban_management` guild-ban feature since then;
  still also has chalkboard, food/item lockers, guild bank, weapons box,
  activity log as previously noted), `state.py` — still undocumented,
  content description otherwise still accurate, spot-checked this pass
- `street/` — `allies_guild.py` (180 lines, ally training), `jakes.py`
  (305 lines, rations/items/horse training/tips) — still undocumented,
  content description still accurate, spot-checked this pass
- `annex/` — `main.py` (202 lines: school info, spells, news, guild
  standings, personal records, message-board reading, outlaw/guild player
  lists) — still undocumented, content description still accurate,
  spot-checked this pass

**New top-level modules:**
- `news.py` — still undocumented; spot-checked this pass, claimed function
  list (`load_news`, `save_news`, `next_id`, `is_visible`, `is_new_since`,
  `mark_seen`, `format_item`) is still accurate and complete (plus private
  `_parse_iso_date`/`_format_lifetime` helpers not previously mentioned)
- `command_version.py` — still undocumented; spot-checked this pass,
  `get_command_version(command)` is still the only public function (git log
  / mtime lookup for the `#version`/`#ver` switch); three private helpers
  (`_repo_root`, `_git_log_date`, `_mtime_date`) not previously mentioned
- `bar/vinny.py` (362 lines), `bar/thug_attack.py`, `bar/allies.py` — see
  their respective sections above

**Core game-logic modules — now documented in full sections above:**
`player.py`, `players.py`, `combat/engine.py`, `combat/resolution.py`,
`combat/duel.py`, `combat/rewards.py`, `party.py`, `group_management.py`,
`inventory.py`, `flags.py`, `base_classes.py` — moved out of this backlog
list this pass; see their own `##` sections earlier in this file.

**Core game-logic modules — given full sections this pass, moved out of
this backlog list:** `net_common.py`, `net_client.py`, `net_server.py`,
`terminal.py`, `terminal_context.py` (rewritten from a stale placeholder
into an accurate current section), `create_character.py`, `new_player_2.py`,
`wild_horse_events.py`, `survival.py`, `books.py`, `messages.py`,
`message_handlers.py`, `command_settings.py`, `user_settings.py`,
`new_server.py`. Several of these turned out to be fully orphaned dead code
confirmed by grep (zero live importers), not just undocumented:
`create_character.py`, `new_player_2.py`, `new_server.py`, and
`user_settings.py`; `net_server.py` is reachable only via a fallback import
in `player.py` that's never actually exercised since `simple_server`
always imports successfully. See their own `##` sections earlier in this
file for the detail and the grep commands used to confirm each.

`character_editor.py` (687 lines) — deleted 8/1/26, was a dead never-wired
stub (had its own orphaned `Horse` class alongside `characters.py`'s and
`players.py`'s copies; all three removed together, Ryan confirmed).

**Other renamed one-off scripts** (not fixed this pass, minor):
`convert_map_data.py`, `convert_object_data.py`, `convert_ration_data.py`
— not previously in the doc at all, so nothing to correct, just missing.

---

## Legend
| Symbol      | Meaning                                  |
|-------------|------------------------------------------|
| ✅ OK        | Works as-is                              |
| ⚠️ Bug      | Known bug, needs fix                     |
| 🔄 Refactor | Planned refactor (usually ctx migration) |
