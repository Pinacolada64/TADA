import os
import sys
from pathlib import Path

# Ensure repository server dir is on sys.path for local imports
repo_server_dir = Path(__file__).resolve().parent.parent
if str(repo_server_dir) not in sys.path:
    sys.path.insert(0, str(repo_server_dir))

print('Running smoke_new_player.py')
print('cwd =', os.getcwd())
print('sys.executable =', sys.executable)
print('sys.path[0:5] =', sys.path[0:5])

import asyncio

from commands.new_player import NewPlayerCommand


async def main():
    print('Inside main()')
    cmd = NewPlayerCommand()
    # Non-interactive path: supply username and password to avoid prompting
    context = {'client': None}
    result = await cmd.execute(context, ['smoketest_user', 'pw'])
    print('Smoke test result:')
    print('success =', getattr(result, 'success', None))
    print('message =', getattr(result, 'message', None))
    print('data keys =', list(result.data.keys()) if getattr(result, 'data', None) else None)


if __name__ == '__main__':
    asyncio.run(main())
