
import json
import enum

serverPort = 5000

class K(str, enum.Enum):
    name = 'name'
    exits = 'exits'
    password = 'password'
    money = 'money'
    room = 'room'

class Mode(str, enum.Enum):
    login = 'login'
    cmd = 'cmd'
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

