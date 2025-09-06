"""
Login command implementation for handling user authentication.
"""
import os
import json
from typing import Dict, Any, List

from .base import Command, CommandResult
from server.net_common import Mode

class LoginCommand(Command):
    """Handles user authentication."""
    
    @property
    def name(self) -> str:
        return 'login'
    
    @property
    def aliases(self) -> List[str]:
        return ["connect", "login"]
    
    @property
    def help_text(self) -> str:
        return """
        Login Command
        -------------
        Usage: login <username> <password>
        
        Authenticates a user with the provided credentials.
        
        Example:
          login myusername mypassword
          
        You will be prompted for your password if not provided.
        """

    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the login command.
        
        Args:
            data: Dictionary containing command data including 'user_id' and 'password'
            
        Returns:
            CommandResult: Result of the login attempt
        """
        user_id = data.get('user_id')
        password = data.get('password')
        
        if not user_id:
            return CommandResult(
                success=False,
                error='missing_user_id',
                message='Please enter a username.',
                data={'mode': Mode.login}
            )
            
        if not password:
            return CommandResult(
                success=False,
                error='missing_password',
                message='Please enter your password.',
                data={
                    'prompt': 'Password: ',
                    'mode': Mode.login
                }
            )
        
        # Check if user exists
        user_file = os.path.join('run', 'server', 'net', f'login-{user_id}.json')
        if not os.path.exists(user_file):
            # New player detected - switch to new player mode
            return CommandResult(
                success=True,
                message='Welcome new player! Let\'s create your character.',
                data={
                    'mode': Mode.new_player,
                    'user_id': user_id,
                    'password': password,  # Store password for account creation
                    'changes': {'user_id': user_id, 'mode': Mode.new_player}
                }
            )
        
        # Verify password (in a real implementation, use proper password hashing)
        try:
            with open(user_file, 'r') as f:
                user_data = json.load(f)
                if user_data.get('password') != password:
                    return CommandResult(
                        success=False,
                        error='invalid_credentials',
                        message='Invalid username or password. Please try again.',
                        data={'mode': Mode.login}
                    )
        except (json.JSONDecodeError, IOError) as e:
            return CommandResult(
                success=False,
                error='server_error',
                message='An error occurred while accessing user data. Please try again later.'
            )
        
        # Login successful
        return CommandResult(
            success=True,
            message=f'Welcome back, {user_id}!',
            data={
                'mode': Mode.app,
                'authenticated': True,
                'user_id': user_id,
                'changes': {'authenticated': True, 'user_id': user_id}
            }
        )
    
    def help_text(self) -> str:
        return """\
        Login Command
        -------------
        Usage: login <username> <password>
        
        Authenticates a user with the provided credentials.
        
        Example:
          login myusername mypassword
          
        You will be prompted for your password if not provided.
        """

def register():
    """Register the login command."""
    return LoginCommand()

# Register the command when the module is imported
from server.commands import register_command
register_command(LoginCommand())
