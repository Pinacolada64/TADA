"""guild_hq/main.py — Guild Headquarters (SPUR.GUILD.S port).

Each of the three guilds (Claw, Sword, Fist) shares this code.
Entry is triggered by movement.py when the player enters a room whose
alignment matches the player's guild.
"""
import json
import logging

from network_context import GameContext
from guild_hq.state import (
    ITEM_LOCKER_MAX, FOOD_LOCKER_MAX, load, save, add_log,
)

log = logging.getLogger(__name__)

# Display info keyed by guild key
_GUILD_INFO = {
    'CLAW':  {'name': 'Mark of the Claw',  'sigil': r'\|/',    'butler': 'Lurch'},
    'SWORD': {'name': 'Mark of the Sword', 'sigil': '-}----',  'butler': 'Lurch'},
    'FIST':  {'name': 'The Iron Fist',     'sigil': '==[]',    'butler': 'Lurch'},
}

# Items forbidden in the item locker (SPUR.GUILD.S drp.a check).
# Lurch refuses quest items, keys, unique relics, and sci-fi zone gear.
#  67=ring               73=crown of Midas       74=inflatable dinghy
#  76=Amulet of Life     80=copper key           82=Crystal Pendant
#  96=Palantir           97=Ice Crystal
# 122=spacesuit         123=Geiger counter      124=radiation suit
# 131=red security card 132=green security card 133=tool kit
# 134=broken spacesuit  135=spacesuit parts     138=space tracker
# 140=nuclear rocket    142=Galadriel's vial (empty)
# 143=Galadriel's vial (full)  144=ruby slippers  145=broomstick
_LOCKER_FORBIDDEN = frozenset({
    67, 73, 74, 76, 80, 82, 96, 97,
    122, 123, 124, 131, 132, 133, 134, 135, 138, 140, 142, 143, 144, 145,
})


def _guild_key_for(player) -> str | None:
    """Return the guild key string for player.guild, or None if not in a combat guild."""
    from base_classes import Guild
    mapping = {
        Guild.CLAW:  'CLAW',
        Guild.SWORD: 'SWORD',
        Guild.FIST:  'FIST',
    }
    return mapping.get(getattr(player, 'guild', None))


# ---------------------------------------------------------------------------
# Chalkboard  (SPUR.GUILD.S chalk.bd)
# ---------------------------------------------------------------------------

async def _chalkboard(ctx: GameContext, player, state: dict, info: dict) -> None:
    board = state['chalkboard']
    author  = board.get('author', '')
    message = board.get('message', '')

    if author and message:
        await ctx.send([
            '',
            'You wander over and read the small chalk board..',
            f"It reads.. FROM {author}:",
            f"  '{message}'",
            '',
        ])
    else:
        await ctx.send(['', '(The chalkboard is blank.)', ''])

    raw = await ctx.prompt('Write over message? y/[N]')
    if raw is None or raw.strip().upper() != 'Y':
        return

    while True:
        await ctx.send([
            'Write new message, 75 char max.',
            '....:....|....:....|....:....|....:....|....:....|....:....|....:....|....:',
        ])
        raw = await ctx.prompt('')
        if raw is None:
            return
        msg = raw.strip()
        if not msg:
            await ctx.send('You write nothing..')
            return
        if len(msg) > 75:
            await ctx.send(f'Too long! ({len(msg)} chars, max 75)')
            continue
        state['chalkboard'] = {'author': player.name, 'message': msg}
        return


# ---------------------------------------------------------------------------
# Food locker  (SPUR.GUILD.S food / give.f / take.fd)
# ---------------------------------------------------------------------------

