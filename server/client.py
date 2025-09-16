#!/bin/env python3
import argparse
import logging
import os
import readline  # For better command line editing
import threading
import sys
import textwrap
from pathlib import Path
from typing import Optional, Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from server.common import K
from server.net_common import Mode
from server.net_client import Client

# Import client config
try:
    from client.config import config as client_config
except ImportError:
    # Fallback if client config is not available
    client_config = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s() - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'client.log'))
    ]
)

logger = logging.getLogger(__name__)

def print_banner():
    """Display a welcome banner."""
    banner = """
    ╔══════════════════════════════════╗
    ║         TADA Game Client         ║
    ╚══════════════════════════════════╝
    Revision 2025-09-16

    Type 'help' for available commands
    Press Ctrl+C or type 'quit' to exit
    """
    print(textwrap.dedent(banner))

def parse_arguments():
    """Parse command line arguments."""
    # Get default values from config if available
    default_host = client_config.get('server.host') if client_config else 'localhost'
    default_port = client_config.get('server.port') if client_config else 5000
    default_debug = client_config.get('client.debug') if client_config else False
    
    parser = argparse.ArgumentParser(description='TADA Game Client')
    parser.add_argument('user_id', nargs='?', help='Your user ID')
    parser.add_argument('password', nargs='?', help='Your password')
    parser.add_argument('--host', default=default_host, 
                       help=f'Server hostname (default: {default_host})')
    parser.add_argument('--port', type=int, default=default_port, 
                       help=f'Server port (default: {default_port})')
    parser.add_argument('--debug', action='store_true', default=default_debug,
                       help='Enable debug logging')
    return parser.parse_args()

class TADAClient(Client):
    """TADA Game Client that extends the base Client with game-specific functionality."""
    
    def __init__(self, host: str = 'localhost', port: int = 5000, debug: bool = False):
        # Initialize the base Client class
        super().__init__()
        
        # Store connection details
        self.host = host
        self.port = port
        
        # Game state
        self.status_line = {
            K.room_name: 'Disconnected',
            K.silver: 0,
            K.hit_points: 0,
            K.experience: 0,
            'last_command': ''
        }
        self.prompt = 'TADA> '
        self.command_history = []
        self.max_history = 100
        
        # Set up logging
        log_level = logging.DEBUG if debug else logging.INFO
        logger.setLevel(log_level)
        logger.info("TADA client initialized")
        
    def show_help(self):
        """Show help for local/offline commands and get help from server."""
        help_text = """
        Available Commands:
          edit .......... Edit client configuration
          help .......... Show this help message
          status ........ Show current game status
          connect ....... Connect to the game server
          quit / exit ... Exit the game
        """
        print(textwrap.dedent(help_text))
        
    def _process_command(self, command: str) -> bool:
        """Process a single command.
        
        Args:
            command: The command to process
            
        Returns:
            bool: True if the client should continue running, False to exit
        """
        if not command:
            return True
            
        # Add command to history
        self.command_history.append(command)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
            
        # Convert command to lowercase for comparison
        cmd = command.lower()
        
        # Handle built-in commands
        if cmd in ('exit', 'quit'):
            if self.connected and self.server:
                try:
                    # Send a bye message to the server
                    logger.debug("Sending 'bye' mode to server...")
                    self.server._send_data({'mode': Mode.bye})
                    # Let the server close the connection
                    # FIXME
                    # self.connected = False
                    logger.debug("Disconnected from server")
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")
            print("\nGoodbye!")
            return False
            
        if cmd in ('help', '?'):
            self.show_help()
            return True
            
        if cmd == 'status':
            self._show_status()
            return True
            
        # Handle game commands if connected and in app mode
        if self.connected and self.server and self.mode == 'app':
            try:
                self.server.default(command)
            except Exception as e:
                print(f"Error executing command: {str(e)}")
        elif self.connected and self.mode == 'init':
            print("Please complete login process first")
        else:
            print("Not connected to server. Type 'connect <username>' to connect or 'help' for more commands.")
            
        return True
        
    def _show_status(self):
        """Display current status information."""
        status = [
            f"Status: {'Connected [{self.host}:{self.port}]' if self.connected else 'Disconnected'}",
            f"User: {self.user_id or 'Not set'}",
        ]
        
        if self.connected:
            status.extend([
                f"Room: {self.status.get(K.room_name, 'Unknown')}",
                f"HP: {self.status.get(K.hit_points, 0)}",
                f"XP: {self.status.get(K.experience, 0)}",
                f"Silver: {self.status.get(K.silver, 0)}"
            ])
            
        print("\n".join(status))
        
    def _run_command_loop(self):
        """Main command loop for the client."""
        print_banner()
        
        while True:
            try:
                # Show prompt and get input
                try:
                    command = input(self.prompt).strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nType 'quit' or 'exit' to exit.")
                    continue
                    
                # Process the command
                if not self._process_command(command):
                    break
                    
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                logger.exception("Unexpected error in command loop")

