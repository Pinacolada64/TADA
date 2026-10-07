"""logon_events/helpstaff.py — login check-in for helpstaff members.

Being on duty is per-connection (helpstaff/duty.py), so every login starts
off duty. For a player with the saved PlayerFlags.HELPSTAFF membership
flag, this:

  a) says how many live requests and saved questions are waiting, and
     asks whether to go on duty
  b) if questions are saved in the queue (asked while nobody was on
     duty), offers to review them now -- helpstaff/review.py, the same
     flow as 'helpstaff #queue'

Return answers "no" to both, so a member who just wants to play isn't
held up. Admins and Dungeon Masters who aren't members aren't asked; they
can still type 'helpstaff #on'. Called from commands/connect.py right
after the login summary, like the other logon_events modules.
"""
from __future__ import annotations

from helpstaff import duty
from helpstaff import queue as help_queue


def _yes(answer: str | None) -> bool:
    return bool(answer) and answer.strip().lower().startswith('y')


def _plural(n: int, word: str) -> str:
    return f'{n} {word}{"" if n == 1 else "s"}'


async def helpstaff_checkin(ctx, player) -> None:
    if not duty.is_member(player):
        return
    from network_context import GuestPlayer
    if isinstance(player, GuestPlayer):
        return

    live = len(getattr(ctx.server, 'pending_help_requests', None) or {})
    saved = help_queue.count()
    others = [getattr(getattr(c, 'ctx', None), 'player', None)
              for c in duty.on_duty_clients(ctx.server) if c is not ctx.client]
    others = [p.name for p in others if p is not None]

    preamble = ['|yellow|Helpstaff|reset|']
    preamble.append(f"On duty now: {', '.join(sorted(others, key=str.lower))}"
                    if others else 'No one else is on duty.')
    if live:
        preamble.append(f'{_plural(live, "player")} waiting for help right now.')
    if saved:
        preamble.append(f'{_plural(saved, "saved question")} waiting for a mailed answer.')
    preamble.append(f'Y to go on duty; N or {player.return_key} to stay off.')

    answer = await ctx.prompt('Go on helpstaff duty? [Y/N]', preamble_lines=preamble)
    if answer is None:
        return
    if _yes(answer):
        duty.set_on_duty(ctx.client, True)
        await ctx.send('You are now on helpstaff duty. '
                       'Type |command|helpstaff #off|reset| to stop.')
        if live:
            await ctx.send('Type |command|helpstaff #list|reset| to see who needs help.')
    else:
        await ctx.send('Staying off duty. Type |command|helpstaff #on|reset| any time.')

    if not saved:
        return
    answer = await ctx.prompt('Review saved questions? [Y/N]', preamble_lines=[
        f'{_plural(saved, "saved question")} waiting. Y to answer now by mail;',
        f'N or {player.return_key} to leave them (|command|helpstaff #queue|reset| later).'])
    if _yes(answer):
        from helpstaff.review import review_queue
        await review_queue(ctx)
