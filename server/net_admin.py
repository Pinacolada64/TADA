#!/bin/env python3

import sys
import uuid

import net_common as nc
import util

K = nc.K

# create user invite
id = input('user id: ')
email = input('email: ')
user = nc.User.load(id)
if user is not None:
    print(f"ERROR:  user exists")
    sys.exit(1)
code = str(uuid.uuid4())
invite = nc.Invite(id, email, code)
invite.save()
print(f"{invite=}")

