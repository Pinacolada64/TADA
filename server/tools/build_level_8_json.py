#!/usr/bin/env python3
"""tools/build_level_8_json.py -- assemble level_8.json from the 2014 sources.

Level 8 ("Forest of Canolbarth" / Sulidam) was authored by Pinacolada in
2014 but never converted to this port's room schema. Two source files in
the repo root carry it between them:

  * ../text-listings/installers/make-level-8.lbl
        365 ``DATA n,e,s,w,up,down,"NAME"`` rows -- the authoritative
        exit graph and room names (its header notes "some map connection
        fixes by dracosilver", so its exits supersede the desc file's).

  * ../text/s.t.roomdescs 8.txt
        224 ``^``-delimited room descriptions, positional (block i -> room
        i), already spell-checked with [bracket] highlighting. Rooms
        225-365 have no prose yet.

This script merges the two into ``server/level_8.json`` using the same
shape as ``level_1.json`` (rooms[] with number/name/room_alignment/flags/
exits/monster/item/weapon/food/desc). Monster/item/weapon/food are all 0
-- level 8 has no content placement yet; that's a later creative pass.
Exits use ``up``/``down`` keys (the engine already knows them, see
base_classes.compass_txts) in addition to north/east/south/west.

Run from the server/ directory::

    .venv/bin/python3 tools/build_level_8_json.py            # writes level_8.json + prints a report
    .venv/bin/python3 tools/build_level_8_json.py --check    # report only, don't write
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_DIR.parent
LBL = REPO_ROOT / "text-listings" / "installers" / "make-level-8.lbl"
DESCS = REPO_ROOT / "text" / "s.t.roomdescs 8.txt"
OUT = SERVER_DIR / "level_8.json"

DIRS = ("north", "east", "south", "west", "up", "down")
_EXITLINE_RE = re.compile(r"^\s*\d+(?:\s*,\s*\d+){5}\s*$")
_ROOMMARK_RE = re.compile(r"^\s*#\d+\s*$")
_DATA_RE = re.compile(r'^\s*DATA\s+(.+?)\s*$')


def parse_lbl() -> list[dict]:
    """Return one dict per room: number, name, exits{dir: dest}."""
    rooms = []
    num = 0
    for line in LBL.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _DATA_RE.match(line)
        if not m:
            continue
        body = m.group(1)
        # split the six leading integers off the trailing name; the name
        # may be "quoted", bare (the lone `un-named room` typo), or
        # "quoted with spaces".
        parts = body.split(",", 6)
        if len(parts) < 7:
            continue
        try:
            vals = [int(p.strip()) for p in parts[:6]]  # int() eats '0103'
        except ValueError:
            continue
        name = parts[6].strip().strip('"').strip()
        num += 1
        exits = {}
        for d, v in zip(DIRS, vals):
            if v and v != num:  # 0 = no exit; v == num = data-entry self-loop
                exits[d] = v
        rooms.append({"number": num, "name": name, "exits": exits})
    return rooms


def parse_descs(names_by_num: dict[int, str]) -> dict[int, str]:
    """Positional: the i-th ^-delimited block is room i's description.

    Each block may carry leading bookkeeping lines (``#12``, an ALL-CAPS
    name, an ``n,e,s,w,u,d`` exit row) left over from the file's stated
    format; strip those and glue the rest into one paragraph.
    """
    raw = DESCS.read_text(encoding="utf-8", errors="replace")
    blocks = raw.split("\n^\n")
    out: dict[int, str] = {}
    room = 0
    for block in blocks:
        lines = block.splitlines()
        # a block only counts once we're past the file's '#'-comment header
        if room == 0 and not any(_ROOMMARK_RE.match(ln) for ln in lines) \
                and not any(ln.strip() and not ln.startswith("#") for ln in lines):
            continue
        room += 1
        kept = []
        want_name = names_by_num.get(room, "").upper()
        for ln in lines:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if _ROOMMARK_RE.match(s) or _EXITLINE_RE.match(s):
                continue
            if s.upper() == want_name and not kept:
                continue  # the redundant name line (rooms 1-20 only)
            kept.append(s)
        text = re.sub(r"\s+", " ", " ".join(kept)).strip()
        if text:
            out[room] = text
    return out


def fallback_desc(name: str) -> str:
    if name.upper() == "MAZE":
        return "You are in a maze of twisting little passages, all alike."
    if not name or name.lower() == "un-named room":
        return "You are in a nondescript room."
    return f"You are in the {name.lower()}."


def build() -> tuple[list[dict], dict]:
    lbl_rooms = parse_lbl()
    names = {r["number"]: r["name"] for r in lbl_rooms}
    descs = parse_descs(names)
    present = set(names)

    rooms = []
    synthesized = []
    for r in lbl_rooms:
        n = r["number"]
        desc = descs.get(n)
        if not desc:
            desc = fallback_desc(r["name"])
            synthesized.append(n)
        rooms.append({
            "number": n,
            "name": r["name"] or "un-named room",
            "room_alignment": "neutral",
            "flags": [],
            "exits": r["exits"],
            "monster": 0,
            "item": 0,
            "weapon": 0,
            "food": 0,
            "desc": desc,
        })

    # --- integrity report ------------------------------------------------
    opp = {"north": "south", "south": "north", "east": "west",
           "west": "east", "up": "down", "down": "up"}
    dangling, nonrecip = [], []
    for r in rooms:
        for d, dest in r["exits"].items():
            if dest not in present:
                dangling.append((r["number"], d, dest))
            elif rooms[dest - 1]["exits"].get(opp[d]) != r["number"]:
                nonrecip.append((r["number"], d, dest))
    report = {
        "rooms": len(rooms),
        "with_prose": len(rooms) - len(synthesized),
        "synthesized_desc_rooms": synthesized,
        "dangling_exits": dangling,
        "one_way_exit_ends": len(nonrecip),
        "unnamed_rooms": [r["number"] for r in rooms
                          if r["name"] == "un-named room"],
    }
    return rooms, report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="print the report but don't write level_8.json")
    args = ap.parse_args()

    for src in (LBL, DESCS):
        if not src.exists():
            raise SystemExit(f"missing source file: {src}")

    rooms, report = build()

    print(f"parsed {report['rooms']} rooms from {LBL.name}")
    print(f"  {report['with_prose']} with authored prose, "
          f"{len(report['synthesized_desc_rooms'])} synthesized "
          f"(rooms {_ranges(report['synthesized_desc_rooms'])})")
    print(f"  {report['one_way_exit_ends']} one-way exit ends (normal for a hand map)")
    if report["dangling_exits"]:
        print(f"  !! {len(report['dangling_exits'])} exits point at missing rooms: "
              f"{report['dangling_exits']}")
    else:
        print("  no dangling exit targets")
    if report["unnamed_rooms"]:
        print(f"  un-named rooms (kept as 'un-named room'): {report['unnamed_rooms']}")

    if args.check:
        print("\n--check: not writing")
        return
    OUT.write_text(json.dumps({"rooms": rooms}, indent=1) + "\n")
    print(f"\nwrote {OUT.relative_to(SERVER_DIR)}  ({OUT.stat().st_size:,} bytes)")


def _ranges(nums: list[int]) -> str:
    if not nums:
        return "-"
    nums = sorted(nums)
    out, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = n
    out.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(out)


if __name__ == "__main__":
    main()
