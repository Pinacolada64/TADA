"""guild_hq/state.py — Per-guild persistent state (treasury, lockers, chalkboard, log)."""
import json
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

# SPUR locker capacities
ITEM_LOCKER_MAX  = 5   # SPUR: if xv>4 "no more room"
FOOD_LOCKER_MAX  = 8   # SPUR: if xv>7 "pantry is full"

# Short keys used in filenames and SPUR zy$ variable
GUILD_KEYS = ('CLAW', 'SWORD', 'FIST')

_EMPTY_STATE = {
    'treasury':    0,
    'item_locker': [],   # list of item dicts {id, name, price, category}
    'food_locker': [],   # list of food dicts {id, name, price, kind}
    'weapons_box': None, # weapon dict or null
    'chalkboard':  {'author': '', 'message': ''},
    'log':         [],   # list of log strings, newest last
}


def _state_path(guild_key: str) -> str:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    if base is None:
        base = './run/server'
    return os.path.join(str(base), f'guild-{guild_key.lower()}.json')


def load(guild_key: str) -> dict:
    """Load guild state from disk; returns a fresh default dict if missing."""
    path = _state_path(guild_key)
    try:
        with open(path) as fh:
            data = json.load(fh)
        # Fill in any keys added since the file was created
        for k, v in _EMPTY_STATE.items():
            data.setdefault(k, v)
        return data
    except FileNotFoundError:
        return dict(_EMPTY_STATE)
    except Exception:
        log.exception('guild_hq.state.load failed for %s', guild_key)
        return dict(_EMPTY_STATE)


def save(guild_key: str, state: dict) -> None:
    """Write guild state to disk."""
    path = _state_path(guild_key)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            json.dump(state, fh, indent=2)
    except Exception:
        log.exception('guild_hq.state.save failed for %s', guild_key)


def add_log(state: dict, player_name: str, action: str, detail: str) -> None:
    """Append a transaction log entry (SPUR: add.lg subroutine)."""
    ts  = datetime.now().strftime('%Y-%m-%d %H:%M')
    state['log'].append(f'{ts}  {player_name} {action} {detail}')
    # Keep the 100 most recent entries so the file doesn't grow forever
    state['log'] = state['log'][-100:]
