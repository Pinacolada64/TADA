"""
Login command handler for user authentication.
"""
import os
import json
from typing import Dict, Any, Optional

from net_common import Message, Mode, Error
from .base import Command

class LoginCommand(Command):
    """Handles user login functionality."""
    
    @property
    def name(self) -> str:
        return 'login'
    
    async def execute(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
            return Message(
                error=Error.user_id,
                error_line='Missing user_id',
                lines=['Please enter a username.']
            )
            
        if not password:
            return Message(
                error=Error.password,
                error_line='Missing password',
                lines=['Please enter your password.'],
                prompt='Password: ',
                mode=Mode.login
            )
            
        # Check if user exists
        user_file = os.path.join('run', 'server', 'net', f'login-{user_id}.json')
        if not os.path.exists(user_file):
            return Message(
                error=Error.login2,
                error_line='Invalid username or password',
                lines=['Invalid username or password. Please try again.'],
                mode=Mode.login
            )
            
        # Verify password (simplified - in real implementation, use proper password hashing)
        try:
            with open(user_file, 'r') as f:
                user_data = json.load(f)
                if user_data.get('password') != password:
                    return Message(
                        error=Error.login2,
                        error_line='Invalid username or password',
                        lines=['Invalid username or password. Please try again.'],
                        mode=Mode.login
                    )
        except (json.JSONDecodeError, IOError) as e:
            return Message(
                error=Error.internal,
                error_line='Error accessing user data',
                lines=['An error occurred while accessing user data. Please try again later.']
            )
        
        # Login successful
        return Message(
            lines=[f'Welcome back, {user_id}!'],
            mode=Mode.app,
            changes={'authenticated': True, 'user_id': user_id}
        )
    
    def help_text(self) -> str:
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

def register():
    """Register the login command."""
    return LoginCommand()
