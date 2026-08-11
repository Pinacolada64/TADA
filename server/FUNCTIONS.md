# FUNCTIONS.md
## Roadmap of functions across the TADA server codebase

Last updated: manually maintained — update when adding, moving, or removing functions.

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
*(STALE — class names below no longer exist; rewrite pending, see FUNCTIONS.md
full-rewrite plan)* GameContext-compatible context for local terminal use.
The module's actual main class is now confusingly also named `GameContext`
(same name as network_context.py's, imported elsewhere as
`from terminal_context import GameContext as TerminalContext` — see
monster_editor.py). `TerminalSettings`/`TerminalPlayer`/`_TerminalReader`/
`_TerminalWriter`/`TerminalContext` as documented below do **not** exist
under those names anymore. `run_local(coro)` still exists as documented.

| Function / Class (STALE NAMES — see note above)       | Notes                                                                                        |
|-------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `TerminalSettings` (dataclass)                        | Mimics `player.client_settings`; `screen_columns`, `screen_rows`, `return_key`               |
| `TerminalPlayer`                                      | Minimal Player stub; `name`, `client_settings`, `query_flag()`, `set_flag()`, `clear_flag()` |
| `_TerminalReader`                                     | Wraps `input()` as async `readline()`, returns JSON wire format                              |
| `_TerminalWriter`                                     | No-op `write()`/`drain()` — output goes through `ctx.send()`                                 |
| `TerminalContext`                                     | Main class; `player`, `reader`, `writer`, `server=None`, `client=None`                       |
| `TerminalContext.send(*lines)`                        | async — prints to terminal; accepts str, multiple args, or list                              |
| `TerminalContext.send_room(*lines)`                   | async no-op                                                                                  |
| `TerminalContext.prompt(prompt_text, preamble_lines)` | async — prints preamble then prompts for input                                               |
| `run_local(coro)`                                     | Convenience wrapper around `asyncio.run()` for editor entry points                           |

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

**Core game-logic modules still never documented here at all** (not
one-off scripts — these predate or postdate the doc's original scope
entirely): `net_client.py` (916), `net_server.py` (515),
`create_character.py` (1115), `new_player_2.py` (553), `terminal.py` (546),
`wild_horse_events.py` (96), `survival.py` (115), `net_common.py` (281),
`new_server.py` (257), `books.py`, `messages.py`/`message_handlers.py`,
`command_settings.py`, `user_settings.py`.

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
