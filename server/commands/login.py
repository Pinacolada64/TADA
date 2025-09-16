"""
Login command implementation for handling user authentication.
"""
import os
import json
from typing import Dict, Any, List

from .base_command import Command, CommandResult
from .command_help import CommandHelp, HelpCategory
from server.net_common import Mode

class LoginCommand(Command):
    """Handles user authentication."""
    
    name = 'login'
    aliases = ["connect", "con"]
    
    def __init__(self, context=None):
        super().__init__(context)
        self.help_info = CommandHelp(
            category=HelpCategory.AUTHENTICATION,
            summary="Authenticate and log in to the game",
            description=(
                "The 'login' command allows you to authenticate and gain access to the game "
                "using your username and password. You can also use this command to switch "
                "between different characters on your account."
            ),
            usage=[
                ("login guest", "Log in as a guest"),
                ("login <username> <password>", "Log in with username and password"),
                ("login <username>", "Log in (you'll be prompted for password)"),
                ("login", "Show login status and available characters")
            ],
            examples=[
                ("connect guest", "Log in as a guest"),
                ("login myusername mypassword", "Log in with username and password"),
                ("login myusername", "Start login process (password will be hidden)"),
                ("login", "Show login status and available characters")
            ],
            notes=[
                "Passwords are case-sensitive.",
                "After 3 failed attempts, your account will be temporarily locked.",
                "Use 'new' to create a new character after logging in.",
                "Use 'quit' to log out when you're done playing."
            ]
        )

    async def execute(self, context: Dict[str, Any], args: List[str]) -> Dict[str, Any]:
        """Execute the login command.
        
        Args:
            context: Dictionary containing command context including:
                - user_id: The ID of the user attempting to log in
                - client: The client connection object
            args: Command arguments [username, password]
                
        Returns:
            Dict containing the command result
        """
        # Get client from context
        client = context.get('client')
        
        # Handle no arguments - show login status
        if not args:
            return await self._show_login_status(context)
            
        # Get username and password from args
        username = args[0]
        password = args[1] if len(args) > 1 else None
        
        # handle guest account ("connect guest")
        if username == 'guest' and password is None:
            return await self._handle_guest_connect(context)
        
        if not password:
            if client:
                await client.send("Password: ", hide_input=True)
                password = await client.get_input()
            else:
                return CommandResult(
                    success=False,
                    error='password_required',
                    message='Password is required for login.'
                ).to_dict()
        
        # Validate username and password
        if not username:
            return CommandResult(
                success=False,
                error='missing_username',
                message='Please enter a username.'
            ).to_dict()
            
        if not password:
            return CommandResult(
                success=False,
                error='missing_password',
                message='Please enter your password.',
                data={
                    'prompt': 'Password: ',
                    'mode': Mode.login
                }
            ).to_dict()
        
        # TODO: Implement actual authentication logic
        # This is a placeholder - replace with your actual authentication
        if username == 'admin' and password == 'password':
            return CommandResult(
                success=True,
                message=f'Welcome back, {username}!',
                data={
                    'authenticated': True,
                    'username': username,
                    'mode': Mode.app
                }
            ).to_dict()
            
        # Authentication failed
        return CommandResult(
            success=False,
            error='authentication_failed',
            message='Invalid username or password.',
            data={
                'mode': Mode.login,
                'remaining_attempts': 2  # This should come from your auth system
            }
        ).to_dict()
        
    async def _handle_guest_connect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle guest user connection.
        
        Args:
            context: Command context containing client information
            
        Returns:
            Dict containing the command result for guest login
        """
        return CommandResult(
            success=True,
            message=(
                'Welcome, Guest!\n'
                'You are connected as a guest.\n'
                'To create a new account, use: register <username> <password>\n'
                'To log in, use: login <username> <password>'
            ),
            data={
                'authenticated': False,
                'mode': Mode.guest,
                'username': 'guest'
            }
        ).to_dict()
        
    async def _show_login_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Show login status and available characters.
        
        Args:
            context: Command context containing user session information
            
        Returns:
            Dict containing the command result with login status
        """
        # Get user_id from context if available
        user_id = context.get('user_id')
        
        # If user is already authenticated, show their characters
        if context.get('authenticated') and user_id:
            # TODO: Load available characters for this user
            characters = []  # This would come from your user data
            
            if characters:
                char_list = '\n  '.join(characters)
                message = (
                    f'Welcome back, {user_id}!\n'
                    'Your characters:\n'
                    f'  {char_list}\n'
                    'To play a character, type: play <character>'
                )
            else:
                message = (
                    f'Welcome, {user_id}!\n'
                    'You don\'t have any characters yet.\n'
                    'To create a new character, type: new'
                )
                
            return CommandResult(
                success=True,
                message=message,
                data={'mode': Mode.app}
            ).to_dict()
        
        # Not logged in - show login/register options
        return CommandResult(
            success=True,
            message=(
                'You are not currently logged in.\n'
                'To log in to an existing character, use: login <username> <password>\n'
                'To log in as a guest, use: login guest\n'
                'To create a new character, use: new'
            ),
            data={'mode': Mode.login}
        ).to_dict()
