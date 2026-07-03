"""commands/lasso.py — Attempt to capture a horse-type monster as a mount.

Ported from the skip branch's SPUR.USE.S "lasso" subroutine.  Only works
against a monster whose name contains "HORSE"; requires an open party slot
and no existing mount ally.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class LassoCommand(Command):
    name    = 'lasso'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Try to capture a wild horse as a mount during combat.',
        category = HelpCategory.COMBAT,
        usage    = [('lasso', 'Attempt to lasso the monster you are fighting.')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        room_no = getattr(ctx.client, 'room', None)
        active  = getattr(ctx.server, 'active_combats', {})
        session = active.get(room_no)

        if not session or session._done.is_set():
            await ctx.send("You're not in a fight.")
            return CommandResult.fail(error='no_combat')

        if ctx not in session.attackers:
            await ctx.send("You're not fighting anything.")
            return CommandResult.fail(error='not_participant')

        captured = await session.lasso(ctx)
        return CommandResult.ok() if captured else CommandResult.fail(error='not_captured')
