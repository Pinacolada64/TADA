import time
from typing import Dict, Any, List

from base_command import Command, CommandResult
from commands.help import HelpCategory


class SayCommand(Command):
    """Broadcast a message to other players in the same room.

    This command returns a CommandResult and relies on the server to handle
    broadcasting to other clients. It chooses the verb (say/ask/exclaim) based on
    punctuation.
    """
    name = 'say'
    aliases = ['"']
    help = HelpCommand(
        summary="Say something to players in your room.",
        category=HelpCategory.COMMUNICATION,
        usage=[
            ("say <message>", "Speak aloud to everyone in the room"),
            ("' <message>", "Shorthand for say"),
        ],
        examples=[
            ("say Hello there!", "Everyone in the room hears you"),
        ],
    )

    def __init__(self, context: Dict[str, Any] = None):
        super().__init__()
        self.quotation_mark = '"'

    @property
    def name(self) -> str:
        return 'say'

    @property
    def aliases(self) -> list[str]:
        return ['"']

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        # args will be the split input; the message is everything after the command
        if not args:
            return CommandResult(success=False, error='no_message', message='What would you like to say?')

        # Reconstruct the message text from args
        message_text = ' '.join(args)
        # If message begins with a quote, strip it
        if message_text.startswith('"'):
            message_text = message_text[1:]

        verb = 'say'
        if message_text.endswith('?'):
            verb = 'ask'
        elif message_text.endswith('!'):
            verb = 'exclaim'

        username = context.get('username', 'Someone')
        to_self = f'You {verb}, "{message_text}"'
        to_others = f'{username} {verb}s, "{message_text}"'

        # Broadcast via client_manager if available in context/server
        client = context.get('client')
        player = get_player_from_context(context, client)
        try:
            # broadcast to other clients via global client_manager or server
            if client and getattr(client, 'server', None):
                client.server.broadcast_message(client.addr, Message(lines=[to_others], type=MessageType.say, mode=Mode.app))
            else:
                # fallback to global client_manager
                client_manager.broadcast({'message': to_others, 'type': 'say'}, exclude_user=username)
        except Exception:
            # best-effort broadcast; ignore errors
            pass

        return CommandResult(success=True, message=to_self, data={'text': message_text})


class SayHelp(BaseHelpText):
    """Help provider for the 'say' command."""
    name = "say"
    aliases = ['"']

    def __init__(self):
        super().__init__()
        # Populate BaseHelpText fields directly
        self.category = HelpCategory.COMMUNICATION
        self.summary = "Say something aloud to other players in the room."
        self.description = (
            "The 'say' command allows you to speak aloud to other players in your current location. "
            "Your message will be broadcast to all players in the same room, and the verb used (say, ask, exclaim) "
            "will depend on the punctuation at the end of your message."
        )
        self.usage = [
            ("say <message>", "Speak to everyone in the room"),
            ('"<message>', "Shorthand using leading quote")
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
            "Speak aloud to everyone in your current room. The verb (say/ask/exclaim) is chosen by punctuation.\n\n"
            "Examples:\n"
            "  say Hello!       - You exclaim, \"Hello!\"\n"
            "  \"How are you?\" - You ask, \"How are you?\"\n"
        )
