#!/bin/env python3

import net_client
import common

K = common.K
Cmd = net_client.Cmd

class Client(net_client.Client):
    def __init__(self):
        self.status = {K.room_name: '', K.money: 0, K.health: 0, K.xp: 0}

    def nextCmd(self, request):
        if request['error'] > 0:
            error_code = request['error']
            error_line = request['error_line']
            print(f"ERROR: {error_line} ({error_code})")
        for f in [K.room_name, K.money, K.health, K.xp]:
            v = request.get('changes', {}).get(f)
            if v:  self.status[f] = v
        print("---< %(room_name)s | health %(health)d | xp %(xp)d | %(money)d gold >---"%self.status)
        for m in request['lines']:  print(m)
        text = input("TADA> ")
        return Cmd(cmd=text)

if __name__ == "__main__":
    host = "localhost"
    client = Client()
    client.start(host, common.server_port, common.app_id, common.app_key,
            common.app_protocol)

