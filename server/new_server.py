#!/bin/env python3

import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
import threading
from typing import Any, Dict, List, Optional, Set

# TADA-specific imports:
from server.base_classes import Map, PlayerMoneyTypes, compass_txts
from server.client_manager import ClientManager
from server.common import K, server_port
from server.flags import PlayerFlags
from server.items import Item, Rations, Weapon
from server.net_server import Message, Mode, UserHandler, start as start_net_server
from server.player import Player

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
            logger.warning(f"Server is already running with PID: {pid}")
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
logger = logging.getLogger(__name__)

class GameServer:
    """Main game server class."""
    
    def __init__(self, host: str = "localhost", port: int = server_port):
        """Initialize the game server.
        
        Args:
            host: The host address to bind the server to
            port: The port to listen on (defaults to the common server_port)
        """
        self.host = host
        self.port = port
        self.running = False
        self.lock = threading.Lock()
        self.client_manager = ClientManager()
        self.client_manager.set_lock(self.lock)
        self.players: Dict[str, Player] = {}
        self.room_players: Dict[int, Set[str]] = {}
        self.game_map: Optional[Map] = None
        self.items: Dict[str, Item] = {}
        self.weapons: Dict[str, Weapon] = {}
        self.rations: Dict[str, Rations] = {}
        
        # Register signal handlers
        self._shutting_down = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle signals by scheduling the async shutdown handler.
        
        Args:
            signum: The signal number
            frame: The current stack frame
        """
        if self._shutting_down:
            return
            
        self._shutting_down = True
        logger.info(f"Received signal {signum}, scheduling shutdown...")
        asyncio.create_task(self._handle_shutdown(signum, frame))
    
    async def _handle_shutdown(self, signum=None, frame=None):
        """Handle server shutdown with graceful broadcast and state saving.
        
        Args:
            signum: The signal number (if called from signal handler)
            frame: The current stack frame (if called from signal handler)
        """
        if not self.running:
            return
            
        logger.info("Starting graceful shutdown...")
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
                logger.info("Broadcasted shutdown message to all players")
                
                # Give clients a moment to receive the message
                await asyncio.sleep(1)
            
            # Save player states if possible
            if hasattr(self, 'players') and self.players:
                with self.lock:  # Ensure thread safety when accessing players
                    for player_id, player in list(self.players.items()):
                        try:
                            if hasattr(player, 'save'):
                                player.save()
                                logger.info(f"Saved player state: {getattr(player, 'name', player_id)}")
                            else:
                                logger.warning(f"Player {player_id} has no save method")
                        except Exception as e:
                            logger.error(f"Error saving player {player_id}: {e}")
                logger.info("Completed saving player states")
                
            # Close all client connections
            if hasattr(self, 'client_manager') and self.client_manager:
                if hasattr(self.client_manager, 'close_all_connections'):
                    await self.client_manager.close_all_connections()
                logger.info("Closed all client connections")
                
            logger.info("Server shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            # Ensure we exit cleanly
            if signum is not None:
                import signal as signal_module
                # Re-raise the signal to allow normal exit
                if signum == signal_module.SIGINT:
                    raise KeyboardInterrupt()
                os._exit(0)
        
        # Stop the server
        logger.info("Shutting down server...")
        self.stop()
    
    def load_game_data(self):
        """Load all game data."""
        try:
            # Get the directory where this script is located
            script_dir = Path(__file__).parent
            
            # Load map
            self.game_map = Map()
            self.game_map.read_map(str(script_dir / "level_1.json"))
            
            # Initialize room players
            self.room_players = {number: set() for number in self.game_map.rooms.keys()}
            logger.debug(f"Initialized players in {len(self.room_players)} rooms")
            
            # Load items
            self.items = Item.read(str(script_dir / "objects.json"))
            logger.info(f"Loaded {len(self.items)} items")
            
            # Load weapons
            self.weapons = Weapon.read(str(script_dir / "weapons.json"))
            logger.info(f"Loaded {len(self.weapons)} weapons")
            
            # Load rations
            self.rations = Rations.read(str(script_dir / "rations.json"))
            logger.info(f"Loaded {len(self.rations)} rations")
            
            # TODO: Load other game data (monsters, etc.)
            
        except Exception as e:
            logger.error(f"Failed to load game data: {e}")
            raise
    
    async def on_client_connect(self, client):
        """Handle new client connections.
        
        Args:
            client: The client connection object
        """
        logger.info(f"New client connected: {client}")
        # Add client to the client manager
        self.client_manager.add_client(client)
        
        # Send welcome message from config
        from setup.test_config import config
        welcome_msg = config.get('welcome_message', 'Welcome to Totally Awesome Dungeon Adventure!')
        await client.send(f"{welcome_msg}\r\n")
        
    async def on_client_disconnect(self, client):
        """Handle client disconnections.
        
        Args:
            client: The client connection object that disconnected
        """
        logger.info(f"Client disconnected: {client}")
        # Remove client from the client manager
        self.client_manager.remove_client(client)
        
    async def on_client_message(self, client, message):
        """Handle incoming messages from clients.
        
        Args:
            client: The client connection object
            message: The message received from the client
        """
        try:
            logger.debug(f"Message from {client}: {message!r}")
            # Process the message (e.g., parse commands)
            # For now, just echo the message back
            response = f"You said: {message}\r\n"
            await client.send(response)
        except Exception as e:
            logger.error(f"Error processing message from {client}: {e}")
            await client.send(f"Error: {e}\r\n")
        
    async def start(self):
        """Start the game server."""
        if self.running:
            logger.warning("Server is already running")
            return
        
        try:
            # Load game data
            self.load_game_data()
            
            # Start the network server
            self.running = True
            logger.info(f"Starting server on {self.host}:{self.port}")
            
            # Start the network server with test credentials
            start_net_server(
                host="localhost",
                port=server_port,
                _id="test_server",  # TODO: change to 'TADA' when debugged
                key="test_key",  # TODO: change to '1234567890' when debugged
                protocol=1,
                handler_class=ClientHandler
            )
            
            logger.info("Server started successfully")
            
            # Keep the server running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop the game server."""
        if not self.running:
            logging.info("Server is not running")
            return
            
        logger.info("Stopping server...")
        self.running = False
        
        # Save all player data
        for player in self.players.values():
            try:
                player.save()
                logging.info(f"Saved player {player.id}")
            except Exception as e:
                logger.error(f"Error saving player {player.id}: {e}")
        
        logger.info("Server stopped")
    
    def create_client_handler(self, *args, **kwargs):
        """Create a new client handler instance."""
        return ClientHandler(self, *args, **kwargs)
    
    def get_online_players(self) -> List[str]:
        """Get a list of online player IDs."""
        with self.lock:
            return list(self.players.keys())
    
    def broadcast(self, data: Dict[str, Any], exclude_user: Optional[str] = None):
        """Broadcast data to all connected clients."""
        self.client_manager.broadcast(data, exclude_user=exclude_user)


