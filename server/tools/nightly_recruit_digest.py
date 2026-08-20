#!/usr/bin/env python3
"""nightly_recruit_digest.py — combined "new recruits" news digest.

commands/new_player.py's _announce_new_recruit() posts an individual
'once' news item immediately when each character finishes creation
(unchanged -- Ryan's call, 2026-08-20) *and* now also appends a
'NEW RECRUIT: <line>' entry to battle.log. This job scours that log for
the previous day's recruit lines and posts ONE combined news item
listing everyone who joined that day, rather than one item per recruit.

Why this exists: the immediate per-recruit posting is what let 1622
duplicate "Thorgar" test-account entries silently accumulate in
news.json over 18 days (tests/new-player/test_new_player_prompts.py's
full main_flow() runs weren't isolated from the real news.json/
battle.log -- fixed the same day in tests/conftest.py's
_isolate_news_file()/_isolate_run_server_dir() fixtures). A once-daily
digest can't repeat the same way even if a future bug reintroduces test
pollution, since it only ever reads yesterday's date once and records
that it did (see _state_path() below) -- same "bake once, mark done"
shape as tools/nightly_guild_maintenance.py's overrides-sidecar clear.

Run nightly via cron, from the server/ directory:
    5 0 * * * cd /path/to/server && .venv/bin/python3 tools/nightly_recruit_digest.py >> run/server/log/nightly_recruit_digest.log 2>&1

Idempotent: records the last digested date in .recruit_digest_state.json
(next to battle.log) so re-running the same day (a manual re-trigger, a
cron retry) doesn't double-post. Pass --force to re-digest anyway, or
--date YYYY-MM-DD to target a specific day (e.g. backfilling a missed
night). --dry-run prints what would be posted without writing anything.

Usage:
    .venv/bin/python3 tools/nightly_recruit_digest.py
    .venv/bin/python3 tools/nightly_recruit_digest.py --date 2026-08-19
    .venv/bin/python3 tools/nightly_recruit_digest.py --dry-run
    .venv/bin/python3 tools/nightly_recruit_digest.py --date 2026-08-19 --force
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

import news as news_store  # noqa: E402

log = logging.getLogger(__name__)

# Matches net_common.append_battle_log()'s stamp format
# ('[YYYY-MM-DD HH:MM UTC] ...') plus commands/new_player.py's
# _announce_new_recruit() tag -- keep in sync if either changes.
_RECRUIT_LINE_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2} UTC\] NEW RECRUIT: (.+)$'
)

_STATE_FILENAME = '.recruit_digest_state.json'


def _battle_log_path() -> Path:
    return _SERVER_DIR / 'run' / 'server' / 'battle.log'


def _state_path() -> Path:
    return _SERVER_DIR / 'run' / 'server' / _STATE_FILENAME


def parse_recruit_lines(log_text: str, target_date: datetime.date) -> list[str]:
    """Return the recruit-announcement message (everything after the tag)
    for every battle.log line dated *target_date*, in file order (== the
    order they joined that day)."""
    target = target_date.isoformat()
    lines = []
    for raw_line in log_text.splitlines():
        match = _RECRUIT_LINE_RE.match(raw_line)
        if match and match.group(1) == target:
            lines.append(match.group(2))
    return lines


def build_digest_item(recruit_lines: list[str], items: list[dict],
                       posted_at: datetime.datetime) -> dict:
    """Build the single combined news record for *recruit_lines* (already
    news_store.next_id()-ready against the current *items* list)."""
    count = len(recruit_lines)
    title = 'New Recruit' if count == 1 else f'{count} New Recruits'
    body = ["Yesterday's new recruits:", ''] + recruit_lines
    return {
        'id':        news_store.next_id(items),
        'title':     title,
        'body':      body,
        'author':    'SPUR',
        'posted_at': posted_at.isoformat(),
        'lifetime':  'once',
        'seen_by':   [],
    }


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, indent=2))


def run(target_date: datetime.date, *, force: bool = False, dry_run: bool = False) -> dict:
    """Digest *target_date*'s recruits. Returns a small result dict for
    callers/tests: {'posted': bool, 'skipped_already_done': bool,
    'skipped_disabled': bool, 'recruit_lines': [...]}."""
    from config import config as server_config
    if not server_config.nightly_recruit_digest_enabled:
        log.info("nightly_recruit_digest_enabled is Off (CONFIG command) -- skipping.")
        return {'posted': False, 'skipped_already_done': False,
                'skipped_disabled': True, 'recruit_lines': []}

    state = _load_state()
    if not force and state.get('last_digested_date') == target_date.isoformat():
        log.info('%s already digested (see %s) -- nothing to do.',
                  target_date.isoformat(), _state_path())
        return {'posted': False, 'skipped_already_done': True,
                'skipped_disabled': False, 'recruit_lines': []}

    log_path = _battle_log_path()
    log_text = log_path.read_text() if log_path.exists() else ''
    recruit_lines = parse_recruit_lines(log_text, target_date)

    if not recruit_lines:
        log.info('No new recruits found for %s.', target_date.isoformat())
        if not dry_run:
            state['last_digested_date'] = target_date.isoformat()
            _save_state(state)
        return {'posted': False, 'skipped_already_done': False,
                'skipped_disabled': False, 'recruit_lines': []}

    items = news_store.load_news()
    digest = build_digest_item(recruit_lines, items, datetime.datetime.now())

    log.info('%d new recruit(s) for %s: %s', len(recruit_lines), target_date.isoformat(),
              '; '.join(recruit_lines))

    if dry_run:
        log.info('(dry run: not writing news.json or state)')
        return {'posted': False, 'skipped_already_done': False,
                'skipped_disabled': False, 'recruit_lines': recruit_lines}

    items.append(digest)
    news_store.save_news(items)
    state['last_digested_date'] = target_date.isoformat()
    _save_state(state)
    log.info('Posted digest news item %r: %s', digest['id'], digest['title'])
    return {'posted': True, 'skipped_already_done': False,
            'skipped_disabled': False, 'recruit_lines': recruit_lines}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument(
        '--date', type=str, default=None,
        help="Target date (YYYY-MM-DD) to digest, default: yesterday (UTC), "
             "matching battle.log's own UTC timestamps.",
    )
    parser.add_argument('--force', action='store_true',
                         help='Digest even if this date was already recorded as done.')
    parser.add_argument('--dry-run', action='store_true',
                         help="Print what would be posted; don't write news.json or state.")
    args = parser.parse_args(argv)

    target_date = (
        datetime.date.fromisoformat(args.date) if args.date
        else datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    )
    run(target_date, force=args.force, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    raise SystemExit(main())
