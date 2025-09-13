import enum

# shared client/server parameters used at connection init, so we can
# more quickly drop bogus connections and know whether client and
# server are using incompatible versions
server_port = 5000
app_id = 'test_server'  # TODO: change to 'TADA' when debugged
app_key = 'test_key'  # TODO: change to '1234567890' when debugged
app_protocol = 1
translation = 'UTF-8'

class K(str, enum.Enum):
    """keys for dictionary use, so that we can avoid 'stringly' typed
    anti-pattern.  When adding new entries make sure the key matches
    the string.

    (see https://www.google.com/search?q=%22stringly%22+typed)
    """
    # rooms
    number = 'number'
    name = 'name'
    desc = 'desc'
    exits = 'exits'
    monster = 'monster'
    item = 'item'
    weapon = 'weapon'
    food = 'food'
    alignment = 'alignment'
    # TODO: 'custom' is used for custom client status bar messages / formats
    custom = 'custom'

    # players
    password = 'password'
    silver = 'silver'
    room = 'room'  # room number player is in
    room_name = 'room_name'
    hit_points = 'hit_points'
    experience = 'experience'
    last_command = 'last_command'
    translation = 'translation'
