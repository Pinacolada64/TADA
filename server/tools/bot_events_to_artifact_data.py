#!/usr/bin/env python3
"""bot_events_to_artifact_data.py — collapse a bot_monster_encounter.py
*.events.json transcript into a clean, de-duplicated narrative for the
progression-viewer artifact.

Every bot in a multi-bot run witnesses most broadcasts, so the raw events
file has 2-3x more rows than real actions -- one per witness. This script
collapses same-tick duplicates and drops the "You did X" self-view line
whenever a third-person broadcast of the same action already exists,
leaving exactly one canonical line per real thing that happened.

Usage:
    .venv/bin/python tools/bot_events_to_artifact_data.py \
        bot_monster_encounter_<timestamp>.events.json \
        > tools/bot_monster_encounter_narrative.json
"""
from __future__ import annotations

import json
import re
import sys

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _clean(text: str) -> str:
    return _ANSI_RE.sub('', text)


def collapse(events: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for e in events:
        if e['phase'] == 'send':
            continue
        e = dict(e, text=_clean(e['text']))
        if (merged and merged[-1]['phase'] == e['phase'] and merged[-1]['text'] == e['text']
                and merged[-1]['t'] == e['t']):
            if e['actor'] not in merged[-1]['seen_by']:
                merged[-1]['seen_by'].append(e['actor'])
            continue
        e['seen_by'] = [e['actor']]
        merged.append(e)

    final = []
    for e in merged:
        if e['phase'] == 'exchange' and e['text'].startswith('You '):
            dup = any(
                o is not e and o['phase'] == 'exchange' and o['t'] == e['t']
                and o['text'].startswith(e['actor'] + ' ')
                for o in merged
            )
            if dup:
                continue
        final.append(e)
    return final


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    raw = json.loads(open(sys.argv[1]).read())
    print(json.dumps(collapse(raw), indent=2))
