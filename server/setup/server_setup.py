import os
import sys
from pathlib import Path

from config import SETTINGS_METADATA, config, format_value, parse_value, resolve_key

# Global flag to track if server is running
server_running = False


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
    """Prompt for and apply a new value for a single config.py setting."""
    _value_type, desc = SETTINGS_METADATA[key]
    current = format_value(config.get(key))
    print(f"\n{key}: {desc}")
    raw = input(f"Current: {current}  -  new value (blank to cancel): ").strip()
    if not raw:
        return
    try:
        value = parse_value(key, raw)
        config.set_validated(key, value)
    except ValueError as exc:
        print(str(exc))
        return
    print(f"{key} set to {format_value(config.get(key))}.")


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
            value = format_value(config.get(key))
            print(f"{i:2d}. {key:<28} {value}")
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
