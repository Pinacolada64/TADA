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
        summary  = "Unready your (or an ally's) readied weapon.",
        category = HelpCategory.GENERAL,
        usage    = [
            ('unready',        'Repack your readied weapon.'),
            ('unready <ally>', 'Have a party ally repack their readied weapon.'),
        ],
        examples = [('unready', "UNREADY (also 'unwield') with no argument repacks "
                                 "whatever weapon you currently have readied, leaving "
                                 "you unarmed. Fails harmlessly with \"No weapon "
                                 "readied!\" if you weren't wielding anything. Name a "
                                 "party ally (\"unready alan\") to have them repack "
                                 "theirs instead -- the same toggle READY offers.")],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        args, _switches = self.parse_args(*args)

        # "unready <ally>" -- repack a party ally's readied weapon, the
        # mirror of READY's ally-weapon toggle (commands/ready.py). Allies
        # no longer auto-ready GIVEn weapons, so the player drives both
        # ends of it.
        if args:
            target = ' '.join(args).lower()
            try:
                from bar.ally_data import Ally, AllyStatus
            except ImportError:
                Ally = None
            party = getattr(player, 'party', None)
            members = (getattr(party, 'members', None) or []) if party else []
            for m in members:
                if Ally is not None and not isinstance(m, Ally):
                    continue
                if getattr(m, 'status', None) == getattr(AllyStatus, 'DEAD', None):
                    continue
                if target not in getattr(m, 'name', '').lower():
                    continue
                a_weapon = getattr(m, 'readied_weapon', None)
                if a_weapon is None:
                    await ctx.send(f'{m.name} has no weapon readied.')
                    return CommandResult.ok()
                aname = getattr(a_weapon, 'name', '?')
                m.readied_weapon = None
                m.ammo_rounds = m.ammo_max = m.ammo_damage = 0
                player.unsaved_changes = True
                pself = getattr(player, 'name', 'Someone')
                await ctx.send(f'{m.name} repacks the {aname}.')
                await ctx.send_room(f'{pself} has {m.name} repack the {aname}.',
                                    exclude_self=True)
                return CommandResult.ok()
            await ctx.send(f'No party ally matching "{" ".join(args)}".')
            return CommandResult.ok()

        weapon = getattr(player, 'readied_weapon', None)

        if weapon is None:
            await ctx.send('No weapon readied!')
            return CommandResult.ok()

        name = getattr(weapon, 'name', '?')
        player.readied_weapon = None
        player.storm_servant_bonus = None
        player.skill_potion_bonus = None
        player.unsaved_changes = True
        await ctx.send(f'You repack the {name}.')
        return CommandResult.ok()
