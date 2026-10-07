"""helpstaff/review.py — answering queued questions by mail.

review_queue() walks helpstaff/queue.py's entries oldest first, offering
for each one:

  [A]nswer  write a reply in the line editor (text_editor.run_editor())
  [F]AQ     mail one of helpstaff/faq.py's saved answers, with an
            optional one-line note in front of it
  [S]kip    leave it for later, or for another staffer
  [C]lose   remove it without replying (spam, a duplicate, solved live)

Answers are mailed from "<name>, Helpstaff member" (helpstaff/duty.py's
sender_name()), with reply_to set to the staffer's plain name so the
player's 'mail #reply' still reaches them. Used by 'helpstaff #queue' and
by logon_events/helpstaff.py's login check-in.
"""
from __future__ import annotations

import datetime

from helpstaff import duty, faq
from helpstaff import queue as help_queue


def _find_client_by_name(server, name: str):
    for client in getattr(server, 'clients', {}).values():
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        if player and player.name.lower() == name.lower():
            return client
    return None


def _when(entry: dict) -> str:
    try:
        dt = datetime.datetime.fromisoformat(entry.get('asked_at', ''))
    except (TypeError, ValueError):
        return 'some time ago'
    return dt.strftime('%b %d, %I:%M %p').replace(' 0', ' ')


def faq_title_lines() -> list[str]:
    entries = faq.load()
    if not entries:
        return ['No saved answers yet.']
    return [f'  {i:>2}. {e["title"]}' for i, e in enumerate(entries, 1)]


async def mail_answer(ctx, entry: dict, answer_lines: list) -> None:
    """Mail *answer_lines* to the player who asked *entry*, remove it from
    the queue, and tell the player now if they're online."""
    import mail

    staffer = ctx.player
    name = entry['name']
    body = [
        'You asked helpstaff:',
        f'  "{entry.get("question", "")}"',
        '',
        *answer_lines,
        '',
        f'-- {duty.sender_name(staffer)}',
    ]
    mail.add_message(name, duty.sender_name(staffer), body, reply_to=staffer.name)
    help_queue.remove(name)

    client = _find_client_by_name(ctx.server, name)
    if client is not None and getattr(client, 'ctx', None) is not None:
        await client.ctx.send(f'{staffer.name} answered your help request. '
                              f'Type |command|mail|reset| to read it.')
    await ctx.send(f'Answer mailed to {name}.')


def _option_lines(ctx) -> list[str]:
    """Borderless two-column option table, same convention as
    commands/board/reply.py's _menu_options_lines()."""
    from table import Table
    t = Table(headers=['', ''], show_header=False, border=False)
    t.add_row(['[A]nswer', 'write a reply (opens the editor)'])
    t.add_row(['[F]AQ', 'mail a saved answer'])
    t.add_row(['[S]kip', 'leave it for later'])
    t.add_row(['[C]lose', 'remove it without replying'])
    t.add_row([f'[{ctx.player.return_key}]', 'stop reviewing'])
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
    return t.render(width=width)


async def _answer_with_editor(ctx, entry: dict) -> bool:
    from text_editor import run_editor
    name = entry['name']
    await ctx.send(f'Write your answer to {name}. It will be mailed from '
                   f'"{duty.sender_name(ctx.player)}".')
    body = await run_editor(ctx, activity_id=f'helpstaff_answer:{name}',
                            activity_label=f'answering {name}')
    if not body:
        await ctx.send('Answer cancelled.')
        return False
    await mail_answer(ctx, entry, body)
    return True


async def _answer_with_faq(ctx, entry: dict) -> bool:
    if not faq.load():
        await ctx.send('There are no saved answers yet. '
                       'Add one with |command|helpstaff #faq #add|reset|.')
        return False
    raw = await ctx.prompt('Saved answer #?',
                           preamble_lines=['Saved answers:', *faq_title_lines(),
                                           f'({ctx.player.return_key} to go back)'])
    if raw is None or not raw.strip():
        return False
    if not raw.strip().isdigit() or faq.get(int(raw.strip())) is None:
        await ctx.send('No saved answer with that number.')
        return False
    answer = faq.get(int(raw.strip()))
    note = await ctx.prompt('Note?',
                            preamble_lines=['Type a line to put before the saved answer, '
                                            f'or {ctx.player.return_key} for none.'])
    if note is None:
        return False
    lines = ([note.strip(), ''] if note.strip() else []) + list(answer['body'])
    await mail_answer(ctx, entry, lines)
    return True


async def review_queue(ctx) -> int:
    """Walk the queue; returns how many questions were answered or closed."""
    entries = help_queue.load()
    if not entries:
        await ctx.send('No questions are waiting.')
        return 0

    handled = 0
    total = len(entries)
    for i, entry in enumerate(entries, 1):
        name = entry['name']
        while True:
            # Another staffer may have answered it since we loaded the queue.
            if help_queue.find(name) is None:
                break
            preamble = [
                f'Question {i} of {total}, from {name} '
                f'({entry.get("location") or "somewhere"}, {_when(entry)}):',
                f'  {entry.get("question", "")}',
                '',
            ]
            if not getattr(ctx.player, 'is_expert', False) or i == 1:
                preamble += _option_lines(ctx)
            choice = await ctx.prompt('[A]/[F]/[S]/[C]?', preamble_lines=preamble)
            if choice is None or not choice.strip():
                await ctx.send(f'Stopped. {help_queue.count()} question(s) still waiting.')
                return handled
            key = choice.strip().lower()[:1]
            if name.lower() == ctx.player.name.lower() and key in ('a', 'f'):
                await ctx.send("You can't answer your own question.")
                continue
            if key == 'a':
                if await _answer_with_editor(ctx, entry):
                    handled += 1
                    break
            elif key == 'f':
                if await _answer_with_faq(ctx, entry):
                    handled += 1
                    break
            elif key == 's':
                break
            elif key == 'c':
                help_queue.remove(name)
                await ctx.send(f"Closed {name}'s question without replying.")
                handled += 1
                break
            else:
                await ctx.send('Choose A, F, S or C.')

    remaining = help_queue.count()
    await ctx.send('That was the last question.' if not remaining
                   else f'{remaining} question(s) still waiting.')
    return handled
