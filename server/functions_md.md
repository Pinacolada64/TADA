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
| `_armory`, `_protection`, `_general_store`, `_bank`, `_wizard`, `_clan`, `_pawn_shop`, `_player_list` | async stubs — each will become a full sub-module |
| `_elevator(ctx)`               | async — delegates to `shoppe.elevator.main(ctx)`                                          |

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
| `_vinny(ctx, bar)`         | async — Vinny stub; broadcasts approach/leave to bar area                                                     |
| `_blue_djinn/_skip/_bar_none/_fat_olaf/_zelda` | async — delegates to respective sub-module `main(ctx, bar)`             |
| `_ROUTINES` (dict)         | Maps routine key strings to async callables for dispatch                                                      |
| `_DIRECTION_NAMES` (dict)  | `'n'→'north'` etc.; used in movement broadcast messages                                                       |

---

## bar/blue_djinn.py
The Blue Djinn interaction: drinks, gambling, combat challenge.

| Function         | Notes                                                                                         |
|------------------|-----------------------------------------------------------------------------------------------|
| `main(ctx, bar)` | async — approach `broadcast_area`, interaction loop, ejection via Mundo or leave broadcast    |

---

## bar/skip.py
Skip's Eats: once-per-day meal counter.

| Function         | Notes                                                                                              |
|------------------|----------------------------------------------------------------------------------------------------|
| `main(ctx, bar)` | async — once-per-day gate; approach `broadcast_area` fires only after gate passes; leave broadcast |

---

## bar/bar_none.py
Bar None (Mae the Bartender): drinks menu.

| Function         | Notes                                                                              |
|------------------|------------------------------------------------------------------------------------|
| `main(ctx, bar)` | async — approach `broadcast_area`; leave broadcast on empty input only (not on EOF) |

---

## bar/fat_olaf.py
Fat Olaf's Servant Trade: buy/sell party allies.

| Function                              | Notes                                                                    |
|---------------------------------------|--------------------------------------------------------------------------|
| `main(ctx, bar)`                      | async — approach `broadcast_area`, buy/sell loop, leave broadcast        |
| `_buy_servant(ctx, allies)`           | async — numbered menu to select and purchase a servant                   |
| `_sell_servant(ctx)`                  | async stub                                                               |
| `filter_allies(ally_list, status)`    | Pure — returns allies matching `AllyStatus`                              |

---

## bar/zelda.py
Madame Zelda's: spy on player stats or resurrect monsters.

| Function                   | Notes                                                                    |
|----------------------------|--------------------------------------------------------------------------|
| `main(ctx, bar)`           | async — approach `broadcast_area`, command loop, leave broadcast         |
| `_study_player(ctx)`       | async — prompts for target player name, charges 1,000 silver, shows stats from disk |
| `_resurrect_monsters(ctx)` | async — charges 6,000 silver, writes to battle log (TODO)                |
| `get_player_info(stats, id_pattern)` | Pure sync — reads player JSON from `run/server/player-<id>.json` |
| `_zelda_menu(ctx)`         | async — prints available options                                          |

---

## bar/ally_data.py
Ally/servant data definitions used by Fat Olaf.

| Symbol / Function                        | Notes                                         |
|------------------------------------------|-----------------------------------------------|
| `AllyFlags`, `AllyStatus` (Enum)         | Flags and lifecycle states for allies         |
| `Ally` (dataclass)                       | `name`, `strength`, `status`, `flags`         |
| `load_allies()`                          | Returns `list[Ally]` from JSON                |
| `assign_random_statuses(allies)`         | Pure — randomly assigns `SERVANT`/`IN_PARTY`  |

---

## commands/
All commands are `Command` subclasses auto-discovered by `command_processor.py`.

| Module / Class      | Keyword(s)            | Notes                                                                                  |
|---------------------|-----------------------|----------------------------------------------------------------------------------------|
| `GetCommand`        | `get`, `g`            | Pick up items from current room; tracks per-player pickup in `player.picked_up_items`  |
| `DropCommand`       | `drop`                | Drop inventory item into current room                                                  |
| `ReadyCommand`      | `ready`, `wield`, `equip` | Select and ready a weapon from inventory; shows weapon class/race bonuses          |
| `WhereatCommand`    | `whereat`, `wa`       | Show all connected players with room/virtual-location; restricted to privileged players |
| `TeleportCommand`   | `teleport`, `tp`      | Move player to target room; flash-of-light `send`+`send_room` at origin and destination |
| `StatsCommand`      | `stats`, `st`         | Show player stats; uses `characters.py` race/class bonus tables                        |
| `InvCommand`        | `inv`, `i`            | Show inventory; persisted across save/load via `player.inventory`                      |
| `LookCommand`       | `look`, `l`           | Describe room; skips players whose `virtual_location` is set (ghost-player fix)        |

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
| `Pixie`, `Ally`, `Horse`, `Monster`      | Concrete character subclasses                                                     |
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

## Legend
| Symbol      | Meaning                                  |
|-------------|------------------------------------------|
| ✅ OK        | Works as-is                              |
| ⚠️ Bug      | Known bug, needs fix                     |
| 🔄 Refactor | Planned refactor (usually ctx migration) |
