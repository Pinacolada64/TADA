"""commands/say.py — Say something to everyone in your room.

Verb is chosen by terminal punctuation:
  default  → says / say
  ?        → asks / ask
  !        → exclaims / exclaim
  ...      → mutters / mutter

The command is also triggered by the bare " shortcut:
  "Hello there!   →  Rulan exclaims, "Hello there!"
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


# ---------------------------------------------------------------------------
# Verb selection
# ---------------------------------------------------------------------------

# (third-person singular, first-person)
_VERB_MAP = [
    ('?',   ('asks',     'ask')),
    ('!',   ('exclaims', 'exclaim')),
    ('...', ('mutters',  'mutter')),
]
_DEFAULT_VERB = ('says', 'say')


def _choose_verb(text: str):
    """Return (third_person, first_person) verb for the given message."""
    stripped = text.rstrip()
    for suffix, verbs in _VERB_MAP:
        if stripped.endswith(suffix):
            return verbs
    return _DEFAULT_VERB


# ---------------------------------------------------------------------------
# Gollum riddle banter (encounters/gollum.py)
# ---------------------------------------------------------------------------

async def _gollum_riddle_check(ctx: GameContext, text: str) -> None:
    """If a living Gollum is in the room and *text* reads like a question
    (trailing '?'), have him banter back at whoever's asking."""
    if not text.rstrip().endswith('?'):
        return

    from encounters.gollum import current_gollum, riddle_response
    response = riddle_response(current_gollum(ctx))
    if response:
        await ctx.send_room(response)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class SayCommand(Command):
    name    = 'say'
    aliases = ['"']
    modes   = {Mode.GAME}

    help = Help(
        summary     = "Say something to players in your room.",
        description = (
            "Broadcasts a message to all players in your room. "
            "The verb changes based on punctuation: "
            "? = asks, ! = exclaims, ... = mutters, otherwise says. "
            'The " shortcut works without typing "say" first.'
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('say <message>', 'Speak aloud to everyone in the room'),
            ('"<message>',    'Shorthand for say'),
        ],
        examples = [
            ('say Hello there!',   'SAY broadcasts a message to everyone in your room, '
                                    'picking a verb from your trailing punctuation rather '
                                    "than always saying \"says\" -- a trailing '!' shows "
                                    'as Rulan exclaims, "Hello there!"'),
            ('say What time is it?', "A trailing '?' shows as asking instead -- Rulan "
                                      'asks, "What time is it?"'),
            ('"See you around.',   'The \'"\' shortcut works without typing \'say\' first '
                                    "-- with no special punctuation at the end, it's just "
                                    'Rulan says, "See you around."'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)

        # Reconstruct the message; strip a leading " if the shortcut was used
        text = ' '.join(args).lstrip('"').strip()

        if not text:
            await ctx.send('Say what?')
            return CommandResult(False, 'No message.')

        third, first = _choose_verb(text)
        name = ctx.player.name

        await ctx.send(f'You {first}, "{text}"')
        await ctx.send_room(f'{name} {third}, "{text}"', exclude_self=True)
        await _gollum_riddle_check(ctx, text)
        return CommandResult.ok()
