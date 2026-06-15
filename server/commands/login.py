"""
This is deprecated. Use commands/login.py instead.
"""
import os
import json
from typing import Dict, Any, Optional, List

from net_common import Message, Mode
from network_context import GameContext
from .base_command import Command


class LoginCommand(Command):
    """Handles user login functionality."""
    
    @property
    def name(self) -> str:
        return 'login'
    
    async def execute(self, ctx: GameContext, args: List[str]):
        """
        Execute the login command.
        
        Args:
            data: Dictionary containing command data including 'user_id' and 'password'
            
        Returns:
            Optional[Dict]: Response message or None if login failed
        """
        user_id = data.get('user_id')
        password = data.get('password')
        
        if not user_id:
            return CommandResult(success=False, message='Please enter your username.').to_dict()

        if not password:
            return CommandResult(success=False, message='Please enter your password.').to_dict()

        # Check if user exists
        user_file = os.path.join('run', 'server', 'net', f'login-{user_id}.json')
        if not os.path.exists(user_file):
            return CommandResult(success=False, message='Invalid username or password.').to_dict()

        # Verify password (simplified - in real implementation, use proper password hashing)
        try:
            with open(user_file, 'r') as f:
                user_data = json.load(f)
                if user_data.get('password') != password:
                    return CommandResult(success=False, message='Invalid username or password.').to_dict()
        except (json.JSONDecodeError, IOError) as e:
            return CommandResult(success=False, message='Error accessing user data.').to_dict()

        # Login successful
        return CommandResult(success=True, message=f'Welcome back, {user_id}!', data={'authenticated': True, 'user_id': user_id, 'mode': Mode.app}).to_dict()

    def help_summary(self) -> str:
        """Return help text for the login command."""
        return """\
        Login Command
        -------------
        Usage: login <username> <password>
        
        Authenticates a user with the provided credentials.
        
        Example:
          login myusername mypassword
          
        You will be prompted for your password if not provided.
        """

    def register(self):
        """Register the connect / login command."""
        return LoginCommand().register()
