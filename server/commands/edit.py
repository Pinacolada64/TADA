"""commands/edit.py — The EDIT command: general-purpose text file editor,
plus a way back into whatever an emergency-shutdown recovery file caught.

Syntax:
  edit                — no filename: if a recovery file exists for you
                        (see text_editor.save_recovery_file(), written by
                        Server.graceful_shutdown() when a SHUTDOWN catches
                        you mid-edit), offers to resume it. Otherwise
                        opens a blank buffer.
  edit <filename>     — load (or create) a personal text file and edit it.
                        Storage is per-player (run/server/user_files/<you>/),
                        so filenames don't collide between players.

Resuming a recovery file hands the recovered text back into the editor,
then tries to actually finish what was interrupted -- the activity_id
stamped into the recovery file (see run_editor()'s activity_id/
activity_label params) carries enough of the original target/context
(who the mail was to, which board thread/news item, or the title for a
brand new post -- commands/news.py's/board.py's _post() fold the title,
and board's own anonymous choice, into activity_id precisely so this can
recover them too) to call straight back into that command's own delivery
method: MailCommand._deliver(), board_store.save_board(),
news_store.save_news(). See _RESUME_HANDLERS below. A recovered new post
lands with sane defaults for anything that genuinely can't survive a
crash (a fresh news post's admin-picked lifetime, since that's collected
even earlier than the title) -- 'permanent' until the admin narrows it
with 'news edit <id>'. Anything whose activity_id has no registered
handler falls back to a plain personal text file the player can review
and repost by hand.
"""
from __future__ import annotations

from typing import Callable, Optional

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from text_editor import (
    run_editor, find_recovery_file, load_recovery_file, delete_recovery_file,
    save_recovery_file, _sanitize_filename, _user_files_dir,
)
from formatting import deserialize_lines, render_lines


async def _resume_mail_compose(ctx, rest: str, body: list) -> Optional[str]:
    from commands.mail import MailCommand
    cmd = MailCommand()
    target_label = rest
    targets, problems = cmd._resolve_targets(ctx, target_label)
    for p in problems:
        await ctx.send(p)
    if not targets:
        return None
    await cmd._deliver(ctx, targets, body)
    return f"Mail sent to {', '.join(targets)}."


async def _resume_board_reply(ctx, rest: str, body: list) -> Optional[str]:
    import datetime
    import board as board_store
    if not rest.isdigit():
        return None
    threads = board_store.load_board()
    thread = next((t for t in threads if t.get('id') == int(rest)), None)
    if thread is None:
        return None
    reply = {
        'author':    ctx.player.name,
        'anonymous': False,  # the original anonymous choice wasn't recoverable
        'posted_at': datetime.datetime.now().isoformat(),
        'body':      body,
    }
    thread.setdefault('replies', []).append(reply)
    board_store.save_board(threads)
    return f"Reply posted to thread #{thread['id']}."


async def _resume_news_edit(ctx, rest: str, body: list) -> Optional[str]:
    import news as news_store
    if not rest.isdigit():
        return None
    items = news_store.load_news()
    item = next((it for it in items if it.get('id') == int(rest)), None)
    if item is None:
        return None
    item['body'] = body
    news_store.save_news(items)
    return f"News item #{item['id']} updated."


async def _resume_news_post(ctx, rest: str, body: list) -> Optional[str]:
    """rest is the title verbatim (no admin-picked lifetime survives a
    crash, since that's collected before the editor opens) -- posted as
    'permanent' by default; the admin can narrow it afterwards with
    'news edit <id>'."""
    import datetime
    import news as news_store
    if not rest:
        return None
    items = news_store.load_news()
    item = {
        'id':        news_store.next_id(items),
        'title':     rest,
        'body':      body,
        'author':    ctx.player.name,
        'posted_at': datetime.datetime.now().isoformat(),
        'lifetime':  'permanent',
        'seen_by':   [],
    }
    items.append(item)
    news_store.save_news(items)
    return (f"News item #{item['id']} posted (as \"permanent\" -- "
            f"use 'news edit {item['id']}' to change that).")


async def _resume_board_post(ctx, rest: str, body: list) -> Optional[str]:
    """rest is 'title\\x1fanonymous_flag' -- see commands/board.py's
    _post() for the other end of this encoding."""
    import datetime
    import board as board_store
    title, _, anon_flag = rest.partition('\x1f')
    if not title:
        return None
    threads = board_store.load_board()
    thread = {
        'id':        board_store.next_id(threads),
        'title':     title,
        'author':    ctx.player.name,
        'anonymous': anon_flag == '1',
        'posted_at': datetime.datetime.now().isoformat(),
        'body':      body,
        'replies':   [],
    }
    threads.append(thread)
    board_store.save_board(threads)
    return f"Thread #{thread['id']} posted."


