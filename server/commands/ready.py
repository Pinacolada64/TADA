"""commands/ready.py — Ready (equip) a weapon from inventory."""
import random

from base_classes import PlayerStat
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import weapon_bonus
from items import ItemCategory
from network_context import GameContext

_MIN_STR = 4

# Battle experience tiers (mirrors SPUR.WEAPON.S vp thresholds).
# VETERAN (+1 to-hit, +1 damage) at 40; ELITE (+2 to-hit, +xp damage) at 99.
_TIERS = [
    (99, 'ELITE',   '|light_cyan|'),
    (40, 'VETERAN', '|yellow|'),
    ( 0, 'GREEN',   '|green|'),
]


def _battle_exp(player, weapon) -> int:
    """Return player's battle experience (0-99) with this weapon."""
    wid = str(getattr(weapon, 'id_number', 0))
    exp = getattr(player, 'weapon_experience', {})
    return int(exp.get(wid, 0))


def _tier_label(vp: int) -> str:
    """Return a colour-coded tier badge for display, e.g. '|yellow|[ VETERAN ]|reset|'."""
    for threshold, name, color in _TIERS:
        if vp >= threshold:
            return f'{color}[ {name} ]|reset|'
    return ''


def _find_storm_in_inventory(player, excluding_id=None):
    """Return the first STORM weapon in inventory that isn't *excluding_id*."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return None
    for entry in inv.entries():
        item = entry.item
        if 'STORM' in (getattr(item, 'name', '') or '').upper():
            if excluding_id is None or getattr(item, 'id_number', None) != excluding_id:
                return item
    return None


def _weapon_entries(player):
    """Return InventoryEntry list for weapons the player carries."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    return inv.entries(category=str(ItemCategory.WEAPON))


def _stat(player, key) -> int:
    stats = getattr(player, 'stats', {}) or {}
    return int(stats.get(key, 0) or 0)


def _weapon_class_line(weapon) -> str:
    wc = getattr(weapon, 'weapon_class', None)
    if wc is None:
        return ''
    wc_str = wc.value if hasattr(wc, 'value') else str(wc)
    targets = {
        'hack_slash_bash': 'Swift, Small, Short; Light Armor',
        'poke_jab':        'Huge, Swift',
        'pole_range':      'Man-sized, Big, Short',
        'projectile':      'Huge, Large (+10% surprise)',
        'proximity':       'Anybody',
        'energy':          'Huge, Large; Light Armor',
    }
    best = targets.get(wc_str.lower(), '')
    line = f'Weapon class: {wc_str}'
    if best:
        line += f'  [ Best targets ]: {best}'
    return line


