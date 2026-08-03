#!/usr/bin/env python3
"""nightly_guild_maintenance.py — Bake each day's duel-driven turf captures
into the static level_<N>.json files, and refresh the guild territory
report that guild_hq reads.

Why this exists: combat/duel.py's turf-capture (_try_capture_turf) already
flips a room's live Room.alignment immediately on a decisive SPORT DUEL
win, and persists that flip to a run/server/room_alignment_level_<N>.json
sidecar (see room_alignment.py) rather than rewriting level_<N>.json --
those files are treated as read-only asset data everywhere else in the
codebase. Ryan wants that sidecar state folded back into level_<N>.json
once a day, so a fresh server restart reflects the current territory
picture as its new baseline rather than the original map authoring data.

Run nightly via cron, from the server/ directory:
    0 3 * * * cd /path/to/server && python3 tools/nightly_guild_maintenance.py >> run/server/log/nightly_guild_maintenance.log 2>&1

Steps, per level (1-7):
  1. Load that level's room_alignment_level_<N>.json overrides (if any).
  2. For each overridden room, write the new alignment into level_<N>.json
     (skipping HQ/FREE_FIRE rooms -- immutable, same guard as
     room_alignment.apply_overrides).
  3. Clear the sidecar file -- the capture is now baked into level_<N>.json
     itself, so re-applying it at next startup would be redundant.
  4. Tally guild-controlled room counts/percentages for the (now-updated)
     level, feeding run/server/guild_control.json for guild_hq's territory
     report.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

from room_alignment import load_overrides, save_overrides  # noqa: E402

log = logging.getLogger(__name__)

_LEVELS = range(1, 8)
_IMMUTABLE = {'hq', 'free_fire'}
_GUILDS = ('fist', 'claw', 'sword')


def _level_file(level: int) -> Path:
    return _SERVER_DIR / f'level_{level}.json'


def _bake_overrides(level: int) -> int:
    """Merge this level's sidecar overrides into level_<N>.json.

    Returns the number of rooms actually changed.
    """
    overrides = load_overrides(level)
    if not overrides:
        return 0

    level_file = _level_file(level)
    if not level_file.exists():
        return 0

    data = json.loads(level_file.read_text())
    changed = 0
    for room in data.get('rooms', []):
        override = overrides.get(str(room['number']))
        if override is None:
            continue
        if room.get('room_alignment') in _IMMUTABLE:
            continue
        if room['room_alignment'] != override:
            room['room_alignment'] = override
            changed += 1

    if changed:
        level_file.write_text(json.dumps(data, indent=2))

    # Baked into level_<N>.json now -- clear so apply_overrides() at next
    # startup doesn't redundantly re-apply the same values.
    save_overrides(level, {})
    return changed


def _tally_level(level: int) -> dict:
    level_file = _level_file(level)
    if not level_file.exists():
        return {}

    data = json.loads(level_file.read_text())
    rooms = data.get('rooms', [])
    total = len(rooms)
    counts = {'neutral': 0, 'free_fire': 0, 'hq': 0, 'fist': 0, 'claw': 0, 'sword': 0}
    for room in rooms:
        alignment = room.get('room_alignment', 'neutral')
        counts[alignment] = counts.get(alignment, 0) + 1

    result = {'total': total, 'counts': counts, 'pct': {}}
    for guild in _GUILDS:
        result['pct'][guild] = round(100 * counts.get(guild, 0) / total, 1) if total else 0.0
    return result


def run() -> dict:
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'levels': {}}
    overall_counts = {'neutral': 0, 'free_fire': 0, 'hq': 0, 'fist': 0, 'claw': 0, 'sword': 0}
    overall_total = 0

    for level in _LEVELS:
        changed = _bake_overrides(level)
        if changed:
            log.info('Level %d: baked %d captured room(s) into level_%d.json', level, changed, level)

        tally = _tally_level(level)
        if not tally:
            continue
        report['levels'][str(level)] = tally
        overall_total += tally['total']
        for key, n in tally['counts'].items():
            overall_counts[key] = overall_counts.get(key, 0) + n

    report['overall'] = {'total': overall_total, 'counts': overall_counts, 'pct': {}}
    for guild in _GUILDS:
        report['overall']['pct'][guild] = (
            round(100 * overall_counts.get(guild, 0) / overall_total, 1) if overall_total else 0.0
        )

    out_file = _SERVER_DIR / 'run' / 'server' / 'guild_control.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2))
    log.info('Wrote guild control report to %s', out_file)
    return report


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run()
