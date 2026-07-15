import asyncio

from simple_server import Server
from commands.command_processor import create_command_processor
import net_common


class FakeWriter:
    def __init__(self):
        self.buf = []
    def write(self, data: bytes):
        # store bytes for inspection
        self.buf.append(data)
    async def drain(self):
        await asyncio.sleep(0)
    def get_extra_info(self, key):
        if key == 'peername':
            return ('127.0.0.1', 0)
        return None
    def close(self):
        pass
    async def wait_closed(self):
        await asyncio.sleep(0)


def test_move_broadcasts_and_changes_room():
    s = Server('127.0.0.1', 0)

    class DummyClient:
        pass

    mover = DummyClient()
    mover.server = s
    mover.room = 1
    mover.username = 'Mover'
    mover.addr = ('127.0.0.1', 10001)
    mover.writer = FakeWriter()

    observer = DummyClient()
    observer.server = s
    observer.room = 1
    observer.username = 'Observer'
    observer.addr = ('127.0.0.1', 10002)
    observer.writer = FakeWriter()

    # register in server.clients so broadcast uses them
    s.clients[mover.addr] = mover
    s.clients[observer.addr] = observer

    # also register in global client_manager for room listing functions
    net_common.client_manager.add_client(mover.username, mover)
    net_common.client_manager.add_client(observer.username, observer)

    # create processor for mover
    proc = create_command_processor(mover, context={'client': mover, 'username': mover.username, 'is_authenticated': True})

    # figure an available direction from the room
    exits = s.game_map.rooms[mover.room].exits
    # choose any available single-letter exit
    direction = None
    for d in ['n','s','e','w','u','d']:
        if d in exits and exits[d]:
            direction = d
            break

    if direction is None:
        raise RuntimeError('No exits available in test room; cannot test movement')

    dest = int(exits[direction])

    # run the move via processor
    res = asyncio.run(proc.process_input(direction))

    assert res.success is True
    # mover's room should be updated
    assert mover.room == dest

    # observer should have received at least one write (the announcement)
    assert len(observer.writer.buf) > 0
    # The JSON bytes should contain the observer announcement text
    joined = b' '.join(observer.writer.buf)
    assert bytes(mover.username, 'utf-8') in joined


if __name__ == '__main__':
    test_move_broadcasts_and_changes_room()
    print('PASS: test_move_broadcasts_and_changes_room')