def process_request(self, request: Dict[str, Any]):
    """Process a request from the server.
    
    Args:
        request: The request dictionary from the server
    """
    if not request:
        return
        
    # Debug log the incoming request
    logger.debug(f"Processing server request: {request}")
    
    try:
        # Handle mode changes
        if 'mode' in request:
            mode = request['mode']
            self.mode = mode  # Update current mode
            
            # Handle login responses
            if mode == 'login':
                if 'error' in request:
                    print(f"Login failed: {request['error']}")
                    self.mode = 'init'
                else:
                    print("Login successful!")
                    self.mode = 'app'
            
            # Update room name if provided
            if 'changes' in request and K.room_name in request['changes']:
                self.status[K.room_name] = request['changes'][K.room_name]
                self.prompt = f"{self.status[K.room_name]}> "
        
        # Display any message lines
        if 'lines' in request and request['lines']:
            print("\n".join(request['lines']))
            
        # Update status line if provided
        if 'status_line' in request:
            changes = request['status_line']
            for key, value in changes.items():
                if key in self.status:
                    self.status[key] = value
            
            # Update status line display
            status_items = []
            if K.hit_points in changes:
                status_items.append(f"HP: {changes[K.hit_points]}")
            if K.experience in changes:
                status_items.append(f"XP: {changes[K.experience]}")
            if K.silver in changes:
                status_items.append(f"Silver: {changes[K.silver]}")
                
            if status_items:
                # if two items: item_1 | item_2
                # if one item: item_1
                if len(status_items) == 1:
                    print(status_items[0])
                else:
                    print(" | ".join(status_items))
                
    except Exception as e:
        logger.exception("Error processing server request")
        print(f"Error processing server response: {str(e)}")    
        prompt = request.get('prompt')
        if prompt == '':
            logging.debug("prompt: %s" % default_prompt)
        
        # TODO: move choices to server-side
        if choices is not None and len(choices) > 0:
            # ryan: changed 'choices' list to dict('option': 'text')
            for k, v in choices.items():
                print(f"  {k}: {v}")
            if prompt == '':
                prompt = '# '
        if prompt == '':
            prompt = default_prompt
        # if just one option, don't loop through checking choices:
        multiple_choice = choices is not None and len(choices) > 0
        if multiple_choice is False:
            # just one option:
            temp = request.get('last_command')
            if temp is not None:
                print(f"[Return] = {temp}\n")
            text = input(prompt)
            if temp is not None and text == '':
                print(f"(Repeating '{temp}.')")
                text = temp
            return cmd(text=text)
        elif multiple_choice:
            # multiple options:
            while True:
                text = input(prompt).lower()
                if text not in choices.keys():
                    print("Choose an option listed above.")
                else:
                    return cmd(text=text)


def main():
    """Main entry point for the TADA client."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Set up client with provided arguments
        client = TADAClient(
            host=args.host,
            port=args.port,
            debug=args.debug
        )
        
        # Set user and password if provided
        if args.user_id:
            client.set_user(args.user_id)
        if args.password:
            client.set_password(args.password)
        
        # Import required modules
        from server.common import app_key, app_protocol, translation
        
        # Connect to the server
        client.connect(
            host=args.host,
            port=args.port,
            server_id='tada_client',  # This should be configured in your server settings
            server_key=app_key,
            protocol_version=app_protocol,
            translation=translation
        )
        
        # Start the command loop
        try:
            while not client._shutdown_event.is_set():
                try:
                    command = input(client.prompt).strip()
                    if command.lower() in ('quit', 'exit'):
                        break
                    # Process command here
                    print(f"Command received: {command}")
                except (KeyboardInterrupt, EOFError):
                    print("\nUse 'quit' or 'exit' to disconnect.")
        finally:
            # Clean up
            if hasattr(client, 'disconnect'):
                client.disconnect()
        
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in client")
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
