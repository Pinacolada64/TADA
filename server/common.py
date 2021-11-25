
import enum

server_port = 5000
app_id = 'TADA'
app_key = '1234567890'
app_protocol = 1

class K(str, enum.Enum):
    name = 'name'
    exits = 'exits'
    password = 'password'
    money = 'money'
    room = 'room'
    room_name = 'room_name'
    health = 'health'
    xp = 'xp'