async def _food_locker(ctx: GameContext, player, state: dict, info: dict) -> None:
    from base_classes import PlayerMoneyTypes
    from items import Rations, ItemCategory

    inv = getattr(player, 'inventory', None)

    await ctx.send('Lurch takes you to the food locker..')

    while True:
        raw = await ctx.prompt('G)ive or T)ake food? (Q to leave)')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return

        if cmd == 'G':
            # Deposit a ration from player inventory into the locker
            if len(state['food_locker']) >= FOOD_LOCKER_MAX:
                await ctx.send("'Sorry, our pantry is full!'")
                continue

            food_entries = [e for e in (inv.entries('Rations') if inv else [])
                            if hasattr(e.item, 'id_number')]
            if not food_entries:
                await ctx.send("'Alas, you have no rations!'")
                continue

            lines = ['', 'You now carry:', '']
            for i, e in enumerate(food_entries, 1):
                lines.append(f'  {i:>3}. {e.item.name}')
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt('Give which ration number? (Q to cancel)')
            if raw is None:
                return
            choice = raw.strip().upper()
            if not choice or choice == 'Q':
                continue

            try:
                idx = int(choice) - 1
                if not (0 <= idx < len(food_entries)):
                    raise ValueError
            except ValueError:
                await ctx.send("You're NOT carrying that!!")
                continue

            entry = food_entries[idx]
            item  = entry.item
            if inv.remove(item):
                state['food_locker'].append({
                    'id':    getattr(item, 'id_number', getattr(item, 'number', 0)),
                    'name':  item.name,
                    'price': getattr(item, 'price', 0),
                    'kind':  getattr(item, 'kind', 'food'),
                })
                add_log(state, player.name, 'GAVE', item.name)
                player.unsaved_changes = True
                await ctx.send(f"Lurch puts the {item.name} on the shelf.")

        elif cmd == 'T':
            # Take a ration from the locker
            if not state['food_locker']:
                await ctx.send("'Alas, the pantry is empty!'")
                continue
            if inv and inv.is_full():
                await ctx.send('No room left in your pack.')
                continue

            lines = ['', 'The Guild now has:', '']
            for i, it in enumerate(state['food_locker'], 1):
                lines.append(f'  {i:>3}. {it["name"]}')
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt('Take which food number? (Q to cancel)')
            if raw is None:
                return
            choice = raw.strip().upper()
            if not choice or choice == 'Q':
                continue

            try:
                idx = int(choice) - 1
                if not (0 <= idx < len(state['food_locker'])):
                    raise ValueError
            except ValueError:
                await ctx.send("We don't have that!!")
                continue

            it = state['food_locker'].pop(idx)
            ration = Rations(
                number=it['id'],
                name=it['name'],
                kind=it.get('kind', 'food'),
                price=it.get('price', 0),
            )
            if inv and inv.add(ration):
                add_log(state, player.name, 'TOOK', it['name'])
                player.unsaved_changes = True
                await ctx.send(f"Lurch hands you the {it['name']}.")
            else:
                # Roll back if inventory refused it
                state['food_locker'].insert(idx, it)
                await ctx.send('Your pack is full.')
        else:
            await ctx.send('G)ive or T)ake food? (Q to leave)')


# ---------------------------------------------------------------------------
# Item locker  (SPUR.GUILD.S item / give / take)
# ---------------------------------------------------------------------------

async def _item_locker(ctx: GameContext, player, state: dict, info: dict) -> None:
    from items import Item, ItemCategory

    inv = getattr(player, 'inventory', None)

    await ctx.send('Lurch shows you to the Items room..')

    while True:
        raw = await ctx.prompt('G)ive or T)ake item? (Q to leave)')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return

        if cmd == 'G':
            if len(state['item_locker']) >= ITEM_LOCKER_MAX:
                await ctx.send('There is no more room!')
                continue

            item_entries = [e for e in (inv.entries(ItemCategory.ITEM) if inv else [])]
            if not item_entries:
                await ctx.send("'Alas, you have no Items!'")
                continue

            lines = ['', 'You are carrying:', '']
            for i, e in enumerate(item_entries, 1):
                lines.append(f'  {i:>3}. {e.item.name}')
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt('Give which item number? (Q to cancel)')
            if raw is None:
                return
            choice = raw.strip().upper()
            if not choice or choice == 'Q':
                continue

            try:
                idx = int(choice) - 1
                if not (0 <= idx < len(item_entries)):
                    raise ValueError
            except ValueError:
                await ctx.send("You're NOT carrying that!!")
                continue

            entry = item_entries[idx]
            item  = entry.item
            iid   = getattr(item, 'id_number', 0)

            # SPUR: Lurch isn't allowed to take certain items
            if iid in _LOCKER_FORBIDDEN:
                await ctx.send("Lurch isn't allowed to take it!")
                continue

            if inv.remove(item):
                state['item_locker'].append({
                    'id':    iid,
                    'name':  item.name,
                    'price': getattr(item, 'price', 0),
                })
                add_log(state, player.name, 'GAVE', item.name)
                player.unsaved_changes = True
                await ctx.send(f'Lurch thanks you..')

        elif cmd == 'T':
            if not state['item_locker']:
                await ctx.send("The Guild doesn't have anything!")
                continue
            if inv and inv.is_full():
                await ctx.send('You can carry no more Items.')
                continue

            lines = ['', 'The Guild now has:', '']
            for i, it in enumerate(state['item_locker'], 1):
                lines.append(f'  {i:>3}. {it["name"]}')
            lines.append('')
            await ctx.send(lines)

            raw = await ctx.prompt('Take which item number? (Q to cancel)')
            if raw is None:
                return
            choice = raw.strip().upper()
            if not choice or choice == 'Q':
                continue

            try:
                idx = int(choice) - 1
                if not (0 <= idx < len(state['item_locker'])):
                    raise ValueError
            except ValueError:
                await ctx.send("We don't have that!!")
                continue

            it = state['item_locker'].pop(idx)
            item = Item(
                id_number=it['id'],
                name=it['name'],
                price=it.get('price', 0),
                category=ItemCategory.ITEM,
            )
            if inv and inv.add(item):
                add_log(state, player.name, 'TOOK', it['name'])
                player.unsaved_changes = True
                await ctx.send(f"Lurch hands you the {it['name']}.")
            else:
                state['item_locker'].insert(idx, it)
                await ctx.send('Your pack is full.')
        else:
            await ctx.send('G)ive or T)ake item? (Q to leave)')


