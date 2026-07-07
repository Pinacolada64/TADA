"""commands/unready.py — Unready (unequip) the currently readied weapon.

SPUR.MAIN.S:84-85 (master) / :90-91 (skip, identical logic, all-caps text):
    if i$="UNREADY" and wr$="" print \\"No weapon readied!":goto advent2
    if i$="UNREADY" print \\"You repack the "wr$:wr$="":goto advent2

No confirmation, no STORM special-casing (STORM only refuses being
*replaced* by another weapon -- see commands/ready.py -- not being
unreadied outright).
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class UnreadyCommand(Command):
    name    = 'unready'
    aliases = ['unwield']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Unready your currently readied weapon.',
        category = HelpCategory.GENERAL,
        usage    = [('unready', 'Repack your readied weapon.')],
        examples = [('unready', 'Stop wielding your current weapon.')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        weapon = getattr(player, 'readied_weapon', None)

        if weapon is None:
            await ctx.send('No weapon readied!')
            return CommandResult.ok()

        name = getattr(weapon, 'name', '?')
        player.readied_weapon = None
        player.storm_servant_bonus = None
        player.unsaved_changes = True
        await ctx.send(f'You repack the {name}.')
        return CommandResult.ok()
