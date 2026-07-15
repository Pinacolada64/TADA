import os
import shutil
import sys
from pathlib import Path

# Running this as a plain script (`python3 setup/server_setup.py`) puts
# only setup/ on sys.path, not server/ where config.py/item_system.py
# live -- ModuleNotFoundError: No module named 'config'. `python3 -m
# setup.server_setup` (run from server/) doesn't need this, but a sysop
# reasonably expects the plain-script form to work too.
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from config import SETTINGS_METADATA, config, format_value, parse_value, resolve_key
from item_system import (
    format_victory_item_choices, format_victory_item_value,
    is_victory_item_number_valid, victory_eligible_treasures,
)

_VICTORY_ITEM_KEY = 'victory_item_number'


def _display_value(key: str, value) -> str:
    """format_value(), except victory_item_number also shows the
    treasure's name once victory_type is 'item'/'both' -- Ryan: '(35)
    Sand Dollar' instead of a bare 35, which means nothing on sight."""
    if key == _VICTORY_ITEM_KEY:
        return format_victory_item_value(value, config.victory_type)
    return format_value(value)


# Global flag to track if server is running
server_running = False


def _print_paged(lines: list, page_size: int = None) -> None:
    """Print *lines* a screenful at a time, mirroring the live game's
    ctx.send() auto-pagination (network_context.py's PlayerFlags.
    MORE_PROMPT gating) for this offline console script -- 115+ Treasure
    items in one dump would otherwise scroll straight off the terminal.

    Enter -- next page. Q -- stop early.
    """
    if page_size is None:
        page_size = max(5, shutil.get_terminal_size(fallback=(80, 24)).lines - 3)
    total = len(lines)
    for start in range(0, total, page_size):
        chunk = lines[start:start + page_size]
        for line in chunk:
            print(line)
        shown_through = start + len(chunk)
        if shown_through >= total:
            break
        choice = input(f'-- More ({shown_through}/{total}) -- Enter to continue, Q to stop: ').strip().lower()
        if choice == 'q':
            break


def headline(text: str) -> str:
    """Simple banner. old_server.commands.help.headline (this script's
    original import) doesn't exist anywhere in this checkout -- there is
    no old_server package at all -- so this is a minimal standalone
    replacement rather than a real dependency."""
    bar = '=' * len(text)
    return f'{bar}\n{text}\n{bar}'


def input_yes_no(prompt):
    """Get yes/no input from user."""
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'.")


def setup_game_data():
    """Setup game data configuration."""
    print("Game data setup not yet implemented.")


def edit_game_config():
    """Edit game configuration -- folded into edit_server_config() now
    that config.py's ServerConfig covers game_name/session_time_limit/
    victory_* alongside the rest of server config, instead of a separate
    game_config.json."""
    edit_server_config()


def edit_game_goal():
    """Edit game goal (win condition) -- SPUR.CONTROL.S's object label
    lives in edit_server_config() as victory_type/victory_gold_amount/
    victory_item_number, not a separate editor."""
    edit_server_config()


def edit_motd():
    """Edit message of the day."""
    print("'Message of the day' editor not yet implemented.")
    print("Use/edit 'motd.txt' for now.")


def edit_news():
    """Edit news."""
    print("News editor not yet implemented.")
    print("Use/edit 'news.txt' for now.")


def _edit_one_setting(key: str) -> None:
    """Prompt for and apply a new value for a single config.py setting.

    victory_item_number gets a special '?' listing of eligible Treasure
    items (item_system.victory_eligible_treasures()) -- same as the live
    in-game CONFIG command.
    """
    info = SETTINGS_METADATA[key]
    while True:
        current = _display_value(key, config.get(key))
        hint = " Type '?' to list eligible items." if key == _VICTORY_ITEM_KEY else ''
        print(f"\n{info.label}: {info.description}")
        raw = input(f"Current: {current}  -  new value (blank to cancel){hint}: ").strip()
        if not raw:
            return

        if key == _VICTORY_ITEM_KEY and raw == '?':
            items = victory_eligible_treasures()
            print('\nTreasure items eligible for Victory Item:\n')
            _print_paged(format_victory_item_choices(items))
            print()
            continue

        try:
            value = parse_value(key, raw)
            if key == _VICTORY_ITEM_KEY and not is_victory_item_number_valid(value):
                raise ValueError(
                    f"{value} isn't a valid Treasure item number (or too generic a "
                    "name -- SPUR.CONTROL.S's chk.obj rule). Type '?' to list eligible items."
                )
            config.set_validated(key, value)
        except ValueError as exc:
            print(str(exc))
            return
        print(f"{info.label} set to {_display_value(key, config.get(key))}.")
        return


