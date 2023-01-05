
client = None
flag = None

def get_client():
    global client
    return client

def set_client(c):
    global client
    client = c

def get_flag():
    global flag
    return flag

def set_flag(f):
    global flag
    flag = f
