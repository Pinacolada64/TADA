"""commands/order.py — ORDER: deploy servants as Point Man / Flank Guard / Rear Guard.

Ported from SPUR.MISC2.S's "order" subroutine. The original kept exactly
three fixed servant slots (a1/a2/a3), so "deploying" a servant and "owning"
one were the same act. This port's party is a plain list (see party.py),
but the 3-servant cap is still enforced elsewhere (combat/engine.py's
_mount_slot_available()), so the SPUR shape maps over directly: every
owned servant must end up in exactly one of the three tactical slots, and a
slot can be left NONE if you own fewer than three.

SPUR.MISC4.S's "tactical" subroutine is the payoff this feeds: when a
monster spots the party first, it picks one of the three slots at random
and that servant either shouts a position-flavored warning and holds, or
gets caught off guard and may desert -- an empty slot just means nobody
was there to get caught. That ambush check isn't ported yet (not tracked
in MECHANICS.md), so today ORDER only affects what's shown on the roster
display; see the Help text's note about this.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from bar.ally_data import AllyPosition, AllyStatus
from bar.allies import purchased_allies
from network_context import GameContext

# (display label, prompt label, AllyPosition)
_SLOTS = [
    ('POINT MAN  ', 'Point Man',   AllyPosition.POINT),
    ('FLANK GUARD', 'Flank Guard', AllyPosition.FLANK),
    ('REAR GUARD ', 'Rear Guard',  AllyPosition.REAR),
]


class OrderCommand(Command):
    name    = 'order'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Deploy your servants as Point Man, Flank Guard, or Rear Guard.",
        description = (
            "Shows your current tactical deployment and, if you want to change "
            "it, walks you through re-assigning each of your (up to 3) owned "
            "servants to one of three positions:\n\n"
            "  POINT MAN    -- takes the front of the group\n"
            "  FLANK GUARD  -- watches the side\n"
            "  REAR GUARD   -- covers the group from behind\n\n"
            "Every servant you own has to be placed somewhere before the new "
            "order takes effect; a position can be left NONE if you have "
            "fewer than three servants. In the original SPUR, this mattered "
            "when a monster ambushed the party: whichever slot the danger "
            "fell on decided which servant shouted the warning and had a "
            "chance to hold the line (an empty slot meant nobody was there "
            "to get caught out) -- that ambush check hasn't been ported to "
            "TADA yet, so for now ORDER's positions are a roster/flavor "
            "display rather than something combat reacts to."
        ),
        category = HelpCategory.INTERACTION,
        usage    = [('order', "Review and, optionally, redeploy your servants")],
        examples = [('order', 'See who is Point/Flank/Rear right now')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        allies = [a for a in purchased_allies(player) if a.status == AllyStatus.SERVANT]

        if not allies:
            await ctx.send("You don't have any servants!")
            return CommandResult.ok()

        await self._show_deployment(ctx, allies)

        raw = await ctx.prompt('Do you wish to change this? Y/N')
        if not raw or raw.strip().upper() != 'Y':
            return CommandResult.ok()

        assignment: dict[AllyPosition, object] = {}
        while True:
            remaining = list(allies)
            assignment = {}
            for _label, prompt_label, position in _SLOTS:
                chosen = await self._pick_slot(ctx, prompt_label, remaining)
                assignment[position] = chosen
                if chosen is not None:
                    remaining.remove(chosen)
            if not remaining:
                break
            await ctx.send("You didn't deploy ALL your servants!")

        for a in allies:
            a.position = AllyPosition.EMPTY
        for position, chosen in assignment.items():
            if chosen is not None:
                chosen.position = position

        player.unsaved_changes = True
        await self._show_deployment(ctx, allies)
        return CommandResult.ok()

    async def _show_deployment(self, ctx: GameContext, allies) -> None:
        lines = ['', 'Tactical deployment of servants:']
        for label, _prompt_label, position in _SLOTS:
            occupant = next((a for a in allies if a.position == position), None)
            if occupant:
                lines.append(f'{label}: {occupant.name}, hp = {occupant.hit_points}')
            else:
                lines.append(f'{label}: NONE')
        await ctx.send(lines)

    async def _pick_slot(self, ctx: GameContext, prompt_label: str, remaining: list):
        """Prompt for one servant to fill *prompt_label*'s slot.

        Returns the chosen Ally, or None for "leave empty" (0 or blank).
        """
        if not remaining:
            return None

        lines = ['']
        for i, a in enumerate(remaining, 1):
            lines.append(f'  {i}. {a.name}')
        await ctx.send(lines)

        raw = await ctx.prompt(f'New {prompt_label} (1-{len(remaining)}, 0 for none)')
        if not raw or not raw.strip() or raw.strip() == '0':
            return None
        try:
            idx = int(raw.strip()) - 1
            if not (0 <= idx < len(remaining)):
                raise ValueError
        except ValueError:
            await ctx.send('Enter a number from the list, or 0.')
            return await self._pick_slot(ctx, prompt_label, remaining)
        return remaining[idx]
