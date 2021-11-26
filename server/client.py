#!/bin/env python3

import sys

import net_client
import common

K = common.K
#Mode1 = common.Mode1
Cmd = net_client.Cmd

default_prompt = 'TADA> '

class Client(net_client.Client):
    def __init__(self):
        self.status = {K.room_name: '', K.money: 0, K.health: 0, K.xp: 0}

    def processRequest(self, request):
        if request['error'] != '':
            error_code = request['error']
            error_line = request['error_line']
            print(f"ERROR: {error_line} ({error_code})")
        for f in [K.room_name, K.money, K.health, K.xp]:
            v = request.get('changes', {}).get(f)
            if v:  self.status[f] = v
        choices = request.get('choices', [])
        prompt = request.get('prompt')
        if prompt == '':
            print("---< %(room_name)s | health %(health)d | xp %(xp)d | %(money)d gold >---"%self.status)
        for m in request['lines']:  print(m)
        if len(choices) > 0:
            choices = request.get('choices', [])
            for i, c in enumerate(choices):
                print(f"  {i}: {c}")
            if prompt == '':  prompt = '# '
        if prompt == '':  prompt = default_prompt
        text = input(prompt)
        return Cmd(text=text)

if __name__ == '__main__':
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    host = 'localhost'
    client = Client()
    client.setUser(user_id)
    client.start(host, common.server_port, common.app_id, common.app_key,
            common.app_protocol)

