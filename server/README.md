# Server code

This directory contains code to run the game server.

## Game data files

The server needs several data files in `.json` format.
There is no need to convert data manually, since they already exist.
But if you wanted to, you could run the `convert_*.py` scripts in this directory.

**NOTE**: If you re-run the `convert_*.py` scripts, they will overwrite the `*.json` files in the repository with slightly outdated source files.
There will be some missing information about items in the level, since the original `.txt` files haven't been updated.

## Starting the server

From @core:

Before you run the server the first time, you should delete the `run/` directory that would have been generated from the last code version to start fresh.

`net_admin.py` uses command-line arguments:

    ./net_admin.py invite <user_id> <email_address>

To generate an invitation for user id `x` with email address `x@gmail.com`, use:

    ./net_admin.py invite x x@gmail.com

(The script doesn't send an email, but just stores it.)

For example, you could have a different way for the user to get their generated invite code.

1. Run `net_admin.py` which will ask you a couple questions to generate an entry for the user and an invite code.
2. Start the server: `server.py`.
3. Start a client (`client.py`) and enter the same user in step 1.

The test client is able to automatically find and use the invite code.
But in a real remote client, the user would need to type it in.

Also, now you can pass the `user_id` argument when starting the client, and the client will use a previously cached password (convenient for testing and a remote C64 client would be able to do the same).
