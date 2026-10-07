"""helpstaff/faq.py — pre-written answers to frequently asked questions.

Saved as a JSON list in helpstaff_faq.json in the save directory
(net_common.run_server_dir, resolved at call time). Each entry:

    {"title": "Hunger and thirst", "body": [<line>, ...]}

where each body line is a plain string or a serialized editor line
(formatting.serialize_lines() output), the same mix MAIL bodies accept.

The first load() on a server with no file yet writes STARTER_ANSWERS --
drafts meant to be edited ('helpstaff #faq #edit <n>'), not final text.
Helpstaff members, Dungeon Masters and Admins can add, edit and delete
entries (helpstaff/duty.py's can_edit_faq()); any staffer can mail one.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

FAQ_FILENAME = 'helpstaff_faq.json'

STARTER_ANSWERS = [
    {'title': 'Getting started',
     'body': [
         "Type |command|help|reset| for a list of commands, and "
         "|command|help <command>|reset| for more about any one of them.",
         "Type |command|look|reset| to see where you are, and the exit "
         "list shows which way you can go.",
     ]},
    {'title': 'Hunger and thirst',
     'body': [
         "Your character needs food and water. Carry rations and use "
         "|command|eat|reset| and |command|drink|reset| when you're told "
         "you're hungry or thirsty.",
     ]},
    {'title': 'Talking to other players',
     'body': [
         "|command|say|reset| talks to everyone in the room, "
         "|command|page|reset| reaches one player anywhere, and "
         "|command|mail|reset| leaves a message for someone who's offline. "
         "|command|who|reset| shows who's online.",
     ]},
]


def faq_path() -> Path:
    import net_common
    base = getattr(net_common, 'run_server_dir', None) or Path('run') / 'server'
    return Path(base) / FAQ_FILENAME


def load() -> list[dict]:
    path = faq_path()
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict) and e.get('title')]
            return []
    except Exception:
        log.exception('Could not read %s', path)
        return []
    # No file yet: seed it with the starter drafts.
    entries = [dict(e, body=list(e['body'])) for e in STARTER_ANSWERS]
    save(entries)
    return entries


def save(entries: list[dict]) -> None:
    path = faq_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def get(number: int) -> dict | None:
    """1-based lookup."""
    entries = load()
    if 1 <= number <= len(entries):
        return entries[number - 1]
    return None


def add(title: str, body: list) -> int:
    """Append an answer; returns its 1-based number."""
    entries = load()
    entries.append({'title': title, 'body': list(body)})
    save(entries)
    return len(entries)


def update(number: int, *, title: str | None = None, body: list | None = None) -> bool:
    entries = load()
    if not 1 <= number <= len(entries):
        return False
    if title is not None:
        entries[number - 1]['title'] = title
    if body is not None:
        entries[number - 1]['body'] = list(body)
    save(entries)
    return True


def delete(number: int) -> dict | None:
    entries = load()
    if not 1 <= number <= len(entries):
        return None
    removed = entries.pop(number - 1)
    save(entries)
    return removed
