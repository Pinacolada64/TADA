"""commands/loot.py — LOOT: steal an item from another player in the room.

SPUR.MISC3.S's "loot" subroutine -- despite the verb, this is PVP item
theft between live players, not searching a dead monster's corpse. Key
mechanics ported:

  - Target must be another real player sharing this room *and* dungeon
    level (send_room() elsewhere in this codebase only checks room
    number; LOOT also checks level to avoid a false match against a
    reused room number on a different level).
  - Guardian block: if the target belongs to Sword/Claw/Fist and another
    player of that SAME guild is also in the room, the theft is blocked
    -- New in TADA simplification of SPUR's finer guild-rank subset
    check (zz$ "67"/"34"/"89" vs the broader "67D"/"34C"/"89E"
    categories, SPUR.MISC3.S:549-551); this port treats "any fellow
    guild member present" as a guardian rather than reproducing the
    rank distinction.
  - Once per session, twice for Outlaws -- tracked as a transient
    per-session counter (player.loot_count), not persisted, mirroring
    SPUR's ys$ flag string the same way player.last_examined mirrors xz$
    for EXAMINE (see commands/look.py).
  - Docks the THIEF's own honor by 30 (50 if the thief is a Knight) --
    confirmed against other vk usages in SPUR.LOGON.S ("vk=1000" at
    character creation) and SPUR.MISC6.S:584 ("You feel less
    honorable"): vk is always the CURRENT player's own honor, never
    another player's.
  - No offline mail system exists in this codebase yet, so the "mail
    the victim" step (SPUR.MISC3.S:484-487) is skipped; battle.log is
    the audit trail instead (PILLAGE! on success, COMRADES! when a
    guardian blocks it), matching SPUR's own logging for both cases.
"""
import datetime
import logging
import os

from base_classes import Guild, PlayerClass
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext, GuestPlayer

log = logging.getLogger(__name__)

_HONOR_COST         = 30
_HONOR_COST_KNIGHT  = 50
_MAX_LOOTS          = 1
_MAX_LOOTS_OUTLAW   = 2

# Guilds whose members can shield each other from theft -- Civilian and
# Outlaw have no guardian mechanic in SPUR (only "67"/"34"/"89" -- Claw/
# Sword/Fist -- feed zw$/zx$/zy$).
_GUARDIAN_GUILDS = (Guild.SWORD, Guild.CLAW, Guild.FIST)


def _append_battle_log(entry: str) -> None:
    """Duplicated per this codebase's convention (see encounters/dwarf.py,
    combat/engine.py, etc. -- each module keeps its own copy rather than
    sharing one)."""
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    path = os.path.join(str(base or './run/server'), 'battle.log')
    try:
        with open(path, 'a') as fh:
            stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            fh.write(f'[{stamp}] {entry}\n')
    except Exception:
        log.exception('Failed to write battle.log')


def _room_mates(ctx) -> list:
    """Return [(client, player), ...] for other real (non-guest) players
    sharing this player's room and dungeon level."""
    my_room  = getattr(ctx.client, 'room', None)
    my_level = getattr(ctx.player, 'map_level', 1)
    mates = []
    for other_client in ctx.server.clients.values():
        if other_client is ctx.client:
            continue
        other_ctx    = getattr(other_client, 'ctx', None)
        other_player = getattr(other_ctx, 'player', None)
        if other_player is None or isinstance(other_player, GuestPlayer):
            continue
        if getattr(other_client, 'room', None) != my_room:
            continue
        if getattr(other_player, 'map_level', 1) != my_level:
            continue
        mates.append((other_client, other_player))
    return mates


def _guardian_present(target_player, target_guild, mates) -> bool:
    """True if another player of *target_player*'s own guild is also in
    the room -- see module docstring for the SPUR-fidelity simplification
    this represents."""
    if target_guild not in _GUARDIAN_GUILDS:
        return False
    for _client, player in mates:
        if player is target_player:
            continue
        if getattr(player, 'guild', None) == target_guild:
            return True
    return False


def _already_carries(player, item_id) -> bool:
    """True if *player* or any of their allies already carries an item
    with this id_number (SPUR.MISC3.S:457-458's xi$/ai$ duplicate check)."""
    if item_id is None:
        return False
    inv = getattr(player, 'inventory', None)
    if inv is not None and inv.find(item_id=item_id):
        return True
    from bar.allies import owned_allies
    for ally in owned_allies(player):
        for entry in (getattr(ally, 'items', None) or []):
            if getattr(entry.item, 'id_number', None) == item_id:
                return True
    return False


