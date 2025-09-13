#!/bin/env python3
import argparse
import logging
import os
import readline  # For better command line editing
import sys
import textwrap
from typing import Optional, Dict, Any

from server.common import K
from server.net_common import Mode

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
    Type 'help' for available commands
    Press Ctrl+C or type 'quit' to exit
    """
    print(textwrap.dedent(banner))

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='TADA Game Client')
    parser.add_argument('user_id', nargs='?', help='Your user ID')
    parser.add_argument('--host', default='localhost', help='Server hostname')
    parser.add_argument('--port', type=int, default=5000, 
                       help=f'Server port (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()

class TADA_Client:
    """TADA Game Client with enhanced user experience."""
    
    def __init__(self, host: str = 'localhost', port: int = 5000, debug: bool = False):
        self.user_id = None
        self.host = host
        self.port = port
        self.mode = Mode.init
        self.status = {
            K.room_name: 'Disconnected',
            K.silver: 0,
            K.hit_points: 0,
            K.experience: 0,
            'last_command': ''
        }
        self.prompt = 'TADA> '
        self.connected = False
        self.server = None
        self.command_history = []
        self.max_history = 100
        
        # Set up logging level
        if debug:
            logger.setLevel(logging.DEBUG)
        logger.debug("TADA_Client initialized")
        
    def show_help(self):
        """Display available commands and usage."""
        help_text = """
        Available Commands:
          help      - Show this help message
          status    - Show current game status
          connect   - Connect to the game server
          quit/exit - Exit the game
          
        Game Commands (when connected):
          look      - Look around the current room
          go [dir]  - Move in a direction (north, south, east, west, etc.)
          take [item] - Pick up an item
          drop [item] - Drop an item
          inventory - Show your inventory
          say [msg] - Say something to other players
        """
        print(textwrap.dedent(help_text))
        
    def set_user(self, user_id):
        """Set the current user ID."""
        self.user_id = user_id
        logging.debug(f"User set to: {user_id}")
        
    def connect(self, host: str = None, port: int = None, user_id: str = None, 
               key: str = None, protocol: int = None, translation: str = None) -> bool:
        """Connect to the TADA server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            user_id: User ID for authentication
            key: Authentication key
            protocol: Protocol version
            translation: Translation settings
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.connected:
            print("Already connected to the server.")
            return True
            
        try:
            from server.net_client import Client
            from server.common import app_key, app_protocol, translation as default_translation
            
            # Use provided values or fall back to instance defaults
            host = host or self.host
            port = port or self.port
            user_id = user_id or self.user_id
            
            if not user_id:
                print("Error: No user ID provided. Please set a user ID first.")
                return False
                
            print(f"Connecting to {host}:{port} as {user_id}...")
            
            self.server = Client()
            self.server.set_user(user_id)
            self.server.start(host, port, user_id, key or app_key, 
                           protocol or app_protocol, 
                           translation or default_translation)
            self.connected = True
            print("Connected successfully!")
            return True
            
        except Exception as e:
            print(f"Failed to connect: {str(e)}")
            logger.exception("Connection error")
            self.connected = False
            return False
            
    def start(self, host: str = None, port: int = None, user_id: str = None, 
             key: str = None, protocol: str = None, translation: str = None):
        """Start the client and connect to the server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            user_id: User ID for authentication
            key: Authentication key
            protocol: Protocol version
            translation: Translation settings
        """
        if user_id:
            self.set_user(user_id)
            
        # Try to connect if we have all required parameters
        if self.user_id and (host or self.host) and (port or self.port):
            self.connect(host, port, self.user_id, key, protocol, translation)
            
        self._run_command_loop()
        
    def _process_command(self, command: str) -> bool:
        """Process a single command.
        
        Args:
            command: The command to process
            
        Returns:
            bool: True if the client should continue running, False to exit
        """
        command = command.strip()
        if not command:
            return True
            
        # Add to command history
        self.command_history.append(command)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
            
        # Handle built-in commands
        if command.lower() in ('quit', 'exit'):
            print("Goodbye!")
            return False
            
        if command.lower() in ('help', '?'):
            self.show_help()
            return True
            
        if command.lower() == 'status':
            self._show_status()
            return True
            
        # Handle server commands
        if self.connected and self.server:
            try:
                self.server.default(command)
            except Exception as e:
                print(f"Error executing command: {str(e)}")
                logger.exception("Command execution error")
        elif command.lower() == 'connect':
            self.connect()
        else:
            print("Not connected to server. Type 'connect' to connect or 'help' for more commands.")
            
        return True
        
    def _show_status(self):
        """Display current status information."""
        status = [
            f"Status: {'Connected' if self.connected else 'Disconnected'}",
            f"User: {self.user_id or 'Not set'}",
            f"Server: {self.host}:{self.port}"
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

    def process_request(self, request: Dict[str, Any]) -> None:
        """Process a request from the server.
        
        Args:
            request: The request dictionary from the server
        """
        try:
            # Handle mode changes
            if self.mode != request.get('mode'):
                self.mode = request['mode']
                logger.debug(f"Mode changed to: {self.mode}")
                
            # Handle errors
            if request.get('error'):
                error_code = request['error']
                error_line = request.get('error_line', 'No error details')
                logger.error(f"Server error: {error_line} (code: {error_code})")
                print(f"\nError: {error_line}\n")
                
            # Update status from server
            changes = request.get('changes', {})
            for field in [K.room_name, K.silver, K.hit_points, K.experience, K.last_command, K.custom]:
                if field in changes:
                    self.status[field] = changes[field]
            
            # Handle multiple-choice prompts
            choices = request.get('choices', {})
            if choices:
                logger.debug(f"Received choices: {choices}")
                print("\n".join(f"  {k}: {v}" for k, v in choices.items()))
            
            # Display any message lines from the server
            lines = request.get('lines')
            if lines:
                print("\n".join(lines))
                
            # Update the prompt to show current room if available
            if K.room_name in changes:
                self.prompt = f"{changes[K.room_name]}> "
            
            # Log detailed request for debugging
            logger.debug(f"Processed request: {request}")
            
        except Exception as e:
            logger.exception("Error processing server request")
            print(f"Error processing server response: {str(e)}")
        if self.status[K.hit_points]:
            status_items.append(f"HP: {self.status[K.hit_points]}")
        if self.status[K.experience]:
            status_items.append(f"Experience: {self.status[K.experience]:,}")
        if self.status[K.silver] or self.status[K.silver] == 0:
            status_items.append(f"Silver: {self.status[K.silver]:,}")
        if status_items:
            status_line = " | ".join(status_items)
            print(f"---< {status_line} >---")
        if request.get('lines') is not None:
            for m in request['lines']:
                print(m)
        
        prompt = request.get('prompt')
        if prompt == '':
            logging.debug("prompt: %s" % default_prompt)
        
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
        client = TADA_Client(
            host=args.host,
            port=args.port,
            debug=args.debug
        )
        
        # Import required modules
        from server.common import app_key, app_protocol, translation as default_translation
        
        # Start the client with the provided user ID and default settings
        client.start(
            host=args.host,
            port=args.port,
            user_id=args.user_id,
            key=app_key,
            protocol=app_protocol,
            translation=default_translation
        )
        
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in client")
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
