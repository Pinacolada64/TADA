#!/bin/env python3
import logging
import sys

import net_client
import common

K = common.K
# Mode1 = common.Mode1
Cmd = net_client.Cmd

default_prompt = 'TADA> '


class Client(net_client.Client):
    def __init__(self):
        self.status = {K.room_name: '', K.silver: 0, K.hit_points: 0, K.experience: 0}

    def process_request(self, request):
        if request['error'] != '':
            error_code = request['error']
            error_line = request['error_line']
            logging.error("process_request: %s (%s)" % (error_line, error_code))
        # update status bar:
        for f in [K.room_name, K.silver, K.hit_points, K.experience, K.last_command]:
            v = request.get('changes', {}).get(f)
            if v:
                self.status[f] = v
        # are there any multiple-choice options (like "Quit game? yes/no")
        choices = request.get('choices')
        if len(choices) > 0:
            logging.debug("process_request: choices=%s" % choices)
        prompt = request.get('prompt')
        if prompt == '':
            # print("---< %(room_name)s | health %(health)d | xp %(xp)d | %(silver)d gold >---" % self.status)
            logging.debug("process_request: prompt: %s" % self.status)
            s = self.status[K.silver]  # returns set() item (as string)
            logging.debug("process_request: silver: %s" % s)
            print(f"---< {self.status[K.room_name]} | "
                  f"HP: {self.status[K.hit_points]} | "
                  f"Experience: {self.status[K.experience]} | "
                  # TODO: f"Silver in hand: {self.status[K.silver['in_hand']]}"
                  f"Silver: {self.status[K.silver]}"                  
                  f" >---")
        for m in request['lines']:
            print(m)
        if len(choices) > 0:
            # ryan: changed 'choices' list to dict('option': 'text')
            for k, v in choices.items():
                print(f"  {k}: {v}")
            if prompt == '':
                prompt = '# '
        if prompt == '':
            prompt = default_prompt
        # if just one option, don't loop through checking choices:
        multiple_choice = len(choices) > 0
        if multiple_choice is False:
            # just one option:
            temp = request.get('last_command')
            if temp is not None:
                print(f"[Return] = {temp}\n")
            text = input(prompt)
            if temp is not None and text == '':
                print(f"(Repeating '{temp}.')")
                text = temp
            return Cmd(text=text)
        elif multiple_choice:
            # multiple options:
            while True:
                text = input(prompt).lower()
                if text not in choices.keys():
                    print("Choose an option listed above.")
                else:
                    return Cmd(text=text)


if __name__ == '__main__':
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    host = 'localhost'
    client = Client()
    client.set_user(user_id)
    client.start(host, common.server_port, common.app_id, common.app_key,
                 common.app_protocol)
