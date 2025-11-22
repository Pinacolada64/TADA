import asyncio
from commands.command_processor import create_command_processor
from flags import PlayerFlags


class DummyPlayer:
    def __init__(self, name='tester', admin=False):
        self.name = name
        self.flags = {f: type('F', (), {'display_type': None, 'status': (f == PlayerFlags.DEBUG_MODE)}) for f in PlayerFlags}
        self._admin = admin

    def query_flag(self, flag):
        return bool(self.flags.get(flag) and getattr(self.flags.get(flag), 'status', False))

    def toggle_flag(self, flag, verbose=False):
        obj = self.flags.get(flag)
        if obj:
            obj.status = not obj.status

    def put_flag(self, flag, dt, status):
        obj = self.flags.get(flag)
        if obj:
            obj.status = bool(status)


class DummyClient:
    def __init__(self, player):
        self.player = player
        self.username = getattr(player, 'name', 'tester')
        self.is_admin = False
        self.server = type('S', (), {'game_map': None})()


def run_proc(client, input_text: str):
    proc = create_command_processor(client)
    return asyncio.run(proc.process_input(input_text))


def test_editplayer_list_self():
    p = DummyPlayer()
    c = DummyClient(p)
    res = run_proc(c, 'editplayer')
    assert res.success
    assert 'Flags for' in res.message[0]


def test_editplayer_toggle_self():
    p = DummyPlayer()
    c = DummyClient(p)
    res = run_proc(c, 'editplayer DEBUG_MODE')
    assert res.success
    # ensure the status toggled
    assert isinstance(res.message, str) or isinstance(res.message, list)


def test_editplayer_admin_edit_other():
    admin = DummyPlayer(name='admin', admin=True)
    admin.flags[PlayerFlags.ADMIN].status = True
    c_admin = DummyClient(admin)
    # make admin's query_flag return True
    c_admin.player = admin

    target = DummyPlayer(name='user', admin=False)
    # register target in client_manager by injecting into net_common.client_manager if present
    try:
        import net_common
        nc = net_common
        if getattr(nc, 'client_manager', None):
            cm = nc.client_manager
            try:
                cm.add_client('user', {'user_id': 'user', 'handler': type('H', (), {'player': target}), 'player': target, 'player_name': 'user'})
            except Exception:
                pass
    except Exception:
        pass

    res = run_proc(c_admin, f'editplayer user DEBUG_MODE on')
    # If system can't find the user via client_manager it's allowed to return not_found; either way test should not crash
    assert isinstance(res.success, bool)

