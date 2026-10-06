"""commands/helpstaff.py — Ask an available staffer for help.

Usage:  helpstaff                  ask what you need, relayed to every
                                    player currently marked available
                                    (PlayerFlags.HELPSTAFF)
        helpstaff cancel           withdraw your own open request
        helpstaff list             (staffer) show every open request
        helpstaff accept <name>    (staffer) claim <name>'s request and
                                    teleport to them
        helpstaff decline <name>   (staffer) pass on <name>'s request,
                                    leaving it open for someone else
        helpstaff on|off           mark yourself available (Admin/DM
                                    only) or step off duty (anyone)

This is a request/relay/accept flow, not a direct summon-by-name: a plain
player describes what they need, every available staffer is notified, and
whichever one accepts first is moved to the requester's room. Closes the
"summoning help staff for assistance" TODO that had sat at the top of
commands/new_player.py since it was written.

Game mode only. The original snapshot was also reachable in Mode.LOGIN so
a player stuck mid character-creation could ask for a hand, but that path
can't actually be reached: creation runs entirely inside ctx.prompt()
calls, which never dispatch commands, and at the bare login prompt every
connection's placeholder player is the same "Generic Name" with no real
room to teleport to. Guests and freshly created characters are both in
Mode.GAME, so they're covered.

Open requests live in Server.pending_help_requests (requester name ->
description); simple_server.py drops a requester's entry when they
disconnect.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


def _player_of(client):
    return getattr(getattr(client, 'ctx', None), 'player', None)


def _available_staffers(ctx) -> list:
    """Connected clients whose player has PlayerFlags.HELPSTAFF set."""
    clients = getattr(ctx.server, 'clients', {})
    result = []
    for client in clients.values():
        player = _player_of(client)
        if player and player.query_flag(PlayerFlags.HELPSTAFF):
            result.append(client)
    return result


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


def _can_go_on_duty(player) -> bool:
    return (player.query_flag(PlayerFlags.ADMIN)
            or player.query_flag(PlayerFlags.DUNGEON_MASTER))


class HelpstaffCommand(Command):
    name    = 'helpstaff'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Ask whoever's on helpstaff duty for a hand.",
        description = (
            "Describes what you need help with, then relays that to "
            "every player currently marked available to help -- whoever "
            "accepts first comes to you. If no one is currently "
            "available, you'll be told so instead."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('helpstaff',                'Ask for help; describes what you need.'),
            ('helpstaff cancel',         'Withdraw your open request.'),
            ('helpstaff list',           '(staffer) Show every open request.'),
            ('helpstaff accept <name>',  "(staffer) Claim <name>'s request and go help."),
            ('helpstaff decline <name>', "(staffer) Pass on <name>'s request."),
            ('helpstaff on',             '(Admin/DM) Go on helpstaff duty.'),
            ('helpstaff off',            '(staffer) Go off helpstaff duty.'),
        ],
        notes = [
            'Asking again replaces your earlier request.',
        ],
        admin_notes = [
            'An admin can also mark any player as helpstaff from '
            '|command|editplayer|reset| (Flags/Counters, Player Status).',
        ],
        see_also = ['help', 'who'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _switches = self.parse_args(*args)
        sub = positional[0].lower() if positional else ''

        if sub in ('accept', 'decline'):
            target = ' '.join(positional[1:]).strip()
            if not target:
                await ctx.send(f'Usage: |command|helpstaff {sub} <name>|reset|')
                return CommandResult.fail('Missing name.', error='missing_name')
            if sub == 'accept':
                return await self._accept(ctx, target)
            return await self._decline(ctx, target)
        if sub == 'list':
            return await self._list(ctx)
        if sub == 'cancel':
            return await self._cancel(ctx)
        if sub in ('on', 'off'):
            return await self._duty(ctx, sub == 'on')
        if sub:
            await ctx.send(f"Unknown option '{sub}'. "
                           f"See |command|help helpstaff|reset|.")
            return CommandResult.fail('Unknown option.', error='bad_option')

        return await self._request(ctx)

    # -- requester side -----------------------------------------------------

    async def _request(self, ctx: GameContext) -> CommandResult:
        requester = ctx.player
        staffers  = [c for c in _available_staffers(ctx) if c is not ctx.client]
        if not staffers:
            await ctx.send('No staff are currently available to help.')
            return CommandResult.ok('No staff available.')

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
        # Asking again replaces the earlier request rather than stacking.
        old = _match_request(pending, requester.name)
        if old is not None:
            del pending[old]
        pending[requester.name] = description

        from commands.whereat import _location_columns
        _, _, location_label = _location_columns(ctx.client, ctx.server)

        for client in staffers:
            await client.ctx.send(
                f'|yellow|{requester.name} needs help ({location_label}): '
                f'{description}|reset|',
                f'Type |command|helpstaff accept {requester.name}|reset| to go help, '
                f'or |command|helpstaff decline {requester.name}|reset| to pass.',
            )

        if len(names) == 1:
            await ctx.send(f'Your request has been sent to {names[0]}.')
        else:
            await ctx.send(f'Your request has been sent to {len(names)} helpstaffers.')
        return CommandResult.ok('Request sent.')

    async def _cancel(self, ctx: GameContext) -> CommandResult:
        pending = _pending(ctx.server)
        match   = _match_request(pending, ctx.player.name)
        if match is None:
            await ctx.send("You don't have an open request.")
            return CommandResult.fail('No open request.', error='not_open')
        del pending[match]
        for client in _available_staffers(ctx):
            if client is not ctx.client:
                await client.ctx.send(f'{match} has withdrawn their request for help.')
        await ctx.send('Your request for help has been withdrawn.')
        return CommandResult.ok('Withdrawn.')

    # -- staffer side -------------------------------------------------------

    async def _require_staffer(self, ctx: GameContext) -> CommandResult | None:
        if ctx.player.query_flag(PlayerFlags.HELPSTAFF):
            return None
        await ctx.send('You are not marked as available to help.')
        return CommandResult.fail('Not available.', error='not_available')

    async def _duty(self, ctx: GameContext, on: bool) -> CommandResult:
        player = ctx.player
        if on:
            if not _can_go_on_duty(player):
                await ctx.send('Only Admins and Dungeon Masters can go on helpstaff duty.')
                return CommandResult.fail('Not permitted.', error='not_permitted')
            player.set_flag(PlayerFlags.HELPSTAFF)
            player.unsaved_changes = True
            count = len(_pending(ctx.server))
            await ctx.send('You are now on helpstaff duty.')
            if count:
                await ctx.send(f'{count} open request{"s" if count != 1 else ""} -- '
                               f'type |command|helpstaff list|reset| to see '
                               f'{"them" if count != 1 else "it"}.')
            return CommandResult.ok('On duty.')

        if not player.query_flag(PlayerFlags.HELPSTAFF):
            await ctx.send("You aren't on helpstaff duty.")
            return CommandResult.ok('Already off duty.')
        player.clear_flag(PlayerFlags.HELPSTAFF)
        player.unsaved_changes = True
        await ctx.send('You are now off helpstaff duty.')
        return CommandResult.ok('Off duty.')

    async def _list(self, ctx: GameContext) -> CommandResult:
        denied = await self._require_staffer(ctx)
        if denied:
            return denied
        pending = _pending(ctx.server)
        if not pending:
            await ctx.send('No open requests for help.')
            return CommandResult.ok('No requests.')

        from commands.whereat import _location_columns
        lines = ['Open requests for help:']
        for name, description in sorted(pending.items(), key=lambda kv: kv[0].lower()):
            client = _find_client_by_name(ctx.server, name)
            label = (_location_columns(client, ctx.server)[2]
                     if client is not None else 'disconnected')
            lines.append(f'  {name} ({label}): {description}')
        await ctx.send(*lines)
        return CommandResult.ok('Listed.')

    async def _accept(self, ctx: GameContext, target_name: str) -> CommandResult:
        denied = await self._require_staffer(ctx)
        if denied:
            return denied
        staffer = ctx.player

        pending    = _pending(ctx.server)
        match_name = _match_request(pending, target_name)
        if match_name is None:
            await ctx.send('That request is no longer open.')
            return CommandResult.fail('No such request.', error='not_open')
        if match_name.lower() == staffer.name.lower():
            await ctx.send("You can't accept your own request.")
            return CommandResult.fail('Own request.', error='own_request')

        description      = pending.pop(match_name)
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