# ---------------------------------------------------------------------------
# Guild bank  (SPUR.GUILD.S bank / pay / withdraw)
# ---------------------------------------------------------------------------

async def _guild_bank(ctx: GameContext, player, state: dict, info: dict) -> None:
    from base_classes import PlayerMoneyTypes

    await ctx.send(f"Lurch takes you to the treasury.")

    while True:
        treasury = state['treasury']
        in_hand  = player.get_silver(PlayerMoneyTypes.IN_HAND)

        await ctx.send([
            '',
            f'  In Guild Treasury : {treasury:>9,} silver',
            f'  In your hand      : {in_hand:>9,} silver',
            '',
        ])

        raw = await ctx.prompt('R)eview, P)ay, T)ake, or Q to leave')
        if raw is None:
            return
        cmd = raw.strip().upper()[:1]
        if not cmd or cmd == 'Q':
            return

        if cmd == 'R':
            continue  # balance is shown at the top of each loop

        elif cmd == 'P':
            # Deposit from hand to treasury
            raw = await ctx.prompt('Give to Guild fund')
            if not raw or not raw.strip():
                await ctx.send('Lurch rolls his eyes...')
                continue
            try:
                amount = int(raw.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send('Lurch stares at the wall..')
                continue
            in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
            if in_hand < amount:
                await ctx.send("You don't have that much!")
                continue
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, amount)
            state['treasury'] += amount
            add_log(state, player.name, 'GAVE', f'{amount} silver')
            player.unsaved_changes = True
            await ctx.send('Lurch thanks you.')

        elif cmd == 'T':
            # Withdraw from treasury to hand
            raw = await ctx.prompt('Take — How much?')
            if not raw or not raw.strip():
                continue
            try:
                amount = int(raw.strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send('Lurch smiles..')
                continue
            if state['treasury'] < amount:
                await ctx.send("We don't have that much!")
                continue
            state['treasury'] -= amount
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -amount)
            add_log(state, player.name, 'TOOK', f'{amount} silver')
            player.unsaved_changes = True
            await ctx.send('Lurch hands it to you.')

        else:
            await ctx.send('R)eview, P)ay, T)ake, or Q to leave.')


# ---------------------------------------------------------------------------
# Territory report (Ryan's own extension -- not a SPUR mechanic).
# Reads run/server/guild_control.json, written nightly by
# tools/nightly_guild_maintenance.py from the current level_<N>.json
# room_alignment data.
# ---------------------------------------------------------------------------

