#!/bin/env python3

import sys
import argparse
import uuid

import net_common as nc
import util

K = nc.K

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='subparser_name', help='sub-command help')

invite_parser = subparsers.add_parser('invite', help='invite help')
invite_parser.add_argument('id', type=str, help='user id')
invite_parser.add_argument('email', type=str, nargs='?', help='email address')
invite_parser.add_argument('--remove', action='store_true', help='remove invite')

user_parser = subparsers.add_parser('user', help='user help')
user_parser.add_argument('id', type=str, help='user id')
user_parser.add_argument('--remove', action='store_true', help='remove user')

args = parser.parse_args()
if args.subparser_name is None:
    parser.print_help()

def loadInvite(id):
    invite = nc.Invite.load(id)
    if invite is None:
        print(f"ERROR:  there is no invite for '{id}'")
        sys.exit(1)
    return invite

def loadUser(id):
    user = nc.User.load(id)
    if user is None:
        print(f"ERROR:  there is no user '{id}'")
        sys.exit(1)

def showInvite(invite):
    print(f"invitation:")
    print(f"  id:    {invite.id}")
    print(f"  email: {invite.email}")
    print(f"  code:  {invite.code}")

if args.subparser_name == 'invite':
    id = args.id
    if args.remove:
        # remove existing invite
        invite = loadInvite(id)
        invite.delete()
        print(f"deleted invite for '{id}'")
    elif args.email:
        # generate user invite
        email = args.email
        user = nc.User.load(id)
        if user is not None:
            print(f"ERROR:  user exists")
            sys.exit(1)
        code = str(uuid.uuid4())
        invite = nc.Invite(id, email, code)
        showInvite(invite)
        invite.save()
    else:
        # print existing invite
        invite = loadInvite(id)
        showInvite(invite)
elif args.subparser_name == 'user':
    id = args.id
    if args.remove:
        user = loadUser(id)
        user.delete()
        print(f"deleted user for '{id}'")
    else:
        user = loadUser(id)
        print(f"user '{id}' exists")

