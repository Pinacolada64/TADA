#!/usr/bin/env python3
"""tools/gen_level_maps.py -- render printable adventure-style level maps.

Path A of the "maps" project: go straight from the structured room data
in ``server/level_<N>.json`` to a poster-sized SVG per level, with room
names, directional exit connectors, and monster / item / weapon / food
markers. No graph exploration or spring layout is needed because the
SPUR levels are laid out on a fixed-width integer grid -- room ``N`` sits
at cell ``((N-1) % W, (N-1) // W)`` and the cardinal exits are just
``+/-1`` (east/west) and ``+/-W`` (south/north). ``W`` (the original
``map_width`` from the binary ``D.LEVEL<N>.TXT`` headers) is recovered
here as the most common ``south`` delta, with a hard-coded fallback.

Non-grid links -- the handful of hand-authored wrap-around edges, plus
``rc`` (1=stairs up / 2=stairs down, a level change) and ``rt`` (room
transporter -> room number) -- are drawn as dashed "portal" connectors
and also collected into the legend so nothing is silently dropped.

Usage::

    .venv/bin/python3 tools/gen_level_maps.py                 # all levels
    .venv/bin/python3 tools/gen_level_maps.py --level 1       # just level 1
    .venv/bin/python3 tools/gen_level_maps.py --cell 160      # bigger cells
    .venv/bin/python3 tools/gen_level_maps.py --out /tmp/maps

Output is one ``level_<N>.svg`` in the output dir (default
``tools/level_maps/``). SVG scales losslessly to any poster size; to
rasterise or make a PDF, open it in a browser and print-to-PDF, or use
``rsvg-convert -f pdf`` / Inkscape if installed (the script will also
emit a PDF automatically when ``rsvg-convert`` is on PATH).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# Fallback grid widths, keyed by level number. These match the mode of the
# `south` exit deltas in each level_<N>.json today and the `map_width`
# fields in ../SPUR-data/level-1/analyse-binary-level-data.py's header
# parse. derive_width() recomputes from the data and only falls back here
# if a level somehow has too few plain north/south exits to vote.
FALLBACK_WIDTHS = {1: 12, 2: 15, 3: 10, 4: 7, 5: 20, 6: 30, 7: 10}

# Room fill by room_alignment value. free_fire rooms are where PvP / free
# combat is allowed in SPUR; "safe" style rooms get a calm green.
ALIGNMENT_FILL = {
    "free_fire": "#ffe0e0",
    "neutral": "#f4f4f4",
    "safe": "#e2f4e2",
    "no_fire": "#e2f4e2",
}
ALIGNMENT_STROKE = {
    "free_fire": "#c0392b",
    "neutral": "#888888",
    "safe": "#2e7d32",
    "no_fire": "#2e7d32",
}

# Friendly level names shown alongside the bare number in each map's
# title -- level_<N>.json has no name field of its own. The canonical
# list lives in shoppe/elevator.py (the in-game elevator to the seven
# levels of the Land); import it so the two never drift, with a copy as
# a fallback for running this script outside a working server tree.
try:  # pragma: no cover - import path depends on cwd
    from shoppe.elevator import _LEVEL_NAMES as _ELEVATOR_LEVEL_NAMES
except Exception:  # noqa: BLE001
    _ELEVATOR_LEVEL_NAMES = [
        "The Land of the Enchanted", "Dark Side", "The Shadowed Land",
        "Maze of Alleyways", "Land of the Wraiths", "A Brave New World",
        "The House",
    ]
LEVEL_NAMES: dict[int, str] = {
    i + 1: name for i, name in enumerate(_ELEVATOR_LEVEL_NAMES)
}
# level 8 is this port's addition and isn't in the elevator's list
LEVEL_NAMES.setdefault(8, "Forest of Canolbarth")

CARDINALS = ("north", "south", "east", "west")
VERTICAL = ("up", "down")
# (col, row) delta for each cardinal, screen coords (row grows downward).
DIR_DELTA = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}

# Levels whose room numbers are NOT a fixed-width grid (see derive_width);
# these get a breadth-first directional placement instead. Level 8 (this
# port's hand-authored addition) is the first.
GRAPH_LAYOUT_LEVELS = {8}


def load_json(name: str):
    with open(SERVER_DIR / name, "r") as f:
        return json.load(f)


def name_index(records, key="number", label="name"):
    """{number: name} from a list-of-dicts data file."""
    out = {}
    for rec in records:
        out[rec[key]] = rec.get(label, f"#{rec[key]}")
    return out


def derive_width(rooms_by_num: dict[int, dict], level: int) -> int:
    """Most common (dest - number) among plain `south` exits == grid width."""
    votes = Counter()
    for num, room in rooms_by_num.items():
        dest = room["exits"].get("south")
        if isinstance(dest, int) and dest > num:
            votes[dest - num] += 1
    if votes:
        width, _ = votes.most_common(1)[0]
        return width
    return FALLBACK_WIDTHS.get(level, 12)


def wrap_label(text: str, width: int = 14, max_lines: int = 3) -> list[str]:
    """Greedy word-wrap a room name into at most `max_lines` short lines."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1:])]
        if len(lines[-1]) > width + 2:
            lines[-1] = lines[-1][: width + 1] + "…"
    return lines


