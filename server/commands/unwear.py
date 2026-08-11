"""commands/unwear.py — UNWEAR: take off equipped armor and/or a shield.

New in TADA, added alongside the 2026-08-08 per-item durability redesign
(commands/wear.py, commands/use.py): equipping is now non-consuming, so
there needs to be a way to take a piece back off. Direct sibling of
commands/unready.py (the weapon equivalent, name='unready', aliases=
['unwield']) -- same shape, but this slot has two independent halves
(armor and shield) instead of one, so a bare `unwear` has to disambiguate
when both are worn, where UnreadyCommand never had to.

The item itself is never touched -- it just stops being active_armor_id/
active_shield_id and stays in the pack at whatever condition it was last
at. player.armor/player.shield get zeroed via player.refresh_equipped_
rating() (equipped_entry() returning None covers "nothing here" the same
way it does everywhere else this pass touches).
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from player import equipped_entry, refresh_equipped_rating

_SLOT_LABEL = {'armor': 'armor', 'shield': 'shield'}


def _worn_slots(player) -> list[str]:
    """Slots ('armor'/'shield') that currently have something equipped."""
    return [slot for slot in ('armor', 'shield') if equipped_entry(player, slot) is not None]


async def _remove_slot(ctx: GameContext, player, slot: str) -> None:
    entry = equipped_entry(player, slot)
    if entry is None:
        await ctx.send(f'You are not wearing any {_SLOT_LABEL[slot]}.')
        return
    name = getattr(entry.item, 'name', slot)
    setattr(player, f'active_{slot}_id', None)
    refresh_equipped_rating(player, slot)
    player.unsaved_changes = True
    await ctx.send(f'You take off the {name}.')


class UnwearCommand(Command):
    name    = 'unwear'
    aliases = ['remove', 'doff']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Take off equipped armor or a shield.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('unwear',        'Take off armor/shield (asks which if both are worn)'),
            ('unwear armor',  'Take off your armor'),
            ('unwear shield', 'Take off your shield'),
        ],
        examples = [
            ('unwear',        "UNWEAR (also 'remove'/'doff') takes off equipped armor "
                               "and/or a shield -- the item itself isn't lost or "
                               "damaged by this, it just stops being equipped and stays "
                               "in your pack. With both slots worn and no argument, it "
                               "asks which one you mean."),
            ('unwear shield', 'Naming a slot ("armor" or "shield") skips the question '
                               'and takes off just that one.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player

        if args:
            pattern = ' '.join(args).lower()
            slot = next((s for s in ('armor', 'shield') if pattern.startswith(s)), None)
            if slot is None:
                # Fall back to matching the currently-worn item's own name,
                # e.g. "unwear leather armor" / "unwear small shield".
                for s in ('armor', 'shield'):
                    entry = equipped_entry(player, s)
                    if entry and pattern in (getattr(entry.item, 'name', '') or '').lower():
                        slot = s
                        break
            if slot is None:
                await ctx.send(f'You are not wearing anything matching "{" ".join(args)}".')
                return CommandResult.ok()
            await _remove_slot(ctx, player, slot)
            return CommandResult.ok()

        worn = _worn_slots(player)
        if not worn:
            await ctx.send('You are not wearing any armor or a shield.')
            return CommandResult.ok()
        if len(worn) == 1:
            await _remove_slot(ctx, player, worn[0])
            return CommandResult.ok()

        raw = await ctx.prompt('Take off which (armor/shield, Enter to cancel)')
        if not raw or not raw.strip():
            return CommandResult.ok()
        slot = next((s for s in ('armor', 'shield') if s.startswith(raw.strip().lower())), None)
        if slot is None:
            await ctx.send("That's not armor or a shield.")
            return CommandResult.ok()
        await _remove_slot(ctx, player, slot)
        return CommandResult.ok()
