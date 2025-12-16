"""Example commands for the game (look, say, etc.)."""

import logging
from typing import List, Dict, Any

from commands.base_command import BaseCommand, CommandResult, HelpCategory
from commands.context import Context
# The @command decorator is imported from the main processor file
from commands.command_processor import command
from commands.help import BaseHelpText
from net_common import client_manager
from commands.utils import get_player_from_context

logger = logging.getLogger(__name__)


@command(name="look", aliases=["l"], summary="Examines the current room or an object.")
class LookCommand(BaseCommand):
    """
    The Look command is used to observe your immediate surroundings or inspect
    a specific object, creature, or player in the area.
    """

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        """

        :param context: information passed to the command, including client and player info
        :param args:
        :return:
        """
        # Check if the command was run via an alias
        command_used = context.get('raw_input', '').split()[0]

        # Attempt to use the server's room description helper if a client+server are available
        client = None
        if isinstance(context, dict):
            client = context.get(Context.CLIENT) or context.get('client')
        player = get_player_from_context(context, client)

        if not args:
            if client and getattr(client, 'server', None) and hasattr(client.server, '_describe_room'):
                try:
                    lines = client.server._describe_room(client)
                    # return the room description as the message list so the server will send each line
                    return CommandResult(success=True, message=lines)
                except Exception:
                    logging.exception('LookCommand: error calling server._describe_room')
                    # fall through to fallback description
            # no server/help available; use a simple fallback description
            return CommandResult(success=True, lines=[
                "You are in a dimly lit chamber.",
                "A large wooden door is to the north.",
                f"You used the alias '{command_used}' to look around."
            ], message="Look successful.")

        # args present: inspect a specific target
        target = args[0]
        if target.lower() in ["me", "self"]:
            return CommandResult(success=True,
                                 message=f"You examine yourself. Your username is {context.get('username', 'a guest')}.")
        return CommandResult(success=True,
                             message=f"You use '{command_used}' to inspect {target}. It appears to be... ordinary.")

class LookHelp(BaseHelpText):
    """Help provider for the 'look' command."""
    name = 'look'
    aliases = ['l']

    def __init__(self):
        super().__init__()
        # Use a safe default category from base_command.HelpCategory
        self.category = HelpCategory.MISCELLANEOUS
        self.summary = 'Examine the current room or an object.'
        self.description = (
            "Use 'look' or 'l' to see a description of your current location or inspect an item. "
            "Without arguments it describes the room; with a target it inspects that object or player."
        )
        self.usage = [
            ("look", "Describe current room"),
            ("look <object>", "Inspect a specific object or player")
        ]

    def help_text(self) -> str:
        return (
            "Look Command\n"
            "------------\n"
            "Usage: look\n"
            "       look <object>\n\n"
            "Describes your surroundings or inspects a target.\n"
        )

@command(name="say", aliases=['"'])
class SayCommand(BaseCommand):
    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(success=False,
                                 error="no_message",
                                 message="What would you like to say?")

        message = " ".join(args)
        verb = "say"
        if message.endswith("?"):
            verb = "ask"
        elif message.endswith("!"):
            verb = "exclaim"
        quotation = '"'

        broadcast_message = f"{context.get('username', 'Guest')} "
        logger.info(f"Broadcast: {context.get('username', 'Guest')} {verb}s, {quotation}{message}{quotation}")

        # tell all users in the room except the player saying something what they said:
        client_manager.tell_room(message=message, exclude=context.get('username'))

        return CommandResult(
            success=True,
            message=f"You tell the room: '{message}'",
            data={'text': message}
        )

class SayHelp(BaseHelpText):
    """Help provider for the 'say' command (example module)."""
    name = 'say'
    aliases = ['"']

    def __init__(self):
        super().__init__()
        self.category = HelpCategory.COMMUNICATION
        self.summary = "Speak a message to everyone in the room."
        self.description = (
            "The 'say' command broadcasts a message to everyone in your current room. "
            "Punctuation determines whether it's a question or exclamation."
        )
        self.usage = [
            ("say <message>", "Speak the message to your current room"),
            ('"<message>', "Shorthand using a leading quote")
        ]
        self.examples = [
            ("say Hello!", 'You exclaim, "Hello!"'),
            ('"How are you?"', 'You ask, "How are you?"')
        ]

    def help_text(self) -> str:
        return (
            "Say Command\n"
            "-----------\n"
            "Usage: say <message>\n"
            "       \"<message>  (leading quote shorthand)\n\n"
            "Broadcast a message to all players in your current room.\n"
        )
