#!/usr/bin/env python3
"""tools/run_throwaway_server.py — start a fully isolated TADA server
instance for scripted bot demos, so they never touch the real `run/server`
save directory (real player accounts, world monster state) that the normal
dev server on port 34083 uses.

Sets net_common.run_server_dir to its own directory BEFORE importing/
constructing simple_server.Server, same pattern tests/conftest.py uses for
e2e tests -- everything Player.save()/load(), the battle log, etc. resolve
through net_common's run_server_dir ends up isolated here instead.

Usage:
    .venv/bin/python tools/run_throwaway_server.py [--host HOST] [--port PORT]
                                                     [--petscii-port PORT]
                                                     [--dir PATH]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

import net_common

parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=34190)
parser.add_argument('--petscii-port', type=int, default=34191)
parser.add_argument('--dir', default=str(_SERVER_DIR / 'run' / 'epic_battle_server'))
args = parser.parse_args()

# Must happen before `from simple_server import Server` triggers any
# module-level net_common usage.
net_common.run_server_dir = args.dir
Path(args.dir, 'net').mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.WARNING, force=True)

from simple_server import Server

server = Server(args.host, args.port, args.petscii_port)


async def main():
    print(f'Throwaway server starting: {args.host}:{args.port} '
          f'(petscii {args.petscii_port}), save dir {args.dir}')
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())
