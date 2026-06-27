"""presence.py — Virtual-location occupancy for non-room areas.

Areas currently using this:
    'elevator' — elevator car (shoppe/elevator.py)
    'shoppe'   — merchant annex (shoppe/main.py)
    'bar'      — Wall Bar & Grill (future)

Usage pattern
-------------
    from presence import enter_area, leave_area, broadcast_area

    async def main(ctx):
        player_name = ctx.player.name
        await enter_area(ctx, 'shoppe')
        try:
            ...interaction loop...
        finally:
            await leave_area(ctx, 'shoppe')
"""
import asyncio
import logging

log = logging.getLogger(__name__)


def occupants(server, area: str) -> list:
    """Return all server-side clients currently in *area*."""
    return [c for c in server.clients.values()
            if getattr(c, 'virtual_location', None) == area]


def others_present(ctx, area: str) -> list[str]:
    """Return names of other players in *area*, excluding the caller."""
    names = []
    for client in occupants(ctx.server, area):
        if client is ctx.client:
            continue
        player = getattr(getattr(client, 'ctx', None), 'player', None)
        name   = getattr(player, 'name', None)
        if name:
            names.append(name)
    return names


async def broadcast_area(ctx, area: str, message: str) -> None:
    """Send *message* to every occupant of *area* except the sender."""
    for client in occupants(ctx.server, area):
        if client is ctx.client:
            continue
        peer_ctx = getattr(client, 'ctx', None)
        if peer_ctx:
            try:
                await peer_ctx.send(message)
            except Exception:
                log.warning('presence.broadcast_area: send failed for %s', client)


async def broadcast_open_room(ctx, message: str) -> None:
    """Send *message* to players in the same map room who are NOT in any virtual sub-area.

    Use this for entranceway events (e.g. "X steps up to the elevator") that
    should be visible to players standing in the open room but not to those
    already inside a sub-area (elevator, shoppe, bar, etc.).
    """
    my_room = getattr(ctx.client, 'room', None)
    for client in ctx.server.clients.values():
        if client is ctx.client:
            continue
        if getattr(client, 'room', None) != my_room:
            continue
        if getattr(client, 'virtual_location', None) is not None:
            continue
        peer_ctx = getattr(client, 'ctx', None)
        if peer_ctx:
            try:
                await peer_ctx.send(message)
            except Exception:
                log.warning('presence.broadcast_open_room: send failed for %s', client)


async def enter_area(ctx, area: str) -> None:
    """Mark this client as being in *area* and notify other occupants."""
    ctx.client.virtual_location = area
    name = getattr(ctx.player, 'name', '???')
    await broadcast_area(ctx, area, f'{name} steps into the {area}.')


async def leave_area(ctx, area: str) -> None:
    """Clear this client's virtual location and notify remaining occupants and the open room."""
    ctx.client.virtual_location = None
    name = getattr(ctx.player, 'name', '???')
    await broadcast_area(ctx, area, f'{name} steps out of the {area}.')
    await broadcast_open_room(ctx, f'{name} steps out of the {area}.')
