"""commands/lurk.py — LURK: fire over your allies' shoulders in combat
(SPUR.MAIN.S:87, SPUR.COMBAT.S:82-96 -- 'LURK' jumps to the same p.attack
routine as 'ATT'). See combat/lurk.py for the mechanic itself.
"""
from combat import lurk
from commands.attack import _active_session, _monster_in_room
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class LurkCommand(Command):
    name    = 'lurk'
    modes   = {Mode.GAME}
    counts_as_move = True

    help = Help(
        summary  = "Fire over your allies' shoulders instead of attacking directly.",
        category = HelpCategory.COMBAT,
        usage    = [
            ('lurk',          'Lurk behind your allies against the monster here.'),
            ('lurk <name>',   'Lurk if name matches the monster here.'),
        ],
        examples = [
            ('lurk',        'Swing this round from behind your allies.'),
            ('lurk goblin', 'Lurk against the goblin (must be in this room).'),
        ],
        description = (
            'Requires at least one living ally in your party. Costs Honor. '
            'A loaded ranged or energy weapon still fires, at a to-hit and '
            'damage penalty; any other weapon (melee, an empty ammo weapon, '
            'or a LIGHT-named weapon) skips your own swing entirely so only '
            "your allies attack. While lurking, the monster's counter-attack "
            'is redirected off you and onto one of your allies instead.'
        ),
        notes = [
            'Same command dispatch as "attack" -- opens or continues a '
            'fight in this room, or gives you one swing if you join one '
            'already in progress.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player

        if int(getattr(player, 'hit_points', 1) or 1) <= 0:
            await ctx.send("You're dead. You can't fight in this condition.")
            return CommandResult.fail(error='player_dead')

        if not lurk.has_living_ally(player):
            await ctx.send('No allies — no LURK!')
            return CommandResult.fail(error='no_allies')

        from monsters import monster_display_name

        session = _active_session(ctx)
        if session:
            mname = session.monster.get('name', 'the monster')
            if args:
                pattern = ' '.join(args).lower()
                if pattern not in mname.lower():
                    await ctx.send(f'There is no "{" ".join(args)}" here — only '
                                    f'{monster_display_name(session.monster)}.')
                    return CommandResult.fail(error='no_match')
            await session.join(ctx, is_lurking=True)
            return CommandResult.ok()

        monster = _monster_in_room(ctx)
        if monster is None:
            await ctx.send("There's nothing to fight here.")
            return CommandResult.fail(error='no_monster')

        mname = monster.get('name', 'monster')

        if args:
            pattern = ' '.join(args).lower()
            if pattern not in mname.lower():
                await ctx.send(f'There is no "{" ".join(args)}" here — only '
                                f'{monster_display_name(monster)}.')
                return CommandResult.fail(error='no_match')

        # Opening a fight this way still goes through the normal per-round
        # menu (which offers [L]urk each round) -- this just gets you into
        # combat and matches SPUR's LURK being typeable at the top-level
        # command prompt.
        from combat import enter_combat
        await enter_combat(ctx, monster)
        return CommandResult.ok()
