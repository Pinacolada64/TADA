"""commands/helpstaff.py — Ask an available staffer for help.

Usage:  helpstaff                  ask what you need, relayed to every
                                    player currently marked available
                                    (PlayerFlags.HELPSTAFF_AVAILABLE)
        helpstaff accept <name>    (staffer) claim <name>'s request and
                                    teleport to them
        helpstaff decline <name>   (staffer) pass on <name>'s request,
                                    leaving it open for someone else

This is a request/relay/accept flow, not a direct summon-by-name: a plain
player describes what they need, every available staffer is notified, and
whichever one accepts first is moved to the requester (or to
commands.new_player.CREATION_ROOM if the requester is still mid character
creation, which has no real room of its own). Closes the two TODOs that
have sat at the top of commands/new_player.py since it was written --
"summoning help staff for assistance" and a new-player help channel.

Reachable in Mode.LOGIN as well as Mode.GAME (same as commands/who.py) so a
player stuck mid character-creation can still ask for a hand -- that's the
actual motivating case.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


def _available_staffers(ctx) -> list:
    """Connected clients whose player has PlayerFlags.HELPSTAFF_AVAILABLE set."""
    clients = getattr(ctx.server, 'clients', {})
    result = []
    for client in clients.values():
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        if player and player.query_flag(PlayerFlags.HELPSTAFF_AVAILABLE):
            result.append(client)
    return result


def _find_client_by_name(server, name: str):
    """Case-insensitive lookup of a connected client by player name."""
    for client in getattr(server, 'clients', {}).values():
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        if player and player.name.lower() == name.lower():
            return client
    return None


class HelpstaffCommand(Command):
    name    = 'helpstaff'
    aliases = []
    modes   = {Mode.GAME, Mode.LOGIN}

    help = Help(
        summary  = "See who's available to help, and ask for a hand.",
        description = (
            "Describes what you need help with, then relays that to "
            "every player currently marked available to help -- whoever "
            "accepts first comes to you. If no one is currently "
            "available, you'll be told so instead."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('helpstaff',               'Ask for help; describes what you need.'),
            ('helpstaff accept <name>', "(staffer) Claim <name>'s request and go help."),
            ('helpstaff decline <name>', "(staffer) Pass on <name>'s request."),
        ],
        see_also = ['help', 'who'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _switches = self.parse_args(*args)

        if positional and positional[0].lower() in ('accept', 'decline'):
            sub    = positional[0].lower()
            target = ' '.join(positional[1:]).strip()
            if not target:
                await ctx.send(f'Usage: helpstaff {sub} <name>')
                return CommandResult.fail('Missing name.', error='missing_name')
            if sub == 'accept':
                return await self._accept(ctx, target)
            return await self._decline(ctx, target)

        return await self._request(ctx)

    async def _request(self, ctx: GameContext) -> CommandResult:
        requester = ctx.player
        staffers  = _available_staffers(ctx)
        if not staffers:
            await ctx.send('No staff are currently available to help.')
            return CommandResult.ok('No staff available.')

        names = sorted(
            getattr(getattr(client, 'ctx', None), 'player', None).name
            for client in staffers
        )

        description = await ctx.prompt(
            'What do you need help with?',
            preamble_lines=[f"Available to help: {', '.join(names)}", ''],
        )
        if description is None or not description.strip():
            await ctx.send('Never mind.')
            return CommandResult.ok('Cancelled.')
        description = description.strip()

        ctx.server.pending_help_requests[requester.name] = description

        from commands.whereat import _location_columns
        _, _, location_label = _location_columns(ctx.client, ctx.server)

        for client in staffers:
            staffer_ctx = client.ctx
            await staffer_ctx.send(
                f'|yellow|{requester.name} needs help ({location_label}): '
                f'{description}|reset|',
                f"Type |white|'helpstaff accept {requester.name}'|reset| to go help, "
                f"or |white|'helpstaff decline {requester.name}'|reset| to pass.",
            )

        if len(names) == 1:
            await ctx.send(f'Your request has been sent to {names[0]}.')
        else:
            await ctx.send(f'Your request has been sent to {len(names)} helpstaffers.')
        return CommandResult.ok('Request sent.')

    async def _accept(self, ctx: GameContext, target_name: str) -> CommandResult:
        staffer = ctx.player
        if not staffer.query_flag(PlayerFlags.HELPSTAFF_AVAILABLE):
            await ctx.send('You are not marked as available to help.')
            return CommandResult.fail('Not available.', error='not_available')

        pending    = ctx.server.pending_help_requests
        match_name = next((n for n in pending if n.lower() == target_name.lower()), None)
        if match_name is None:
            await ctx.send('That request is no longer open.')
            return CommandResult.fail('No such request.', error='not_open')

        description      = pending.pop(match_name)
        requester_client = _find_client_by_name(ctx.server, match_name)
        requester_ctx     = getattr(requester_client, 'ctx', None)
        if requester_ctx is None:
            await ctx.send(f'{match_name} is no longer connected.')
            return CommandResult.fail('Requester gone.', error='requester_gone')

        for client in _available_staffers(ctx):
            if client is ctx.client:
                continue
            other_ctx = getattr(client, 'ctx', None)
            if other_ctx:
                await other_ctx.send(
                    f"{match_name}'s request has been claimed by {staffer.name}."
                )

        await self._summon(ctx, requester_ctx, description)
        return CommandResult.ok('Accepted.')

    async def _decline(self, ctx: GameContext, target_name: str) -> CommandResult:
        await ctx.send(f"Passed on {target_name}'s request.")
        return CommandResult.ok('Declined.')

    async def _summon(self, ctx: GameContext, requester_ctx: GameContext,
                       description: str) -> None:
        """Move the *accepting staffer's* session (ctx) to the requester."""
        from commands.new_player import CREATION_ROOM
        from commands.teleport import TeleportCommand

        staffer   = ctx.player
        requester = requester_ctx.player

        virtual_location = getattr(requester_ctx.client, 'virtual_location', None)
        if virtual_location:
            dest_level, dest_room = 1, CREATION_ROOM
        else:
            dest_level = int(getattr(requester, 'map_level', 1) or 1)
            dest_room  = getattr(requester_ctx.client, 'room', None) or requester.map_room

        await requester_ctx.send(f'{staffer.name} is on the way to help you.')
        await ctx.send(f'Heading to {requester.name} ({description}).')

        await TeleportCommand()._teleport(ctx, dest_room, level=dest_level)
