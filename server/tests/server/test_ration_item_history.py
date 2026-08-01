"""tests/server/test_ration_item_history.py

Coverage for Player.ration_history / Player.item_history -- the port of
SPUR's xo/xo$ (rations, 20-entry ring buffer) and xt/xt$ (items/weapons,
60-entry ring buffer), documented in
../../../programming-notes/spur-variables.md.

These replace the old single `picked_up_items` list, which was wrong in
two ways: it never reset (SPUR's xo$/xt$ are reset every login --
SPUR.LOGON.S:198 `xo=xf:xo$=xf$`, SPUR.LOGON.S:208 `xt$="":xt=0`) and it
had no cap (SPUR's ring buffers evict the oldest entry once full, so an
old pickup eventually cycles out and the room's copy can respawn).
"""
from __future__ import annotations

from player import Player


# ---------------------------------------------------------------------------
# Ring-buffer append/eviction
# ---------------------------------------------------------------------------

def test_ration_history_caps_at_20_and_evicts_oldest():
    p = Player(name='Rulan')
    for item_id in range(1, 25):
        p.record_ration_pickup(item_id)

    assert len(p.ration_history) == 20
    # Oldest four (1-4) evicted; 5-24 remain, in pickup order.
    assert p.ration_history == list(range(5, 25))


def test_item_history_caps_at_60_and_evicts_oldest():
    p = Player(name='Rulan')
    for item_id in range(1, 65):
        p.record_item_pickup(item_id)

    assert len(p.item_history) == 60
    assert p.item_history == list(range(5, 65))


def test_ration_and_item_history_are_independent():
    p = Player(name='Rulan')
    p.record_ration_pickup(5)
    p.record_item_pickup(5)

    assert p.ration_history == [5]
    assert p.item_history == [5]


def test_repeated_pickup_is_deduplicated():
    """Unlike SPUR's xo$/xt$ (which append unconditionally on every
    pickup), this port dedupes: picking the same ration up twice (e.g.
    after dropping and re-getting it) shouldn't burn two ring-buffer
    slots for one item."""
    p = Player(name='Rulan')
    p.record_ration_pickup(7)
    p.record_ration_pickup(7)

    assert p.ration_history == [7]


# ---------------------------------------------------------------------------
# Login reset / reseed (SPUR.LOGON.S:198, :208)
# ---------------------------------------------------------------------------

def test_item_history_resets_to_empty_on_relogin(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    original = Player(id='histtest', name='histtest')
    original.record_item_pickup(11)
    original.record_item_pickup(12)
    assert original.save(force=True)

    relogged = Player(name='histtest', id='histtest')
    assert relogged.item_history == []


def test_ration_history_reseeds_from_carried_rations_on_relogin(tmp_path):
    """SPUR.LOGON.S:198 `xo=xf:xo$=xf$` replaces the ration ring buffer
    with whatever rations are currently carried, on top of (not merged
    with) whatever pickup history was saved -- so a still-carried ration
    stays suppressed from the room description even once its original
    pickup event has aged out of the 20-entry buffer."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from inventory import Inventory
    from items import Item, ItemCategory

    original = Player(id='reseedtest', name='reseedtest')
    original.inventory = Inventory(capacity=10)
    original.inventory.add(Item(id_number=5, name='LOAF OF BREAD',
                                 category=ItemCategory.FOOD, kind='food'))
    original.inventory.add(Item(id_number=12, name='MINERAL WATER',
                                 category=ItemCategory.DRINK, kind='drink'))
    # Pickup history from a prior session that should be discarded, not merged.
    original.ration_history = [99]
    assert original.save(force=True)

    relogged = Player(name='reseedtest', id='reseedtest')
    assert sorted(relogged.ration_history) == [5, 12]
    assert 99 not in relogged.ration_history


def test_ration_history_empty_when_no_rations_carried_on_relogin(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from inventory import Inventory

    original = Player(id='norationtest', name='norationtest')
    original.inventory = Inventory(capacity=10)
    original.record_ration_pickup(3)
    assert original.save(force=True)

    relogged = Player(name='norationtest', id='norationtest')
    assert relogged.ration_history == []


# ---------------------------------------------------------------------------
# Respawn after eviction (integration through commands.get._room_available_items)
# ---------------------------------------------------------------------------

def test_ration_respawns_once_evicted_from_ring_buffer():
    """Once a ration's pickup record ages out of the 20-entry buffer (and
    it isn't currently carried), the room offers it again -- matching
    SPUR's ring-buffer behavior rather than a permanent ban."""
    from unittest.mock import MagicMock
    from commands.get import _room_available_items
    from inventory import Inventory

    room = MagicMock()
    room.item = 0
    room.weapon = 0
    room.food = 1
    room.monster = 0

    server = MagicMock()
    server.items = []
    server.weapons = []
    server.rations = [{'number': 1, 'id_number': 1, 'name': 'LOAF OF BREAD', 'kind': 'food'}]
    server.game_map.get_room.return_value = room

    player = Player(name='Rulan')
    player.inventory = Inventory(capacity=10)
    # Fill the ration ring buffer with 20 unrelated pickups so item 1's
    # original pickup (if it were still in there) would have aged out.
    for other_id in range(100, 120):
        player.record_ration_pickup(other_id)

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.client.room = 1

    available = _room_available_items(ctx)
    assert any(name == 'LOAF OF BREAD' for name, _entry, _remove in available)


def test_ration_suppressed_while_still_in_ring_buffer():
    from unittest.mock import MagicMock
    from commands.get import _room_available_items
    from inventory import Inventory

    room = MagicMock()
    room.item = 0
    room.weapon = 0
    room.food = 1
    room.monster = 0

    server = MagicMock()
    server.items = []
    server.weapons = []
    server.rations = [{'number': 1, 'id_number': 1, 'name': 'LOAF OF BREAD', 'kind': 'food'}]
    server.game_map.get_room.return_value = room

    player = Player(name='Rulan')
    player.inventory = Inventory(capacity=10)
    player.record_ration_pickup(1)

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.client.room = 1

    available = _room_available_items(ctx)
    assert available == []
