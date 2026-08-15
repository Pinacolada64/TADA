"""commands/look.py

LookCommand — examine the current room or inspect a target.

Plain description only -- SPUR's original LOOK just redisplayed the
room and took no target at all (SPUR.MAIN.S:102). The roll-based
flavor-text/magic-cursed/"already examined" logic (SPUR.MISC3.S's
EXAMINE/X) lives in commands/examine.py now, split out so LOOK stays a
simple "show me around" command -- Ryan's request.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from tada_utilities import PronounType, get_pronoun, get_article_and_quantity

_SELF_TARGETS = {'me', 'self', 'myself'}


class LookCommand(Command):
    """Examine the current room or inspect a target."""

    name    = 'look'
    aliases = ['l']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Examine the current room, or inspect an object.',
        description = (
            'Without a target, describes your current location. '
            'With a target, gives a plain description of that object, '
            'creature, or player -- see EXAMINE for a closer look that '
            'might reveal something LOOK misses.'
        ),
        category = HelpCategory.INTERACTION,
        usage    = [
            ('look',          'Describe the current room.'),
            ('l',             'Shorthand for look.'),
            ('look <target>', 'Describe an object, creature, or player.'),
        ],
        examples = [
            ('look',       "LOOK re-describes wherever you currently are -- the same "
                            "room description you saw on arrival, useful after other "
                            "messages have scrolled it out of view."),
            ('look sword', "Naming a target gives a plain description of that object, "
                            "creature, or player instead of the room -- for anything "
                            "riskier (checking for a curse before picking it up), use "
                            "EXAMINE instead, which LOOK deliberately doesn't attempt."),
            ('look me',    "'me' (also 'self'/'myself') targets your own character, "
                            "showing how you currently appear to others."),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not positional:
            await ctx.server._show_room(ctx)
            await ctx.send_room(
                f'{ctx.player.name} looks around.',
                exclude_self=True,
            )
            return CommandResult.ok()

        target = ' '.join(positional).lower()

        if target in _SELF_TARGETS:
            name      = ctx.player.name
            reflexive = get_pronoun(ctx.player, PronounType.REFLEXIVE)
            await ctx.send(f'You examine yourself.')
            await ctx.send_room(f'{name} examines {reflexive}.', exclude_self=True)
            return CommandResult.ok()

        # Search the player's own party for a matching ally.
        from bar.allies import owned_allies
        for ally in owned_allies(ctx.player):
            if target in ally.name.lower():
                await self._describe_ally(ctx, ally)
                return CommandResult.ok()

        # A monster mid-fight in this room (checked first so a live
        # CombatSession's own per-fight copy -- e.g. after damage/flag
        # changes -- wins over the static room.monster template below).
        active_combats = getattr(ctx.server, 'active_combats', {}) or {}
        session = active_combats.get(getattr(ctx.client, 'room', None))
        if session is not None and not session._done.is_set():
            mname = (session.monster.get('name') or '').lower()
            if mname and target in mname:
                await self._describe_monster(ctx, session.monster)
                return CommandResult.ok()

        # The room's own monster -- shown by the "There is X here" line
        # (simple_server.py's _describe_room_parts()) as soon as the room
        # is entered, well before anyone ATTACKs it and starts a
        # CombatSession above. Ryan's request: LOOK should work on a
        # monster any time it's in the room, not just mid-fight -- a
        # killed-by-this-player monster still resolves here (room.monster
        # isn't cleared per-player, dead_monsters is the actual gate) and
        # _describe_monster() below reports it as dead rather than using
        # the alive-flavored description. Only skipped when the monster
        # has actually left the room (charmed and recruited into the
        # party -- see _room_monster()'s charmed_monsters check).
        monster = self._room_monster(ctx)
        if monster is not None:
            mname = (monster.get('name') or '').lower()
            if mname and target in mname:
                await self._describe_monster(ctx, monster)
                return CommandResult.ok()

        # Another player sharing the room -- mirrors EXAMINE's own player
        # lookup (commands/examine.py's _examine_player/_room_players) so
        # "look <player>" and "x <player>" report the same thing. Ryan's
        # request: LOOK didn't handle other players at all before this.
        from commands.examine import _examine_player, _room_players
        for other_ctx in _room_players(ctx, exclude=ctx):
            other_name = (getattr(other_ctx.player, 'name', '') or '').strip()
            if other_name and target in other_name.lower():
                await ctx.send(_examine_player(other_ctx))
                return CommandResult.ok()

        # Search inventory for a matching item.
        inv = getattr(ctx.player, 'inventory', None)
        if inv is not None:
            for entry in inv.entries():
                item = entry.item
                iname = (getattr(item, 'name', '') or '').strip()
                if target in iname.lower():
                    await self._describe_item(ctx, iname, item)
                    return CommandResult.ok()

        # Search items on the ground too.
        from commands.get import _room_available_items
        for name, entry, _remove_fn in _room_available_items(ctx):
            if target in name.lower():
                await self._describe_item(ctx, name, entry.item)
                return CommandResult.ok()

        await ctx.send(f"You don't see any '{target}' here.")
        return CommandResult.ok()

    async def _describe_item(self, ctx: GameContext, name: str, item) -> None:
        description = (getattr(item, 'description', '') or '').strip()
        await ctx.send(description or f'You see {get_article_and_quantity(name)} {name}.')

    async def _describe_ally(self, ctx: GameContext, ally) -> None:
        await describe_ally(ctx, ally)

    def _room_monster(self, ctx: GameContext) -> dict | None:
        """The static monster.json entry room.monster points at, or None
        if there isn't one or it's actually left the room (charmed and
        recruited into the party). Deliberately does NOT gate on
        dead_monsters -- a monster this player already killed should
        still resolve here so _describe_monster() can report it as dead,
        rather than LOOK falling through to "you don't see any"."""
        server = ctx.server
        game_map = getattr(server, 'game_map', None)
        if game_map is None:
            return None
        room_no = getattr(ctx.client, 'room', None)
        if not room_no:
            return None
        level = int(getattr(ctx.player, 'map_level', 1) or 1)
        room = game_map.get_room(level, int(room_no))
        if room is None:
            return None
        mon_number = int(getattr(room, 'monster', 0) or 0)
        if not mon_number:
            return None
        from monsters import get_monster
        monster = get_monster(getattr(server, 'monsters', []) or [], mon_number)
        if monster is None:
            return None
        # A charmed-and-recruited monster has actually left the room (it
        # joined the party as an ally, found via owned_allies() above) --
        # unlike a plain kill, LOOKing its old room slot should find
        # nothing there rather than a "dead" line. A merely *pending*
        # charm (charm_greeting_line) is still physically in the room, so
        # that case falls through to a normal describe below.
        charmed_monsters = getattr(ctx.player, 'charmed_monsters', []) or []
        if mon_number in charmed_monsters:
            return None
        return monster

    async def _describe_monster(self, ctx: GameContext, monster: dict) -> None:
        from monsters import monster_is_alive
        if not monster_is_alive(monster, ctx.player):
            # Most flavor text in monsters.json assumes the monster is
            # still up and fighting ("rears back", "snarls") -- Ryan's
            # request: a killed monster should say so instead, matching
            # simple_server.py's own room-description wording for a dead
            # monster (_describe_room_parts()'s dead_monsters branch).
            name = monster.get('name') or 'monster'
            if (monster.get('flags') or {}).get('mechanical'):
                await ctx.send(f'The wrecked remains of {name} lie here.')
            else:
                await ctx.send(f'You see a dead {name} here.')
            return
        description = (monster.get('description') or '').strip()
        if description:
            await ctx.send(description)
            return
        from monsters import monster_display_name
        await ctx.send(f'You see {monster_display_name(monster)}.')


async def describe_ally(ctx: GameContext, ally) -> None:
    """Shared LOOK/EXAMINE flavor for a party member -- both commands
    search owned_allies() by name and fall back to this same description,
    so an ally examined comes back identical to one looked at (Ryan's
    request to expand EXAMINE to cover allies too).

    A non-mount ally with a bar/allies.json "description" field shows it
    (run through tada_utilities.substitute_tokens() so %n/%p/etc. resolve
    against the ally's own name/gender) instead of the generic fallback
    line. Descriptions use "%y side" ("ready to fight at %y side"), not
    "%p side" -- %y is owner-relative, not the ally's own pronoun (%p is
    reserved for that, e.g. DARTH VADER's "wheezing behind %p mask").
    substitute_tokens() defaults %y to literal "your", which is correct
    today since both LOOK and EXAMINE only ever reach this branch via
    owned_allies(ctx.player) -- the viewer is always the ally's owner.
    If a bystander is ever allowed to LOOK at another player's ally, pass
    owner_pronoun= explicitly here (that ally's owner's real pronoun, or
    "NAME's") instead of leaving the default.

    A MOUNT ally (AllyFlags.MOUNT) also gets its gender/breed/colour,
    e.g. "SILVER is a female Palomino Arabian." -- see MECHANICS.md's
    "Horses" section and base_classes.HorseBreed/HorseColor's
    docstrings. General NPC/ally flavor text beyond this is a wider,
    not-yet-scoped gap (see the project_npc_descriptions_todo memory
    note) -- this only covers the horse-specific case Ryan asked for.

    A mount also gets a second line reporting saddle/armor status
    (AllyFlags.SADDLED/ARMORED, set by USEing a Saddle/Horse Armor
    bought at Jake's Stable -- commands/use.py's SPUR.USE.S eq.horse
    port) -- there was previously no way to check this without USEing
    the items again. Ryan's request.

    A mount with saddlebags (AllyFlags.SADDLEBAGS) gets a third line
    noting them, plus a thin/fat build based on how full they are
    (ally.items vs commands/give.py's _MOUNT_CAPACITY_WITH_SADDLEBAGS)
    -- a whimsical way to check pack fullness at a glance without
    opening the inventory menu. Ryan's request.
    """
    from bar.ally_data import AllyFlags
    from base_classes import Gender

    if AllyFlags.MOUNT in (ally.flags or []):
        gender_word = 'female' if ally.gender == Gender.FEMALE else 'male'
        if ally.breed and ally.color:
            await ctx.send(f'{ally.name} is a {gender_word} {ally.color} {ally.breed}.')
        else:
            # Legacy/older save: mount predates the breed/colour fields.
            await ctx.send(f'{ally.name} is a {gender_word} horse.')

        flags      = ally.flags or []
        has_saddle = AllyFlags.SADDLED in flags
        has_armor  = AllyFlags.ARMORED in flags
        if has_saddle and has_armor:
            await ctx.send(f'{ally.name} is saddled and wearing horse armor.')
        elif has_saddle:
            await ctx.send(f'{ally.name} is saddled, but has no horse armor.')
        elif has_armor:
            await ctx.send(f'{ally.name} is wearing horse armor, but has no saddle.')
        else:
            await ctx.send(f'{ally.name} has no saddle or horse armor.')

        if AllyFlags.SADDLEBAGS in flags:
            from commands.give import _MOUNT_CAPACITY_WITH_SADDLEBAGS
            count = len(ally.items or [])
            if count <= 0:
                build = 'looking a bit thin'
            elif count >= _MOUNT_CAPACITY_WITH_SADDLEBAGS:
                build = 'looking fat and well-packed'
            else:
                build = 'looking comfortably full'
            await ctx.send(f'{ally.name} has saddlebags strapped on, {build}.')
        else:
            await ctx.send(f'{ally.name} has no saddlebags.')
        return

    description = (getattr(ally, 'description', '') or '').strip()
    if description:
        from tada_utilities import substitute_tokens
        await ctx.send(substitute_tokens(description, ally))
        return

    await ctx.send(f'{ally.name} is here with you, ready to help.')
