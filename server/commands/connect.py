"""
Login command implementation for handling user authentication.
"""
from typing import Dict, Any, List
from pathlib import Path

from context import GameContext
from net_common import Message, User, Mode
from .base_command import CommandResult, Command
from .help import HelpCategory, BaseHelpText
from commands.utils import get_player_from_context
from commands.command_processor import command


class ConnectCommand(Command):
    """Handles user authentication."""
    from commands.help import CommandHelp

    help = CommandHelp(
        summary="Connect as a guest to look around",
        category=HelpCategory.AUTHENTICATION,
        usage=[("connect guest", "Connect as a guest character to look around without creating a new account")],
        description="""The guest account has a number attached to the name 'Guest' which increments to the next 
        available number, depending on how many guests are already logged in.
        """,
        examples=[("connect guest", "If two guests are already logged in, logging in as a guest would give you the player name 'Guest 3.'")]
    )

    async def execute(self, context: GameContext, args: List[str]) -> dict[str, Any] | Any:
        """Execute the connect / login command.

        :param context: Dictionary containing command context including:
            - user_id: The ID of the user attempting to log in
            - client: The client connection object
        :param args: Command arguments [username, password]

        :return: CommandResult: Dict containing the command result
        """
        # Get client from context
        client = context.get('client')
        player = get_player_from_context(context, client)

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
            ],
            data={'mode': Mode.login}
        ).to_dict()

    @staticmethod
    def register() -> Command:
        """Factory function to create a ConnectCommand instance."""
        return ConnectCommand

class ConnectHelp(BaseHelpText):
    """Help provider for the 'connect' command."""
    @property
    def name(self) -> str:
        return "connect"

    @property
    def aliases(self):
        return ["conn", "login"]

    @property
    def summary(self) -> str:
        return "Connect to the server and log in."

    @property
    def usage(self) -> List[tuple[str, str]]:
        return [
            ("connect <username> <password>", "Connect with your username and password"),
            ("connect guest", "Connect as a guest user")
        ]

    def help_text(self) -> str:
        return """\
        Connect Command
        ---------------
        Usage: connect <username> <password>
               connect guest

        Connects you to the server. You can log in with your username and password,
        or connect as a guest.

        Examples:
          connect admin password
          connect guest
        """
