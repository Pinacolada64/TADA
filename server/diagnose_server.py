# Run: python diagnose_server.py --report
import sys, traceback, asyncio, logging, argparse, json, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- logging error catcher --------------------------------------------------
class _ErrorCatcher(logging.Handler):
    def __init__(self):
        super().__init__()
        self.had_error = False
    def emit(self, record):
        try:
            if record.levelno >= logging.ERROR:
                self.had_error = True
        except Exception:
            self.had_error = True

handler = _ErrorCatcher()
root_logger = logging.getLogger()
root_logger.addHandler(handler)

state = {'exit_code': 0}

# --- helper diagnostics ----------------------------------------------------

def _resolve_run_dir():
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    if base is None:
        base = Path('./run/server')
    return Path(str(base))


def check_run_dir_writeable():
    path = _resolve_run_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Cannot create run dir {path}: {e}"
    # attempt to write a temp file
    try:
        fd, tmpname = tempfile.mkstemp(prefix='diag_', dir=str(path))
        os.write(fd, b'test')
        os.close(fd)
        os.remove(tmpname)
        return True, f"Run dir {path} is writable"
    except Exception as e:
        return False, f"Cannot write to run dir {path}: {e}"


def check_json_file(path: Path):
    if not path.exists():
        return False, f"Missing: {path}"
    try:
        with open(path, 'r') as f:
            json.load(f)
        return True, f"OK: {path.name}"
    except Exception as e:
        return False, f"JSON parse error in {path}: {e}"


def check_map_load(json_path: Path):
    try:
        from base_classes import Map
        m = Map()
        m.read_map(str(json_path))
        return True, f"Map loaded ({len(m.rooms)} rooms)"
    except Exception as e:
        return False, f"Map load failed: {e}"

# --- interactive helpers --------------------------------------------------

async def _interactive_repl(server):
    """Minimal async REPL: commands: status, players, save <id>, quit"""
    print('\nInteractive mode: type commands. Available: status, players, save <id>, quit')
    loop = asyncio.get_running_loop()
    while True:
        try:
            # run builtin input in executor to avoid blocking loop
            cmd = await loop.run_in_executor(None, input, 'diag> ')
        except (EOFError, KeyboardInterrupt):
            print('\nShutting down interactive session')
            break
        if not cmd:
            continue
        parts = cmd.strip().split()
        if not parts:
            continue
        if parts[0] in ('quit', 'exit'):
            break
        if parts[0] == 'status':
            print(f"Server running: {getattr(server, 'server', None) is not None and bool(server.server.sockets)}")
            continue
        if parts[0] == 'players':
            try:
                print('Clients:', list(getattr(server, 'clients', {}).values()))
            except Exception as e:
                print('Error listing players:', e)
            continue
        if parts[0] == 'save' and len(parts) >= 2:
            pid = parts[1]
            try:
                # attempt to find client and call player.save()
                for addr, c in list(getattr(server, 'clients', {}).items()):
                    if getattr(c, 'username', None) == pid or getattr(getattr(c, 'player', None), 'id', None) == pid:
                        pl = getattr(c, 'player', None)
                        if pl:
                            ok = pl.save(force=True)
                            print(f"Saved {pid}: {ok}")
                        else:
                            print('Player object missing')
                        break
                else:
                    print('No matching client found')
            except Exception as e:
                print('Save failed:', e)
            continue
        print('Unknown command:', parts[0])

# --- main diagnostic/startup flow -----------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description='Diagnose and optionally run the server')
    parser.add_argument('--report', action='store_true', help='Run diagnostics and exit')
    parser.add_argument('--interactive', action='store_true', help='Keep server running and provide REPL')
    parser.add_argument('--timeout', type=float, default=2.0, help='Startup wait time in seconds')
    args = parser.parse_args(argv)

    # run some pre-start diagnostics
    print('Running pre-start diagnostics...')
    ok, msg = check_run_dir_writeable()
    print(' * run dir:', msg)
    if not ok:
        state['exit_code'] = 1

    # check standard JSON assets
    base = Path(__file__).parent
    assets = ['level_1.json', 'objects.json', 'weapons.json', 'rations.json']
    for a in assets:
        p = base / a
        ok2, m2 = check_json_file(p)
        print(' *', m2)
        if not ok2:
            state['exit_code'] = 1

    # try to load the map (gives more specific errors than raw json parse)
    mpath = base / 'level_1.json'
    okm, mm = check_map_load(mpath)
    print(' * map:', mm)
    if not okm:
        state['exit_code'] = 1

    # if only reporting, don't attempt to start the server (but still exit non-zero if diagnostics failed)
    if args.report and not args.interactive:
        if state['exit_code'] != 0:
            print('diagnose_server: problems detected; exit code non-zero')
            sys.exit(state['exit_code'])
        print('diagnose_server: pre-start diagnostics OK; no startup performed')
        sys.exit(0)

    # --- proceed to start the server to surface runtime startup errors ---
    try:
        import simple_server
        Server = getattr(simple_server, 'Server', None)
        if Server is None:
            print('simple_server imported but Server class not found')
            raise SystemExit(1)

        srv = Server('127.0.0.1', 0)
        print('Instantiated Server OK; attempting to start for %.1fs...' % args.timeout)

        async def run_and_optionally_stop():
            try:
                task = asyncio.create_task(srv.start())
                await asyncio.sleep(args.timeout)
                # If interactive, leave server running and hand REPL back
                if args.interactive:
                    await _interactive_repl(srv)
                else:
                    try:
                        if getattr(srv, 'server', None):
                            srv.server.close()
                            await srv.server.wait_closed()
                    except Exception as e:
                        print('Error closing server:', e)
                        traceback.print_exc()
                        state['exit_code'] = 1
                # cancel background task if still active
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            except Exception:
                print('Exception while running server:')
                traceback.print_exc()
                state['exit_code'] = 1

        asyncio.run(run_and_optionally_stop())

        # If any ERROR log records were captured, set non-zero exit
        if getattr(handler, 'had_error', False):
            print('ERROR-level logs were emitted during startup; exiting non-zero')
            state['exit_code'] = 1

    except Exception as e:
        print('Import/instantiation failed:', type(e).__name__, e)
        traceback.print_exc()
        state['exit_code'] = 1

    # cleanup
    try:
        root_logger.removeHandler(handler)
    except Exception:
        pass

    if state['exit_code'] != 0:
        print('diagnose_server: exiting with errors (code=%d)' % state['exit_code'])
        sys.exit(state['exit_code'])
    else:
        print('diagnose_server: no startup errors detected; exiting 0')
        sys.exit(0)


if __name__ == '__main__':
    main()

