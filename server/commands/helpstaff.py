"""commands/helpstaff.py — Ask an available staffer for help.

Usage:  helpstaff                  ask what you need: relayed to whoever's
                                    on duty, or saved for staff to answer
                                    by mail if nobody is
        helpstaff #show            list who's on helpstaff duty right now
        helpstaff #cancel          withdraw your own open or saved question
        helpstaff #list            (on duty) show every open request
        helpstaff #accept <name>   (on duty) claim <name>'s request and
                                    teleport to them
        helpstaff #decline <name>  (on duty) pass on <name>'s request,
                                    leaving it open for someone else
        helpstaff #on|#off         go on / off helpstaff duty (helpstaff
                                    members, Admins, Dungeon Masters)
        helpstaff #queue           (staff) answer saved questions by mail
        helpstaff #faq [<n>]       (staff) list saved answers, or show one
        helpstaff #faq #add        (staff) write a new saved answer
        helpstaff #faq #edit <n>   (staff) rewrite saved answer <n>
        helpstaff #faq #delete <n> (staff) remove saved answer <n>

This is a request/relay/accept flow, not a direct summon-by-name: a plain
player describes what they need, every on-duty staffer is notified, and
whichever one accepts first is moved to the requester's room. Closes the
"summoning help staff for assistance" TODO that had sat at the top of
commands/new_player.py since it was written.

PlayerFlags.HELPSTAFF means "is helpstaff" (saved, set from editplayer);
being on duty is per-connection and never saved -- see helpstaff/duty.py.
A question asked while nobody is on duty goes to the saved queue
(helpstaff/queue.py) instead; staff answer it by mail from '#queue' or
from the login check-in (logon_events/helpstaff.py), optionally using a
saved answer (helpstaff/faq.py).

Game mode only. The original snapshot was also reachable in Mode.LOGIN so
a player stuck mid character-creation could ask for a hand, but that path
can't actually be reached: creation runs entirely inside ctx.prompt()
calls, which never dispatch commands, and at the bare login prompt every
connection's placeholder player is the same "Generic Name" with no real
room to teleport to. Guests and freshly created characters are both in
Mode.GAME, so they're covered.

Open live requests live in Server.pending_help_requests (requester name ->
description); simple_server.py drops a requester's entry when they
disconnect.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from helpstaff import duty, faq
from helpstaff import queue as help_queue
from helpstaff.duty import HELPSTAFF_TAG, tagged_name  # noqa: F401  (re-exported)
from network_context import GameContext


def _player_of(client):
    return getattr(getattr(client, 'ctx', None), 'player', None)


def _available_staffers(ctx) -> list:
    """Connected clients currently on helpstaff duty."""
    return duty.on_duty_clients(ctx.server)


def _find_client_by_name(server, name: str):
    """Case-insensitive lookup of a connected client by player name."""
    for client in getattr(server, 'clients', {}).values():
        player = _player_of(client)
        if player and player.name.lower() == name.lower():
            return client
    return None


def _pending(server) -> dict:
    """Server.pending_help_requests, created on first use for servers
    (or test doubles) built without it."""
    pending = getattr(server, 'pending_help_requests', None)
    if not isinstance(pending, dict):
        pending = {}
        server.pending_help_requests = pending
    return pending


def _match_request(pending: dict, name: str) -> str | None:
    """Case-insensitive key lookup in the pending-request dict."""
    return next((n for n in pending if n.lower() == name.lower()), None)


def _plural(n: int, word: str) -> str:
    return f'{n} {word}{"" if n == 1 else "s"}'


class HelpstaffCommand(Command):
    name    = 'helpstaff'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Ask whoever's on helpstaff duty for a hand.",
        description = (
            "Describes what you need help with, then relays that to "
            "every helpstaff member currently on duty -- whoever accepts "
            "first comes to you. If nobody is on duty, your question is "
            "saved and a helpstaff member answers it by mail."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('helpstaff',                  'Ask for help; describes what you need.'),
            ('helpstaff #ask',             'The same -- and how staff ask for help themselves.'),
            ('helpstaff #show',            "Show who's on helpstaff duty right now."),
            ('helpstaff #cancel',          'Withdraw your open or saved question.'),
            ('helpstaff #list',            '(on duty) Show every open request.'),
            ('helpstaff #accept <name>',   "(on duty) Claim <name>'s request and go help."),
            ('helpstaff #decline <name>',  "(on duty) Pass on <name>'s request."),
            ('helpstaff #on',              '(staff) Go on helpstaff duty.'),
            ('helpstaff #off',             '(staff) Go off helpstaff duty.'),
            ('helpstaff #queue',           '(staff) Answer saved questions by mail.'),
            ('helpstaff #faq [<n>]',       '(staff) List saved answers, or show one.'),
            ('helpstaff #faq #add',        '(staff) Write a new saved answer.'),
            ('helpstaff #faq #edit <n>',   '(staff) Rewrite saved answer <n>.'),
            ('helpstaff #faq #delete <n>', '(staff) Remove saved answer <n>.'),
        ],
        notes = [
            'Asking again replaces your earlier question.',
            'Answers to saved questions arrive by |command|mail|reset|, from '
            '"<name>, Helpstaff member".',
            '"Staff" means helpstaff members, Admins and Dungeon Masters.',
            'Staff who type a bare |command|helpstaff|reset| get a reminder of '
            '|command|helpstaff #show|reset| and |command|helpstaff #list|reset| '
            'instead -- use |command|helpstaff #ask|reset| to ask for help yourself.',
        ],
        admin_notes = [
            'Mark a player as a helpstaff member from |command|editplayer|reset| '
            '(Flags/Counters, Player Status). Members are asked at login whether '
            'to go on duty, and offered any saved questions.',
        ],
        see_also = ['help', 'who', 'mail'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, switches = self.parse_args(*args)
        target = ' '.join(positional).strip()

        if not switches:
            if positional:
                await ctx.send(f"Unknown option '{positional[0]}'. "
                               f"See |command|help helpstaff|reset|.")
                return CommandResult.fail('Unknown option.', error='bad_option')
            # Staff typing a bare HELPSTAFF almost always meant to check on
            # requests, not ask for help themselves (Ryan, testing as
            # railbender) -- remind them instead; #ask still asks.
            if duty.can_go_on_duty(ctx.player):
                await ctx.send('(You are helpstaff -- did you mean '
                               '|command|helpstaff #show|reset| or '
                               '|command|helpstaff #list|reset|? To ask for help '
                               'yourself, type |command|helpstaff #ask|reset|.)')
                return CommandResult.ok('Staff reminder shown.')
            return await self._request(ctx)

        sub = switches[0]
        if sub == '#ask':
            return await self._request(ctx)
        if sub in ('#accept', '#decline'):
            if not target:
                await ctx.send(f'Usage: |command|helpstaff {sub} <name>|reset|')
                return CommandResult.fail('Missing name.', error='missing_name')
            if sub == '#accept':
                return await self._accept(ctx, target)
            return await self._decline(ctx, target)
        if sub == '#show':
            return await self._show(ctx)
        if sub == '#list':
            return await self._list(ctx)
        if sub == '#cancel':
            return await self._cancel(ctx)
        if sub in ('#on', '#off'):
            return await self._duty(ctx, sub == '#on')
        if sub == '#queue':
            return await self._queue(ctx)
        if sub == '#faq':
            return await self._faq(ctx, switches[1:], target)

        await ctx.send(f"Unknown option '{sub}'. "
                       f"See |command|help helpstaff|reset|.")
        return CommandResult.fail('Unknown option.', error='bad_option')

    # -- requester side -----------------------------------------------------

    async def _request(self, ctx: GameContext) -> CommandResult:
        requester = ctx.player
        staffers  = [c for c in _available_staffers(ctx) if c is not ctx.client]
        if not staffers:
            return await self._request_queued(ctx)

        names = sorted(_player_of(client).name for client in staffers)

        description = await ctx.prompt(
            'What do you need help with?',
            preamble_lines=[f"Available to help: {', '.join(names)}", ''],
        )
        if description is None or not description.strip():
            await ctx.send('Never mind.')
            return CommandResult.ok('Cancelled.')
        description = description.strip()

        pending = _pending(ctx.server)
        # Asking again replaces the earlier request rather than stacking --
        # including one saved to the queue while nobody was on duty.
        old = _match_request(pending, requester.name)
        if old is not None:
            del pending[old]
        help_queue.remove(requester.name)
        pending[requester.name] = description

        from commands.whereat import _location_columns
        _, _, location_label = _location_columns(ctx.client, ctx.server)

        for client in staffers:
            await client.ctx.send(
                f'|yellow|{requester.name} needs help ({location_label}): '
                f'{description}|reset|',
                f'Type |command|helpstaff #accept {requester.name}|reset| to go help, '
                f'or |command|helpstaff #decline {requester.name}|reset| to pass.',
            )

        if len(names) == 1:
            await ctx.send(f'Your request has been sent to {names[0]}.')
        else:
            await ctx.send(f'Your request has been sent to {len(names)} helpstaffers.')
        return CommandResult.ok('Request sent.')

    async def _request_queued(self, ctx: GameContext) -> CommandResult:
        """Nobody on duty: save the question for staff to answer by mail."""
        description = await ctx.prompt(
            'What do you need help with?',
            preamble_lines=['No one is on helpstaff duty right now, so your '
                            'question will be saved and answered by mail.', ''],
        )
        if description is None or not description.strip():
            await ctx.send('Never mind.')
            return CommandResult.ok('Cancelled.')

        from commands.whereat import _location_columns
        _, _, location_label = _location_columns(ctx.client, ctx.server)
        help_queue.add(ctx.player.name, description.strip(), location_label)
        await ctx.send('Your question has been saved. A helpstaff member will '
                       'answer it by |command|mail|reset|.')
        return CommandResult.ok('Queued.')

    async def _show(self, ctx: GameContext) -> CommandResult:
        """'helpstaff #show' -- who's on duty, for anyone to check before
        (or instead of) asking."""
        names = sorted((_player_of(c).name for c in _available_staffers(ctx)),
                       key=str.lower)
        if not names:
            await ctx.send('No one is on helpstaff duty right now.')
        else:
            await ctx.send(f"On helpstaff duty: {', '.join(names)}")
        return CommandResult.ok('Shown.')

    async def _cancel(self, ctx: GameContext) -> CommandResult:
        pending = _pending(ctx.server)
        match   = _match_request(pending, ctx.player.name)
        queued  = help_queue.remove(ctx.player.name)
        if match is None and not queued:
            await ctx.send("You don't have an open request.")
            return CommandResult.fail('No open request.', error='not_open')
        if match is not None:
            del pending[match]
            for client in _available_staffers(ctx):
                if client is not ctx.client:
                    await client.ctx.send(f'{match} has withdrawn their request for help.')
        await ctx.send('Your request for help has been withdrawn.')
        return CommandResult.ok('Withdrawn.')

    # -- staffer side -------------------------------------------------------

    async def _require_staffer(self, ctx: GameContext) -> CommandResult | None:
        """On duty right now (for #list/#accept/#decline)."""
        if duty.on_duty(ctx.client):
            return None
        if duty.can_go_on_duty(ctx.player):
            await ctx.send("You're not on helpstaff duty. "
                           "Type |command|helpstaff #on|reset| first.")
        else:
            await ctx.send('You are not marked as available to help.')
        return CommandResult.fail('Not available.', error='not_available')

    async def _require_staff(self, ctx: GameContext) -> CommandResult | None:
        """Staff, on duty or not (for #queue/#faq)."""
        if duty.can_go_on_duty(ctx.player):
            return None
        await ctx.send('Only helpstaff members, Admins and Dungeon Masters can do that.')
        return CommandResult.fail('Not permitted.', error='not_permitted')

    async def _duty(self, ctx: GameContext, on: bool) -> CommandResult:
        player = ctx.player
        if on:
            if not duty.can_go_on_duty(player):
                await ctx.send('Only helpstaff members, Admins and Dungeon Masters '
                               'can go on helpstaff duty.')
                return CommandResult.fail('Not permitted.', error='not_permitted')
            duty.set_on_duty(ctx.client, True)
            await ctx.send('You are now on helpstaff duty.')
            await self._waiting_notice(ctx)
            return CommandResult.ok('On duty.')

        if not duty.on_duty(ctx.client):
            await ctx.send("You aren't on helpstaff duty.")
            return CommandResult.ok('Already off duty.')
        duty.set_on_duty(ctx.client, False)
        await ctx.send('You are now off helpstaff duty.')
        return CommandResult.ok('Off duty.')

    @staticmethod
    async def _waiting_notice(ctx: GameContext) -> None:
        """'N open requests' / 'N saved questions' lines after going on duty."""
        live = len(_pending(ctx.server))
        if live:
            await ctx.send(f'{_plural(live, "open request")} -- type '
                           f'|command|helpstaff #list|reset| to see '
                           f'{"them" if live != 1 else "it"}.')
        saved = help_queue.count()
        if saved:
            await ctx.send(f'{_plural(saved, "saved question")} waiting -- type '
                           f'|command|helpstaff #queue|reset| to answer by mail.')

    async def _list(self, ctx: GameContext) -> CommandResult:
        denied = await self._require_staffer(ctx)
        if denied:
            return denied
        pending = _pending(ctx.server)
        # Saved questions from players who are online right now can be
        # taken live with #accept, same as an open request.
        online_queued = [e for e in help_queue.load()
                         if _find_client_by_name(ctx.server, e['name']) is not None
                         and _match_request(pending, e['name']) is None]
        saved_total = help_queue.count()
        if not pending and not online_queued:
            await ctx.send('No open requests for help.')
            if saved_total:
                await ctx.send(f'{_plural(saved_total, "saved question")} waiting -- '
                               f'type |command|helpstaff #queue|reset|.')
            return CommandResult.ok('No requests.')

        from commands.whereat import _location_columns
        lines = []
        if pending:
            lines.append('Open requests for help:')
            for name, description in sorted(pending.items(), key=lambda kv: kv[0].lower()):
                client = _find_client_by_name(ctx.server, name)
                label = (_location_columns(client, ctx.server)[2]
                         if client is not None else 'disconnected')
                lines.append(f'  {name} ({label}): {description}')
        if online_queued:
            lines.append('Saved questions from players online now:')
            for e in online_queued:
                client = _find_client_by_name(ctx.server, e['name'])
                label = _location_columns(client, ctx.server)[2]
                lines.append(f'  {e["name"]} ({label}): {e["question"]}')
            lines.append('|command|helpstaff #accept <name>|reset| works on these too.')
        offline_saved = saved_total - len(online_queued)
        if offline_saved > 0:
            lines.append(f'{_plural(offline_saved, "more saved question")} -- '
                         f'type |command|helpstaff #queue|reset|.')
        await ctx.send(*lines)
        return CommandResult.ok('Listed.')

    async def _accept(self, ctx: GameContext, target_name: str) -> CommandResult:
        denied = await self._require_staffer(ctx)
        if denied:
            return denied
        staffer = ctx.player

        pending    = _pending(ctx.server)
        match_name = _match_request(pending, target_name)
        from_queue = None
        if match_name is None:
            # A saved question from someone who's online can be taken live.
            from_queue = help_queue.find(target_name)
            if from_queue is not None and _find_client_by_name(ctx.server,
                                                               from_queue['name']) is not None:
                match_name = from_queue['name']
        if match_name is None:
            await ctx.send('That request is no longer open.')
            return CommandResult.fail('No such request.', error='not_open')
        if match_name.lower() == staffer.name.lower():
            await ctx.send("You can't accept your own request.")
            return CommandResult.fail('Own request.', error='own_request')

        if from_queue is not None:
            description = from_queue['question']
            help_queue.remove(match_name)
        else:
            description = pending.pop(match_name)
        requester_client = _find_client_by_name(ctx.server, match_name)
        requester_ctx    = getattr(requester_client, 'ctx', None)
        if requester_ctx is None:
            await ctx.send(f'{match_name} is no longer connected.')
            return CommandResult.fail('Requester gone.', error='requester_gone')

        result = await self._summon(ctx, requester_ctx, description)
        if not result.success:
            # Teleport was blocked (e.g. a tough monster's Freeze
            # Adventurer spell) -- put the request back so someone else,
            # or this staffer once free, can still take it.
            if from_queue is not None:
                help_queue.add(match_name, description, from_queue.get('location', ''))
            else:
                pending[match_name] = description
            await ctx.send(f"{match_name}'s request is still open.")
            return result

        for client in _available_staffers(ctx):
            if client is ctx.client:
                continue
            other_ctx = getattr(client, 'ctx', None)
            if other_ctx:
                await other_ctx.send(
                    f"{match_name}'s request has been claimed by {staffer.name}."
                )
        return CommandResult.ok('Accepted.')

    async def _decline(self, ctx: GameContext, target_name: str) -> CommandResult:
        denied = await self._require_staffer(ctx)
        if denied:
            return denied
        match_name = _match_request(_pending(ctx.server), target_name)
        if match_name is None:
            await ctx.send('That request is no longer open.')
            return CommandResult.fail('No such request.', error='not_open')
        await ctx.send(f"Passed on {match_name}'s request.")
        return CommandResult.ok('Declined.')

    async def _summon(self, ctx: GameContext, requester_ctx: GameContext,
                       description: str) -> CommandResult:
        """Move the *accepting staffer's* session (ctx) to the requester.

        A requester inside a virtual location (bar, shoppe, reading mail,
        etc. -- presence.py's enter_area()) still has a real room under
        it in client.room, so the staffer lands just outside."""
        from commands.teleport import TeleportCommand

        staffer   = ctx.player
        requester = requester_ctx.player

        dest_level = int(getattr(requester, 'map_level', 1) or 1)
        dest_room  = getattr(requester_ctx.client, 'room', None) or requester.map_room

        await ctx.send(f'Heading to {requester.name} ({description}).')

        here_level = int(getattr(staffer, 'map_level', 1) or 1)
        here_room  = getattr(ctx.client, 'room', None) or staffer.map_room
        if (here_level, here_room) == (dest_level, dest_room):
            await requester_ctx.send(f'{staffer.name} is here to help you.')
            await ctx.send(f"You're already with {requester.name}.")
            return CommandResult.ok()

        result = await TeleportCommand()._teleport(ctx, dest_room, level=dest_level)
        if result is not None and not getattr(result, 'success', True):
            if result.message:
                await ctx.send(result.message)
            return result

        await requester_ctx.send(f'{staffer.name} has arrived to help you.')
        return CommandResult.ok()

    # -- saved questions and answers ----------------------------------------

    async def _queue(self, ctx: GameContext) -> CommandResult:
        denied = await self._require_staff(ctx)
        if denied:
            return denied
        from helpstaff.review import review_queue
        handled = await review_queue(ctx)
        return CommandResult.ok(f'Reviewed ({handled} handled).')

    async def _faq(self, ctx: GameContext, more_switches: list, target: str) -> CommandResult:
        denied = await self._require_staff(ctx)
        if denied:
            return denied
        action = more_switches[0] if more_switches else ''
        number = int(target) if target.isdigit() else None

        if action == '#add':
            return await self._faq_add(ctx)
        if action in ('#edit', '#delete'):
            if number is None or faq.get(number) is None:
                await ctx.send(f'Usage: |command|helpstaff #faq {action} <n>|reset| '
                               f'-- see |command|helpstaff #faq|reset| for the numbers.')
                return CommandResult.fail('No such answer.', error='not_found')
            if action == '#edit':
                return await self._faq_edit(ctx, number)
            return await self._faq_delete(ctx, number)
        if action:
            await ctx.send(f"Unknown option '{action}'. "
                           f"See |command|help helpstaff|reset|.")
            return CommandResult.fail('Unknown option.', error='bad_option')

        if number is not None:
            entry = faq.get(number)
            if entry is None:
                await ctx.send('No saved answer with that number.')
                return CommandResult.fail('No such answer.', error='not_found')
            await ctx.send(f'|yellow|{number}. {entry["title"]}|reset|', *self._render(ctx, entry['body']))
            return CommandResult.ok('Shown.')

        from helpstaff.review import faq_title_lines
        await ctx.send('Saved answers:', *faq_title_lines(),
                       'Type |command|helpstaff #faq <n>|reset| to read one.')
        return CommandResult.ok('Listed.')

    @staticmethod
    def _render(ctx, body: list) -> list[str]:
        from formatting import deserialize_lines, render_lines
        width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
        return render_lines(deserialize_lines(body), ctx, width)

    async def _faq_add(self, ctx: GameContext) -> CommandResult:
        title = await ctx.prompt('Title?', preamble_lines=[
            'A short title for the new saved answer,',
            f'or {ctx.player.return_key} to cancel.'])
        if title is None or not title.strip():
            await ctx.send('Cancelled.')
            return CommandResult.ok('Cancelled.')
        from text_editor import run_editor
        body = await run_editor(ctx, activity_id='helpstaff_faq_add',
                                activity_label='writing a saved helpstaff answer')
        if not body:
            await ctx.send('Cancelled.')
            return CommandResult.ok('Cancelled.')
        number = faq.add(title.strip(), body)
        await ctx.send(f'Saved answer {number} added.')
        return CommandResult.ok('Added.')

    async def _faq_edit(self, ctx: GameContext, number: int) -> CommandResult:
        entry = faq.get(number)
        title = await ctx.prompt('New title?', preamble_lines=[
            f'Current title: {entry["title"]}',
            f'Type a new one, or {ctx.player.return_key} to keep it.'])
        if title is None:
            return CommandResult.ok('Cancelled.')
        from formatting import deserialize_lines
        from text_editor import run_editor
        body = await run_editor(ctx, initial_lines=deserialize_lines(entry['body']),
                                activity_id=f'helpstaff_faq_edit:{number}',
                                activity_label=f'editing saved helpstaff answer {number}')
        if body is None:
            await ctx.send('Edit cancelled.')
            return CommandResult.ok('Cancelled.')
        faq.update(number, title=title.strip() or None, body=body or entry['body'])
        await ctx.send(f'Saved answer {number} updated.')
        return CommandResult.ok('Updated.')

    async def _faq_delete(self, ctx: GameContext, number: int) -> CommandResult:
        entry = faq.get(number)
        answer = await ctx.prompt('Delete it? [Y/N]', preamble_lines=[
            f'Saved answer {number}: {entry["title"]}'])
        if not answer or not answer.strip().lower().startswith('y'):
            await ctx.send('Kept.')
            return CommandResult.ok('Kept.')
        faq.delete(number)
        await ctx.send(f'Saved answer {number} deleted.')
        return CommandResult.ok('Deleted.')
