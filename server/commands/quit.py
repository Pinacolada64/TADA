"""commands/quit.py — Quit the game and disconnect."""
import random

from base_classes import PlayerStat, PlayerMoneyTypes
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory


# SPUR stat caps for the on-quit restoration (+2 each if below cap)
_STAT_RESTORE = {
    PlayerStat.STR: 7,   # pw
    PlayerStat.INT: 7,   # pi
    PlayerStat.CON: 10,  # ps
    PlayerStat.EGY: 10,  # pe
}
_HP_RESTORE_CAP = 20


class QuitCommand(Command):
    name    = 'quit'
    aliases = ['q', 'exit', 'bye']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Quit the game and disconnect.',
        category = HelpCategory.GENERAL,
        usage    = [('quit', 'Save your character and disconnect.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        player = ctx.player

        # Confirmation prompt
        raw = await ctx.prompt('Leave SPUR [Y/N]?', preamble_lines=['Y: Yes', "N: No"])
        if raw is None or raw.strip().upper() != 'Y':
            await ctx.send('(Returning to the game.)')
            return CommandResult.ok()

        # Award bonus silver for experience earned this session
        # TODO: track session experience separately (ep); for now use total experience
        exp = getattr(player, 'experience', 0)
        if exp > 0:
            bonus = random.randint(0, exp) // 3
            if bonus > 0:
                await ctx.send(f'SPUR awards you {bonus:,} silver for your experience.')
                # TODO: call player.adjust_silver_relative() once that method exists
                current = player.get_silver(PlayerMoneyTypes.IN_HAND)
                player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, current + bonus)
                player.unsaved_changes = True

        # Party member farewells
        # TODO: map party member positions to d1$/d2$/d3$ slots as in original SPUR
        party = getattr(player, 'party', None)
        if party:
            members = list(party)
            if len(members) >= 1:
                await ctx.send(f"'I WILL WATCH FOR YOUR RETURN!' shouts {members[0].name}")
            if len(members) >= 2:
                await ctx.send(f"'YEAH? AND WHO WILL WATCH YOU?' snickers {members[1].name}")
            if len(members) >= 3:
                await ctx.send(f"{members[2].name} looks sad as you leave..")

        # Stat restoration (+2 each if below cap) — original SPUR: only if not in combat (cr=0)
        # TODO: check combat state (cr flag) once combat is wired up
        for stat, cap in _STAT_RESTORE.items():
            current_val = player.stats.get(stat, 0)
            if current_val < cap:
                player.stats[stat] = min(current_val + 2, cap)
                player.unsaved_changes = True
        if player.hit_points < _HP_RESTORE_CAP:
            player.hit_points = min(player.hit_points + 2, _HP_RESTORE_CAP)
            player.unsaved_changes = True

        # Save message — shown before _player_quit() writes to disk
        await ctx.send(
            "SPUR says hold whilst your adventure "
            "is written in the BOOK of SPUR...."
        )

        # Broadcast to room before disconnecting
        await ctx.send_room(f'{player.name} falls asleep.', exclude_self=True)

        await ctx.send('It is written!')

        return CommandResult(success=True, data={'quit': True})
