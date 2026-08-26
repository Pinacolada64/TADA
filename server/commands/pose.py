"""commands/pose.py — Emote an action to everyone in your room.

Works like SAY, but with no added verb/quoting. Type the action in
third-person (as it will appear to others); the leading verb is
de-conjugated to first person for the actor's own line:
  :stares at the wall.  →  You: "You stare at the wall."
                           Others: "Rulan stares at the wall."

The command is also triggered by the bare : shortcut, and by the aliases
"emote" and "/me" (borrowed from other RP/MUD/chat conventions).
"""
import re

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

_TRAILING_PUNCT = re.compile(r'([^\W\d_]+)([^\w]*)$', re.UNICODE)


def _first_person(word: str) -> str:
    """De-conjugate a third-person-singular verb for the actor's own line.

    'stares' -> 'stare', 'watches.' -> 'watch.', 'tries!' -> 'try!'. Any
    trailing punctuation stays put; words with no trailing 's' (already
    first person, or not a verb at all) are left alone.
    """
    match = _TRAILING_PUNCT.search(word)
    if not match:
        return word
    verb, punct = match.group(1), match.group(2)
    prefix = word[:match.start(1)]

    lower = verb.lower()
    if lower.endswith('ies') and len(verb) > 3:
        base = verb[:-3] + 'y'
    elif lower.endswith(('ches', 'shes', 'xes', 'sses')):
        base = verb[:-2]
    elif lower.endswith('s') and not lower.endswith('ss'):
        base = verb[:-1]
    else:
        return word

    if verb[0].isupper():
        base = base[0].upper() + base[1:]
    return f'{prefix}{base}{punct}'


class PoseCommand(Command):
    name    = 'pose'
    aliases = [':', 'emote', '/me']
    modes   = {Mode.GAME}

    help = Help(
        summary     = "Emote an action to players in your room.",
        description = (
            "Broadcasts an emote to everyone in your room. Type the action "
            "in third-person, as it will appear to others -- your own line "
            "de-conjugates the leading verb to first person: "
            '"pose stares at the wall." shows as "You stare at the wall." '
            'to you and "Rulan stares at the wall." to everyone else. '
            'The : shortcut works without typing "pose" first, and '
            '"emote"/"/me" are accepted as aliases.'
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('pose <action>', 'Emote an action to everyone in the room'),
            (':<action>',     'Shorthand for pose'),
            ('emote <action>', 'Alias for pose'),
            ('/me <action>',   'Alias for pose'),
        ],
        examples = [
            ('pose stares at the wall.', 'POSE broadcasts your action, typed in '
                                          'third-person -- you see "You stare at '
                                          'the wall." (de-conjugated) while everyone '
                                          'else sees "Rulan stares at the wall."'),
            (':grins.', 'The \':\' shortcut works without typing "pose" first.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)

        # Reconstruct the message; strip a leading : if the shortcut was used
        text = ' '.join(args).lstrip(':').strip()

        if not text:
            await ctx.send('Pose what?')
            return CommandResult(False, 'No message.')

        name = ctx.player.name
        words = text.split(' ', 1)
        first_word = _first_person(words[0])
        rest = f' {words[1]}' if len(words) > 1 else ''

        await ctx.send(f'You {first_word}{rest}')
        await ctx.send_room(f'{name} {text}', exclude_self=True)
        return CommandResult.ok()