class MapRenderer:
    CELL = 150          # room cell size in px (overridable via --cell)
    GUTTER_FRAC = 0.34   # fraction of a cell left blank between rooms
    MARGIN = 60          # outer margin in px

    def __init__(self, level: int, cell: int | None = None):
        self.level = level
        if cell:
            self.CELL = cell
        self.data = load_json(f"level_{level}.json")
        all_rooms = {r["number"]: r for r in self.data["rooms"]}
        # Some level files carry empty placeholder slots (no name, no exits,
        # no contents). Don't draw a mystery box for them -- list the slot
        # numbers in the legend instead.
        self.orphans = sorted(
            n for n, r in all_rooms.items()
            if not r["name"].strip() and not r["exits"]
            and not any(r.get(k) for k in ("monster", "item", "weapon", "food"))
        )
        self.rooms = {n: r for n, r in all_rooms.items() if n not in self.orphans}
        self.graph_layout = level in GRAPH_LAYOUT_LEVELS
        self.parked: list[int] = []  # graph layout: rooms the walk never reached
        self.width = None if self.graph_layout else derive_width(self.rooms, level)

        self.monsters = name_index(load_json("monsters.json"))
        self.weapons = name_index(load_json("weapons.json"))
        self.rations = name_index(load_json("rations.json"))
        self.items = name_index(load_json("objects.json")["items"])

        # Cell position for every room, then trim to the populated bbox so
        # sparse levels (e.g. level 6: 292 rooms in a 30-wide grid) don't
        # carry acres of empty margin. Grid levels derive the position
        # straight from the room number; level 8 is walked breadth-first.
        if self.graph_layout:
            self.pos = self._graph_layout()
        else:
            self.pos = {
                num: ((num - 1) % self.width, (num - 1) // self.width)
                for num in self.rooms
            }
        cols = [c for c, _ in self.pos.values()]
        rows = [r for _, r in self.pos.values()]
        self.min_col, self.min_row = min(cols), min(rows)
        self.n_cols = max(cols) - self.min_col + 1
        self.n_rows = max(rows) - self.min_row + 1

        self.portal_notes: list[str] = []  # collected for the legend
        self._stub_seen: Counter = Counter()  # stub labels already placed per room

    # -- geometry ---------------------------------------------------------
    @property
    def box(self) -> float:
        return self.CELL * (1 - self.GUTTER_FRAC)

    def cell_xy(self, num: int) -> tuple[float, float]:
        c, r = self.pos[num]
        return (
            self.MARGIN + (c - self.min_col) * self.CELL,
            self.MARGIN + (r - self.min_row) * self.CELL,
        )

    def box_xy(self, num: int) -> tuple[float, float]:
        x, y = self.cell_xy(num)
        pad = (self.CELL - self.box) / 2
        return x + pad, y + pad

    def center(self, num: int) -> tuple[float, float]:
        x, y = self.box_xy(num)
        return x + self.box / 2, y + self.box / 2

    # -- svg helpers ----------------------------------------------------
    def _room_markers(self, room: dict) -> list[str]:
        """Short 'K: name' style badges for the room's contents."""
        out = []
        if room.get("monster"):
            out.append(("M", self.monsters.get(room["monster"], f"#{room['monster']}")))
        if room.get("item"):
            out.append(("I", self.items.get(room["item"], f"#{room['item']}")))
        if room.get("weapon"):
            out.append(("W", self.weapons.get(room["weapon"], f"#{room['weapon']}")))
        if room.get("food"):
            out.append(("F", self.rations.get(room["food"], f"#{room['food']}")))
        return out

    def _draw_room(self, num: int) -> list[str]:
        room = self.rooms[num]
        x, y = self.box_xy(num)
        b = self.box
        align = room.get("room_alignment", "neutral")
        fill = ALIGNMENT_FILL.get(align, "#f4f4f4")
        stroke = ALIGNMENT_STROKE.get(align, "#888888")
        s = [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{b:.1f}" height="{b:.1f}" '
            f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        ]
        # room number, top-left inside the box
        s.append(
            f'<text x="{x + 6:.1f}" y="{y + 15:.1f}" class="rnum">{num}</text>'
        )
        # stairs badge (rc), top-right
        rc = room["exits"].get("rc")
        if rc in (1, 2):
            glyph = "▲ up" if rc == 1 else "▼ dn"
            s.append(
                f'<text x="{x + b - 6:.1f}" y="{y + 15:.1f}" '
                f'class="stairs" text-anchor="end">{glyph}</text>'
            )
        # room name -- at most two lines, in a fixed zone below the number
        name_lines = wrap_label(
            room["name"].strip().rstrip("+").strip() or "(unnamed)",
            width=max(10, int(b / 7)), max_lines=2,
        )
        ty = y + 30
        for line in name_lines:
            s.append(
                f'<text x="{x + b / 2:.1f}" y="{ty:.1f}" class="rname" '
                f'text-anchor="middle">{escape(line)}</text>'
            )
            ty += 15
        # content markers -- at most three, stacked up from the box bottom
        markers = self._room_markers(room)[:3]
        cap = max(8, int(b / 6))
        my = y + b - 8 - 12 * (len(markers) - 1)
        for kind, label in markers:
            short = label if len(label) <= cap else label[: cap - 1] + "…"
            s.append(
                f'<text x="{x + b / 2:.1f}" y="{my:.1f}" class="mark mark-{kind}" '
                f'text-anchor="middle">{kind}: {escape(short)}</text>'
            )
            my += 12
        return s

    def _graph_layout(self) -> dict[int, tuple[int, int]]:
        """Breadth-first directional placement for a non-grid level.

        Start at the lowest-numbered room with a cardinal exit, then walk
        the graph placing each room one cell off its neighbour in the
        exit's direction. Occupied cells push the newcomer to the nearest
        free cell (drawn later as a dashed jog). up/down don't move you on
        the sheet -- they become labelled portal stubs in _draw_connectors.
        """
        from collections import deque

        rooms = self.rooms
        start = next((n for n in sorted(rooms)
                      if any(d in rooms[n]["exits"] for d in CARDINALS)),
                     min(rooms))
        pos: dict[int, tuple[int, int]] = {start: (0, 0)}
        occupied = {(0, 0)}

        # pass 1 follows only cardinals (keeps the geography honest); later
        # sweeps also follow up/down, repeating to a fixpoint so a wing
        # joined to the map only by staircases (the castle, the temples)
        # still gets drawn next to whatever it connects to.
        def _put(near_cell, delta):
            dcol, drow = delta
            target = (near_cell[0] + dcol, near_cell[1] + drow)
            if target in occupied:
                target = self._nearest_free(target, occupied)
            occupied.add(target)
            return target

        def grow(dirs):
            """Forward: place rooms hanging off an already-placed room's exit."""
            q = deque(pos)
            placed = False
            while q:
                cur = q.popleft()
                for d in dirs:
                    dest = rooms[cur]["exits"].get(d)
                    if not isinstance(dest, int) or dest not in rooms or dest in pos:
                        continue
                    pos[dest] = _put(pos[cur], DIR_DELTA.get(d, (1, 1)))
                    q.append(dest)
                    placed = True
            return placed

        def pull(dirs):
            """Reverse: place an unplaced room that has a one-way exit INTO a
            placed room (the 2014 data has many non-reciprocal links)."""
            placed = False
            for n in sorted(rooms):
                if n in pos:
                    continue
                for d in dirs:
                    dest = rooms[n]["exits"].get(d)
                    if isinstance(dest, int) and dest in pos:
                        back = DIR_DELTA.get(_opposite(d), (-1, -1))
                        pos[n] = _put(pos[dest], back)
                        placed = True
                        break
            return placed

        grow(CARDINALS)
        alldirs = CARDINALS + VERTICAL
        while grow(alldirs) or pull(alldirs):
            pass

        # disconnected leftovers -- rooms the walk never reached from the
        # start room by any n/e/s/w/up/down chain. Park them in a column to
        # the right; record them so the legend can flag it.
        self.parked = sorted(n for n in rooms if n not in pos)
        if self.parked:
            col = max(x for x, _ in pos.values()) + 3
            row_span = max(y for _, y in pos.values()) + 1
            row = 0
            for n in self.parked:
                while (col, row) in occupied:
                    row += 1
                    if row > row_span:
                        row, col = 0, col + 1
                pos[n] = (col, row)
                occupied.add((col, row))
                row += 1
        return pos

    @staticmethod
    def _nearest_free(cell, occupied):
        from itertools import count
        cx, cy = cell
        for r in count(1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    c = (cx + dx, cy + dy)
                    if c not in occupied:
                        return c

    def _draw_connectors(self, num: int) -> list[str]:
        room = self.rooms[num]
        cx, cy = self.center(num)
        src = self.pos[num]
        s: list[str] = []
        for direction in CARDINALS:
            dest = room["exits"].get(direction)
            if not isinstance(dest, int) or dest == 0 or dest not in self.rooms:
                if isinstance(dest, int) and dest not in self.rooms:
                    s.append(self._portal(num, dest, direction.upper()[:1], cx, cy))
                continue
            dcol, drow = DIR_DELTA[direction]
            want = (src[0] + dcol, src[1] + drow)
            reciprocal = self.rooms[dest]["exits"].get(_opposite(direction)) == num
            if self.pos.get(dest) == want:
                # tidy neighbour: draw a stub across the shared gutter
                s.append(self._grid_stub(num, dest, direction, reciprocal))
            else:
                # displaced / non-adjacent: dashed portal line + legend note
                s.append(self._portal(num, dest, direction.upper()[:1], cx, cy))
        # up / down exits: a dashed link if the far room is on the sheet,
        # otherwise a labelled stub. Always a legend note.
        for direction in VERTICAL:
            dest = room["exits"].get(direction)
            if not isinstance(dest, int) or dest == 0:
                continue
            tag = direction[0].upper()  # U / D
            if dest in self.rooms:
                self.portal_notes.append(
                    f"{tag}: #{num} {room['name'].strip() or '(unnamed)'} "
                    f"→ #{dest} {self.rooms[dest]['name'].strip() or '(unnamed)'}")
            if dest in self.pos:
                bx, by = self.center(dest)
                mx, my = (cx + bx) / 2, (cy + by) / 2
                s.append(
                    f'<path d="M {cx:.1f} {cy:.1f} L {bx:.1f} {by:.1f}" '
                    f'class="vlink" marker-end="url(#arrow)"/>'
                    f'<text x="{mx:.1f}" y="{my:.1f}" class="ptag" '
                    f'text-anchor="middle">{tag}</text>')
            else:
                s.append(self._stub_text(num, f"{tag}&#8594;#{dest}"))
        # rt = room transporter -> a room number
        rt = room["exits"].get("rt")
        if isinstance(rt, int) and rt != 0:
            s.append(self._portal(num, rt, "RT", cx, cy))
        return s

    def _grid_stub(self, a: int, b: int, direction: str, reciprocal: bool) -> str:
        ax, ay = self.center(a)
        bx, by = self.center(b)
        half = self.box / 2
        if direction in ("east", "west"):
            x1 = ax + (half if direction == "east" else -half)
            x2 = bx + (half if direction == "west" else -half)
            y1 = y2 = ay
        else:
            y1 = ay + (half if direction == "south" else -half)
            y2 = by + (half if direction == "north" else -half)
            x1 = x2 = ax
        marker = "" if reciprocal else ' marker-end="url(#arrow)"'
        cls = "link" if reciprocal else "link oneway"
        return (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="{cls}"{marker}/>'
        )

    def _portal(self, a: int, b: int, tag: str, cx: float, cy: float) -> str:
        aname = self.rooms[a]["name"].strip() or "(unnamed)"
        if b in self.rooms:
            bname = self.rooms[b]["name"].strip() or "(unnamed)"
            self.portal_notes.append(f"{tag}: #{a} {aname} → #{b} {bname}")
            ac, ar = self.pos[a]
            bc, br = self.pos[b]
            if abs(ac - bc) + abs(ar - br) <= 2:
                # near enough to draw without dominating the sheet
                bx, by = self.center(b)
                mx, my = (cx + bx) / 2, (cy + by) / 2
                return (
                    f'<path d="M {cx:.1f} {cy:.1f} L {bx:.1f} {by:.1f}" '
                    f'class="portal" marker-end="url(#arrow)"/>'
                    f'<text x="{mx:.1f}" y="{my:.1f}" class="ptag" '
                    f'text-anchor="middle">{tag}</text>'
                )
            # far jump (row/column wrap, cross-map transporter): a labelled
            # stub keeps the sheet readable; the legend carries the detail.
            return self._stub_text(a, f"{tag}&#8594;#{b}")
        # destination not on this level -- draw a short labelled stub
        self.portal_notes.append(f"{tag}: #{a} {aname} → room #{b} (off-level)")
        return self._stub_text(a, f"{tag}&#8594;#{b}")

    def _stub_text(self, room: int, label: str) -> str:
        """A small portal label just outside a room box -- below it, or
        above it when the room is on the last row (keeps clear of the
        legend)."""
        cx, cy = self.center(room)
        n = self._stub_seen[room]
        self._stub_seen[room] += 1
        last_row = self.pos[room][1] == self.min_row + self.n_rows - 1
        if last_row:
            dy = -(self.box / 2 + 6) - 11 * n
        else:
            dy = (self.box / 2 + 12) + 11 * n
        return (
            f'<text x="{cx:.1f}" y="{cy + dy:.1f}" class="ptag" '
            f'text-anchor="middle">{label}</text>'
        )

    # -- document -----------------------------------------------------
    def render(self) -> str:
        w = self.MARGIN * 2 + self.n_cols * self.CELL
        legend_h = 40 + 14 * (len(self._legend_lines()))
        h = self.MARGIN * 2 + self.n_rows * self.CELL + legend_h

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" '
            f'height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}" '
            f'font-family="Helvetica, Arial, sans-serif">',
            _STYLE,
            _DEFS,
            f'<rect width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>',
            f'<text x="{self.MARGIN}" y="{self.MARGIN - 24}" class="title">'
            f'{escape(self._title())}</text>',
            f'<text x="{self.MARGIN}" y="{self.MARGIN - 6}" class="subtitle">'
            f'{len(self.rooms)} rooms &#183; '
            f'{"walked breadth-first" if self.graph_layout else f"grid width {self.width}"}'
            f' &#183; generated {date.today().isoformat()}</text>',
        ]
        # connectors first so room boxes paint on top of the line ends
        for num in sorted(self.rooms):
            parts.extend(self._draw_connectors(num))
        for num in sorted(self.rooms):
            parts.extend(self._draw_room(num))
        parts.extend(self._draw_legend(w, self.MARGIN + self.n_rows * self.CELL + 30))
        parts.append("</svg>")
        return "\n".join(parts)

    def _title(self) -> str:
        base = f"Level {self.level}"
        if self.level in LEVEL_NAMES:
            return f"{base} — {LEVEL_NAMES[self.level]}"
        return base

    def _legend_lines(self) -> list[str]:
        lines = [
            "Room fill: red = free-fire (PvP) · grey = neutral · green = safe",
            "Markers: M = monster · I = item · W = weapon · F = food/drink"
            "   |   ▲ up / ▼ dn = stairs to another level",
            "Solid line = two-way passage · arrow = one-way · "
            "dashed = transporter / non-grid link",
        ]
        if self.orphans:
            slots = ", ".join(f"#{n}" for n in self.orphans)
            lines.append(f"Unmapped room slots (empty in the data): {slots}")
        if self.parked:
            slots = ", ".join(f"#{n}" for n in self.parked)
            lines.append(
                f"Parked at right ({len(self.parked)} rooms) -- reachable from the "
                f"start room only by up/down stairs or not at all: {slots}")
        if self.portal_notes:
            lines.append("")
            lines.extend(sorted(set(self.portal_notes)))
        return lines

    def _draw_legend(self, w: float, y0: float) -> list[str]:
        s = [
            f'<line x1="{self.MARGIN}" y1="{y0 - 14:.1f}" x2="{w - self.MARGIN}" '
            f'y2="{y0 - 14:.1f}" stroke="#cccccc"/>'
        ]
        y = y0
        for line in self._legend_lines():
            s.append(
                f'<text x="{self.MARGIN}" y="{y:.1f}" class="legend">'
                f'{escape(line)}</text>'
            )
            y += 14
        return s


def _opposite(direction: str) -> str:
    return {"north": "south", "south": "north", "east": "west", "west": "east",
            "up": "down", "down": "up"}.get(direction, direction)


_STYLE = """<style>
  .title { font-size: 26px; font-weight: bold; fill: #222; }
  .subtitle { font-size: 12px; fill: #666; }
  .rnum { font-size: 10px; fill: #999; }
  .stairs { font-size: 10px; fill: #6a1b9a; font-weight: bold; }
  .rname { font-size: 12px; fill: #111; font-weight: bold; }
  .mark { font-size: 9px; fill: #333; }
  .mark-M { fill: #b71c1c; }
  .mark-I { fill: #1565c0; }
  .mark-W { fill: #4527a0; }
  .mark-F { fill: #2e7d32; }
  .link { stroke: #444; stroke-width: 2; }
  .link.oneway { stroke: #444; }
  .portal { stroke: #6a1b9a; stroke-width: 1.6; stroke-dasharray: 5 4; fill: none; }
  .vlink { stroke: #2e7d32; stroke-width: 1.3; stroke-dasharray: 2 3; fill: none; opacity: 0.75; }
  .ptag { font-size: 9px; fill: #6a1b9a; font-weight: bold; }
  .legend { font-size: 11px; fill: #444; }
</style>"""

_DEFS = """<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
          markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#444"/>
  </marker>
</defs>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--level", type=int, help="render only this level (1-8)")
    ap.add_argument("--cell", type=int, default=None,
                    help=f"room cell size in px (default {MapRenderer.CELL})")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "level_maps",
                    help="output directory (default tools/level_maps/)")
    ap.add_argument("--png", type=int, nargs="?", const=2400, default=None,
                    metavar="WIDTH",
                    help="also write a PNG (needs cairosvg); optional pixel width")
    args = ap.parse_args()

    levels = [args.level] if args.level else sorted(
        int(p.stem.split("_")[1])
        for p in SERVER_DIR.glob("level_*.json")
    )
    args.out.mkdir(parents=True, exist_ok=True)
    rsvg = shutil.which("rsvg-convert")

    for level in levels:
        r = MapRenderer(level, cell=args.cell)
        svg_path = args.out / f"level_{level}.svg"
        svg_path.write_text(r.render())
        layout = "walk" if r.graph_layout else "grid"
        note = f"{r.n_cols}x{r.n_rows} {layout}, {len(r.rooms)} rooms"
        if r.parked:
            note += f", {len(r.parked)} parked (no walkable link from start)"
        print(f"level {level}: {svg_path}  ({note})")
        if rsvg:
            pdf_path = args.out / f"level_{level}.pdf"
            subprocess.run([rsvg, "-f", "pdf", "-o", str(pdf_path), str(svg_path)],
                           check=False)
            print(f"level {level}: {pdf_path}")
        if args.png is not None:
            try:
                import cairosvg
            except ImportError:
                print("  (--png needs cairosvg: pip install cairosvg)")
            else:
                png_path = args.out / f"level_{level}.png"
                cairosvg.svg2png(url=str(svg_path), write_to=str(png_path),
                                 output_width=args.png)
                print(f"level {level}: {png_path}")


if __name__ == "__main__":
    main()