class LootCommand(Command):
    name    = 'loot'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Steal an item from another player in this room.',
        description = (
            'A once-per-session gamble (twice for Outlaws): pick another '
            'player sharing this room and take one item from their '
            'inventory. Costs you honor whether or not a guardian (a '
            'fellow guild member of theirs) steps in to stop you.'
        ),
        category = HelpCategory.INTERACTION,
        usage    = [
            ('loot', 'List other players here and choose one to steal from.'),
        ],
        examples = [
            ('loot', 'Attempt to steal from someone in this room.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        self.parse_args(*args)
        player = ctx.player

        is_outlaw  = getattr(player, 'guild', None) == Guild.OUTLAW
        max_loots  = _MAX_LOOTS_OUTLAW if is_outlaw else _MAX_LOOTS
        loot_count = getattr(player, 'loot_count', 0)
        if loot_count >= max_loots:
            await ctx.send('The SPUR gestapo frowns on taking too many items per game session!')
            return CommandResult.ok()

        inv = getattr(player, 'inventory', None)
        if inv is not None and inv.is_full():
            await ctx.send('You can carry no more Items.')
            return CommandResult.ok()

        mates = _room_mates(ctx)
        if not mates:
            await ctx.send('No adventurers here!')
            return CommandResult.ok()

        lines = ['People in the area:', '']
        for i, (_client, p) in enumerate(mates, 1):
            lines.append(f'  {i:>2}. {p.name}')
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt(f'Loot which Adventurer (1-{len(mates)}, {player.return_key} to abort)')
        if not raw or not raw.strip():
            return CommandResult.ok()
        try:
            pick = int(raw.strip()) - 1
            if not (0 <= pick < len(mates)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            return CommandResult.ok()

        _target_client, target = mates[pick]
        target_guild = getattr(target, 'guild', None)

        if _guardian_present(target, target_guild, mates):
            await ctx.send([
                f"{target.name}'s guildmate blocks the path!",
                f"'{target.name} is a member of my guild,",
                "you must defeat ME first!'",
            ])
            _append_battle_log(
                f'{player.name} tried to PILLAGE {target.name} but was blocked '
                f'by a guildmate (COMRADES!).'
            )
            return CommandResult.ok()

        target_inv     = getattr(target, 'inventory', None)
        target_entries = target_inv.entries() if target_inv is not None else []
        if not target_entries:
            await ctx.send(f"{target.name} isn't carrying any items!")
            return CommandResult.ok()

        lines = [f'{target.name} is carrying:', '']
        for i, entry in enumerate(target_entries, 1):
            lines.append(f'  {i:>2}. {getattr(entry.item, "name", "?")}')
        lines.append('')
        await ctx.send(lines)

        raw = await ctx.prompt(f'Take which item number? (1-{len(target_entries)}, {player.return_key} to abort)')
        if not raw or not raw.strip():
            return CommandResult.ok()
        try:
            item_pick = int(raw.strip()) - 1
            if not (0 <= item_pick < len(target_entries)):
                raise ValueError
        except ValueError:
            await ctx.send(f"{target.name} doesn't carry that!")
            return CommandResult.ok()

        entry     = target_entries[item_pick]
        item      = entry.item
        item_id   = getattr(item, 'id_number', None)
        item_name = getattr(item, 'name', '?')

        if _already_carries(player, item_id):
            await ctx.send('You already have one!')
            return CommandResult.ok()

        target_inv.remove(item)
        if inv is not None:
            inv.add(item)
        player.unsaved_changes = True
        target.unsaved_changes = True

        await ctx.send(f'You steal the {item_name} from {target.name}!')
        await ctx.send_room(f'{player.name} steals from {target.name}!', exclude_self=True)

        honor_cost = _HONOR_COST_KNIGHT if getattr(player, 'char_class', None) == PlayerClass.KNIGHT else _HONOR_COST
        honor      = int(getattr(player, 'honor', 0) or 0)
        player.honor = max(0, honor - honor_cost)

        player.loot_count = loot_count + 1

        _append_battle_log(f'{player.name} STOLE {item_name} FROM {target.name}.')

        return CommandResult.ok()
