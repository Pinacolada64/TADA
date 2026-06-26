"""commands/inv.py — Display the player's inventory."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import InventoryEntry
from items import ItemCategory
from network_context import GameContext


_CATEGORY_ORDER = [
    ItemCategory.WEAPON,
    ItemCategory.ARMOR,
    ItemCategory.SPELL,
    ItemCategory.FOOD,
    ItemCategory.DRINK,
    ItemCategory.CONTAINER,
    ItemCategory.ITEM,
]


def _format_entry(entry: InventoryEntry, index: int) -> str:
    name = getattr(entry.item, 'name', '?') or '?'
    qty  = f'{entry.quantity}x ' if entry.quantity > 1 else '   '
    if entry.charges is not None:
        max_ch = getattr(entry.item, 'max_charges', 0)
        pct    = int(entry.charges / max_ch * 100) if max_ch else 0
        charges_str = f' [{entry.charges} charges, {pct}%]'
    else:
        charges_str = ''
    if entry.is_container and entry.contents:
        n   = len(entry.contents)
        cap = getattr(entry.item, 'capacity', '?')
        container_str = f' ({n}/{cap} items)'
    else:
        container_str = ''
    return f'{index:>3}. {qty}{name}{charges_str}{container_str}'


def _container_lines(entry: InventoryEntry) -> list[str]:
    if not entry.is_container or not entry.contents:
        return []
    return [
        f'         > {getattr(sub.item, "name", "?")}'
        + (f' x{sub.quantity}' if sub.quantity > 1 else '')
        for sub in entry.contents
    ]


class InvCommand(Command):
    name    = 'inv'
    aliases = ['inventory']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'List items you are carrying.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('inv',     'List all items together'),
            ('inv cat', 'List items grouped by category'),
        ],
        examples = [
            ('inv',     'Show flat inventory list'),
            ('inv cat', 'Show inventory sorted by type'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        categorized = bool(args) and args[0].lower() in ('cat', 'c', 'categorized')

        inventory = getattr(ctx.player, 'inventory', None)
        capacity  = getattr(ctx.player, 'max_inventory_size', None)

        if not inventory:
            await ctx.send('You are carrying nothing.')
            return CommandResult.ok()

        lines: list[str] = []
        cap_str = f'/{capacity}' if capacity else ''
        lines.append(f'Inventory ({len(inventory)}{cap_str} slots used):')
        lines.append('')

        if categorized:
            index = 1
            any_shown = False
            for cat in _CATEGORY_ORDER:
                cat_entries = inventory.entries(category=str(cat))
                if not cat_entries:
                    continue
                lines.append(f'-- {cat} --')
                for entry in cat_entries:
                    lines.append(_format_entry(entry, index))
                    lines.extend(_container_lines(entry))
                    index += 1
                lines.append('')
                any_shown = True
            if not any_shown:
                lines.append('  (nothing)')
        else:
            for index, entry in enumerate(inventory, 1):
                lines.append(_format_entry(entry, index))
                lines.extend(_container_lines(entry))

        await ctx.send(lines)
        return CommandResult.ok()
