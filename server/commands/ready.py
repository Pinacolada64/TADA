"""commands/ready.py — Ready (equip) a weapon from inventory."""
from base_classes import PlayerStat
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import weapon_bonus
from items import ItemCategory
from network_context import GameContext

_MIN_STR = 4


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
                lines.append(f'  {i:>2}. {name:<22} {wc_str}')
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

        # Display weapon info
        info = [_weapon_class_line(weapon)]
        dmg = getattr(weapon, 'stability', None)
        if dmg is not None:
            info.append(f'Base damage : {dmg}')
        skill = getattr(weapon, 'to_hit', None)
        if skill is not None:
            info.append(f'Ease of use : {100 - skill}%')

        # Class/race bonuses
        char_class = getattr(player, 'char_class', None)
        char_race  = getattr(player, 'char_race',  None)
        class_str  = (char_class.value if hasattr(char_class, 'value') else str(char_class)) if char_class else 'Fighter'
        race_str   = (char_race.value  if hasattr(char_race,  'value') else str(char_race))  if char_race  else 'Human'
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

        player.readied_weapon = weapon
        await ctx.send(f'{name.upper()} READIED.')
        return CommandResult.ok()