async def _territory_report(ctx: GameContext, player, state: dict, info: dict) -> None:
    import net_common
    from pathlib import Path

    guild_key = info['key'].lower()  # 'claw' / 'sword' / 'fist'
    base = getattr(net_common, 'run_server_dir', None) or './run/server'
    report_file = Path(str(base)) / 'guild_control.json'

    if not report_file.exists():
        await ctx.send(['', "Lurch shrugs. 'No territory report yet -- ask the sysop", "to run the nightly maintenance job.'", ''])
        return

    try:
        report = json.loads(report_file.read_text())
    except Exception:
        log.exception('guild_hq: failed to read %s', report_file)
        await ctx.send(['', "Lurch frowns. 'The territory report seems to be broken.'", ''])
        return

    lines = ['', f"Territory held by {info['name']}:", '']
    for level_num, level_data in sorted(report.get('levels', {}).items(), key=lambda kv: int(kv[0])):
        counts = level_data.get('counts', {})
        pct = level_data.get('pct', {}).get(guild_key, 0.0)
        held = counts.get(guild_key, 0)
        total = level_data.get('total', 0)
        lines.append(f'  Level {level_num:>2}: {pct:>5.1f}%  ({held}/{total} rooms)')

    overall = report.get('overall', {})
    overall_pct = overall.get('pct', {}).get(guild_key, 0.0)
    overall_held = overall.get('counts', {}).get(guild_key, 0)
    overall_total = overall.get('total', 0)
    lines.append('')
    lines.append(f'  Overall  : {overall_pct:>5.1f}%  ({overall_held}/{overall_total} rooms)')

    generated_at = report.get('generated_at', '')
    if generated_at:
        lines.append('')
        lines.append(f'  (as of {generated_at})')
    lines.append('')
    await ctx.send(lines)


# ---------------------------------------------------------------------------
# View log  (SPUR.GUILD.S show.lg)
# ---------------------------------------------------------------------------

async def _view_log(ctx: GameContext, player, state: dict, info: dict) -> None:
    await ctx.send('Lurch shows you the Guild Log..')
    entries = state.get('log', [])
    if not entries:
        await ctx.send(['', '(The log is empty.)', ''])
        return
    lines = ['']
    guild_key = info.get('key', '???')
    lines.append(f'[]=-=-=-=-=-=-=[ {guild_key} ]=-=-=-=-=-=-=[]')
    lines += entries
    lines.append(f'[]=-=-=-=-=-=-=[ {guild_key} ]=-=-=-=-=-=-=[]')
    lines.append('')
    await ctx.send(lines)


# ---------------------------------------------------------------------------
# Weapons box  (SPUR.GUILD.S weapon / give.wep)
# ---------------------------------------------------------------------------

async def _weapons_box(ctx: GameContext, player, state: dict, info: dict) -> None:
    from items import Weapon, ItemCategory
    from inventory import PACK_FULL_MESSAGE

    inv = getattr(player, 'inventory', None)

    await ctx.send('You open up the weapon box.')

    box = state.get('weapons_box')

    if box:
        await ctx.send([
            '',
            f"There is a {box['name']} in the box.",
            '',
        ])
        raw = await ctx.prompt('Take it? y/[N]')
        if raw and raw.strip().upper() == 'Y':
            if inv and inv.is_full():
                await ctx.send('You can carry no more weapons!')
                return
            weapon_entries = inv.entries(ItemCategory.WEAPON) if inv else []
            if len(weapon_entries) >= 6:
                await ctx.send('You can carry no more weapons!')
                return
            already = any(getattr(e.item, 'id_number', None) == box['id']
                          for e in weapon_entries)
            if already:
                await ctx.send('You already have one!')
                return
            w = Weapon(
                id_number    = box['id'],
                name         = box['name'],
                price        = box.get('price', 0),
                to_hit       = box.get('to_hit', 0),
                stability    = box.get('stability', 0),
                location     = box.get('location', 0),
                weapon_class = box.get('weapon_class'),
            )
            if inv and inv.add(w):
                state['weapons_box'] = None
                # SPUR: if vk>5 vk=vk-5 (taking costs a little honor)
                player.honor = max(0, int(getattr(player, 'honor', 0) or 0) - 5)
                add_log(state, player.name, 'TOOK', box['name'])
                player.unsaved_changes = True
                await ctx.send(f"Lurch hands you the {box['name']}.")
            else:
                await ctx.send(PACK_FULL_MESSAGE)
        return

    # Box is empty — offer to deposit a weapon
    raw = await ctx.prompt('The box is empty. Put in a weapon? y/[N]')
    if raw is None or raw.strip().upper() != 'Y':
        return

    weapon_entries = inv.entries(ItemCategory.WEAPON) if inv else []
    if not weapon_entries:
        await ctx.send("You don't have any!")
        return

    lines = ['', 'Give which weapon:', '']
    for i, e in enumerate(weapon_entries, 1):
        lines.append(f'  {i}. {e.item.name}')
    lines.append('')
    await ctx.send(lines)

    while True:
        raw = await ctx.prompt('Which (Q to cancel)')
        if raw is None or raw.strip().upper() == 'Q':
            return
        try:
            idx = int(raw.strip()) - 1
            if not (0 <= idx < len(weapon_entries)):
                raise ValueError
        except ValueError:
            await ctx.send("You don't have that!")
            continue

        entry = weapon_entries[idx]
        item  = entry.item
        iid   = getattr(item, 'id_number', 0)

        # SPUR: Lurch refuses Excalibur (#17) and deducts honor for it
        if iid == 17:
            honor_loss = min(10, int(getattr(player, 'honor', 0) or 0))
            player.adjust_honor(-honor_loss)
            await ctx.send("'I will not take that!!'")
            return

        if inv.remove(item):
            state['weapons_box'] = {
                'id':          iid,
                'name':        item.name,
                'price':       getattr(item, 'price', 0),
                'to_hit':      getattr(item, 'to_hit', 0),
                'stability':   getattr(item, 'stability', 0),
                'location':    getattr(item, 'location', 0),
                'weapon_class': str(getattr(item, 'weapon_class', '') or ''),
            }
            # SPUR: if vk<2000 vk=vk+5 (donating a weapon earns a little honor)
            player.honor = min(2000, int(getattr(player, 'honor', 0) or 0) + 5)
            add_log(state, player.name, 'GAVE', item.name)
            player.unsaved_changes = True
            await ctx.send(f"Lurch carefully places the {item.name} in the box.")
        return


