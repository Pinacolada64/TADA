import os
import sys
from pathlib import Path
from old_server import menu_system
from old_server.commands.help import headline
from old_server.setup import GameConfig

# Global flag to track if server is running
server_running = False

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
    """Edit game configuration."""
    print("Game config editor not yet implemented.")
    print("Use/edit 'server_config.json' for now.")

def edit_game_goal():
    """Edit game goal configuration."""
    print("Game goal editor not yet implemented.")
    print("Use/edit 'game_config.json' for now.")

def edit_motd():
    """Edit message of the day."""
    print("'Message of the day' editor not yet implemented.")
    print("Use/edit 'motd.txt' for now.")

def edit_news():
    """Edit news."""
    print("News editor not yet implemented.")
    print("Use/edit 'news.txt' for now.")

def edit_server_config():
    """Edit server configuration."""
    from old_server.config import config
    
    def toggle_invites():
        current = config.require_invites
        new_setting = not current
        config.require_invites = new_setting
        status = "enabled" if new_setting else "disabled"
        print(f"\nInvite requirement is now {status}.")
    
    while True:
        print("\n" + headline("Server Configuration"))
        print(f"1. {'[X]' if config.require_invites else '[ ]'} Require invites for registration")
        print("2. Back to main menu")
        
        choice = input("\nSelect an option (1-2): ").strip()
        
        if choice == '1':
            toggle_invites()
        elif choice == '2':
            break
        else:
            print("Invalid choice. Please try again.")


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
    menu = menu_system.Menu(title="Server Setup")
    menu.add_menu_item('s', 'Set up game data', submenu=setup_data)
    menu.add_menu_item('m', 'Make directories', submenu=create_directories)
    menu.add_menu_item('e', 'Edit directories', submenu=edit_directories)
    menu.add_menu_item('v', 'Convert data files', submenu=convert_data_files)
    menu.add_menu_item('n', 'Edit news', submenu=edit_news)
    menu.add_menu_item('c', 'Edit server config', submenu=edit_server_config)
    menu.add_menu_item('g', 'Edit game config', submenu=edit_game_config)
    menu.add_menu_item('q', 'Quit', lambda: sys.exit(0))
    menu.run()

def setup_data():
    menu = menu_system.Menu(title="Set up game data")
    menu.add_menu_item('Configure game goal', GameConfig.setup_game_goal)
    menu.run()

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

def edit_data_dir():
    menu = menu_system.Menu(title="Edit Data Directory")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'data_dir', ServerDefaults.data_dir))
    menu.add_menu_item('Data directory', 
                     dot_leader_handler=lambda: GameConfig.directories.data_dir,
                     action=lambda: move_directory(GameConfig.directories.data_dir, GameConfig.directories.data_dir))
    menu.run()
    
def edit_log_dir():
    menu = menu_system.Menu(title="Edit Log Directory")
    menu.add_menu_item("The log directory is where server logs are stored.")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'log_dir', ServerDefaults.log_dir))
    menu.add_menu_item('Log directory',
                     dot_leader_handler=lambda: GameConfig.directories.log_dir,
                     action=lambda: move_directory(GameConfig.directories.log_dir, GameConfig.directories.log_dir))
    menu.run()

def edit_mail_dir():
    menu = menu_system.Menu(title="Edit Mail Directory")
    menu.add_menu_item("The mail directory is where player mail is stored.")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'mail_dir', ServerDefaults.mail_dir))
    menu.add_menu_item('Mail directory',
                     dot_leader_handler=lambda: GameConfig.directories.mail_dir,
                     action=lambda: move_directory(GameConfig.directories.mail_dir, GameConfig.directories.mail_dir))
    menu.run()

def edit_invite_dir():
    menu = menu_system.Menu(title="Edit Invite Directory")
    menu.add_menu_item("The invite directory is where player invites are stored.")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'invite_dir', ServerDefaults.invite_dir))
    menu.add_menu_item('Invite directory',
                     dot_leader_handler=lambda: GameConfig.directories.invite_dir,
                     action=lambda: move_directory(GameConfig.directories.invite_dir, GameConfig.directories.invite_dir))
    menu.run()

def edit_client_dir():
    menu = menu_system.Menu(title="Edit Client Directory")
    menu.add_menu_item("The client directory is where the client IP addresses and user data are stored.")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'client_dir', ServerDefaults.client_dir))
    menu.add_menu_item('Client directory',
                     dot_leader_handler=lambda: GameConfig.directories.client_dir,
                     action=lambda: move_directory(GameConfig.directories.client_dir, GameConfig.directories.client_dir))
    menu.run()

def edit_server_dir():
    menu = menu_system.Menu(title="Edit Server Directory")
    menu.add_menu_item("The server directory stores server invites and client login data.")
    menu.add_menu_item('Restore server default', action=lambda: setattr(GameConfig.directories, 'server_dir', ServerDefaults.server_dir))
    menu.add_menu_item('Server directory',
                     dot_leader_handler=lambda: GameConfig.directories.server_dir,
                     action=lambda: move_directory(GameConfig.directories.server_dir, GameConfig.directories.server_dir))
    menu.run()

def move_directory(old_path, new_path):
    if server_running:
        print("NOTE: This will move the directory and all its contents. This will not take effect until the server is restarted.")
    if os.path.isabs(old_path) or os.path.isabs(new_path) or os.path.commonpath([old_path, new_path]) != os.path.sep:
        print("Error: Paths must be relative and not contain root folder access.")
        return

    if input_yes_no(f"Move directory {old_path} to {new_path}? "):
        if os.path.exists(old_path):
            os.rename(old_path, new_path)

def edit_directories():
    menu = menu_system.Menu(title="Edit Directories")
    menu.add_menu_item('Data directory', action=edit_data_dir, dot_leader_handler=lambda: GameConfig.directories.data_dir)
    menu.add_menu_item('Log directory', action=edit_log_dir, dot_leader_handler=lambda: GameConfig.directories.log_dir)
    menu.add_menu_item('Invite directory', action=edit_invite_dir, dot_leader_handler=lambda: GameConfig.directories.invite_dir)
    menu.add_menu_item('Client directory', action=edit_client_dir, dot_leader_handler=lambda: GameConfig.directories.client_dir)
    menu.add_menu_item('Server directory', action=edit_server_dir, dot_leader_handler=lambda: GameConfig.directories.server_dir)
    menu.run()

def blah():
    """Menu-driven setup program for the server."""
    # TODO: just throwing spaghetti at the wall, check CONTROL.S in spur-code/
    menu = menu_system.Menu(title="Server Setup")
    menu.add_menu_item('Setup server data', action=setup_data)
    menu.add_menu_item('Setup game data', action=setup_game_data)
    menu.add_menu_item('Setup directories', action=create_directories)
    menu.add_menu_item('Edit directories', action=edit_directories)
    menu.add_menu_item('Convert data files', action=convert_data_files)
    menu.add_menu_item('Edit game config', action=edit_game_config)
    menu.add_menu_item('Edit game goal', action=edit_game_goal)
    menu.add_menu_item('Upgrade server', action=upgrade_server)
    menu.add_menu_item('Quit', action=sys.exit)
    menu.run()

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
    """
    if not Path(GameConfig.directories.data_dir + '/server_config.json').exists():
        print('No server config found. Creating default config...')
        GameConfig.save()
        print('Running setup program...')
        main()
    else:
        print('Server config found. Loading server configuration...')
        GameConfig.load()
        print('Running server...')
    """
    main()
    