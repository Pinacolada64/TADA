"""bar/fat_olaf.py — Fat Olaf's Servant Trade."""
import logging
from typing import List

from bar.ally_data import AllyFlags, assign_random_statuses, AllyStatus, Ally, load_allies
from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)

_NPC = "Fat Olaf"
_AP = "'"


async def _fat_olaf_menu(ctx: GameContext) -> None:
    return_key = ctx.player.client_settings.return_key
    await ctx.send(
        f"[B]uy, [S]ell, or [M]aintain a servant; "
        f"[?] / [H]: Help; "
        f"[L] / [{return_key}]: Leave"
    )


async def _sell_servant(ctx: GameContext) -> None:
    # TODO: implement sell servant
    await ctx.send(f'{_NPC} shrugs. "Zelling ist not yet available."')


async def _buy_servant(ctx: GameContext, allies: List[Ally]) -> List[Ally]:
    """Let the player browse and purchase a servant. Returns the (possibly updated) ally list."""
    await ctx.send("Buy servant")

    while True:
        servants = filter_allies(allies, AllyStatus.SERVANT)
        if not servants:
            await ctx.send(f'{_NPC} mutters, "Surry, ald solt ut!"')
            return servants

        log.debug("Servants available: %i", len(servants))

        lines = [
            "Servants:", "",
            f"## {'Name'.ljust(20)} {'Strength'.rjust(8)} {'Price'.rjust(5)} Special",
        ]
        for i, servant in enumerate(servants, 1):
            price = servant.strength * 100
            elite_str = ""
            if any(f.value == AllyFlags.ELITE.value for f in servant.flags):
                price *= 2
                elite_str = "[Elite!]"
            lines.append(
                f"{i:>2} {servant.name.ljust(20, '.')} "
                f"{servant.strength:>8} {price:>5,} {elite_str}"
            )
        if not ctx.player.query_flag(PlayerFlags.EXPERT_MODE):
            return_key = ctx.player.client_settings.return_key
            lines.append(f"[{return_key}] = Done")
        await ctx.send(lines)

        # Number selection
        total = len(servants)
        selection = None
        while True:
            raw = await ctx.prompt(f'"Buy vich vun?" (1-{total})')
            if raw is None or raw.strip() == '':
                await ctx.send(f'{_NPC} dismisses you with a wave. "Hokay, vine. See yu later!"')
                # TODO: should return full allies list so status updates are visible next time
                return servants
            try:
                num = int(raw.strip())
                if 1 <= num <= total:
                    selection = num
                    break
            except ValueError:
                pass
            await ctx.send(f'"Whoa, dun{_AP}t hav that many!"')

        chosen_servant = servants[selection - 1]
        price = chosen_servant.strength * 100 * (2 if AllyFlags.ELITE in chosen_servant.flags else 1)

        if ctx.player.subtract_silver(PlayerMoneyTypes.IN_HAND, price):
            await ctx.send(f"You bought {chosen_servant.name}.")
            log.debug("servants before purchase: %i", len(servants))
            chosen_servant.status = AllyStatus.IN_PARTY
            log.debug("%s status → IN_PARTY", chosen_servant.name)
            for i, servant in enumerate(servants):
                if servant == chosen_servant:
                    servants[i] = chosen_servant
                    log.debug("servant %i %s status updated in list", i, chosen_servant.name)
            await ctx.player.party.add(ctx, ctx.player, chosen_servant)
            log.debug("servants after purchase: %i", len(servants))
        else:
            await ctx.send(f'{_NPC} shakes his head. "Yu can{_AP}t afford zat vun, friend."')


def filter_allies(ally_list: List[Ally], filter_by_status: AllyStatus) -> List[Ally]:
    """Return allies matching *filter_by_status* — pure, sync."""
    filtered = [a for a in ally_list if a.status.name == filter_by_status.name]
    log.debug("filter_allies: %i with status %r", len(filtered), filter_by_status.name)
    return filtered


async def main(ctx: GameContext, bar=None) -> None:
    """Fat Olaf's Servant Trade interaction loop."""
    player = ctx.player

    master_ally_list = load_allies()
    master_ally_list = assign_random_statuses(master_ally_list)

    await ctx.send(f"The slave trader {_NPC} sits behind a table, gnawing a chicken leg.")
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send([
            '"I buy und sell servants yu can add tu your party! ',
            'They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"',
        ])
        await _fat_olaf_menu(ctx)

    while True:
        await ctx.send("")
        raw = await ctx.prompt(f'"Vot kin I du ver ya?"')
        if raw is None:
            break

        inp = raw.strip().lower()
        if not inp:
            if player.previous_command:
                inp = player.previous_command
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    await ctx.send(f"(Repeating '{inp}'.)")
            else:
                continue

        command = inp[0]
        player.previous_command = command

        if command in ('l', 'q'):
            await ctx.send(f'"Hokey dokey." {_NPC} watches you leave.')
            break
        elif command in ('?', 'h'):
            await _fat_olaf_menu(ctx)
        elif command == 'b':
            master_ally_list = await _buy_servant(ctx, master_ally_list)
        elif command == 's':
            await _sell_servant(ctx)
        elif command == 'm':
            await ctx.send("[FIXME]: That hasn't been written yet.")
        else:
            await ctx.send(f'{_NPC} looks puzzled. "Vot?"')


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from party import Party

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.name = 'Rulan'
    ctx.player.hit_points = 20
    ctx.player.party = Party()
    ctx.player.client_settings = MagicMock(return_key='Return')
    ctx.player.query_flag = lambda _: False
    ctx.player.subtract_silver = lambda *_: True
    ctx.send = AsyncMock()

    answers = iter(['b', '1', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print("Standalone fat_olaf test complete.")
