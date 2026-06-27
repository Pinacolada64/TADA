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

## context.py
Core context object passed to all commands and editor functions.

| Function / Class                                  | Notes                                                                               |
|---------------------------------------------------|-------------------------------------------------------------------------------------|
| `GameContext` (dataclass)                         | Holds `player`, `reader`, `writer`, `server`, `client`                              |
| `GameContext.send(*lines)`                        | async — send text to this player only                                               |
| `GameContext.send_room(*lines, exclude_self)`     | async — send to all players in same room                                            |
| `GameContext.prompt(prompt_text, preamble_lines)` | async — send prompt, await single-line response; mirrors `TerminalContext.prompt()` |

---

## terminal_context.py
GameContext-compatible context for local terminal use. Satisfies the same
interface as `GameContext` so editor functions work identically locally or
wired into the network server.

| Function / Class                                      | Notes                                                                                        |
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
| `prompt_client(ctx, preamble_lines, prompt_text)`                                       | ⚠️ Bug     | `reader` should be `ctx.reader`                |
| `input_string(ctx, default, prompt, allow_empty, keep_msg, reminder)`                   | ⚠️ Bug     | Some `ctx.send()` calls missing `await`        |
| `input_number_range(ctx, default, prompt_msg, min_value, max_value, out_of_bounds_msg)` | ⚠️ Partial | Uses bare `input()` instead of `prompt_client` |
| `set_logging_level(ctx)`                                                                | ⚠️ Bug     | Calls `input_string` without `await`           |
| `text_pager(ctx, text_lines)`                                                           | ⚠️ Partial | Some `ctx.send()` calls missing `await`        |
| `header(ctx, header_text)`                                                              | ✅ OK       | async, sends underlined header                 |

### Pure / sync (no ctx)
| Function                                           | Status | Notes                                      |
|----------------------------------------------------|--------|--------------------------------------------|
| `oxford_comma_list(items)`                         | ✅ OK   | Pure string utility                        |
| `grammatical_list(item_list)`                      | ✅ OK   | Pure string utility                        |
| `a_or_an(string, capitalize)`                      | ✅ OK   | Pure string utility                        |
| `get_article_and_quantity(item_name)`              | ✅ OK   | Pure string utility                        |
| `list_players_in_room(player_list)`                | ⚠️ Bug | Calls `oxford_comma_list()` with no args   |
| `make_random_id()`                                 | ✅ OK   | Returns random int 1-65536                 |
| `input_yes_no(prompt)`                             | ✅ OK   | Sync, no ctx — keep for local terminal use |
| `get_pronoun(character, pronoun_type, capitalize)` | ✅ OK   | Player-aware, pure output                  |
| `frame_text(p, text, title, width)`                | ✅ OK   | Returns list[str], no I/O                  |
| `tip(p, title, message)`                           | ✅ OK   | Returns list[str], respects EXPERT_MODE    |
| `bulleted_list_format(text, width, ...)`           | ✅ OK   | Pure formatting                            |

---

### Needs full rewrite
| Function                       | Notes                                                        |
|--------------------------------|--------------------------------------------------------------|
| `fileread(self, filename, p)`  | Uses old `UserHandler`/`self` pattern — rewrite to use `ctx` |
| `game_help(self, player, arg)` | Uses old pattern — rewrite to use `ctx`                      |

---

## menu_system.py
Hierarchical menu system. All functions now take `ctx` (GameContext or TerminalContext).

| Function / Class                          | Notes                                                                                |
|-------------------------------------------|--------------------------------------------------------------------------------------|
| `MenuItem` (dataclass)                    | `text`, `shortcuts`, `dot_leader_handler`, `submenu`, `action`; `is_header` property |
| `Menu` (dataclass)                        | `title`, `columns`, `menu_items`; `selectable` property                              |
| `format_menu_lines(ctx, menu)`            | Returns `list[str]`; reads screen width from `ctx.player.client_settings`            |
| `print_menu(ctx, menu)`                   | async — formats and sends menu via `ctx.send()`                                      |
| `get_user_choice(ctx, menu, stack_depth)` | async — prompts via `ctx.prompt()`, returns `MenuItem` or `None`                     |
| `navigate_menu(ctx, menu_stack)`          | async — interactive loop; pushes submenus, pops on cancel                            |
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
| `PETSCIICodec` (dataclass)                             | Commodore reverse-video highlighting; full palette TODO                                                                    |
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

## monsters.py
Monster data and flag definitions. Shared by editor and game server.

| Function / Symbol               | Notes                                 |
|---------------------------------|---------------------------------------|
| `monster_flag_labels` (dict)    | Snake_case key → human-readable label |
| `load_monsters(path)`           | Returns `list[dict]` from JSON        |
| `save_monsters(monsters, path)` | Writes `list[dict]` to JSON           |

---

## monster_editor.py
Standalone terminal editor for monsters.json. Will eventually be wired into server command structure via `GameContext`.

| Function                                      | Notes                                                             |
|-----------------------------------------------|-------------------------------------------------------------------|
| `prompt(msg, default)`                        | Sync wrapper — replace with `ctx.prompt()` when async             |
| `confirm(msg)`                                | Sync yes/no — replace with `input_yes_no()` from `tada_utilities` |
| `pause()`                                     | Sync — replace with `ctx.prompt()`                                |
| `header(title)`                               | Sync — replace with `tada_utilities.header(ctx, ...)`             |
| `numbered_menu(items, title, extra_inputs)`   | Replace with `menu_system` integration                            |
| `load_monster_locations(level_files)`         | Loads level JSON, builds monster→room lookup                      |
| `load_quotes(path)`                           | Returns `dict[int, str]`                                          |
| `load_weapons(path)`                          | Returns `dict[int, str]`                                          |
| `active_flags(monster)`                       | Returns list of active flag keys                                  |
| `show_monster(m, quotes, weapons, locations)` | Display monster stats — move to `monsters.py`?                    |
| `list_quotes(quotes)`                         | Numbered menu of quotes, returns quote number                     |
| `edit_basic(m, quotes, weapons)`              | Edit non-flag attributes                                          |
| `edit_flags(m)`                               | Toggle flags via numbered menu                                    |
| `edit_monster(m, quotes, weapons, locations)` | Per-monster edit menu                                             |
| `search_by_attribute(monsters, weapons)`      | Attribute search with weapon menu                                 |
| `main()`                                      | Top-level editor loop                                             |

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

---

## convert_monster_data.py
Converts `monsters.txt` binary to `monsters.json`.

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
Converts `MONSTER.QUOTE.TXT` to `monster_quotes.json`.

| Function                               | Notes                                     |
|----------------------------------------|-------------------------------------------|
| `is_allcaps(text)`                     | Returns True if >80% uppercase            |
| `sentence_case(text)`                  | Converts all-caps string to sentence case |
| `normalize(text)`                      | Applies sentence_case if needed           |
| `convert(txt_filename, json_filename)` | Main conversion entry point               |

---

## cross_reference.py
Cross-references ammo items against weapons.

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

## patch_descriptions.py
One-shot script to patch descriptions into monsters.json.

| Symbol                | Notes                                 |
|-----------------------|---------------------------------------|
| `DESCRIPTIONS` (dict) | `monster_number → description string` |

---

## Legend
| Symbol      | Meaning                                  |
|-------------|------------------------------------------|
| ✅ OK        | Works as-is                              |
| ⚠️ Bug      | Known bug, needs fix                     |
| 🔄 Refactor | Planned refactor (usually ctx migration) |
