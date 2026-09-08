"""commands/take.py — Take an item from a party ally.

Mirrors SPUR.MISC.S TAKE: lists what the ally is carrying, player picks
one item to transfer back to their own inventory.

Syntax:
  take                         list all items across all servants
  take from <ally>             list items that specific ally carries
  take <item> from <ally>      take a specific item directly

TADA extension (JoyfulColor's request): when more than one servant is in
play, bare TAKE follows the item pick with a "give to whom?" step -- pick
another ally and the item goes straight into their pack, skipping the
take-to-yourself-then-give-again shuffle. Picking "yourself" is the
original behaviour. See _reroute_between_allies() for why the ally->ally
hop is a plain cargo move (no auto-ready / auto-wear / ammo-load).
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from bar.ally_data import AllyStatus
from bar.allies import purchased_allies
from inventory_select import gather_items, resolve_or_prompt
from network_context import GameContext


async def _reroute_between_allies(ctx, player, src_ally, dest_ally, entry) -> CommandResult:
    """Hand one unit of *entry*'s item from *src_ally*'s pack straight to
    *dest_ally*'s, without it passing through the player's inventory.

    Deliberately a plain relocation -- no auto-ready, auto-wear or
    ammo-load. Those GIVE side-effects model the *player* equipping an
    ally; shuffling cargo from one ally to another just moves the item.
    READY / UNREADY already operate on either ally's pack
    (inventory_select.gather_items(include_allies=True)), so the player
    wields it from its new owner if they want to.
    """
    from bar.ally_data import add_ally_item
    from commands.give import _mount_capacity

    item  = entry.item
    iname = getattr(item, 'name', 'it')

    capacity = _mount_capacity(dest_ally)
    if capacity is not None:
        if capacity == 0:
            await ctx.send(f'{dest_ally.name} has nowhere to carry it -- needs saddlebags first.')
            return CommandResult.ok()
        if len(dest_ally.items or []) >= capacity:
            await ctx.send(f"{dest_ally.name}'s saddlebags are full.")
            return CommandResult.ok()

    # Take one unit off the source ally (decrement a stack, else drop the entry).
    if getattr(entry, 'quantity', 1) > 1:
        entry.quantity -= 1
    elif entry in src_ally.items:
        src_ally.items.remove(entry)
    add_ally_item(dest_ally, item, quantity=1)
    player.unsaved_changes = True

    pself = getattr(player, 'name', 'Someone')
    await ctx.send(f'{src_ally.name} hands the {iname} to {dest_ally.name}.')
    await ctx.send_room(
        f'{pself} has {src_ally.name} hand the {iname} to {dest_ally.name}.',
        exclude_self=True)
    return CommandResult.ok()


class TakeCommand(Command):
    name    = 'take'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Take an item back from a party ally.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('take',                   'List everything your servants carry'),
            ('take from <ally>',       'List items that ally carries'),
            ('take <item> from <ally>', 'Take a specific item from a named ally'),
        ],
        examples = [
            ('take from batman',       "TAKE retrieves an item you'd previously GIVEn to "
                                        "a servant ally, back into your own inventory -- "
                                        'it only works on servants, not every ally in '
                                        'your party. "take from batman" lists what an '
                                        'ally named Batman is currently carrying.'),
            ('take sword from batman', 'Naming an item skips the listing and takes it '
                                        'directly, if Batman is actually carrying one '
                                        'matching that name.'),
            ('take',                   "With two or more servants, bare TAKE asks who to "
                                        "hand the item to after you pick it -- choose "
                                        "another ally to move it straight across (no need "
                                        "to TAKE it to yourself and GIVE it on), or "
                                        "\"yourself\" to pocket it as before."),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player    = ctx.player
        inventory = getattr(player, 'inventory', None)

        allies = purchased_allies(player)
        active = [a for a in allies if a.status == AllyStatus.SERVANT]

        if not active:
            await ctx.send('You have no servants to take from.')
            return CommandResult.ok()

        # Parse "take <item> from <ally>" or "take from <ally>" or "take"
        arg_list   = list(args)
        item_words = []
        from_words = []
        if 'from' in arg_list:
            fi         = arg_list.index('from')
            item_words = arg_list[:fi]
            from_words = arg_list[fi + 1:]
        else:
            item_words = arg_list

        # Resolve which servant(s) to list from.
        if from_words:
            target = ' '.join(from_words).lower()
            selected = [a for a in active if target in a.name.lower()]
            if not selected:
                await ctx.send(
                    f'No servant named "{" ".join(from_words)}" in your party.')
                return CommandResult.ok()
        else:
            selected = active

        # The item pool = the selected servants' packs, numbered as one
        # list (inventory_select.gather_items; each ItemChoice carries the
        # ally who holds it as .owner).
        choices = gather_items(player, include_player=False,
                               include_allies=True, allies=selected)
        if not choices:
            if from_words:
                await ctx.send(f'{selected[0].name} is not carrying anything.')
            else:
                await ctx.send('Your servants are not carrying anything.')
            return CommandResult.ok()

        choice = await resolve_or_prompt(
            ctx, choices, args=item_words, prompt_text='Take which item',
            label_fn=lambda c: f'{c.name:<24}  (carried by {c.owner_name})',
            list_header='Your servants carry:',
            no_match_msg=lambda q: f'None of your servants are carrying anything matching "{q}".',
        )
        if choice is None:
            return CommandResult.ok()

        src_ally     = choice.owner
        chosen_entry = choice.entry
        iname        = getattr(chosen_entry.item, 'name', 'it')

        # Destination. With another servant available, offer to route the
        # item straight to them (JoyfulColor's shortcut); with only the
        # source servant in play, the sole destination is you -- unchanged.
        others    = [a for a in active if a is not src_ally]
        dest_ally = None                       # None => the player
        if others:
            options = [('yourself', None)] + [(a.name, a) for a in others]
            picked  = await resolve_or_prompt(
                ctx, options, args=[], prompt_text='Give to whom',
                label_fn=lambda o: o[0],
                list_header='Give to whom?',
            )
            if picked is None:
                return CommandResult.ok()
            dest_ally = picked[1]

        if dest_ally is not None:
            return await _reroute_between_allies(
                ctx, player, src_ally, dest_ally, chosen_entry)

        # --- Take it back into your own pack (the original TAKE) ---
        if inventory and inventory.is_full():
            await ctx.send('You cannot carry any more.')
            return CommandResult.ok()

        if chosen_entry in src_ally.items:
            src_ally.items.remove(chosen_entry)
        if inventory:
            inventory.add(chosen_entry.item,
                          quantity=getattr(chosen_entry, 'quantity', 1))
        player.unsaved_changes = True
        await ctx.send(f'{src_ally.name} hands you the {iname}.')
        # This command had no send_room() at all -- bystanders never saw
        # an item change hands from a servant back to the player.
        # Ryan's request.
        pself = getattr(player, 'name', 'Someone')
        await ctx.send_room(
            f'{src_ally.name} hands {iname} to {pself}.', exclude_self=True)
        return CommandResult.ok()
