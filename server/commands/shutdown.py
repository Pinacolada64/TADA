"""commands/shutdown.py — Admin-only SHUTDOWN command: schedule (or
cancel) a graceful server shutdown, similar to Unix's `shutdown`.

Syntax:
  shutdown #time <minutes>   schedule shutdown in <minutes> minutes
  shutdown #time now         shutdown immediately
  shutdown #cancel           cancel a pending scheduled shutdown
  shutdown                   show current shutdown status

Broadcasts warnings to every connected player as the deadline
approaches (Unix shutdown's own habit of nagging repeatedly rather than
warning once and going silent), then raises SIGTERM against the
server's own process at T-0 -- reusing the exact SIGINT/SIGTERM
handling simple_server.py's __main__ already has wired up
(Server.graceful_shutdown(): notify + save each connected player, then
exit) instead of duplicating that logic here.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import signal

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags

log = logging.getLogger(__name__)

# Broadcast a countdown warning at each of these remaining-minute
# checkpoints -- only the ones actually less than the scheduled total
# fire for a given run. Descending order matters (see _countdown()).
_WARNING_CHECKPOINTS = (60, 30, 15, 10, 5, 2, 1)


def _fmt_minutes(minutes: float) -> str:
    if minutes == int(minutes):
        minutes = int(minutes)
    if minutes < 1:
        seconds = round(minutes * 60)
        return f'{seconds} second{"s" if seconds != 1 else ""}'
    return f'{minutes} minute{"s" if minutes != 1 else ""}'


class ShutdownCommand(Command):
    name    = 'shutdown'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Schedule or cancel a graceful server shutdown. (Admin only)',
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('shutdown #time <minutes>', 'Schedule a shutdown in <minutes> minutes.'),
            ('shutdown #time now',       'Shut the server down immediately.'),
            ('shutdown #cancel',         'Cancel a pending scheduled shutdown.'),
            ('shutdown',                 'Show the current shutdown status.'),
        ],
        examples = [
            ('shutdown #time 30',  'Shut down in 30 minutes, warning everyone along the way.'),
            ('shutdown #time now', 'Shut down right now.'),
            ('shutdown #cancel',   'Call off a scheduled shutdown.'),
        ],
        notes = [
            'Every connected player is notified and saved before the '
            'process actually exits (see simple_server.py\'s '
            'Server.graceful_shutdown()).',
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        positional, switches = self.parse_args(*args)
        server = ctx.server

        if '#cancel' in switches:
            return await self._cancel(ctx, server)

        if '#time' in switches:
            if not positional:
                await ctx.send('Usage: shutdown #time <minutes|now>')
                return CommandResult.fail('Missing time.', error='missing_args')
            return await self._schedule(ctx, server, positional[0])

        return await self._status(ctx, server)

    # ------------------------------------------------------------------

    async def _cancel(self, ctx, server) -> CommandResult:
        task = getattr(server, '_shutdown_task', None)
        if task is None or task.done():
            await ctx.send('No shutdown is currently scheduled.')
            return CommandResult.ok('Nothing to cancel.')

        task.cancel()
        server._shutdown_task = None
        server._shutdown_at = None
        await self._broadcast(server, 'Scheduled shutdown has been cancelled.')
        return CommandResult.ok('Shutdown cancelled.')

    async def _schedule(self, ctx, server, raw_minutes: str) -> CommandResult:
        existing = getattr(server, '_shutdown_task', None)
        if existing is not None and not existing.done():
            await ctx.send('A shutdown is already scheduled. Use "shutdown #cancel" first.')
            return CommandResult.fail('Already scheduled.', error='already_scheduled')

        if raw_minutes.strip().lower() == 'now':
            minutes = 0.0
        else:
            try:
                minutes = float(raw_minutes)
            except ValueError:
                await ctx.send('Usage: shutdown #time <minutes|now>')
                return CommandResult.fail('Invalid time.', error='invalid_args')
            if minutes < 0:
                await ctx.send('Minutes must be 0 or more.')
                return CommandResult.fail('Invalid time.', error='invalid_args')

        server._shutdown_at   = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        server._shutdown_task = asyncio.create_task(self._countdown(server, minutes))

        if minutes == 0:
            await ctx.send('Shutting down now.')
        else:
            await ctx.send(f'Shutdown scheduled in {_fmt_minutes(minutes)}.')
        return CommandResult.ok('Shutdown scheduled.')

    async def _status(self, ctx, server) -> CommandResult:
        shutdown_at = getattr(server, '_shutdown_at', None)
        task        = getattr(server, '_shutdown_task', None)
        if not shutdown_at or task is None or task.done():
            await ctx.send('No shutdown is currently scheduled.')
        else:
            remaining = shutdown_at - datetime.datetime.now()
            mins      = max(0.0, remaining.total_seconds() / 60)
            await ctx.send(f'Shutdown scheduled in {_fmt_minutes(mins)} '
                           f'(at {shutdown_at.strftime("%H:%M:%S")}).')
        return CommandResult.ok('Status shown.')

    # ------------------------------------------------------------------

    async def _countdown(self, server, minutes: float) -> None:
        """Sleep from *minutes* down to zero, broadcasting a warning at
        every checkpoint in _WARNING_CHECKPOINTS actually reached, then
        signal the process to shut down for real. Cancellable via
        `shutdown #cancel` (task.cancel()) at any point before T-0."""
        try:
            if minutes <= 0:
                await self._broadcast(server, 'Server going down for shutdown NOW.')
            else:
                await self._broadcast(
                    server, f'Server going down for shutdown in {_fmt_minutes(minutes)}.')

                schedule = [c for c in _WARNING_CHECKPOINTS if c < minutes] + [0]
                remaining = minutes
                for target in schedule:
                    sleep_for = (remaining - target) * 60
                    if sleep_for > 0:
                        await asyncio.sleep(sleep_for)
                    remaining = target
                    if target > 0:
                        await self._broadcast(
                            server, f'Server going down for shutdown in {_fmt_minutes(target)}.')
                    else:
                        await self._broadcast(server, 'Server going down for shutdown NOW.')

            # Reuse the exact SIGTERM handling already wired up in
            # simple_server.py's __main__ instead of duplicating it here.
            os.kill(os.getpid(), signal.SIGTERM)
        except asyncio.CancelledError:
            log.info('shutdown: scheduled shutdown cancelled before it fired')
            raise

    @staticmethod
    async def _broadcast(server, message: str) -> None:
        for addr, client in list(server.clients.items()):
            ctx = getattr(client, 'ctx', None)
            if not ctx:
                continue
            try:
                await ctx.send(f'*** {message} ***')
            except Exception:
                log.exception('shutdown broadcast: failed to notify a client')
