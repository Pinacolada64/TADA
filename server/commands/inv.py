"""commands/inv.py — Display the player's inventory."""
import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory, Spell
from network_context import GameContext


def _make_test_inventory() -> Inventory:
    """Build a random inventory for display testing."""
    inv = Inventory(capacity=14)

    weapons = ['Shortsword', 'Battle Axe', 'Longbow', 'Dagger', 'War Hammer']
    armors  = ['Chain Mail', 'Leather Armor', 'Tower Shield', 'Ring Mail']
    foods   = ['Dried Beef', 'Hard Biscuit', 'Salted Pork', 'Trail Mix']
    drinks  = ['Ale', 'Water Flask', 'Healing Draught']
    spells  = ['Fireball', 'Lightning Bolt', 'Cure Light Wounds', 'Detect Magic']
    misc    = ['Rope (50 ft)', 'Torch', 'Lockpick Set', 'Map Fragment']

    pool = (
        [(n, ItemCategory.WEAPON)   for n in random.sample(weapons, k=random.randint(1, 2))]
      + [(n, ItemCategory.ARMOR)    for n in random.sample(armors,  k=random.randint(0, 2))]
      + [(n, ItemCategory.FOOD)     for n in random.sample(foods,   k=random.randint(1, 3))]
      + [(n, ItemCategory.DRINK)    for n in random.sample(drinks,  k=random.randint(0, 2))]
      + [(n, ItemCategory.ITEM)     for n in random.sample(misc,    k=random.randint(0, 2))]
    )
    random.shuffle(pool)

    for i, (name, cat) in enumerate(pool, start=1):
        item = Item(id_number=i, name=name, category=cat)
        qty  = random.randint(1, 3) if cat in (ItemCategory.FOOD, ItemCategory.DRINK) else 1
        inv.add(item, quantity=qty)

    # Always add at least one spell
    effect_types = list('SWDCEIPTMURLGA')
    spell_name   = random.choice(spells)
    max_ch       = random.randint(3, 10)
    charges      = random.randint(0, max_ch)
    cast_chance  = random.choice([30, 40, 50, 60, 70, 80, 90])
    spell = Spell(
        id_number        = 90,
        name             = spell_name,
        charges          = charges,
        max_charges      = max_ch,
        cast_chance      = cast_chance,
        effect_type      = random.choice(effect_types),
        effect_magnitude = random.randint(1, 5),
    )
    inv.add(spell, charges=charges)

    # Maybe add a bag of holding with a couple of items inside
    if random.random() > 0.4:
        bag = Item(id_number=99, name='Bag of Holding', category=ItemCategory.CONTAINER, capacity=5)
        inv.add(bag)
        bag_entry = inv.find(item_id=99)[0]
        for j, name in enumerate(random.sample(misc, k=random.randint(1, 2)), start=100):
            sub = Item(id_number=j, name=name, category=ItemCategory.ITEM)
            bag_entry.contents.add(sub)

    return inv


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
        max_ch      = getattr(entry.item, 'max_charges', 0)
        charge_pct  = int(entry.charges / max_ch * 100) if max_ch else 0
        cast_chance = getattr(entry.item, 'cast_chance', None)
        cast_str    = f', cast: {cast_chance}%' if cast_chance else ''
        charges_str = f' [{entry.charges}/{max_ch} charges, {charge_pct}%{cast_str}]'
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
            ('inv',          'List all items together'),
            ('inv cat',      'List items grouped by category'),
            ('inv #test',    'Fill with random items and list flat'),
            ('inv #test cat','Fill with random items and list by category'),
        ],
        examples = [
            ('inv',          'Show flat inventory list'),
            ('inv cat',      'Show inventory sorted by type'),
            ('inv #test cat','Test categorized display with random items'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, switches = self.parse_args(*args)

        testing     = '#test' in switches
        categorized = bool(args) and args[0].lower() in ('cat', 'c', 'categorized')

        if testing:
            inventory = _make_test_inventory()
            capacity  = inventory.capacity
        else:
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
