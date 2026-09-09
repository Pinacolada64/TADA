"""commands/unready.py — Unready (unequip) the currently readied weapon.

SPUR.MAIN.S:84-85 (master) / :90-91 (skip, identical logic, all-caps text):
    if i$="UNREADY" and wr$="" print \\"No weapon readied!":goto advent2
    if i$="UNREADY" print \\"You repack the "wr$:wr$="":goto advent2

No confirmation, no STORM special-casing (STORM only refuses being
*replaced* by another weapon -- see commands/ready.py -- not being
unreadied outright).

TADA extension: allies no longer auto-ready GIVEn weapons, so the player
drives both ends of it. Bare UNREADY offers a numbered menu of every
weapon readied in the party (the player's own plus each ally's) whenever
an ally has one wielded -- the mirror of bare READY's list. A solo
player with only their own weapon readied keeps SPUR's direct repack.
`unready <ally>` still targets that ally's weapon by name.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory_select import ItemChoice, party_allies, resolve_or_prompt
from network_context import GameContext


async def _repack_player(ctx, player, weapon) -> CommandResult:
    """Repack the player's own readied weapon (SPUR.MAIN.S:85)."""
    name = getattr(weapon, 'name', '?')
    player.readied_weapon = None
    player.storm_servant_bonus = None
    player.skill_potion_bonus = None
    player.unsaved_changes = True
    await ctx.send(f'You repack the {name}.')
    return CommandResult.ok()


async def _repack_ally(ctx, player, ally, weapon) -> CommandResult:
    """Repack *ally*'s readied weapon -- mirror of READY's ally toggle.
    Ammo counters reset, same as commands/ready.py's _toggle_ally_weapon."""
    name = getattr(weapon, 'name', '?')
    ally.readied_weapon = None
    ally.ammo_rounds = ally.ammo_max = ally.ammo_damage = 0
    player.unsaved_changes = True
    pself = getattr(player, 'name', 'Someone')
    await ctx.send(f'{ally.name} repacks the {name}.')
    await ctx.send_room(f'{pself} has {ally.name} repack the {name}.',
                        exclude_self=True)
    return CommandResult.ok()


class UnreadyCommand(Command):
    name    = 'unready'
    aliases = ['unwield']
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Unready your (or an ally's) readied weapon.",
        category = HelpCategory.GENERAL,
        usage    = [
            ('unready',        "Repack your readied weapon -- or pick from a list "
                                "when allies are also wielding something."),
            ('unready <ally>', 'Have a party ally repack their readied weapon.'),
        ],
        examples = [('unready', "UNREADY (also 'unwield') with no argument repacks "
                                 "whatever weapon you currently have readied, leaving "
                                 "you unarmed. Fails harmlessly with \"No weapon "
                                 "readied!\" if nobody in the party is wielding "
                                 "anything. When a party ally has a weapon readied "
                                 "too, UNREADY lists every readied weapon (yours and "
                                 "theirs) and lets you pick one -- the mirror of "
                                 "READY's list. Name a party ally (\"unready alan\") "
                                 "to repack theirs directly.")],
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
                AllyStatus = None
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
                return await _repack_ally(ctx, player, m, a_weapon)
            await ctx.send(f'No party ally matching "{" ".join(args)}".')
            return CommandResult.ok()

        # Bare UNREADY. Gather every readied weapon in the party.
        own = getattr(player, 'readied_weapon', None)
        ally_readied = [(a, w) for a in party_allies(player)
                        if (w := getattr(a, 'readied_weapon', None)) is not None]

        # No ally is wielding anything -- unchanged SPUR behaviour.
        if not ally_readied:
            if own is None:
                await ctx.send('No weapon readied!')
                return CommandResult.ok()
            return await _repack_player(ctx, player, own)

        # An ally has a weapon readied: offer the list (player's own first,
        # if any, then each ally's) via the shared numbered-pick helper.
        # A lone candidate needs no menu -- resolve_or_prompt() returns it
        # outright.
        choices = ([ItemChoice(item=own, owner=None, readied=True)]
                   if own is not None else [])
        choices += [ItemChoice(item=w, owner=a, readied=True)
                    for (a, w) in ally_readied]

        choice = await resolve_or_prompt(
            ctx, choices, args=[], prompt_text='Unready which',
            label_fn=lambda c: f'{c.owner_name}: {c.name}',
            list_header='Weapons readied:',
            auto_select_single=True,
        )
        if choice is None:
            return CommandResult.ok()
        if choice.is_ally:
            return await _repack_ally(ctx, player, choice.owner, choice.item)
        return await _repack_player(ctx, player, choice.item)
