import json
import os
import types
import pytest

import flags
from player import Player
from flags import PlayerFlags, Flag, FlagDisplayTypes


def test_toggle_and_player_delegator(tmp_path):
    # Create player and ensure initial defaults are set
    p = Player(name='togtest', id='tog1')

    # Using module-level helpers
    assert flags.query_flag(p, PlayerFlags.EXPERT_MODE) in (True, False)
    before = flags.query_flag(p, PlayerFlags.EXPERT_MODE)
    new = flags.toggle_flag(p, PlayerFlags.EXPERT_MODE)
    assert new == (not before)
    # Toggle again -> back
    new2 = flags.toggle_flag(p, PlayerFlags.EXPERT_MODE)
    assert new2 == before

    # Using Player delegator -- each returns (new_state, message)
    p.set_flag(PlayerFlags.DEBUG_MODE)
    assert p.query_flag(PlayerFlags.DEBUG_MODE) is True
    t, _ = p.toggle_flag(PlayerFlags.DEBUG_MODE)
    assert t is False
    c, _ = p.clear_flag(PlayerFlags.DEBUG_MODE)
    assert c is False


def test_serialize_edge_cases_and_save(tmp_path):
    import net_common
    # redirect run dir for save
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    p = Player(name='sertest', id='ser1')

    # Manually set a mix of value types in p.flags to simulate older or malformed data
    weird_map = {}
    # valid Flag instance
    weird_map[PlayerFlags.ADMIN] = Flag(name=PlayerFlags.ADMIN.value, display_type=FlagDisplayTypes.YESNO, status=True)
    # numeric value
    weird_map['weird_numeric'] = 123
    # object without attrs
    weird_map['obj'] = object()
    # value with .status attribute but no .name
    class Minimal:
        def __init__(self, s):
            self.status = s
    weird_map['min'] = Minimal(True)

    p.flags = weird_map

    ser = flags.serialize_flags_for_save(p)
    # Should include 'Administrator' and string keys
    assert 'Administrator' in ser
    assert 'weird_numeric' in ser
    assert 'obj' in ser
    assert 'min' in ser
    # values only contain name and status
    for v in ser.values():
        assert set(v.keys()) <= {'name', 'status'}
        assert isinstance(v['status'], bool)

    # Save and read back file to ensure flags written as simple map
    saved = p.save(force=True)
    assert saved is True
    path = p._json_path(p.id)
    with open(path, 'r') as f:
        data = json.load(f)
    assert isinstance(data.get('flags'), dict)
    for k, v in data.get('flags').items():
        assert set(v.keys()) <= {'name', 'status'}
        assert isinstance(v['status'], bool)

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass

