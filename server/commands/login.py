"""
commands/login.py.
"""
import json
from pathlib import Path
from typing import List

from net_common import Mode
from network_context import GameContext
from .base_command import Command, CommandResult


class LoginCommand(Command):
    """Handles user login functionality."""
    
    async def execute(self, ctx: GameContext, *args: List[str]):
        """
        Execute the login command.
        
        Args:
            ctx: The game context
            args: List containing command data including 'user_id' and 'password'
            
        Returns:
            CommandResult: Response message or None if login failed
        """
        user_id = args[1] if args else ''   # user name
        password = args[2] if args else ''  # password
        
        if not user_id:
            return CommandResult.fail('Please enter your username.')

        if not password:
            return CommandResult.fail('Please enter your password.')

        # Check if user exists
        user_file = Path('run') / 'server' / 'net' / f'login-{user_id}.json'
        if not user_file.exists():
            return CommandResult.fail('Invalid username or password.')

        # Verify password (simplified - in real implementation, use proper password hashing)
        try:
            with open(user_file, mode='r') as f:
                user_data = json.load(f)
                if user_data.get('password') != password:
                    return CommandResult.fail('Invalid username or password.')

        except (json.JSONDecodeError, IOError) as e:
            return CommandResult.fail('Error accessing user data.')

        # Login successful
        return CommandResult.ok(['', f'Welcome back, {user_id}!', ''],
                                data={'authenticated': True, 'user_id': user_id, 'mode': Mode.GAME})