# ---------------------------------------------------------------------------
# Help  (Ryan's own extension -- not a SPUR mechanic)
# ---------------------------------------------------------------------------

_HELP_TEXT = (
    ('C', 'Read or write the chalk board message for the guild.'),
    ('F', 'Give or take a ration from the shared food locker.'),
    ('I', 'Give or take an item from the shared item locker (Lurch refuses '
          'quest items, keys, and unique relics).'),
    ('B', 'Review, pay into, or withdraw from the guild treasury.'),
    ('V', 'View the guild log of recent gives and takes.'),
    ('W', "Store or retrieve a weapon from the shared weapons box (holds "
          "one weapon at a time; Lurch won't take Excalibur)."),
    ('T', 'See what share of the map your guild currently holds.'),
    ('Q', 'Leave the guild hall.'),
)


async def _help(ctx: GameContext, player, state: dict, info: dict) -> None:
    from table import Column, Table
    from formatting import border_style_for_ctx

    border_style = border_style_for_ctx(ctx)
    width = getattr(ctx.player.client_settings, 'screen_columns', 78)

    t = Table(
        headers=[Column('Key', min_width=3), Column('What it does', min_width=10)],
        border=False,
        border_style=border_style,
        header_color='white',
        text_color=['cyan', 'light_blue'],
    )
    for key, desc in _HELP_TEXT[:-1]:
        t.add_row([key, desc])
    if _can_manage_bans(player):
        t.add_row(['K', 'Ban or un-ban a player from this guild HQ.'])
    t.add_row(_HELP_TEXT[-1])  # Q - Leave, kept last

    await ctx.send([
        '',
        f"Lurch clears his throat. 'Allow me to explain, {player.name}:'",
        '',
        *t.render(width=width),
        '',
    ])


# ---------------------------------------------------------------------------
# Ban management  (SPUR.GUILD.S bann -- gated to guild officers there via
# flag(19). This port has no separate "guild officer" rank yet, so it's
# gated to Admin/Dungeon Master instead, matching every other privileged
# menu in the codebase (e.g. commands/board.py, commands/reload.py).)
# ---------------------------------------------------------------------------

def _can_manage_bans(player) -> bool:
    from flags import PlayerFlags
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


async def _ban_management(ctx: GameContext, player, state: dict, info: dict) -> None:
    if not _can_manage_bans(player):
        await ctx.send('Lurch snickers..')
        return

    from base_classes import Guild
    from commands.editplayer import _find_character
    from commands.messaging import prompt_player_choice

    banned = state.setdefault('banned', [])

    lines = ['', f'Banned from the {info["name"]}:', '']
    lines += [f'  {n}' for n in banned] if banned else ['  (nobody)']
    lines.append('')
    await ctx.send(lines)

    name = await prompt_player_choice(ctx, '*', prompt_text='Ban/unban whom')
    if name is None:
        return

    found = await _find_character(ctx, name)
    if found is None:
        await ctx.send(f'No character named "{name}".')
        return
    target, is_online = found

    already_banned = target.name in banned
    if not already_banned and _guild_key_for(target) != info['key']:
        await ctx.send(f"{target.name} isn't a member of the {info['name']}.")
        return

    await ctx.send(f"{target.name} is currently {'BANNED' if already_banned else 'not banned'}.")

    raw = await ctx.prompt('Switch status? [Y]/n')
    if raw and raw.strip().upper() == 'N':
        return

    if already_banned:
        banned.remove(target.name)
        action, verb = 'UNBANNED', 'un-banned'
    else:
        banned.append(target.name)
        action, verb = 'BANNED', 'banned'
        # SPUR: banning a member of your own guild demotes them to Outlaw
        target.guild = Guild.OUTLAW
        target.unsaved_changes = True
        if not is_online:
            target.save(force=True)

    add_log(state, player.name, action, target.name)
    await ctx.send(f"Done. {target.name} is now {verb} from the {info['name']}.")