# activity_id prefix (the part before ':', or the whole id for no-arg
# activities) -> handler(ctx, rest_after_colon, body) -> success message,
# or None to fall back to a plain personal text file. Only activities
# whose id carries enough context (target/thread/item/title) to finish
# the original action land here -- see the module docstring.
_RESUME_HANDLERS: dict[str, Callable] = {
    'mail_compose': _resume_mail_compose,
    'board_reply':  _resume_board_reply,
    'board_post':   _resume_board_post,
    'news_edit':    _resume_news_edit,
    'news_post':    _resume_news_post,
}


async def _dispatch_resume(ctx, activity_id: Optional[str], body: list) -> Optional[str]:
    if not activity_id:
        return None
    prefix, _, rest = activity_id.partition(':')
    handler = _RESUME_HANDLERS.get(prefix)
    if handler is None:
        return None
    return await handler(ctx, rest, body)


class EditCommand(Command):
    name    = 'edit'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Edit a personal text file, or resume unsaved work from a shutdown.',
        category = HelpCategory.MISCELLANEOUS,
        usage    = [
            ('edit',            'Resume a recovered session if one exists, else start blank.'),
            ('edit <filename>', 'Load/create your own text file and edit it.'),
        ],
        examples = [
            ('edit',          'Check for and resume anything recovered from a shutdown.'),
            ('edit notes.txt', 'Edit your own notes.txt.'),
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if args:
            return await self._edit_file(ctx, ' '.join(args).strip())
        return await self._edit_bare(ctx)

    # ------------------------------------------------------------------

    async def _edit_bare(self, ctx) -> CommandResult:
        player_name = ctx.player.name
        recovery_path = find_recovery_file(player_name)
        if recovery_path is None:
            body = await run_editor(ctx, activity_id='edit_scratch', activity_label='editing')
            if body is None:
                await ctx.send('Cancelled.')
                return CommandResult.ok('Cancelled.')
            await ctx.send('(Not saved anywhere permanent -- use "edit <filename>" to keep it.)')
            return CommandResult.ok('Edited scratch buffer.')

        return await self._resume_recovery(ctx, recovery_path)

    async def _resume_recovery(self, ctx, recovery_path) -> CommandResult:
        data = load_recovery_file(recovery_path)
        label = data.get('activity_label') or 'writing something'
        choice = await ctx.prompt(
            f'Before the server went down, you were {label}. Resume editing? y/n')
        if not (choice or '').strip().lower().startswith('y'):
            delete_recovery_file(recovery_path)
            await ctx.send('Recovery text discarded.')
            return CommandResult.ok('Discarded recovery file.')

        activity_id = data.get('internal_id')
        initial_lines = deserialize_lines(data.get('lines', []))
        body = await run_editor(ctx, initial_lines=initial_lines,
                                 activity_id=activity_id,
                                 activity_label=label)
        delete_recovery_file(recovery_path)
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.ok('Cancelled.')

        finished = await _dispatch_resume(ctx, activity_id, body)
        if finished is not None:
            await ctx.send(finished)
            return CommandResult.ok('Resumed and completed.')

        safe_name = _sanitize_filename(activity_id or 'recovered') + '.txt'
        path = _user_files_dir(ctx.player.name) / safe_name
        text = '\n'.join(render_lines(deserialize_lines(body), ctx, 76))
        path.write_text(text)
        await ctx.send(
            f'Saved to "{safe_name}" ("edit {safe_name}" to see it). '
            f'This was not automatically re-sent -- compose it fresh and paste it in.')
        return CommandResult.ok('Recovered text saved.')

    async def _edit_file(self, ctx, raw_name: str) -> CommandResult:
        if not raw_name:
            await ctx.send('Usage: edit <filename>')
            return CommandResult.fail('Missing filename.', error='missing_args')

        safe_name = _sanitize_filename(raw_name)
        directory = _user_files_dir(ctx.player.name)
        path = directory / safe_name

        initial_lines = None
        if path.is_file():
            initial_lines = path.read_text(errors='replace').splitlines()
            await ctx.send(f'Editing "{safe_name}" ({len(initial_lines)} line(s)).')
        else:
            await ctx.send(f'"{safe_name}" is new.')

        body = await run_editor(ctx, initial_lines=initial_lines,
                                 activity_id=f'edit_file:{safe_name}',
                                 activity_label=f'editing "{safe_name}"')
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.ok('Cancelled.')

        text = '\n'.join(render_lines(deserialize_lines(body), ctx, 76))
        path.write_text(text)
        await ctx.send(f'Saved "{safe_name}".')
        return CommandResult.ok('File saved.')
