"""Small runner to start the simple_server.Server and keep it running.

Usage:
  python run_server.py [--host HOST] [--port PORT]

Examples:
  python run_server.py --host 127.0.0.1 --port 34083
  nohup python run_server.py &
"""
import argparse
import asyncio
import logging
import sys

sys.path.insert(0, str(__file__).rsplit('/', 1)[0])

from simple_server import Server, _PlayerFilter

# Matches simple_server.py's own __main__ block -- without this, running
# the server via this script (rather than `python simple_server.py`
# directly) fell back to a plain format with no connecting player/IP
# field at all, since this basicConfig() call runs before simple_server's
# own and there was nothing here to override it.
logging.basicConfig(
    level  = logging.DEBUG,
    format = '%(asctime)s | %(levelname)-8s | %(player)-16s | %(module)s.%(funcName)s: %(message)s',
    force  = True,
)
logging.getLogger().handlers[0].addFilter(_PlayerFilter())

parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=34083)
args = parser.parse_args()

server = Server(args.host, args.port)

async def main():
    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    except Exception:
        logging.exception('Server failed')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Server interrupted, shutting down')
