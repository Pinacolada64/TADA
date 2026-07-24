"""commands/mail.py — The MAIL command: compose/read/reply/delete private mail.

Design per MECHANICS.md's "News & Mail" > "Mail / Paging" section's
"Future" note. Storage/schema lives in mail.py (top-level); this module
is just the in-game command surface:

  mail                     — list your mailbox (From/date/read status),
                              stay in the listing (like NEWS) until Enter
  mail <n>                 — read message <n> in full, marks it read
  mail #delete <n>         — remove message <n>
  mail #reply <n>=<msg>    — page (or, if offline, leave mail for)
                              whoever sent message <n>
  mail #read               — with PlayerFlags.PROMPT_MODE on and more
                              than one message, walk the mailbox one
                              message at a time with an end-of-message
                              [R]eply/[D]elete/[A]rchive/[K]eep/Read
                              [O]ver menu (see _read_interactive()) --
                              same idea as commands/board_reply.py's
                              PROMPT_MODE-gated thread reader. Falls back
                              to the plain listing (mail) otherwise.
  mail <target>[,<target2>...]=<message>
                            — send a short one-line message directly to
                              each target's mailbox (always -- unlike
                              PAGE, this never tries a live delivery).
                              Targets: comma/space-delimited names
                              (shlex-accepted, so a quoted "Dark Lord"
                              works), or #groupname (commands/groups.py) --
                              same target syntax as commands/page.py.
  mail <target>[,<target2>...]
                            — no '=' -- opens the line editor
                              (text_editor.run_editor(), same as NEWS/
                              BOARD authoring) for a longer message,
                              delivered to every target on .S Save.

Composing always writes to the mailbox regardless of online status -- MAIL
is a left-behind letter, not a live chat message (that's what PAGE is
for). If a target happens to be online right now, though, they also get
a quick "You have new mail from <sender>." notice in their own session,
so they don't have to wait for their next login to notice it.

Every "<n>" above numbers the *active* (non-archived) messages, in
mailbox order -- archiving a message (mail.mark_archived()) doesn't
delete it, just drops it out of that numbering/listing/unread count, the
same way it disappears from `mail #read`'s walk. '#read'/'#delete'/
'#reply' are reserved control words (mirrors commands/page.py's
#ignore/#haven convention), so a saved group can't be named "read",
"delete", or "reply" and used as a mail target.

Login-time "you have N unread message(s)" is handled by
commands/connect.py, which calls mail.py's unread_count() directly --
same split as news.py/commands/news.py.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import parse_targets, expand_groups, find_online, player_exists
from flags import PlayerFlags
import mail as mail_store
from formatting import deserialize_lines, hrule_char, make_rule, render_lines

_DATE_COL_WIDTH = 20  # "YYYY-MM-DDTHH:MM:SS"[:16] + padding


class MailCommand(Command):
    name    = 'mail'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Compose, read, reply to, and delete your private mail.',
        description = (
            'Lists messages left for you (see PAGE\'s offline fallback, or '
            'send mail directly with MAIL itself). Pick one by number to '
            'read it in full.'
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('mail',                      'List your mailbox.'),
            ('mail <n>',                  'Read message <n> in full.'),
            ('mail #delete <n>',          'Delete message <n>.'),
            ('mail #reply <n>=<message>', 'Reply to whoever sent message <n>.'),
            ('mail #read',                'Walk your mailbox one message at a time.'),
            ('mail <target>=<message>',   'Send a short message directly.'),
            ('mail <target>',             'Open the editor for a longer message.'),
        ],
        examples = [
            ('mail',                          'See what mail you have.'),
            ('mail 2',                        'Read message #2.'),
            ('mail #delete 2',                'Remove message #2.'),
            ('mail #reply 2=On my way!',      'Reply to message #2\'s sender.'),
            ('mail #read',                    'Read through everything, one at a time.'),
            ('mail Alice=Meet at the inn',    'Short message to Alice.'),
            ('mail Alice,Bob=Party tonight',  'Short message to Alice and Bob.'),
            ('mail #friends=Where is everyone?', 'Short message to a saved group.'),
            ('mail "Dark Lord"',              'Opens the editor for a longer letter.'),
        ],
        notes = [
            'Unread mail is announced when you log in.',
            'Inside the listing, a bare number reads that message; '
            "'d<n>' deletes it.",
            "'mail #read' walks your mailbox one message at a time with "
            'a Reply/Delete/Archive/Keep menu -- requires Prompt Mode '
            '(PREFS) on and more than one message.',
            'MAIL always leaves a letter in the mailbox, whether or not '
            'the recipient is online -- use PAGE for a live message.',
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not args:
            return await self._list(ctx)

        first = args[0].lower()
        if first == '#delete' and len(args) > 1:
            return await self._delete(ctx, args[1])
        if first == '#reply' and len(args) > 1:
            return await self._reply(ctx, ' '.join(args[1:]))
        if first == '#read':
            return await self._read_interactive(ctx)
        if len(args) == 1 and args[0].isdigit():
            return await self._read_one(ctx, int(args[0]))

        return await self._compose(ctx, args)

    # ------------------------------------------------------------------
    # Listing / reading
    # ------------------------------------------------------------------

    @staticmethod
    def _active_entries(name: str) -> list[tuple[int, dict]]:
        """(raw_index, message) pairs for non-archived messages, in
        mailbox order. Every player-facing "<n>" (listing, read, delete,
        reply, #read) numbers *this* sequence, never raw file positions --
        so archiving a message (see mail.mark_archived()) drops it out of
        the numbering instead of leaving a gap or a stale index."""
        raw = mail_store.load_mailbox(name)
        return [(i, m) for i, m in enumerate(raw) if not m.get('archived', False)]

    def _render_listing(self, ctx, inbox: list[dict]) -> list[str]:
        rule_width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
        lines = [
            '', '|yellow|Mail|reset|', '',
            f"  Num  {'Date':<{_DATE_COL_WIDTH}}{'From':<16}Status",
            make_rule(rule_width, hrule_char(ctx)),
        ]
        for i, msg in enumerate(inbox, 1):
            posted = msg.get('timestamp', '')[:16].replace('T', ' ')
            status = 'New' if not msg.get('read', False) else ''
            lines.append(f"  {i:>3}. {posted:<{_DATE_COL_WIDTH}}{msg.get('from', '?'):<16}{status}")
        lines.append('')
        return lines

    async def _list(self, ctx) -> CommandResult:
        """Show the mailbox and stay in it -- reading/deleting redisplays
        the listing -- until the player presses Enter to leave. While
        active, virtual_location (commands/whereat.py) reads 'Reading mail'."""
        name = ctx.player.name
        entries = self._active_entries(name)
        if not entries:
            await ctx.send('You have no mail.')
            return CommandResult.ok('No mail.')

        previous_location = getattr(ctx.client, 'virtual_location', None)
        ctx.client.virtual_location = 'Reading mail'
        try:
            while True:
                entries = self._active_entries(name)
                if not entries:
                    await ctx.send('No more mail to read.')
                    return CommandResult.ok('No mail.')

                raw = await ctx.prompt(
                    f"Read which (#, 'd<n>' to delete, or {ctx.player.return_key} to exit)",
                    preamble_lines=self._render_listing(ctx, [m for _, m in entries]),
                )
                if raw is None or not raw.strip():
                    return CommandResult.ok('Exited mail.')

                choice = raw.strip()
                if choice.isdigit():
                    await self._read_one(ctx, int(choice))
                elif choice[:1].lower() == 'd' and choice[1:].isdigit():
                    await self._delete(ctx, choice[1:])
                else:
                    await ctx.send(f"'{choice}' is not a valid mail number.")
        finally:
            ctx.client.virtual_location = previous_location

    async def _read_one(self, ctx, number: int) -> CommandResult:
        name    = ctx.player.name
        entries = self._active_entries(name)
        if not (1 <= number <= len(entries)):
            await ctx.send('No such mail message.')
            return CommandResult.fail('Unknown mail message.', error='not_found')

        raw_index = entries[number - 1][0]
        msg = mail_store.mark_read(name, raw_index)
        await ctx.send(
            '',
            f"|yellow|From:|reset| {msg.get('from', '?')}",
            f"|yellow|Date:|reset| {msg.get('timestamp', '')[:16].replace('T', ' ')}",
            '',
            *self._render_body(msg.get('body', ''), ctx),
            '',
        )
        return CommandResult.ok('Displayed mail message.')

    @staticmethod
    def _render_body(body, ctx) -> list[str]:
        """A message body is either a plain string (PAGE's one-liner
        offline fallback, or MAIL's own short <target>=<message> form) or
        a list of formatting.serialize_lines()'s output (MAIL's editor-
        composed long-form letters) -- render either the same way news.py's
        format_item() does for its own structurally-stored bodies."""
        if isinstance(body, str):
            return [body]
        width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
        return render_lines(deserialize_lines(body), ctx, width)

    # ------------------------------------------------------------------
    # Delete / reply
    # ------------------------------------------------------------------

    async def _delete(self, ctx, raw_number: str) -> CommandResult:
        if not raw_number.isdigit():
            await ctx.send('Delete which mail number?')
            return CommandResult.fail('Missing number.', error='missing_args')

        number  = int(raw_number)
        name    = ctx.player.name
        entries = self._active_entries(name)
        if not (1 <= number <= len(entries)):
            await ctx.send('No such mail message.')
            return CommandResult.fail('Unknown mail message.', error='not_found')

        mail_store.delete_message(name, entries[number - 1][0])
        await ctx.send(f'Message #{number} deleted.')
        return CommandResult.ok('Deleted mail message.')

    async def _reply(self, ctx, raw: str) -> CommandResult:
        if '=' not in raw:
            await ctx.send('Usage: mail #reply <n>=<message>')
            return CommandResult.fail('Missing =.', error='missing_args')

        number_str, _, message = raw.partition('=')
        number_str = number_str.strip()
        message    = message.strip()

        if not number_str.isdigit():
            await ctx.send('Usage: mail #reply <n>=<message>')
            return CommandResult.fail('Missing number.', error='missing_args')
        if not message:
            await ctx.send('Reply with what?  Usage: mail #reply <n>=<message>')
            return CommandResult.fail('Missing message.', error='missing_args')

        name    = ctx.player.name
        entries = self._active_entries(name)
        number  = int(number_str)
        if not (1 <= number <= len(entries)):
            await ctx.send('No such mail message.')
            return CommandResult.fail('Unknown mail message.', error='not_found')

        target = entries[number - 1][1].get('from', '')
        if not target or target.lower() == name.lower():
            await ctx.send('Cannot reply to that message.')
            return CommandResult.fail('No valid sender.', error='not_found')

        # Delegate to PAGE's own targeting/delivery/offline-mail-fallback
        # logic rather than duplicating it -- a reply is just a page to
        # the original sender.
        from commands.page import PageCommand
        return await PageCommand().execute(ctx, f'{target}={message}')

    # ------------------------------------------------------------------
    # '#read' -- PROMPT_MODE interactive walk
    # ------------------------------------------------------------------

    async def _read_interactive(self, ctx) -> CommandResult:
        """`mail #read`: with PlayerFlags.PROMPT_MODE on and more than one
        message, walk the (active, non-archived) mailbox one message at a
        time, each followed by a [R]eply/[D]elete/[A]rchive/[K]eep/Read
        [O]ver menu -- same shape as commands/board_reply.py's
        PROMPT_MODE-gated thread reader. Falls back to the plain listing
        (self._list()) when PROMPT_MODE is off or there's 0-1 messages,
        since there's nothing to "walk" through."""
        name    = ctx.player.name
        entries = self._active_entries(name)
        if not entries:
            await ctx.send('You have no mail.')
            return CommandResult.ok('No mail.')

        if not ctx.player.query_flag(PlayerFlags.PROMPT_MODE) or len(entries) < 2:
            return await self._list(ctx)

        previous_location = getattr(ctx.client, 'virtual_location', None)
        ctx.client.virtual_location = 'Reading mail'
        try:
            idx = 0
            while True:
                entries = self._active_entries(name)
                if idx >= len(entries):
                    await ctx.send('End of mail.')
                    return CommandResult.ok('Read all mail.')

                raw_index, msg = entries[idx]
                msg = mail_store.mark_read(name, raw_index)
                await ctx.send(
                    '',
                    f"|yellow|Message {idx + 1} of {len(entries)}|reset|  "
                    f"|yellow|From:|reset| {msg.get('from', '?')}"
                    f"  |yellow|Date:|reset| {msg.get('timestamp', '')[:16].replace('T', ' ')}",
                    '',
                    *self._render_body(msg.get('body', ''), ctx),
                    '',
                )

                raw = await ctx.prompt(
                    f'[R]eply, [D]elete, [A]rchive, [K]eep, Read [O]ver, '
                    f'or {ctx.player.return_key} for next',
                )
                if raw is None:
                    return CommandResult.ok('Exited mail.')

                choice = raw.strip().lower()
                if not choice or choice == 'k':
                    idx += 1
                elif choice == 'r':
                    await self._reply_interactive(ctx, msg)
                    idx += 1
                elif choice == 'd':
                    mail_store.delete_message(name, raw_index)
                    # Don't advance -- the next active message shifts
                    # into this same slot.
                elif choice == 'a':
                    mail_store.mark_archived(name, raw_index)
                    await ctx.send('Message archived.')
                    # Don't advance, same reasoning as delete.
                elif choice == 'o':
                    continue  # redisplay the same message
                else:
                    await ctx.send(f"Unrecognized choice '{choice}'.")
        finally:
            ctx.client.virtual_location = previous_location

    async def _reply_interactive(self, ctx, msg: dict) -> None:
        """[R]eply from within `mail #read`: prompt for a short reply
        right there and page (or, offline, mail) the sender -- same
        delivery path as the standalone `mail #reply <n>=<message>`."""
        target = msg.get('from', '')
        if not target or target.lower() == ctx.player.name.lower():
            await ctx.send('Cannot reply to that message.')
            return

        raw = await ctx.prompt(f'Reply to {target}')
        if raw is None or not raw.strip():
            await ctx.send('Reply cancelled.')
            return

        from commands.page import PageCommand
        await PageCommand().execute(ctx, f'{target}={raw.strip()}')

    # ------------------------------------------------------------------
    # Composing new mail
    # ------------------------------------------------------------------

    def _resolve_targets(self, ctx, targets_str: str) -> tuple[list[str], list[str]]:
        """Parse/expand *targets_str* (shlex-accepted names, comma/space
        delimited, #groupname tokens) into (valid_names, problem_lines) --
        problem_lines are already-formatted "can't do that" messages for
        unknown groups/players/self, ready to send as-is."""
        my_name = ctx.player.name
        problems: list[str] = []

        all_names = parse_targets(targets_str)
        names = [n for n in all_names if n.lower() != my_name.lower()]
        if all_names and not names:
            problems.append('You cannot mail yourself.')

        names, unknown_groups = expand_groups(ctx.player, names)
        for g in unknown_groups:
            problems.append(f'You have no group named "{g[1:]}".')

        valid: list[str] = []
        for n in names:
            if n.lower() == my_name.lower():
                continue
            if not player_exists(ctx.server, n):
                problems.append(f'No such player: {n}.')
                continue
            valid.append(n)

        return valid, problems

    async def _deliver(self, ctx, targets: list[str], body) -> None:
        """Append *body* to each of *targets*' mailboxes, and -- if a
        target happens to be online right now -- send them a live
        "You have new mail" notice too (find_online(), same lookup
        commands/page.py uses) so they don't have to wait until their
        next login to notice it. Doesn't affect delivery either way;
        MAIL always writes to the mailbox regardless of online status."""
        online_ctxs, _ = find_online(ctx, targets)

        for name in targets:
            mail_store.add_message(name, ctx.player.name, body)

        for tctx in online_ctxs:
            hint = '' if tctx.player.is_expert else " (type 'mail' to read)"
            await tctx.send(f'You have new mail from {ctx.player.name}.{hint}')

    async def _compose(self, ctx, args: tuple) -> CommandResult:
        """Dispatch for anything that isn't list/read/delete/reply: a
        <target>=<message> short-form send, or a bare <target> that opens
        the editor for a longer letter."""
        raw = ' '.join(args)

        if '=' in raw:
            targets_str, _, message = raw.partition('=')
            message = message.strip()
            if not message:
                await ctx.send('Mail what?  Usage: mail <target[,target2]>=<message>')
                return CommandResult.fail('Missing message.', error='missing_args')
            return await self._send_short(ctx, targets_str, message)

        return await self._compose_long(ctx, raw)

    async def _send_short(self, ctx, targets_str: str, message: str) -> CommandResult:
        if not targets_str.strip():
            await ctx.send('Mail whom?  Usage: mail <target[,target2]>=<message>')
            return CommandResult.fail('Missing target.', error='missing_args')

        targets, problems = self._resolve_targets(ctx, targets_str)
        for p in problems:
            await ctx.send(p)
        if not targets:
            return CommandResult.fail('No valid target.', error='missing_args')

        await self._deliver(ctx, targets, message)
        await ctx.send(f"Mail sent to {', '.join(targets)}.")
        return CommandResult.ok('Mail sent.')

    async def _compose_long(self, ctx, targets_str: str) -> CommandResult:
        targets, problems = self._resolve_targets(ctx, targets_str)
        for p in problems:
            await ctx.send(p)
        if not targets:
            if not problems:
                await ctx.send('Mail whom?  Usage: mail <target[,target2]> (opens the editor)')
            return CommandResult.fail('No valid target.', error='missing_args')

        from text_editor import run_editor
        target_label = ', '.join(targets)
        body = await run_editor(ctx, activity_id=f'mail_compose:{target_label}',
                                 activity_label=f'writing mail to {target_label}')
        if not body:
            await ctx.send('Mail cancelled.')
            return CommandResult.ok('Cancelled.')

        await self._deliver(ctx, targets, body)
        await ctx.send(f"Mail sent to {', '.join(targets)}.")
        return CommandResult.ok('Mail sent.')