# ---------------------------------------------------------------------------
# Menu and entry point
# ---------------------------------------------------------------------------

_MENU = (
    ('C', 'Chalk board'),
    ('F', 'Food locker'),
    ('I', 'Item locker'),
    ('B', 'Guild bank'),
    ('V', 'View guild log'),
    ('W', 'Weapons box'),
    ('T', 'Territory report'),
    ('H', 'Help'),
    ('Q', 'Leave'),
)

_HANDLERS = {
    'C': _chalkboard,
    'F': _food_locker,
    'I': _item_locker,
    'B': _guild_bank,
    'V': _view_log,
    'W': _weapons_box,
    'T': _territory_report,
    'H': _help,
    'K': _ban_management,
}


async def main(ctx: GameContext, guild_key: str) -> None:
    """Guild HQ entry point. guild_key is 'CLAW', 'SWORD', or 'FIST'.
    (SPUR.GUILD.S main / menu.a)
    """
    from base_classes import Guild
    from presence import enter_area, leave_area

    player = ctx.player
    info   = _GUILD_INFO[guild_key]
    info   = {**info, 'key': guild_key}

    # Gate: player must be a member of this guild
    player_key = _guild_key_for(player)
    if player_key != guild_key:
        guild_name = info['name']
        await ctx.send([
            f'A gruff guard informs you that you are not a member of the {guild_name}',
            'and politely throws you out..',
        ])
        return

    # Gate: banned members are turned away (SPUR.GUILD.S bann); officers
    # (here: Admin/Dungeon Master) bypass their own ban list.
    if player.name in load(guild_key).get('banned', []) and not _can_manage_bans(player):
        await ctx.send([
            f"A guard blocks the door. 'You've been banned from the {info['name']}!'",
            "'Take it up with your Guildmaster.'",
        ])
        return

    # Lurch greets you (SPUR: setint(1) print "Lurch the butler meets you..")
    await ctx.send([
        '',
        f"Lurch the butler meets you at the door. 'Greetings {player.name}! Welcome",
        f"to The {info['name']}.' He hands you a warmed brandy and leads you inside.",
        '',
    ])

    # SPUR: if pe<15 pe=pe+4 (small energy bonus on entry)
    energy = int(getattr(player, 'drink', 0) or 0)
    if energy < 15:
        player.drink = energy + 4
        player.unsaved_changes = True
        await ctx.send('(Energy: +4)')

    area_key = info['name'].removeprefix('The ') + ' HQ'
    await enter_area(ctx, area_key)
    try:
        await _hq_session(ctx, player, guild_key, info)
    finally:
        await leave_area(ctx, area_key)


async def _hq_session(ctx, player, guild_key: str, info: dict) -> None:
    """Inner HQ loop — load state once, save on each mutation."""
    sigil = info['sigil']
    name  = info['name']
    key   = info['key']

    while True:
        state = load(guild_key)

        is_officer = _can_manage_bans(player)

        if not player.is_expert:
            lines = ['', f'{name} {sigil}', '']
            menu_items = list(_MENU)
            if is_officer:
                menu_items.insert(-1, ('K', 'Ban management'))
            for k, label in menu_items:
                lines.append(f'  [{k}] {label}')
            lines.append('')
            await ctx.send(lines)

        raw = await ctx.prompt(f'{key}')
        if raw is None:
            break
        cmd = raw.strip().upper()[:1]

        if not cmd or cmd == 'Q':
            await ctx.send('You return to the street..')
            break

        handler = _HANDLERS.get(cmd)
        if handler and (cmd != 'K' or is_officer):
            await handler(ctx, player, state, info)
            save(guild_key, state)
        else:
            keys = 'C/F/I/B/V/W/T/H' + ('/K' if is_officer else '') + '/Q'
            await ctx.send(f'{keys} to choose.')
