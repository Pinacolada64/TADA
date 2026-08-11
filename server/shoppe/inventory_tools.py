"""shoppe/inventory_tools.py — Merchant Shoppe pack management.

Two entry points, both reachable from anywhere in the Shoppe (registered
directly on shoppe/main.py's top-level menu, not buried in one specific
stall, since managing your own pack isn't tied to any single shop):

  [I] Inventory — view your pack, sort it by category, or drop (permanently
      discard) an item to free a slot.
  [T] Transfer  — hand an item off to a party ally or your horse's
      saddlebags, to work around the base pack's tight slot limit. Ryan's
      request: only offer [T] at all once there's actually somewhere to
      send an item (see has_transfer_targets()).

Item movement here mirrors commands/give.py's ally branch (weapon/armor/
shield unworn bookkeeping, saddlebag capacity via _mount_capacity()) rather
than reinventing it, but trimmed to self -> own-ally/mount only -- no
player/monster targets, since this isn't a combat or trade interaction.
"""
from bar.allies import purchased_allies
from bar.ally_data import AllyFlags, add_ally_item
from commands.give import _mount_capacity
from commands.inv import _CATEGORY_ORDER, _format_entry, _container_lines
from network_context import GameContext

_CATEGORY_ORDER_STRS = [str(c) for c in _CATEGORY_ORDER]


def has_transfer_targets(player) -> bool:
    """Gate for showing [T]ransfer at all -- a lone adventurer with no
    party and no horse has nobody to hand items off to."""
    return bool(purchased_allies(player))


async def inventory_main(ctx: GameContext) -> None:
    player = ctx.player
    inv = getattr(player, 'inventory', None)
    if inv is None:
        await ctx.send('You have no pack to manage.')
        return

    while True:
        capacity = getattr(player, 'max_inventory_size', None)
        cap_str = f'/{capacity}' if capacity else ''
        lines = ['', f'Your pack ({len(inv)}{cap_str} slots used):', '']
        if len(inv) == 0:
            lines.append('  (nothing)')
        else:
            for index, entry in enumerate(inv, 1):
                lines.append(_format_entry(entry, index))
                lines.extend(_container_lines(entry))
        lines += ['', '[S]ort by category, [D]rop an item, [Enter] to leave', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Pack')
        if raw is None or not raw.strip():
            return
        cmd = raw.strip().lower()[:1]

        if cmd == 's':
            inv.sort(_CATEGORY_ORDER_STRS)
            player.unsaved_changes = True
            await ctx.send('Sorted by category.')
        elif cmd == 'd':
            await _drop_item(ctx, player, inv)
        else:
            await ctx.send('Unrecognized. [S]ort, [D]rop, or Enter to leave.')


async def _drop_item(ctx: GameContext, player, inv) -> None:
    if len(inv) == 0:
        await ctx.send('Nothing to drop.')
        return

    entries = list(inv)
    raw = await ctx.prompt(f'Drop which item (1-{len(entries)}, Enter to cancel)')
    if raw is None or not raw.strip():
        return
    try:
        choice = int(raw.strip()) - 1
        if not (0 <= choice < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return

    entry = entries[choice]
    name = getattr(entry.item, 'name', 'item')
    confirm = await ctx.prompt(f'Discard the {name} for good? This cannot be undone (y/N)')
    if not confirm or confirm.strip().lower() not in ('y', 'yes'):
        await ctx.send('Never mind.')
        return

    from player import unworn_if_given_away, unworn_notice
    unworn_slot = unworn_if_given_away(player, entry.item)
    inv.remove(entry.item, quantity=entry.quantity)
    player.unsaved_changes = True
    await ctx.send(f'You discard the {name}.')
    if not player.is_expert:
        notice = unworn_notice(unworn_slot, name)
        if notice:
            await ctx.send(notice)


async def transfer_main(ctx: GameContext) -> None:
    player = ctx.player
    inv = getattr(player, 'inventory', None)
    allies = purchased_allies(player)
    if not allies:
        await ctx.send('You have no party members or horse to send anything to.')
        return
    if inv is None or len(inv) == 0:
        await ctx.send('You have nothing to transfer.')
        return

    entries = list(inv)
    lines = ['', 'Your pack:', '']
    for index, entry in enumerate(entries, 1):
        lines.append(_format_entry(entry, index))
    lines += ['', '[Enter] to cancel']
    await ctx.send(lines)

    raw = await ctx.prompt(f'Transfer which item (1-{len(entries)}, Enter to cancel)')
    if raw is None or not raw.strip():
        return
    try:
        choice = int(raw.strip()) - 1
        if not (0 <= choice < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return
    entry = entries[choice]
    item = entry.item
    name = getattr(item, 'name', 'item')

    lines = ['', 'Send to:', '']
    for i, ally in enumerate(allies, 1):
        lines.append(f'  {i}. {ally.name}')
    lines += ['', '[Enter] to cancel']
    await ctx.send(lines)

    raw = await ctx.prompt(f'Recipient (1-{len(allies)}, Enter to cancel)')
    if raw is None or not raw.strip():
        return
    try:
        r_choice = int(raw.strip()) - 1
        if not (0 <= r_choice < len(allies)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return
    ally = allies[r_choice]

    if not hasattr(ally, 'items') or ally.items is None:
        ally.items = []

    from commands.use import _SADDLEBAGS_ID
    if (getattr(item, 'id_number', None) == _SADDLEBAGS_ID
            and AllyFlags.MOUNT not in (ally.flags or [])):
        await ctx.send(f"{ally.name} has no back to strap them to -- saddlebags are for a mount.")

    capacity = _mount_capacity(ally)
    if capacity is not None:
        if capacity == 0:
            await ctx.send(f'{ally.name} has nowhere to carry it -- needs saddlebags first.')
            return
        if len(ally.items) >= capacity:
            await ctx.send(f"{ally.name}'s saddlebags are full.")
            return

    from player import unworn_if_given_away, unworn_notice
    unworn_slot = unworn_if_given_away(player, item)
    if not inv.remove(item, quantity=1):
        await ctx.send("You don't have that anymore.")
        return

    add_ally_item(ally, item, quantity=1)
    player.unsaved_changes = True
    await ctx.send(f'You hand the {name} to {ally.name}.')
    if not player.is_expert:
        notice = unworn_notice(unworn_slot, name)
        if notice:
            await ctx.send(notice)
