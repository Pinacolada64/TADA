"""helpstaff/queue.py — questions asked while nobody was on duty.

Saved as a JSON list in helpstaff_queue.json in the save directory
(net_common.run_server_dir, resolved at call time so a throwaway/e2e
server keeps its own). One entry per player -- asking again replaces it:

    {"name": "Newbie", "question": "How do I find the bar?",
     "asked_at": "2026-10-06T16:16:00", "location": "UNDERGROUND FOREST"}

Oldest first. Staff answer entries from 'helpstaff #queue' or the login
check-in (helpstaff/review.py); answering or closing one removes it.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

QUEUE_FILENAME = 'helpstaff_queue.json'


def queue_path() -> Path:
    import net_common
    base = getattr(net_common, 'run_server_dir', None) or Path('run') / 'server'
    return Path(base) / QUEUE_FILENAME


def load() -> list[dict]:
    path = queue_path()
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict) and e.get('name')]
    except Exception:
        log.exception('Could not read %s', path)
    return []


def save(entries: list[dict]) -> None:
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def find(name: str) -> dict | None:
    return next((e for e in load() if e['name'].lower() == name.lower()), None)


def add(name: str, question: str, location: str = '') -> dict:
    """Queue *name*'s question, replacing any earlier one of theirs."""
    entries = [e for e in load() if e['name'].lower() != name.lower()]
    entry = {
        'name': name,
        'question': question,
        'asked_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'location': location,
    }
    entries.append(entry)
    save(entries)
    return entry


def remove(name: str) -> bool:
    """Drop *name*'s queued question. False if they had none."""
    entries = load()
    kept = [e for e in entries if e['name'].lower() != name.lower()]
    if len(kept) == len(entries):
        return False
    save(kept)
    return True


def count() -> int:
    return len(load())