class ReadyCommand(Command):
    name    = 'ready'
    aliases = ['wield', 'equip']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Ready a weapon from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('ready',         'List carried weapons and choose one'),
            ('ready <name>',  'Ready the weapon matching name'),
        ],
        examples = [
            ('ready',         'Choose from weapon list'),
            ('ready sword',   'Ready anything with "sword" in the name'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        player  = ctx.player
        entries = _weapon_entries(player)

        if not entries:
            await ctx.send('You have no weapons to ready.')
            return CommandResult.ok()

        str_val = _stat(player, PlayerStat.STR)
        if str_val < _MIN_STR:
            await ctx.send('Not enough strength to ready a weapon!')
            return CommandResult.ok()

        # Resolve target entry: by name arg or interactive prompt
        if args:
            pattern = ' '.join(args).lower()
            matches = [(i, e) for i, e in enumerate(entries)
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying any weapon matching "{" ".join(args)}".')
                return CommandResult.ok()
            if len(matches) == 1:
                entry = matches[0][1]
            else:
                lines = ['Which weapon?', '']
                for _, (orig_i, e) in enumerate(matches, 1):
                    lines.append(f'  {orig_i + 1:>2}. {getattr(e.item, "name", "?")}')
                lines.append('')
                await ctx.send(lines)
                raw = await ctx.prompt(f'Ready which (1-{len(matches)}, Enter to cancel)')
                if not raw or not raw.strip():
                    return CommandResult.ok()
                try:
                    pick = int(raw.strip()) - 1
                    if not (0 <= pick < len(matches)):
                        raise ValueError
                except ValueError:
                    await ctx.send('Invalid selection.')
                    return CommandResult.ok()
                entry = matches[pick][1]
        else:
            lines = ['Weapons you carry:', '']
            for i, e in enumerate(entries, 1):
                name    = getattr(e.item, 'name', '?')
                wc      = getattr(e.item, 'weapon_class', None)
                wc_str  = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
                vp      = _battle_exp(player, e.item)
                badge   = _tier_label(vp)
                lines.append(f'  {i:>2}. {name:<22} {wc_str:<18} {badge}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Ready which weapon (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                choice = int(raw.strip()) - 1
                if not (0 <= choice < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send('Invalid selection.')
                return CommandResult.ok()
            entry = entries[choice]

        weapon = entry.item
        name   = getattr(weapon, 'name', '?')

        # Already have this one readied?
        current = getattr(player, 'readied_weapon', None)
        if current is not None:
            cur_id   = getattr(current, 'id_number', None)
            new_id   = getattr(weapon,  'id_number', None)
            if cur_id is not None and cur_id == new_id:
                await ctx.send(
                    f'YOU ALREADY HAVE THE {name.upper()} READIED!',
                    "(You feel dumber)",
                )
                player.set_stat(ctx, PlayerStat.INT, -2)
                return CommandResult.ok()

            # STORM weapon refuses to be replaced — zaps and disintegrates.
            # Mirrors SPUR.WEAPON.S lines 26 and spec4 (169-194).
            cur_name = getattr(current, 'name', '') or ''
            if 'STORM' in cur_name.upper():
                dmg = random.randint(1, 10)
                await ctx.send([
                    f'THE {cur_name.upper()} HOWLS IN RAGE!',
                    "'I REFUSE! YOU ARE MINE!!'",
                    '',
                    'A BOLT OF POWER BLASTS YOU BACKWARDS!',
                    f'YOU TAKE {dmg} DAMAGE!',
                ])
                hp = getattr(player, 'hit_points', 0) - dmg
                player.hit_points = hp
                player.unsaved_changes = True
                inv = getattr(player, 'inventory', None)
                if inv is not None:
                    inv.remove(current)
                player.readied_weapon = None
                await ctx.send([
                    f'THE {cur_name.upper()} DISINTEGRATES!',
                    '(No weapon readied..)',
                ])
                if hp <= 0:
                    player.hit_points = 0
                    await ctx.send([
                        '|red|The blast was fatal. You have perished!|reset|',
                        'Your adventure ends here...',
                    ])
                return CommandResult.ok()

        # Display weapon info
        info = [_weapon_class_line(weapon)]
        dmg = getattr(weapon, 'stability', None)
        if dmg is not None:
            info.append(f'Base damage : {dmg}')
        skill = getattr(weapon, 'to_hit', None)
        if skill is not None:
            info.append(f'Ease of use : {100 - skill}%')
        vp = _battle_exp(player, weapon)
        info.append(f'Battle exp. : {vp} {_tier_label(vp)}')

        # Class/race bonuses
        char_class = getattr(player, 'char_class', None)
        char_race  = getattr(player, 'char_race',  None)
        class_str  = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
        race_str   = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
        skill_b = dmg_b = 0
        try:
            skill_b, dmg_b = weapon_bonus(weapon, class_str, race_str)
            if skill_b:
                sign = '+' if skill_b > 0 else ''
                info.append(f'Skill bonus : {sign}{skill_b} ({class_str}/{race_str})')
            if dmg_b:
                sign = '+' if dmg_b > 0 else ''
                info.append(f'Damage bonus: {sign}{dmg_b} ({class_str}/{race_str})')
        except Exception:
            pass

        info = [l for l in info if l]
        if info:
            await ctx.send(info)

        new_is_storm = 'STORM' in name.upper()

        # --- STORM jealousy / servant / rejection (SPUR.WEAPON.S lines 156-163) ---
        #
        # These fire AFTER we've confirmed the new weapon is different from the current
        # one and the current weapon is not itself a STORM (that case is handled above).

        if not new_is_storm:
            # Jealous rage: a STORM weapon sits unreadied in inventory and howls
            # when ignored.  It zaps the player, disintegrates, and the ready is
            # aborted — the player ends up with no weapon readied.
            # Mirrors SPUR.WEAPON.S line 156 → spec5 → spec4 → spec6.
            storm_in_inv = _find_storm_in_inventory(
                player, excluding_id=getattr(weapon, 'id_number', None)
            )
            if storm_in_inv is not None:
                sname = storm_in_inv.name.upper()
                dmg   = random.randint(1, 10)
                await ctx.send([
                    f'THE STORM WEAPON YOU IGNORED,',
                    f'HOWLS IN JEALOUS RAGE!!',
                    '',
                    'A BOLT OF POWER BLASTS YOU BACKWARDS!',
                    f'YOU TAKE {dmg} DAMAGE!',
                ])
                hp = getattr(player, 'hit_points', 0) - dmg
                player.hit_points = hp
                player.unsaved_changes = True
                inv = getattr(player, 'inventory', None)
                if inv is not None:
                    inv.remove(storm_in_inv)
                player.readied_weapon = None
                await ctx.send([
                    f'THE {sname} DISINTEGRATES!',
                    '(No weapon readied..)',
                ])
                if hp <= 0:
                    player.hit_points = 0
                    await ctx.send([
                        '|red|The blast was fatal. You have perished!|reset|',
                        'Your adventure ends here...',
                    ])
                return CommandResult.ok()

        else:
            # New weapon IS a STORM weapon.
            # "YOU ARE NOT MINE": class/race has no affinity for this weapon.
            # Mirrors SPUR.WEAPON.S line 158 → spec3 → spec4.
            if skill_b + dmg_b < 1:
                dmg = random.randint(1, 10)
                await ctx.send([
                    f'A THUNDERING HOWL OF RAGE BLASTS FROM',
                    f'THE {name.upper()}! \'YOU ARE NOT MINE!!\'',
                    '',
                    'A BOLT OF POWER BLASTS YOU BACKWARDS!',
                    f'YOU TAKE {dmg} DAMAGE!',
                ])
                hp = getattr(player, 'hit_points', 0) - dmg
                player.hit_points = hp
                player.unsaved_changes = True
                if hp <= 0:
                    player.hit_points = 0
                    await ctx.send([
                        '|red|The blast was fatal. You have perished!|reset|',
                        'Your adventure ends here...',
                    ])
                return CommandResult.ok()

            # Servant: STORM weapon accepts the player.  Grants +2 to skill and
            # damage bonus for this session (stored on player, used by _swing()).
            # Mirrors SPUR.WEAPON.S lines 161-163.
            await ctx.send([
                'THUNDERING LAUGHTER SHRIEKS FROM THE',
                f'{name.upper()}! \'I ACCEPT THEE AS',
                'MY SERVANT!\'',
                '',
                'A jolt of power surges up your arm..',
            ])
            player.storm_servant_bonus = (2, 2)

        player.readied_weapon = weapon
        # Clear servant bonus when switching to any non-STORM weapon.
        if not new_is_storm:
            player.storm_servant_bonus = None
        await ctx.send(f'{name.upper()} READIED.')
        return CommandResult.ok()
