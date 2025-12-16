import sys, asyncio, json
sys.path.insert(0, '..')
from simple_server import Server
from commands.movement import MoveCommand
from commands.teleport import TeleportCommand
from shoppe import elevator
from player import Player
import flags

async def run():
    server = Server('127.0.0.1', 0)
    server.game_map.rooms = {
        1: type('R',(),{'number':1,'name':'R1','desc':'r1','exits':{'e':2}})(),
        2: type('R',(),{'number':2,'name':'R2','desc':'r2','exits':{}})()
    }
    class C: pass
    client = C(); client.server = server; client.room = 1; client.username = 'smoke'; client.addr=('127.0.0.1',12345)
    p = Player(name='smoke', id='smoke')
    client.player = p

    print('Initial:', client.room, p.map_room)

    mv = MoveCommand()
    res = await mv.execute({'client':client,'server':server,'raw_input':'e'}, ['e'])
    print('Move result:', getattr(res,'success',None), getattr(res,'data',None))
    print('After move:', client.room, p.map_room)

    # Teleport as admin
    p.set_flag(flags.PlayerFlags.ADMIN)
    tele = TeleportCommand()
    tres = await tele.execute({'client':client,'server':server,'raw_input':'# 2'}, ['2'])
    print('Teleport result:', getattr(tres,'success',None), getattr(tres,'data',None))
    print('After teleport:', client.room, p.map_room)

    # Elevator: simulate non-interactive using args: combination not needed for test; force success by setting combinations
    p.combinations = { }
    # set a fake combination so elevator allows travel in non-interactive mode
    # call elevator.execute with args to set target level 3
    await elevator.execute(None, None, {'player': p, 'client': client}, ['', '3'])
    print('After elevator:', p.map_level, getattr(client, 'map_level', None))

    # Save player and inspect JSON
    saved = p.save(force=True)
    print('Saved:', saved)
    path = p._json_path(p.id)
    print('Saved file:', path)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        print('JSON flags keys sample:', list(data.get('flags', {}).keys())[:5])
        print('JSON map_room:', data.get('map_room'))
    except Exception as e:
        print('Failed reading saved JSON:', e)

asyncio.run(run())

