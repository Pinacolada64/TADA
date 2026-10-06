"""commands/whisper.py — Whisper a private message to one or more players in the same room.

Syntax:  whisper <targets>=<message>
Targets: a comma- or space-delimited list of names; quote names that contain
         spaces; use #groupname to address everyone in a saved group.

Use #reply (or #r) as the target to whisper back to whoever you last
whispered with, without retyping their name -- the last correspondent is
remembered in command_settings.whisper.last_whispered.

"whisper #last [N]" lists the last people you whispered to (newest first,
each with a relative timestamp, from command_settings.whisper.history);
"whisper #last N" also saves N (1-10) as how many entries to show.

Examples:
    whisper Bob=Did you see that?
    whisper Alice,Bob=Let's sneak out
    whisper "Dark Lord"=I come in peace
    whisper #friends=Meet at the inn
    whisper #r=me too
    whisper #last
    whisper #last 5
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import (
    parse_targets, expand_groups, find_online, substitute_reply,
    record_message_target, render_last_history, parse_last_limit,
)
from network_context import GameContext


class WhisperCommand(Command):
    name    = 'whisper'
    # can't be 'w' — that's an alias for 'go west'
    aliases = ['wh']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Whisper a private message to one or more players in your room.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('whisper <name>=<message>',           'Whisper to one player'),
            ('whisper <name>,<name2>=<message>',   'Whisper to multiple players'),
            ('whisper #<group>=<message>',         'Whisper to everyone in a group'),
            ('whisper #r=<message>',               'Whisper back to your last correspondent'),
            ('whisper #last [N]',                  'List the last people you whispered to (N: how many, 1-10)'),
        ],
        examples = [
            ('whisper Bob=Did you see that?',      "WHISPER sends a message only the "
                                                    "named target(s) can see, unlike SAY "
                                                    "-- everyone else in the room stays "
                                                    "unaware you said anything. Only Bob "
                                                    "hears this one, and only because "
                                                    "he's in the same room as you (use "
                                                    "PAGE instead for cross-room "
                                                    "messages)."),
            ('whisper Alice,Bob=Lets go',          'Comma-separate names to whisper the '
                                                    'same message to several people at '
                                                    'once, same as PAGE.'),
            ('whisper #friends=Meet at the inn',   'A saved GROUPS name works as a '
                                                    'target too, whispering to everyone '
                                                    'in it who happens to be in the room '
                                                    'with you.'),
            ('whisper #r=me too',                  "'#reply' (or '#r') stands in for the "
                                                    'last player you whispered with -- '
                                                    'either direction -- so you can '
                                                    "answer without retyping their name."),
            ('whisper #last 5',                    "'#last' lists who you've whispered to "
                                                    'recently, newest first, with how '
                                                    "long ago.  '#last 5' also saves 5 as "
                                                    'the number of entries to show (1-10).'),
        ],
        notes = ['Target must be in the same room.  Use [page] for cross-room messages.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        # Don't call parse_args: #groupname tokens start with '#' and would be
        # classified as switches, breaking the targets=message syntax.
        if not args:
            await ctx.send('Whisper to whom?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('No arguments.')

        # 'whisper #last [N]' -- list recent recipients / set the show limit.
        # Handled before the '=' check since it has no message part.
        if args[0].lower() == '#last':
            cs = ctx.player.command_settings.whisper
            new_limit, err = parse_last_limit(args[1:])
            if err:
                await ctx.send(err)
                return CommandResult.fail(err, error='bad_args')
            if new_limit is not None and new_limit != cs.last_limit:
                cs.last_limit = new_limit
                ctx.player.unsaved_changes = True
                await ctx.send(f'whisper #last now shows up to {new_limit}.')
            await ctx.send(render_last_history(
                cs.history, cs.last_limit, verb='whispered'))
            return CommandResult.ok('Shown.')

        raw = ' '.join(args)

        if '=' not in raw:
            await ctx.send('Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing =.')

        targets_str, _, message = raw.partition('=')
        message = message.strip()

        if not message:
            await ctx.send('Whisper what?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing message.')

        target_names = parse_targets(targets_str)
        if not target_names:
            await ctx.send('Whisper to whom?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing target name.')

        # '#reply' / '#r' -> whoever you last whispered with
        target_names, unresolved_reply = substitute_reply(
            target_names, ctx.player.command_settings.whisper.last_whispered)
        if unresolved_reply:
            await ctx.send("You haven't whispered with anyone yet.")
            return CommandResult.fail('No one to reply to.')

        my_name = ctx.player.name

        # Remove self from target list silently
        target_names = [n for n in target_names if n.lower() != my_name.lower()]
        if not target_names:
            await ctx.send('You mutter to yourself, but no one notices.')
            return CommandResult.ok()

        # Expand group tokens
        target_names, unknown_groups = expand_groups(ctx.player, target_names)
        for g in unknown_groups:
            await ctx.send(f'You have no group named "{g[1:]}".')

        if not target_names:
            return CommandResult.ok()

        found_ctxs, not_found = find_online(ctx, target_names, same_room_only=True)
        for n in not_found:
            await ctx.send(f'{n} is not here.')

        if not found_ctxs:
            return CommandResult.ok()

        names_str = ', '.join(tctx.player.name for tctx in found_ctxs)
        await ctx.send(f'You whisper to {names_str}, "{message}"')
        for tctx in found_ctxs:
            await tctx.send(f'{my_name} whispers to you, "{message}"')
            # Recipient's '#reply' now points back at the sender.
            tctx.player.command_settings.whisper.last_whispered = my_name
            tctx.player.unsaved_changes = True
            # ...and joins the sender's 'whisper #last' history.
            record_message_target(
                ctx.player.command_settings.whisper.history, tctx.player.name)

        # Sender's '#reply' points at the last person actually reached.
        ctx.player.command_settings.whisper.last_whispered = found_ctxs[-1].player.name
        ctx.player.unsaved_changes = True

        return CommandResult.ok()
