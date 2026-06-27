#!/bin/env python3

import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, Dict, List, Optional

# TADA-specific imports:
from base_classes import Map, PlayerMoneyTypes, compass_txts
from characters import Monster
from client_manager import ClientManager
from command_handler import CommandHandler
from items import Item, Rations, Weapon
from player import Player
from net_server import Mode, UserHandler
from net_common import Message, MessageType, to_jsonb, from_jsonb
from net_client import Client
from tada_utilities import a_or_an

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Ensure logs and run directories exist
logs_dir = project_root / 'logs'
run_dir = project_root / 'run'
logs_dir.mkdir(exist_ok=True)
run_dir.mkdir(exist_ok=True)

# Check if server is already running
pid_file = run_dir / 'tada_server.pid'
if pid_file.exists():
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        # Check if process is still running
        if (run_dir / f'proc/{pid}').exists():
            logging.warning(f"Server is already running with PID: {pid}")
            sys.exit(1)
    except (ValueError, ProcessLookupError):
        # PID file exists but process is not running, remove stale file
        pid_file.unlink(missing_ok=True)

# Write current PID to file
with open(pid_file, 'w') as f:
    f.write(str(os.getpid()))

# Clean up PID file on exit
import atexit
atexit.register(lambda: pid_file.unlink(missing_ok=True))

# Configure logging
log_file = logs_dir / 'server.log'
logging.basicConfig(
    level=logging.DEBUG,
    format=f'%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logging = logging.getLogger(__name__)

class Init:
    """
    Represents the initialization message exchanged between the server and client.

    Attributes:
        server_id (str): The unique identifier for the server.
        server_key (str): The key used for server authentication.
        protocol_version (int): The version of the communication protocol.
        translation (str): The character encoding used for communication.
        type (MessageType): The type of the message, set to `MessageType.init`.
    """
    def __init__(self, server_id="test_server", server_key="test_key", protocol_version=1,
                 translation="utf-8"):
        self.server_id = server_id
        self.server_key = server_key
        self.protocol_version = protocol_version
        self.translation = translation
        self.type = MessageType.init

class GameServer:
    """
    Manages the server state, client connections, and game data.

    Attributes:
        running (bool): Indicates whether the server is running.
        host (str): The hostname or IP address the server binds to.
        port (int): The port number the server listens on.
        server (asyncio.Server): The asyncio server instance.
        clients (dict): A dictionary of connected clients, keyed by their address.
        client_manager (ClientManager): Manages client connections and interactions.
        players (dict): A dictionary of players, keyed by their IDs.
        room_players (dict): Tracks which players are in which rooms.
        lock (asyncio.Lock): Ensures thread-safe access to shared resources.
        game_map (Map): Represents the game map and its data.
        _shutting_down (bool): Indicates whether the server is in the process of shutting down.
    """
    quotation_mark = '"'
    server_init_object = Init(
        server_id="test_server",
        server_key="test_key",
        protocol_version=1,
        translation='utf-8'
    )

    def __init__(self, host, port):
        """
        Initializes the GameServer instance.

        Args:
            host (str): The hostname or IP address the server binds to.
            port (int): The port number the server listens on.
        """
        self.running = True
        self.host = host
        self.port = port
        self.server = None
        self.clients = {}
        self.client_manager = ClientManager()
        self.players = {}
        self.room_players = {}
        self.lock = asyncio.Lock()
        self.game_map = None
        self._shutting_down = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handles system signals to initiate server shutdown.

        Args:
            signum (int): The signal number.
            frame (frame): The current stack frame.
        """
        if self._shutting_down:
            return

        self._shutting_down = True
        logging.info(f"Received signal {signum}, scheduling shutdown...")
        asyncio.create_task(self._handle_shutdown(signum, frame))

    async def _handle_shutdown(self, signum=None, frame=None):
        """
        Handles the server shutdown process, including notifying clients and saving state.

        Args:
            signum (int, optional): The signal number, if called from a signal handler.
            frame (frame, optional): The current stack frame, if called from a signal handler.
        """
        if not self.running:
            return

        logging.info("Starting graceful shutdown...")
        self.running = False

        try:
            # Notify all connected clients
            if hasattr(self, 'client_manager') and self.client_manager:
                shutdown_msg = {
                    'type': 'server_message',
                    'message': 'Server is shutting down. Disconnecting...',
                    'timestamp': time.time()
                }
                self.client_manager.broadcast(shutdown_msg, exclude_user=None)
                logging.info("Broadcasted shutdown message to all players")

                # Give clients a moment to receive the message
                await asyncio.sleep(1)

            # Save player states if possible
            if hasattr(self, 'players') and self.players:
                with self.lock:  # Ensure thread safety when accessing players
                    for player_id, player in list(self.players.items()):
                        try:
                            if hasattr(player, 'save'):
                                player.save()
                                logging.info(f"Saved player state: {getattr(player, 'name', player_id)}")
                            else:
                                logging.warning(f"Player {player_id} has no save method")
                        except Exception as e:
                            logging.error(f"Error saving player {player_id}: {e}")
                logging.info("Completed saving player states")

            # Close all client connections
            if hasattr(self, 'client_manager') and self.client_manager:
                if hasattr(self.client_manager, 'close_all_connections'):
                    await self.client_manager.close_all_connections()
                logging.info("Closed all client connections")

            logging.info("Server shutdown complete")

        except Exception as e:
            logging.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            # Ensure we exit cleanly
            if signum is not None:
                import signal as signal_module
                # Re-raise the signal to allow normal exit
                if signum == signal_module.SIGINT:
                    raise KeyboardInterrupt()
                os._exit(0)

        # Stop the server
        logging.info("Shutting down server...")
        self.stop()

    def load_game_data(self):
        """
        Loads game data such as the map, items, weapons, and rations.

        Raises:
            Exception: If any game data fails to load.
        """
        try:
            script_dir = Path(__file__).parent

            # Load map
            self.game_map = Map()
            self.game_map.read_map(str(script_dir / "level_1.json"))

            # Initialize room players
            self.room_players = {number: set() for number in self.game_map.rooms.keys()}
            logging.debug(f"Initialized players in {len(self.room_players)} rooms")

            # Load items
            self.items = Item.read(str(script_dir / "objects.json"))
            logging.info(f"Loaded {len(self.items)} items")

            # Load weapons
            self.weapons = Weapon.read(str(script_dir / "weapons.json"))
            logging.info(f"Loaded {len(self.weapons)} weapons")

            # Load rations
            self.rations = Rations.read_rations("rations.json")
            logging.info(f"Loaded {len(self.rations)} rations")

            # Load monsters
            self.monsters = Monster.read_monsters("monsters.json")
            logging.info(f"Loaded {len(self.monsters)} monsters")

        except Exception as e:
            logging.error(f"Failed to load game data: {e}")
            raise
