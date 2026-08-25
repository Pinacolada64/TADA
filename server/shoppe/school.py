"""shoppe/school.py — Formal Shield Training (SPUR.MISC2.S `school.3` port).

Only the shield-training purchase is ported here -- the original SCHOOL
command's other two options (read manuals, change class for 3000 gold)
are separate, unrelated features. "Read manuals" already exists elsewhere
(the Annex, see annex/main.py); class re-training is still an unported
loose end (quests/README.md).

Odin the Shield Master is never named in the SPUR source itself -- he's
only in the recovered flavor text (messages.json #13), printed via
SPUR's `a=13:gosub messages` once training is bought. The mechanic
itself is a flat gold purchase gated on race+class, not a quest: no
dialogue tree, no room, no prerequisite.
"""
import logging

from network_context import GameContext

log = logging.getLogger(__name__)

# SPUR.MISC2.S:451-454 -- cost by class (pc) and race (pr), summed then
# multiplied by 3/2. Original storage was two comma-joined digit strings
# indexed by pc*4-3 / pr*4-3; kept here as plain dicts instead.
_CLASS_COST = {
    'Wizard':   900,
    'Druid':    750,
    'Fighter':  350,
    'Paladin':  300,
    'Ranger':   600,
    'Thief':    650,
    'Archer':   800,
    'Assassin': 750,
    'Knight':   200,
}

_RACE_COST = {
    'Human':    500,
    'Ogre':     700,
    'Pixie':    400,
    'Elf':      600,
    'Hobbit':   500,
    'Gnome':    500,
    'Dwarf':    600,
    'Orc':      600,
    'Half-Elf': 550,
}


def _training_cost(char_class, char_race) -> int:
    class_cost = _CLASS_COST.get(getattr(char_class, 'value', char_class), 0)
    race_cost  = _RACE_COST.get(getattr(char_race, 'value', char_race), 0)
    return (class_cost + race_cost) * 3 // 2


async def main(ctx: GameContext) -> None:
    """Buy formal shield training: a permanent shield-combat bonus.
    (SPUR.MISC2.S school.3)
    """
    from base_classes import PlayerMoneyTypes
    from flags import PlayerFlags
    from messages import send_message

    player = ctx.player

    if player.query_flag(PlayerFlags.SHIELD_TRAINED):
        await ctx.send("Ye already has shield training.")
        return

    cost = _training_cost(player.char_class, player.char_race)
    await ctx.send([
        '',
        'A jolly huge Paladin looks you over. "So ye wants schoolin\' with your shield, eh?"',
        f'Cost for your Race/Class combo: {cost} gold',
        '',
    ])

    in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    if in_hand < cost:
        await ctx.send('Ye do not have enough gold.')
        return

    raw = await ctx.prompt('Do ye wish shield training? Y/N')
    if raw is None or raw.strip().upper() != 'Y':
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
    player.set_flag(PlayerFlags.SHIELD_TRAINED)
    player.unsaved_changes = True

    await send_message(ctx, 13)
