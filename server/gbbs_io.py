#!/bin/env python3
"""
gbbs_io.py

Low-level binary file reader for GBBS/ACOS/SPUR data files.

All SPUR data files share the same physical format:
  - Fixed-size records, null-padded to record_size bytes
  - Fields within each record separated by CR (0x0D)
  - Record 0 is either all-nulls or contains a record count
  - Apple II DOS 'T' (text) files have the high bit set on every byte;
    other files are plain ASCII. We auto-detect which is which.

Usage:
    from gbbs_io import read_file, iter_records, RECORD_SIZES

    data = read_file('monsters.txt')
    for record_num, fields in iter_records(data, record_size=32):
        status, info, strength, *rest = fields
"""

import logging
from pathlib import Path
from typing import Iterator
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Known record sizes from file-formats.txt.
# These are best guesses -- update as more files are confirmed.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Record:
    filename: str
    record_size: int
    record_count: int
#                     filename,   rec_size, rec_count
record_info = [Record('monsters',       32, 160),
               Record('weapons',        34,   0),
               Record('items',          30,   0),
               Record('spur.monsters',  44,   0),
               Record('spur.users',    130,   0),
               Record('spur.status',    32,   0),
               Record('spur.stores',    44,   0),
               Record('spur.spells',    44,   0),
               Record('spur.weapons',   64,   0),
               Record('spur.allies',    78,   0),
               Record('allies',         15,   0),
               Record('ally.items',     84,   0),
               Record('honor',          10,   0),
               Record('misc.data',     250,   0),
]

# High-bit detection threshold: if this fraction of non-null bytes
# have bit 7 set, treat the whole file as Apple II high-bit encoded.
HIGH_BIT_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# High-bit detection and stripping
# ---------------------------------------------------------------------------

def _has_high_bits(data: bytes) -> bool:
    """Return True if the majority of non-null bytes have bit 7 set."""
    non_null = [b for b in data if b != 0x00]
    if not non_null:
        return False
    high = sum(1 for b in non_null if b & 0x80)
    ratio = high / len(non_null)
    logging.debug("High-bit ratio: %.2f (%d/%d bytes)", ratio, high, len(non_null))
    return ratio >= HIGH_BIT_THRESHOLD


def strip_high_bits(data: bytes) -> bytes:
    """Strip the high bit from every byte."""
    return bytes(b & 0x7F for b in data)


def normalize(data: bytes) -> bytes:
    """
    Auto-detect and strip high bits if needed.
    Returns plain 7-bit ASCII bytes.
    """
    if _has_high_bits(data):
        logging.info("High-bit encoding detected, stripping.")
        return strip_high_bits(data)
    return data


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

def read_file(path: str | Path) -> bytes:
    """
    Read a SPUR data file and return normalized (7-bit ASCII) bytes.
    High bits are stripped automatically if detected.
    """
    data = Path(path).read_bytes()
    logging.info("Read %d bytes from '%s'", len(data), path)
    return normalize(data)


# ---------------------------------------------------------------------------
# Record iteration
# ---------------------------------------------------------------------------

def _split_record(chunk: bytes) -> list[str]:
    """
    Split a raw record chunk into fields.
    Strips null bytes, splits on CR (0x0D) or high-bit comma (0xAC),
    strips whitespace from each field.
    Returns only non-empty fields.
    """
    # Normalise 0xAC (high-bit comma) to 0x0D before splitting
    clean = chunk.replace(b'\x00', b'').replace(b'\xac', b'\x0d')
    fields = clean.split(b'\x0d')
    return [f.decode('ascii', errors='replace').strip()
            for f in fields if f.strip(b'\x00\x0d\x20')]

def iter_records(data: bytes,
                 record_size: int,
                 skip_first: bool = True) -> Iterator[tuple[int, list[str]]]:
    """
    Iterate over fixed-size records in a SPUR data file.

    Yields (record_number, fields) tuples where:
      - record_number is 1-based (matching in-game numbering)
      - fields is a list of non-empty strings from the record

    Args:
        data:        Normalized (7-bit) file bytes from read_file()
        record_size: Fixed record size in bytes
        skip_first:  If True (default), skip record 0 which is typically
                     a count or padding record
    """
    total = len(data) // record_size
    logging.info("Record size: %d, total records: %d", record_size, total)

    start_idx = 1 if skip_first else 0
    for i in range(start_idx, total):
        chunk = data[i * record_size:(i + 1) * record_size]
        # Skip all-null records
        if not chunk.strip(b'\x00'):
            logging.debug("Skipping null record %d", i)
            continue
        fields = _split_record(chunk)
        if fields:
            yield i, fields


def read_count(data: bytes, record_size: int) -> int | None:
    """
    Try to read a record count from record 0.
    Returns the count as an int, or None if record 0 is empty or non-numeric.
    """
    chunk = data[0:record_size]
    fields = _split_record(chunk)
    if fields and fields[0].isdigit():
        count = int(fields[0])
        logging.info("Record count from file header: %d", count)
        return count
    logging.debug("Record 0 is empty or non-numeric: %r", fields)
    return None


# ---------------------------------------------------------------------------
# Convenience: look up record size by filename
# ---------------------------------------------------------------------------

def record_size_for(filename: str | Path) -> int | None:
    """
    Look up the known record size for a given filename.
    Matches case-insensitively against RECORD_INFO keys.
    Returns None if unknown.
    """
    stem = Path(filename).stem.lower()
    info = RECORD_INFO.get(stem)
    if info is None:
        logging.warning("Unknown record info for '%s'", filename)
        return None
    return info.record_size