"""commands/attack.py — Attack the monster in the current room."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


def _monster_in_room(ctx: GameContext) -> dict | None:
    """Return the monster dict for the player's current room, or None."""
    game_map = getattr(ctx.server, 'game_map', None)
    monsters = getattr(ctx.server, 'monsters', [])
    if not game_map or not monsters:
        return None

    room_no = getattr(ctx.client, 'room', None)
    if room_no is None:
        return None

    room = game_map.rooms.get(int(room_no))
    if not room:
        return None

    mon_idx = int(getattr(room, 'monster', 0) or 0) - 1   # 1-based → 0-based
    if 0 <= mon_idx < len(monsters):
        return monsters[mon_idx]
    return None


def _active_session(ctx: GameContext):
    """Return an active CombatSession in this room, or None."""
    room_no = getattr(ctx.client, 'room', None)
    active  = getattr(ctx.server, 'active_combats', {})
    session = active.get(room_no)
    if session and not session._done.is_set():
        return session
    return None


class AttackCommand(Command):
    name    = 'attack'
    aliases = ['kill', 'fight', 'k']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Attack the monster in your current room.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('attack',          'Attack the monster here.'),
            ('attack <name>',   'Attack if name matches the monster here.'),
        ],
        examples = [
            ('attack',         'Begin or join a fight.'),
            ('attack goblin',  'Attack the goblin (must be in this room).'),
            ('k',              'Shortcut: same as attack.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player

        # Don't allow combat if the player is already dead
        if int(getattr(player, 'hit_points', 1) or 1) <= 0:
            await ctx.send("You're dead. You can't fight in this condition.")
            return CommandResult.fail(error='player_dead')

        # Join an existing fight if one is running
        session = _active_session(ctx)
        if session:
            if ctx in session.attackers:
                await ctx.send("You're already in this fight!")
                return CommandResult.ok()
            mname = session.monster.get('name', 'the monster')
            if args:
                pattern = ' '.join(args).lower()
                if pattern not in mname.lower():
                    await ctx.send(f'There is no "{" ".join(args)}" here — only the {mname}.')
                    return CommandResult.fail(error='no_match')
            await session.join(ctx)
            return CommandResult.ok()

        # Find the monster in this room
        monster = _monster_in_room(ctx)
        if monster is None:
            await ctx.send("There's nothing to fight here.")
            return CommandResult.fail(error='no_monster')

        mname = monster.get('name', 'monster')

        # Name filter: if player typed 'attack goblin' make sure it matches
        if args:
            pattern = ' '.join(args).lower()
            if pattern not in mname.lower():
                await ctx.send(f'There is no "{" ".join(args)}" here — only the {mname}.')
                return CommandResult.fail(error='no_match')

        # Warn if no weapon readied, but allow bare-hands combat
        weapon = getattr(player, 'readied_weapon', None)
        if weapon is None:
            await ctx.send('(Fighting unarmed!  Use "ready" to equip a weapon.)')

        from combat import enter_combat
        await enter_combat(ctx, monster)
        return CommandResult.ok()
