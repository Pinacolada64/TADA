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
    inv.add(spell)

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


def _format_entry(entry: InventoryEntry, index: int, worn: bool = False) -> str:
    name  = getattr(entry.item, 'name', '?') or '?'
    flags = getattr(entry.item, 'flags', None)
    # Ammo (shoppe/ollys.py): loose boxes show per-box rounds and how many
    # boxes are stacked ("[4 rounds x6]"); a reusable carrier (flags has
    # 'capacity') shows how full it currently is instead of a box count,
    # since it's always a single item, never stacked.
    is_ammo = isinstance(flags, dict) and 'rounds' in flags and 'used_with' in flags
    if is_ammo:
        qty = '   '
        if 'capacity' in flags:
            ammo_str = f" [{flags['rounds']}/{flags['capacity']} rounds]"
        else:
            ammo_str = f" [{flags['rounds']} rounds x{entry.quantity}]"
    else:
        qty = f'{entry.quantity}x ' if entry.quantity > 1 else '   '
        ammo_str = ''
    charges = getattr(entry.item, 'charges', None)
    if charges is not None:
        max_ch      = getattr(entry.item, 'max_charges', 0)
        charge_pct  = int(charges / max_ch * 100) if max_ch else 0
        cast_chance = getattr(entry.item, 'cast_chance', None)
        cast_str    = f', cast: {cast_chance}%' if cast_chance else ''
        charges_str = f' [{charges}/{max_ch} charges, {charge_pct}%{cast_str}]'
    else:
        charges_str = ''
    if entry.is_container and entry.contents:
        n   = len(entry.contents)
        cap = getattr(entry.item, 'capacity', '?')
        container_str = f' ({n}/{cap} items)'
    else:
        container_str = ''
    # Worn armor/shield (2026-08-08 per-item durability redesign): mirrors
    # the ammo carrier's [cur/cap rounds] display above, but for the
    # equipped piece's real .condition -- see player.py's equipped_entry().
    # "left" (not "worn") to match Ryan's own framing -- "percentage
    # left" -- and avoid "90% worn" reading backwards as "90% worn out".
    condition = getattr(entry.item, 'condition', None)
    worn_str = f' [{condition}% left]' if worn and condition is not None else ''
    return f'{index:>3}. {qty}{name}{ammo_str}{charges_str}{container_str}{worn_str}'


def _container_lines(entry: InventoryEntry) -> list[str]:
    if not entry.is_container or not entry.contents:
        return []
    return [
        f'         > {getattr(sub.item, "name", "?")}'
        + (f' x{sub.quantity}' if sub.quantity > 1 else '')
        for sub in entry.contents
    ]


def _ally_inventory_lines(player) -> list[str]:
    """New in TADA: INV previously only ever showed the player's own
    inventory -- allies carrying gifted items (ally.items, see
    commands/give.py) were invisible here entirely. A mount specifically
    needs AllyFlags.SADDLEBAGS to carry anything at all (commands/
    give.py's _mount_capacity()); other ally types have always been
    unlimited. Ryan's request."""
    from bar.ally_data import AllyFlags
    from bar.allies import owned_allies
    from commands.give import _MOUNT_CAPACITY_WITH_SADDLEBAGS

    lines: list[str] = []
    for ally in owned_allies(player):
        flags = ally.flags or []
        items = getattr(ally, 'items', None) or []

        if AllyFlags.MOUNT in flags and AllyFlags.SADDLEBAGS not in flags:
            lines.append(f'{ally.name}: no saddlebags (nothing carried).')
            lines.append('')
            continue

        cap_str = f'/{_MOUNT_CAPACITY_WITH_SADDLEBAGS}' if AllyFlags.MOUNT in flags else ''
        if not items:
            # A mount reaching this branch always has saddlebags (the
            # "no saddlebags" case above already returned) -- say so
            # explicitly rather than leaving "carrying nothing" to imply
            # it, so equipped-but-empty doesn't read the same as
            # unequipped at a glance. Ryan's request.
            if AllyFlags.MOUNT in flags:
                lines.append(f'{ally.name}: has saddlebags, carrying nothing.')
            else:
                lines.append(f'{ally.name}: carrying nothing.')
            lines.append('')
            continue

        lines.append(f"{ally.name}'s pack ({len(items)}{cap_str} items):")
        for i, entry in enumerate(items, 1):
            lines.append(f'  {_format_entry(entry, i)}')
        lines.append('')
    return lines


class InvCommand(Command):
    name    = 'inv'
    aliases = ['inventory', 'i']
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
            ('inv',          "INV lists what you're carrying. With no argument, it shows "
                              "everything in one flat list, in whatever order you picked "
                              "items up."),
            ('inv cat',      "'cat' regroups the same list under headings -- weapons, "
                              "armor, food, drink, items -- rather than one undivided "
                              "list, handy once you're carrying a lot."),
            ('inv #test cat','#test fills your inventory with a random assortment before '
                              'listing it -- a developer/testing switch for previewing the '
                              "display, not something you'd normally use while playing."),
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

        lines: list[str] = []
        # 2026-08-08 durability redesign: tag whichever entry is currently
        # equipped so its listing shows real condition, not just its name
        # (same active_armor_id/active_shield_id commands/stats.py already
        # keys off of).
        worn_ids = {getattr(ctx.player, 'active_armor_id', None),
                    getattr(ctx.player, 'active_shield_id', None)} - {None}

        if inventory is None or len(inventory) == 0:
            lines.append('You are carrying nothing.')
        else:
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
                        worn = getattr(entry.item, 'id_number', None) in worn_ids
                        lines.append(_format_entry(entry, index, worn=worn))
                        lines.extend(_container_lines(entry))
                        index += 1
                    lines.append('')
                    any_shown = True
                if not any_shown:
                    lines.append('  (nothing)')
            else:
                for index, entry in enumerate(inventory, 1):
                    worn = getattr(entry.item, 'id_number', None) in worn_ids
                    lines.append(_format_entry(entry, index, worn=worn))
                    lines.extend(_container_lines(entry))

        # New in TADA -- allies carrying gifted items were invisible here
        # entirely (see _ally_inventory_lines' docstring). Skipped in
        # #test mode since that's about randomizing the player's own
        # inventory display, not allies.
        if not testing:
            ally_lines = _ally_inventory_lines(ctx.player)
            if ally_lines:
                lines.append('')
                lines.extend(ally_lines)

        await ctx.send(lines)
        return CommandResult.ok()
