
import os
import json
import enum
from dataclasses import dataclass, field
import datetime
import bcrypt

import util

run_server_dir = 'run/server'
invite_dir = os.path.join(run_server_dir, 'invite')
net_dir = os.path.join(run_server_dir, 'net')

class K(str, enum.Enum):
    id = 'id'
    password = 'password'
    code = 'code'
    hash = 'hash'
    salt = 'salt'

class Mode0(str, enum.Enum):
    login = 'login'
    app = 'app'
    bye = 'bye'

def toJSONB(obj):
    """turn arbitrary object into JSON string"""
    json_out = json.dumps(obj, default=lambda o: o.__dict__)
    return bytes(json_out, 'utf-8')

def fromJSONB(bytes):
    try:
        json_in = str(bytes, 'utf-8')
        if len(json_in) == 0:  return None
        return json.loads(json_in)
    except:
        return None

@dataclass
class Invite(object):
    id: str
    email: str
    code: str
    generated: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @staticmethod
    def _json_path(user_id):
        util.makeDirs(invite_dir)
        return os.path.join(invite_dir, f"user-{user_id}.json")

    @staticmethod
    def load(user_id):
        path = Invite._json_path(user_id)
        if os.path.exists(path):
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return Invite(**lh_data)
        else:
            return None

    def save(self):
        with open(Invite._json_path(self.id), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                    in o.__dict__.items() if v}, indent=4)

    def delete(self):
        os.remove(Invite._json_path(self.id))

@dataclass
class User(object):
    id: str
    salt: int = 0
    hash: str = ''

    def hashPassword(self, password):
        salt = bcrypt.gensalt()
        self.salt = salt.hex()
        self.hash = bcrypt.hashpw(bytes(password, 'utf-8'), salt).hex()

    def matchPassword(self, password):
        salt = bytes.fromhex(self.salt)
        hash = bcrypt.hashpw(bytes(password, 'utf-8'), salt).hex()
        return self.hash == hash

    @staticmethod
    def _json_path(user_id):
        util.makeDirs(net_dir)
        return os.path.join(net_dir, f"user-{user_id}.json")

    @staticmethod
    def load(user_id):
        path = User._json_path(user_id)
        if os.path.exists(path):
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return User(**lh_data)
        else:
            return None

    def save(self):
        with open(User._json_path(self.id), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                    in o.__dict__.items() if v}, indent=4)

class Test(object):
    server_port = 5001
    id = 'testing'
    key = '999999999'
    protocol = 1

