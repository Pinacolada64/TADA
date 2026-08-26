"""commands/say.py — Say something to everyone in your room.

Verb is chosen by terminal punctuation:
  default  → says / say
  ?        → asks / ask
  !        → exclaims / exclaim
  ...      → mutters / mutter

The command is also triggered by the bare " shortcut:
  "Hello there!   →  Rulan exclaims, "Hello there!"

With command_settings.say.split enabled (PREFS 'Y'), a ',,' in the text
splits it into a mid-sentence attribution instead of one leading quote:
  say This is something,,up with which I will not put!
    →  "This is something," Rulan exclaims, "up with which I will not put!"

A ',,,' instead attaches a one-off verb straight after the quote, in
"<verb> <name>." order, overriding punctuation-based selection for just
that line (doesn't touch command_settings.say.verb):
  say Argh!,,,moan
    →  "Argh!" moans Rulan.

'say #verb=<word>' overrides the punctuation-based verb entirely
(command_settings.say.verb), e.g. 'say #verb=grumble' then 'say Hello'
  →  Rulan grumbles, "Hello"
'say #verb=off' (or '#verb='/'#verb=none') clears it. Bare 'say #verb'
previews the current verb without broadcasting anything.
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


def _third_person(verb: str) -> str:
    """Naive English 3rd-person-singular conjugation for a custom verb,
    e.g. 'grumble' -> 'grumbles', 'hiss' -> 'hisses', 'cry' -> 'cries'."""
    if verb.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return verb + 'es'
    if verb.endswith('y') and not verb.endswith(('ay', 'ey', 'iy', 'oy', 'uy')):
        return verb[:-1] + 'ies'
    return verb + 's'


def _resolve_verb(ctx: GameContext, text: str):
    """Return (third_person, first_person) verb, preferring a custom
    command_settings.say.verb override ('say #verb=<word>') over the
    default punctuation-based selection."""
    custom = getattr(ctx.player.command_settings.say, 'verb', None)
    if custom:
        return _third_person(custom), custom
    return _choose_verb(text)


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
            'The " shortcut works without typing "say" first. '
            "With Say Split turned on in PREFS ('Y'), a ',,' in your "
            "message splits it into a mid-sentence attribution, and a "
            "',,,' attaches a one-off verb right after the quote instead.\n\n"
            "'say #verb=<word>' sets a permanent custom verb instead, "
            "overriding punctuation entirely -- 'say #verb' previews it, "
            "'say #verb=off' clears it."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('say <message>',        'Speak aloud to everyone in the room'),
            ('"<message>',           'Shorthand for say'),
            ('say <msg>,,<msg2>',    "Split into a mid-sentence attribution (Say Split, PREFS 'Y')"),
            ('say <msg>,,,<verb>',   'One-off verb straight after the quote (Say Split, PREFS \'Y\')'),
            ('say #verb=<word>',     'Always use <word> as your say verb'),
            ('say #verb',            'Preview your current say verb'),
            ('say #verb=off',        'Clear the custom verb'),
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
            ('say This is something,,up with which I will not put!',
             "If you've turned on Say Split in PREFS ('Y'), a ',,' splits your "
             'message into a mid-sentence attribution instead of one leading '
             'quote -- shows as "This is something," Rulan exclaims, "up with '
             'which I will not put!"'),
            ('say Argh!,,,moan',   "With Say Split on, a ',,,' attaches a one-off verb "
                                    'right after the quote instead of a mid-sentence split '
                                    '-- shows as "Argh!" moans Rulan., overriding the '
                                    "punctuation-based verb for just this line without "
                                    "touching your saved #verb."),
            ('say #verb=grumble',   "Sets your say verb permanently -- afterward, "
                                    '"say Hello" shows as Rulan grumbles, "Hello", '
                                    'overriding the punctuation-based verb entirely. '
                                    "'say #verb' alone previews the current verb "
                                    "without saying anything, and 'say #verb=off' "
                                    'clears it.'),
        ],
        notes = [
            "Say Split (PREFS 'Y') must be on for ',,' and ',,,' to do "
            "anything special -- otherwise they're just literal commas.",
            "'say #verb=off' also accepts 'say #verb=' and 'say #verb=none'.",
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, switches = self.parse_args(*args)

        verb_switch = next((s for s in switches if s == '#verb' or s.startswith('#verb=')), None)
        if verb_switch is not None:
            return await self._handle_verb_switch(ctx, verb_switch)

        # Reconstruct the message; strip a leading " if the shortcut was used
        text = ' '.join(args).lstrip('"').strip()

        if not text:
            await ctx.send('Say what?')
            return CommandResult(False, 'No message.')

        name = ctx.player.name
        split_enabled = getattr(ctx.player.command_settings.say, 'split', False)

        if split_enabled and ',,,' in text:
            quote, _, inline_verb = text.partition(',,,')
            quote, inline_verb = quote.strip(), inline_verb.strip()
            if inline_verb:
                third = _third_person(inline_verb)
                await ctx.send(f'"{quote}" you {inline_verb}.')
                await ctx.send_room(f'"{quote}" {third} {name}.', exclude_self=True)
                await _gollum_riddle_check(ctx, quote)
                return CommandResult.ok()
            text = quote  # trailing ',,,' with no verb -- fall through as plain text

        third, first = _resolve_verb(ctx, text)

        if split_enabled and ',,' in text:
            part1, part2 = (p.strip() for p in text.split(',,', 1))
            await ctx.send(f'"{part1}," you {first}, "{part2}"')
            await ctx.send_room(f'"{part1}," {name} {third}, "{part2}"', exclude_self=True)
        else:
            await ctx.send(f'You {first}, "{text}"')
            await ctx.send_room(f'{name} {third}, "{text}"', exclude_self=True)
        await _gollum_riddle_check(ctx, text)
        return CommandResult.ok()

    async def _handle_verb_switch(self, ctx: GameContext, switch: str) -> CommandResult:
        """'say #verb' (preview), 'say #verb=<word>' (set), or
        'say #verb=off'/'#verb='/'#verb=none' (clear)."""
        say_settings = ctx.player.command_settings.say

        if switch == '#verb':
            if say_settings.verb:
                third = _third_person(say_settings.verb)
                await ctx.send(f'Your say verb is "{say_settings.verb}" -- '
                                f'{ctx.player.name} {third}, "..."')
            else:
                await ctx.send('No custom say verb set -- the verb follows your '
                                "trailing punctuation (says/asks/exclaims/mutters). "
                                "Set one with 'say #verb=<word>'.")
            return CommandResult.ok()

        value = switch[len('#verb='):].strip()
        if value in ('', 'off', 'none'):
            say_settings.verb = None
            await ctx.send('Say verb cleared -- back to punctuation-based '
                            '(says/asks/exclaims/mutters).')
            return CommandResult.ok()

        say_settings.verb = value
        third = _third_person(value)
        await ctx.send(f'Say verb set to "{value}" -- '
                        f'{ctx.player.name} {third}, "..."')
        return CommandResult.ok()
