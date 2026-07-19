#!/usr/bin/env python3
"""One-off: create a single admin account named 'tester' (password
'puppy123') for manually trying out text_editor.py's news post/edit flow
against a locally-running server. Mirrors setup_bot_accounts.py's
make_account() but for one plain account, not the bot-demo fixtures.

Run from anywhere:
    .venv/bin/python tools/make_test_admin.py
"""
import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

from base_classes import Gender, PlayerClass
from flags import PlayerFlags
from player import Player

import net_common
net_common.run_server_dir = str(_SERVER_DIR / 'run' / 'server')

_USER_DIR = _SERVER_DIR / 'run' / 'server' / 'net'
_NAME = 'tester'
_PASSWORD = 'puppy123'

player = Player(id=_NAME, name=_NAME, char_class=PlayerClass.FIGHTER, gender=Gender.MALE,
                 map_level=1, map_room=1)
player.set_flag(PlayerFlags.ADMIN)
player.unsaved_changes = True
ok = player.save(force=True)
if not ok:
    print(f'FAILED to save {_NAME}')
    sys.exit(1)

_USER_DIR.mkdir(parents=True, exist_ok=True)
(_USER_DIR / f'login-{_NAME}.json').write_text(
    json.dumps({'password': net_common.hash_password(_PASSWORD)}, indent=2)
)
print(f"Created '{_NAME}' (admin) -- password {_PASSWORD!r}")
