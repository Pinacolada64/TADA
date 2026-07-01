"""parse_date.py — Flexible date and date-range parser (dateutil-backed).

Public API
----------
parse_date(text)        -> date | None
parse_date_range(text)  -> tuple[date, date] | None
DATE_HELP               -> str  (paste into any prompt that accepts dates)

Supported single-date formats (all case-insensitive)
-----------------------------------------------------
  7/1/26          M/D/YY   → 2026-07-01
  7/1/2026        M/D/YYYY → 2026-07-01
  7/1             M/D, year assumed from _DEFAULT_YEAR → 2026-07-01
  2026-07-01      ISO 8601 → 2026-07-01
  Jul 1           month-name day, year from _DEFAULT_YEAR
  July 1          full month name
  Jul 1 2026      month-name day year
  July 1, 2026    with comma

Ambiguity note
--------------
  Dash-separated two-digit inputs (e.g. 1-7-26) are read M-D-YY, so
  1-7-26 = January 7, 2026 — NOT July 1.  Use slashes or month names
  to be unambiguous: 7/1/26 or Jul 1.

Supported range formats
-----------------------
  Jul 1 to Dec 31
  7/1/26 to 12/31/26
  from Jul 1 to Dec 31     leading "from" is stripped
  Jul 1 - Dec 31           single hyphen surrounded by spaces
  7/1 – 12/31              en-dash

  For open-ended ranges, pass a single date to parse_date() and
  construct the other end in calling code.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from dateutil import parser as _dp
from dateutil.parser import ParserError

# Year used when the input contains no year (e.g. "Jul 1", "7/1").
# Callers can override by monkeypatching or passing year= to parse_date().
_DEFAULT_YEAR = date.today().year

# Separators recognised between the two halves of a range.
_RANGE_SEP = re.compile(
    r'\s+to\s+|\s*–\s*|\s*—\s*|\s+-\s+',   # "to", en-dash, em-dash, spaced hyphen
    re.IGNORECASE,
)

DATE_HELP: str = """\
Date formats accepted:
  7/1/26        M/D/YY
  7/1/2026      M/D/YYYY
  7/1           M/D  (current year assumed)
  2026-07-01    ISO 8601
  Jul 1         month abbreviation + day
  July 1 2026   full month name + day + year

  Note: dash-separated numbers (1-7-26) are read M-D-YY, so 1-7-26 = Jan 7.
  Use slashes or month names to avoid ambiguity.

Date range formats:
  Jul 1 to Dec 31
  7/1/26 to 12/31/26
  from Jul 1 to Dec 31
  7/1 - 12/31            (spaced hyphen)
  7/1 – 12/31            (en-dash)\
"""


def parse_date(text: str, year: Optional[int] = None) -> Optional[date]:
    """Parse a single date string. Returns a date or None on failure."""
    if not text or not text.strip():
        return None
    text = text.strip()
    default_dt = _dp.parse(f'{year or _DEFAULT_YEAR}-01-01')
    try:
        return _dp.parse(text, default=default_dt).date()
    except (ParserError, ValueError, OverflowError):
        return None


def parse_date_range(
    text: str,
    year: Optional[int] = None,
) -> Optional[tuple[date, date]]:
    """Parse a date range string into a (start, end) pair.

    Returns None if the text cannot be parsed as a range.
    For a single date, use parse_date() instead.
    """
    if not text or not text.strip():
        return None

    # Strip leading "from"
    cleaned = re.sub(r'^\s*from\s+', '', text.strip(), flags=re.IGNORECASE)

    parts = _RANGE_SEP.split(cleaned, maxsplit=1)
    if len(parts) != 2:
        return None

    start = parse_date(parts[0].strip(), year=year)
    end   = parse_date(parts[1].strip(), year=year)

    if start is None or end is None:
        return None
    if end < start:
        # Tolerate reversed order by swapping
        start, end = end, start
    return start, end


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    singles = [
        '7/1/26', '7/1/2026', '7/1', '2026-07-01',
        'Jul 1', 'July 1', 'July 1 2026', 'July 1, 2026',
        '1-7-26',       # ambiguous: Jan 7
        'not a date',
    ]
    ranges = [
        'Jul 1 to Dec 31',
        '7/1/26 to 12/31/26',
        'from Jul 1 to Dec 31',
        '7/1 - 12/31',
        '7/1 – 12/31',
        'garbage to more garbage',
    ]

    print('=== Single dates ===')
    for s in singles:
        result = parse_date(s)
        print(f'  {s!r:25} -> {result}')

    print()
    print('=== Ranges ===')
    for s in ranges:
        result = parse_date_range(s)
        print(f'  {s!r:35} -> {result}')

    print()
    print('=== Help text ===')
    print(DATE_HELP)