def edit_server_config():
    """Edit server configuration.

    Lists every setting in config.py's SETTINGS_METADATA -- the exact same
    table the live in-game CONFIG command (commands/config.py) uses, so
    this offline tool and a logged-in admin always see/validate the same
    settings, nothing duplicated between the two.
    """
    keys = list(SETTINGS_METADATA)
    while True:
        print("\n" + headline("Server Configuration"))
        for i, key in enumerate(keys, start=1):
            value = _display_value(key, config.get(key))
            print(f"{i:2d}. {SETTINGS_METADATA[key].label:<28} {value}")
        print(f"{len(keys) + 1:2d}. Back to main menu")

        choice = input(
            f"\nSelect a setting to edit (1-{len(keys) + 1}), "
            "or type its name (abbreviations OK): "
        ).strip()
        if not choice:
            continue
        if choice == str(len(keys) + 1):
            break
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(keys):
                _edit_one_setting(keys[idx - 1])
            else:
                print("Invalid choice. Please try again.")
            continue

        # Typed a name (possibly abbreviated) instead of a number --
        # config.resolve_key() is the same partial-match logic the live
        # in-game CONFIG command uses.
        key, candidates = resolve_key(choice)
        if key is None:
            if candidates:
                print(f"'{choice}' matches more than one setting: {', '.join(candidates)}.")
            else:
                print(f"Unknown setting '{choice}'.")
            continue
        _edit_one_setting(key)


class ServerDefaults:
    def __init__(self):
        self.data = "server/data"
        self.logs = "server/logs"
        self.invites = "server/invites"
        self.client = "server/client"
        self.server = "server/server"
        self.motd = "server/motd.txt"
        self.news = "server/news.txt"
        self.server_config = "server/server_config.json"
        self.game_config = "server/game_config.json"


def main():
    print(headline("*** Totally Awesome Dungeon Adventure (TADA) Game Server Setup ***"))
    while True:
        print("\n" + headline("Server Setup"))
        print("s. Set up game data")
        print("m. Make directories")
        print("e. Edit directories")
        print("v. Convert data files")
        print("n. Edit news")
        print("c. Edit server config")
        print("g. Edit game config")
        print("q. Quit")

        choice = input("\nChoice: ").strip().lower()
        if choice == 's':
            setup_data()
        elif choice == 'm':
            create_directories()
        elif choice == 'e':
            edit_directories()
        elif choice == 'v':
            convert_data_files()
        elif choice == 'n':
            edit_news()
        elif choice == 'c':
            edit_server_config()
        elif choice == 'g':
            edit_game_config()
        elif choice == 'q':
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")


def setup_data():
    # This used to open a submenu for "Configure game goal" -- that's
    # edit_server_config()'s victory_type/victory_gold_amount/
    # victory_item_number now, not a separate GameConfig-backed screen
    # (GameConfig doesn't exist anywhere in this checkout).
    print("Game data setup not yet implemented.")
    print("(Game goal / victory conditions: see 'c' Edit server config.)")


def create_directories():
    # create directories if they don't exist
    print("Skipping server directory creation, this is just a placeholder for now.")
    """
    if not Path(GameConfig.directories.data_dir).exists():
        Path(GameConfig.directories.data_dir).mkdir(parents=True, exist_ok=True)
    if not Path(GameConfig.directories.log_dir).exists():
        Path(GameConfig.directories.log_dir).mkdir(parents=True, exist_ok=True)
    if not Path(GameConfig.directories.invite_dir).exists():
        Path(GameConfig.directories.invite_dir).mkdir(parents=True, exist_ok=True)
    if not Path(GameConfig.directories.client_dir).exists():
        Path(GameConfig.directories.client_dir).mkdir(parents=True, exist_ok=True)
    if not Path(GameConfig.directories.server_dir).exists():
        Path(GameConfig.directories.server_dir).mkdir(parents=True, exist_ok=True)
    """

def convert_data_files():
    # convert data .txt files to .json
    # TODO: convert "monsters.txt" files (use convert_monster_data.py)
    # TODO: convert "items.txt" files (use convert_object_data.py)
    # TODO: convert "weapons.txt" files (use convert_weapon_data.py)
    # TODO: convert "rations.txt" files (use convert_food_data.py)
    # TODO: convert "map_data.txt" files (use convert_map_data.py)
    # TODO: check if run/client/net/ directory exists: overwriting will destroy player logins!
    # TODO: check if run/server/net/ directory exists: overwriting will destroy user data!
    print("Skipping data conversion, this is just a placeholder for now.")


def edit_directories():
    # TODO: this whole directories subsystem depended on a GameConfig
    # class that doesn't exist anywhere in this checkout (unrelated to
    # config.py's ServerConfig) -- needs a real design, not a quick patch.
    print("Directory editing not yet implemented.")


def move_directory(old_path, new_path):
    if server_running:
        print("NOTE: This will move the directory and all its contents. This will not take effect until the server is restarted.")
    if os.path.isabs(old_path) or os.path.isabs(new_path) or os.path.commonpath([old_path, new_path]) != os.path.sep:
        print("Error: Paths must be relative and not contain root folder access.")
        return

    if input_yes_no(f"Move directory {old_path} to {new_path}? "):
        if os.path.exists(old_path):
            os.rename(old_path, new_path)


def upgrade_server():
    """Upgrade the server to the latest version."""
    print("NOTE: This will upgrade the server to the latest version. The upgrade will not take effect until the server is restarted.")
    if input_yes_no("Upgrade server? "):
        print('Upgrading server...')
        # TODO: import server_upgrade
        # result = server_upgrade.main()
        result = 1
        if result == 0:
            print('Server upgrade complete, no errors.')
        else:
            print(f'Server upgrade failed, status {result}')
    else:
        print('Server upgrade cancelled.')


if __name__ == "__main__":
    main()
