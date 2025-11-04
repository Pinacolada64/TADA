"""
Login command implementation for handling user authentication.
"""
import json
from typing import Dict, Any, List, Coroutine
from pathlib import Path

import net_client
from commands.base_command import CommandResult
from net_common import Message, client_manager, User, Mode
from .base_command import Command, CommandResult, BaseCommand
from .help import HelpCategory, BaseHelpText


class ConnectCommand(Command):
    """Handles user authentication."""
    name = 'connect'
    aliases = ["con", "login"]
    
    def __init__(self, context=None):
        super().__init__(context)

    async def _handle_guest_connect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle guest user connection.

        Args:
            context: Command context containing client information

        Returns:
            Dict containing the command result for guest login
        """
        # Determine a unique guest name using the client/server state from context.
        client = context.get('client') if isinstance(context, dict) else None

        # Default fallback
        username = 'Guest1'

        try:
            if client and getattr(client, 'server', None):
                server = client.server
                # Collect current usernames (may include None)
                existing = {getattr(c, 'username', None) for c in server.clients.values()}
                base = 'Guest'
                n = 1
                while f"{base}{n}" in existing:
                    n += 1
                username = f"{base}{n}"
            else:
                # if we don't have a server reference, try client_manager as a fallback
                try:
                    from net_common import client_manager as global_cm
                    existing = {getattr(ci.handler, 'username', None) for ci in global_cm.clients.values()}
                    base = 'Guest'
                    n = 1
                    while f"{base}{n}" in existing:
                        n += 1
                    username = f"{base}{n}"
                except Exception:
                    username = 'Guest1'
        except Exception:
            username = 'Guest1'

        welcome_text = (
            f"Welcome, {username}!\n"
            "You are connected as a guest.\n"
            "To create a new account, use: register <username> <password>\n"
            "To log in, use: login <username> <password>"
        )

        return CommandResult(
            success=True,
            message=welcome_text,
            data={
                'authenticated': False,
                'mode': Mode.guest,
                'username': username
            }
        ).to_dict()

    async def execute(self, context: Dict[str, Any], args: List[str]) -> dict[str, Any] | Any:
        """Execute the connect / login command.
        
        :param context: Dictionary containing command context including:
            - user_id: The ID of the user attempting to log in
            - client: The client connection object
        :param args: Command arguments [username, password]

        :return: CommandResult: Dict containing the command result
        """
        # Get client from context
        client = context.get('client')
        
        # Handle no arguments - show usage information:
        if not args:
            message = Message(lines=["Please supply a username and password to log in, or 'login guest' to connect as a guest.",
                                     "Type 'new' to create a new character."],
                              mode=Mode.login)
            failure = CommandResult(False, message)
            return await client.send(failure)
            
        # Get username and password from args
        username = args[0].lower()
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
        # Verify password (simplified - in real implementation, use proper password hashing)
        try:
            # find user file:
            user_file = User._json_path()
            if not Path(user_file).exists():
                print("user_name does not exist")
                return CommandResult(
                    success=False,
                    error='authentication_failed',
                    message='Invalid username or password.',
                    data={
                        'mode': Mode.login,
                        'remaining_attempts': 2  # This should come from your auth system
                    }
                ).to_dict()
            password_matches = User.match_password()
            if not password_matches:
                return CommandResult(
                    success=False,
                    error='authentication_failed',
                    message='Invalid username or password.',
                    data={
                        'mode': Mode.login,
                        'remaining_attempts': 2  # This should come from your auth system
                    }
                ).to_dict()
        except Exception as e:
            # Log and return a generic internal error to the caller
            # Avoid executing any further file-based recovery logic here to keep the
            # module importable and the control flow simple.
            return CommandResult(
                success=False,
                error='internal_error',
                message='An internal error occurred during authentication.'
            ).to_dict()

        # FIXME: For demonstration, assume a single valid user
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


    # TODO: keep this; will add multiple characters in User login-x.json file later
    async def _show_login_status(self, context: Dict[str, Any]) -> dict[str, Any] | CommandResult:
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
            lines=[
                'You are not currently logged in.',
                'To log in to an existing character, use: login <username> <password>,',
                'To log in as a guest, use: login guest',
                'To create a new character, use: new',
            ]),
            data={'mode': Mode.login}
        ).to_dict()

    def register() -> Command:
        """Factory function to create a ConnectCommand instance."""
        return ConnectCommand


class QuitCommand(BaseCommand):
    @property
    def name(self) -> str:
        return "quit"

    @property
    def aliases(self):
        return ["q", "exit", "bye"]

    async def execute(self, context, args=None):
        # todo: add 'quit' command which disconnects the user and closes the client connection
        # this should be available in guest and logged-in modes
        # ask "are you sure?" before quitting

        return CommandResult(success=True, message="Goodbye!", data={'mode': Mode.bye})

class QuitHelp(BaseHelpText):
    @property
    def name(self) -> str:
        return "quit"

    @property
    def aliases(self):
        return ["exit", "bye"]

    @property
    def summary(self) -> str:
        return "Quit the game and disconnect."

    def help_text(self) -> str:
        return """\
        Quit Command
        ------------
        Usage: quit

        Disconnects you from the game and exits the client.
        You can also use the aliases: q, exit, bye.
        """