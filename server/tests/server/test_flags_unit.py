import os
import json
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import flags
from flags import PlayerFlags
from player import Player


def test_ensure_player_flags_returns_enum_keys():
    p = Player(name='u1', id='u1')
    fm = flags.ensure_player_flags(p)
    # mapping should contain PlayerFlags keys (enums). Checked against
    # flags.PlayerFlags (module attribute, always current) rather than the
    # top-level `from flags import PlayerFlags` binding above -- tests/admin/
    # test_reload.py's importlib.reload(flags) mid-suite mints a new
    # PlayerFlags class, and this module's own import captured the old one
    # at collection time, so a plain isinstance() check against it would be
    # order-dependent (same hazard documented in commands/reload.py).
    assert any(isinstance(k, flags.PlayerFlags) for k in fm.keys())
    # default ADMIN flag exists
    assert PlayerFlags.ADMIN in fm
    assert hasattr(fm[PlayerFlags.ADMIN], 'status')


def test_set_and_clear_create_expected_entries():
    p = Player(name='u2', id='u2')
    # clear first (creates entry with False)
    res = flags.clear_flag(p, PlayerFlags.ADMIN)
    assert res is False
    assert flags.query_flag(p, PlayerFlags.ADMIN) is False
    # set it
    res2 = flags.set_flag(p, PlayerFlags.ADMIN)
    assert res2 is True
    assert flags.query_flag(p, PlayerFlags.ADMIN) is True


def test_toggle_on_missing_sets_true_and_toggle_flips():
    p = Player(name='u3', id='u3')
    # ensure removed if present
    # create empty flags mapping
    p.flags = {}
    t1 = flags.toggle_flag(p, PlayerFlags.ARCHITECT)
    assert t1 is True
    assert flags.query_flag(p, PlayerFlags.ARCHITECT) is True
    t2 = flags.toggle_flag(p, PlayerFlags.ARCHITECT)
    assert t2 is False
    assert flags.query_flag(p, PlayerFlags.ARCHITECT) is False


def test_serialize_returns_string_keys_and_minimal_values(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    p = Player(name='u4', id='u4')
    # set several flags
    flags.set_flag(p, PlayerFlags.ADMIN)
    flags.set_flag(p, PlayerFlags.DEBUG_MODE)
    # intentionally add a non-enum key to simulate legacy data
    p.flags['legacy'] = type('L', (), {'name': 'legacy', 'status': True})()
    ser = flags.serialize_flags_for_save(p)
    # keys are strings
    assert all(isinstance(k, str) for k in ser.keys())
    # values are dicts with only name and status
    for v in ser.values():
        assert set(v.keys()) <= {'name', 'status'}
        assert isinstance(v['status'], bool)
    # save file check
    saved = p.save(force=True)
    assert saved is True
    path = p._json_path(p.id)
    with open(path, 'r') as f:
        data = json.load(f)
    assert isinstance(data.get('flags'), dict)
    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass


def test_player_delegator_accepts_optional_status():
    p = Player(name='u5', id='u5')
    # set_flag always turns on; its optional second param is verbose (a
    # message flag), not a desired on/off state -- clear_flag is the way
    # to turn a flag off.
    p.set_flag(PlayerFlags.ADMIN)
    assert p.query_flag(PlayerFlags.ADMIN) is True
    # be explicit and clear using optional verbose param
    p.clear_flag(PlayerFlags.ADMIN, False)
    assert p.query_flag(PlayerFlags.ADMIN) is False
    # p.clear_flag works too
    p.set_flag(PlayerFlags.ADMIN)
    p.clear_flag(PlayerFlags.ADMIN)
    assert p.query_flag(PlayerFlags.ADMIN) is False

