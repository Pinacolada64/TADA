"""
New player command implementation for handling new player creation.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from .base import Command, CommandResult
from net_common import Mode

# Room where new players will be placed after creation
CREATION_ROOM = "1"  # Default starting room

class NewPlayerCommand(Command):
    """Handles new player creation."""
    
    @property
    def name(self) -> str:
        return 'newplayer'
    
    @property
    def aliases(self) -> List[str]:
        return ["create", "new"]

    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the new player creation command.
        
        Args:
            data: Dictionary containing player creation data
            
        Returns:
            CommandResult: Result of the player creation attempt
        """
        user_id = data.get('user_id')
        password = data.get('password')
        
        if not user_id or not password:
            return CommandResult(
                success=False,
                error='missing_credentials',
                message='Missing user ID or password.',
                data={'mode': Mode.login}
            )
        
        # Create user directory if it doesn't exist
        user_dir = Path('run/server/net')
        user_dir.mkdir(parents=True, exist_ok=True)
        user_file = user_dir / f'login-{user_id}.json'
        
        # Create player data
        player_data = {
            'user_id': user_id,
            'password': password,  # In a real app, hash this password
            'created_at': str(datetime.utcnow()),
            'last_login': str(datetime.utcnow()),
            'stats': {
                'level': 1,
                'experience': 0,
                'health': 100,
                'max_health': 100,
                'mana': 50,
                'max_mana': 50,
                'strength': 10,
                'dexterity': 10,
                'intelligence': 10,
                'vitality': 10,
                'luck': 10
            },
            'inventory': [],
            'equipment': {},
            'location': 'starting_area',
            'last_room': CREATION_ROOM,  # Starting room
            'mode': Mode.app,
            'in_creation': True  # Flag to indicate player is in creation process
        }
        
        # Save player data
        try:
            with open(user_file, 'w') as f:
                json.dump(player_data, f, indent=2)
                
            # Create success result
            result = CommandResult(
                success=True,
                message=f'Welcome to the game, {user_id}! Your character has been created. You are now in the creation room.',
                data={
                    'mode': Mode.app,
                    'authenticated': True,
                    'user_id': user_id,
                    'player_data': player_data,
                    'changes': {
                        'authenticated': True,
                        'user_id': user_id,
                        'mode': Mode.app,
                        'player_data': player_data,
                        'room': CREATION_ROOM,  # Notify client of room change
                        'in_creation': True
                    }
                }
            )
            
            return result
            
        except IOError as e:
            return CommandResult(
                success=False,
                error='save_error',
                message='Failed to create player. Please try again.',
                data={'mode': Mode.login}
            )
    
    def help_text(self) -> str:
        return """\
        New Player Command
        -----------------
        Creates a new player account.
        
        This command is used during the new player creation process.
        """

def register():
    """Register the new player command."""
    from commands.manager import command_manager
    command_manager.register_command(NewPlayerCommand())