class ClientHandler(UserHandler):
    """Handles client connections and commands."""
    
    def __init__(self, *args, **kwargs):
        # First call the parent class's __init__ with all arguments
        super().__init__(*args, **kwargs)
        
        # Now set up our custom attributes
        self.player: Optional[Player] = None
        self._command_handler = None
        self._output_buffer: List[str] = []
        
        # Get the server instance from the parent's server attribute
        # which is set by the ServerAwareHandler wrapper
        if hasattr(self, 'server_instance'):
            self.server = self.server_instance
        else:
            # Fallback in case server_instance isn't available
            self.server = None
            logger.warning("ClientHandler initialized without server instance")
        
    @property
    def command_handler(self):
        if self._command_handler is None:
            # Lazy import to avoid circular imports
            from command_handler import CommandHandler
            self._command_handler = CommandHandler(self)
        return self._command_handler
    
    def connection_made(self, transport):
        """Handle new client connection."""
        super().connection_made(transport)
        client_id = id(self)
        self.server.client_manager.add_client(str(client_id), {
            'transport': transport,
            'handler': self
        })
        logger.info(f"Client connected: {client_id}")
    
    async def close_connection(self):
        """Close the client connection gracefully.
        
        This method is called during server shutdown to ensure the connection
        is properly closed.
        """
        try:
            if hasattr(self, 'transport') and self.transport and not self.transport.is_closing():
                self.transport.close()
                logger.info(f"Closed connection for client {id(self)}")
        except Exception as e:
            logger.error(f"Error closing client connection: {e}")
    
    def connection_lost(self, exc):
        """Handle client disconnection."""
        if self.player:
            client_id = id(self)
            logger.info(f"Client disconnected: {client_id} (User: {self.player.id})")
            self.server.client_manager.remove_client(str(client_id))
            
            # Remove player from room
            if self.player.room in self.server.room_players:
                self.server.room_players[self.player.room].discard(self.player.id)
            
            # Save player data
            try:
                self.player.save()
                logger.info(f"Saved player {self.player.id}")
            except Exception as e:
                logger.error(f"Error saving player {self.player.id}: {e}")
            
            # Remove player from online list
            self.server.players.pop(self.player.id, None)
        
        super().connection_lost(exc)
    
    def data_received(self, data):
        """Handle incoming data from client."""
        try:
            message = json.loads(data.decode('utf-8'))
            logger.debug(f"Received message: {message}")
            
            # Process the message in a separate task
            asyncio.create_task(self._process_message(message))
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON data received: {data}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process a message from the client."""
        try:
            if not self.command_handler and message.get('type') != 'login':
                self.send_error("Not authenticated. Please log in first.")
                return
            
            if message['type'] == 'login':
                await self._handle_login(message)
            elif message['type'] == 'command':
                await self._handle_command(message)
            else:
                self.send_error(f"Unknown message type: {message.get('type')}")
                
        except Exception as e:
            logger.error(f"Error in _process_message: {e}", exc_info=True)
            self.send_error("An error occurred while processing your request.")
    
    async def _handle_login(self, data: Dict[str, Any]):
        """Handle login request."""
        user_id = data.get('user_id')
        password = data.get('password')
        
        if not user_id or not password:
            self.send_error("Missing username or password")
            return
        
        # Create command handler for this client
        self.command_handler = CommandHandler(
            player=self.player or Player(user_id),  # Create new player if not exists
            client_manager=self.server.client_manager,
            server=self.server
        )
        
        # Process login command
        result = await self.command_handler.handle_command(
            f"login {user_id} {password}",
            data
        )
        
        if result.success:
            # If this is a new player, send them to character creation
            if result.data.get('mode') == Mode.new_player:
                self.send_message({
                    'type': 'new_player',
                    'user_id': user_id,
                    'message': result.message,
                    'mode': Mode.new_player
                })
                logger.info(f"New player detected: {user_id}")
                return
                
            # Existing player login flow
            self.player = self.command_handler.player
            self.server.players[user_id] = self.player
            
            # Add player to starting room
            starting_room = 5  # TODO: Get from config
            self.player.map_room = starting_room
            
            # Initialize room tracking if needed
            if starting_room not in self.server.room_players:
                self.server.room_players[starting_room] = set()
            self.server.room_players[starting_room].add(user_id)
            
            # Send success response
            self.send_message({
                'type': 'login_success',
                'user_id': user_id,
                'message': result.message,
                'room': starting_room,
                'mode': Mode.app
            })
            
            logger.info(f"User logged in: {user_id}")
        else:
            self.send_error(result.message or "Login failed")
    
    async def _handle_command(self, data: Dict[str, Any]):
        """Handle a command from the client.
        
        Args:
            data: Command data containing 'text' (the command string)
        """
        if not self.player:
            self.send_error("Not authenticated. Please log in first.")
            return
            
        command_text = data.get('text', '').strip()
        if not command_text:
            self.send_error("Empty command")
            return
            
        logger.info(f"Processing command from {self.player.id}: {command_text}")
        
        try:
            # Process the command using the new command handler
            from command_handler import CommandHandler
            command_handler = CommandHandler(
                player=self.player,
                client_manager=self.server.client_manager,
                server=self.server
            )
            
            # Process the command
            result = await command_handler.handle_command(command_text, data or {})
            
            # Prepare the response
            response = {
                'type': 'command_result',
                'success': result.success,
                'message': result.message,
                'data': result.data or {}
            }
            
            # Handle room changes if present in the result
            if result.success and result.data and 'room_change' in result.data:
                room_change = result.data['room_change']
                old_room = str(room_change.get('from_room')) if 'from_room' in room_change else None
                new_room = str(room_change.get('to_room'))
                
                # Update room tracking
                if old_room and old_room in self.server.room_players:
                    self.server.room_players[old_room].discard(self.player.id)
                if new_room not in self.server.room_players:
                    self.server.room_players[new_room] = set()
                self.server.room_players[new_room].add(self.player.id)
                
                # Update player's current room
                self.player.room = new_room
                
                # Notify other players in the new room
                self._notify_room_entered(new_room)
                
                # Get room data for the response
                room = self.server.game_map.get_room(new_room)
                if room:
                    response['data']['room'] = {
                        'id': new_room,
                        'name': room.name,
                        'description': room.description,
                        'exits': room.exits,
                        'players': [
                            p.id for p in 
                            (self.server.players.get(pid) for pid in self.server.room_players.get(new_room, []))
                            if p and p.id != self.player.id
                        ]
                    }
            
            # Handle errors
            if not result.success:
                response['error'] = result.error or 'command_failed'
                if result.error_code:
                    response['error_code'] = result.error_code
            
            # Send the response
            self.send_message(response)
                
        except Exception as e:
            logger.exception(f"Error processing command '{command_text}': {str(e)}")
            self.send_error(
                message=f"An error occurred: {str(e)}",
                error_code='server_error'
                )
            
            # If this is a look command, include room description
            if command.startswith('look') or command == 'l':
                room = self.server.game_map.rooms.get(self.player.room, {})
                if room:
                    response['room'] = {
                            'name': room.get('name', 'Unknown Room'),
                            'description': room.get('desc', ''),
                            'exits': list(room.get('exits', {}).keys())
                        }
                
                self.send_message(response)
            else:
                self.send_error(result.message or "Command failed", 
                              result.error or 'command_failed')
                
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            self.send_error("An error occurred while processing your command.", 'server_error')
    
    def _notify_room_entered(self, room_id: str):
        """Notify other players in the room that this player has entered."""
        room_players = self.server.room_players.get(room_id, set())
        for player_id in room_players:
            if player_id != self.player.id:
                self.server.client_manager.send_to(player_id, {
                    'type': 'player_entered',
                    'player_id': self.player.id,
                    'player_name': self.player.name,
                    'room_id': room_id
                })
    
    def _send_room_message(self, message: str, room_id: str = None, exclude_self: bool = False):
        """Send a message to all players in a room."""
        if not room_id:
            room_id = str(self.player.room)
            
        self.server.client_manager.send_to_room(
            room_id,
            {
                'type': 'room_message',
                'message': message,
                'from_player': self.player.id,
                'room_id': room_id
            },
            exclude_user=self.player.id if exclude_self else None
        )
    
    def send_message(self, data: Dict[str, Any]):
        """Send a message to the client."""
        if not self.transport or self.transport.is_closing():
            return
        
        try:
            message = json.dumps(data).encode('utf-8')
            self.transport.write(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
    
    def send_error(self, message: str, error_code: str = "error"):
        """Send an error message to the client."""
        self.send_message({
            'type': 'error',
            'error': error_code,
            'message': message
        })


def main():
    """Main entry point for the server."""
    # Set up signal handlers
    def signal_handler(sig, frame):
        print("\nShutting down server...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start the server
    server = GameServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        print(f"Server error: {e}")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
