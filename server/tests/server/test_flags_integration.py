import json
import os
from pprint import pprint

from player import Player
import flags


def test_flags_save_minimal(tmp_path):
    # ensure run/server directory points to tmp_path/run/server by setting net_common.run_server_dir
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    # create player and manipulate flags
    p = Player(name='flagtester', id='flagtester1')
    # Use Player delegators (thin wrappers) -- each returns (new_state, message)
    assert p.set_flag(flags.PlayerFlags.ADMIN)[0] is True
    assert p.query_flag(flags.PlayerFlags.ADMIN) is True
    assert p.toggle_flag(flags.PlayerFlags.ADMIN)[0] is False
    assert p.query_flag(flags.PlayerFlags.ADMIN) is False
    assert p.clear_flag(flags.PlayerFlags.ADMIN)[0] is False
    assert p.query_flag(flags.PlayerFlags.ADMIN) is False

    # set another flag
    p.set_flag(flags.PlayerFlags.DEBUG_MODE)

    # Save the player
    saved = p.save(force=True)
    assert saved is True

    path = p._json_path(p.id)
    assert os.path.exists(path)

    with open(path, 'r') as f:
        data = json.load(f)
        pprint(data)

    # flags should be a mapping of string -> {name,status}
    assert 'flags' in data
    flags_map = data['flags']
    assert isinstance(flags_map, dict)
    # keys must be strings (flag names)
    for k in list(flags_map.keys())[:10]:
        assert isinstance(k, str)
    # values must only contain name and status
    for v in flags_map.values():
        assert set(v.keys()) <= {'name', 'status'}
        assert isinstance(v['status'], bool)

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass

