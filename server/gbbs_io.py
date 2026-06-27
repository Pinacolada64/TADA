#!/bin/env python3
"""
gbbs_io.py

Low-level binary file reader for GBBS/ACOS/SPUR data files.

All SPUR data files share the same physical format:
  - Fixed-size records, null-padded to record_size bytes
  - Fields within each record separated by CR (0x0D) or
    high-bit comma (0xAC = 0x2C | 0x80)
  - Record 0 is either all-nulls or contains a record count
  - Apple II DOS 'T' (text) files have the high bit set on every byte;
    other files are plain ASCII. We auto-detect which is which.

Usage:
    import gbbs_io
    from gbbs_io import read_file, iter_records, read_count

    data = read_file('monsters.txt')
    for record_num, fields in iter_records(data, gbbs_io.RECORD_INFO['monsters'].record_size):
        status, info, strength, *rest = fields
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# RecordInfo -- describes the physical layout of a data file's records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecordInfo:
    record_size:  int
    field_count:  int
    description:  str = ''    # optional, for documentation purposes


# ---------------------------------------------------------------------------
# Known record info from file-formats.txt.
# field_count=0 means not yet reverse-engineered -- update as confirmed.
# ---------------------------------------------------------------------------
RECORD_INFO: dict[str, RecordInfo] = {
    'items':         RecordInfo(30,  3, 'active, type.name, price'),
    'monsters':      RecordInfo(32,  5, 'active, type.[size]name|flags, strength, special_weapon, to_hit'),
    'weapons':       RecordInfo(34,  6, 'location, kind.sfx_class.name|flags, stability, to_hit, price, weapon_class'),
    'spur.monsters': RecordInfo(44,  5, 'location, type.[size]name|flags, strength, special_weapon, to_hit'),
    'spur.users':    RecordInfo(130, 0, ''),
    'spur.status':   RecordInfo(32,  0, ''),
    'spur.stores':   RecordInfo(44,  0, ''),
    'spur.spells':   RecordInfo(44,  0, ''),
    'spur.weapons':  RecordInfo(64,  0, ''),
    'spur.allies':   RecordInfo(78,  0, ''),
    'allies':        RecordInfo(15,  0, ''),
    'ally.items':    RecordInfo(84,  0, ''),
    'honor':         RecordInfo(10,  0, ''),
    'misc.data':     RecordInfo(250, 0, ''),
}


# ---------------------------------------------------------------------------
# High-bit detection threshold: if this fraction of non-null bytes
# have bit 7 set, treat the whole file as Apple II high-bit encoded.
# ---------------------------------------------------------------------------
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
    High-bit comma (0xAC) field separators are replaced with CR first,
    before high-bit detection, since they appear regardless of whether
    the rest of the file has high bits set.
    High bits are then stripped automatically if detected.
    """
    data = Path(path).read_bytes()
    logging.info("Read %d bytes from '%s'", len(data), path)
    # Replace 0xAC (high-bit comma, used as field separator) with CR
    # before normalize() so it isn't counted in the high-bit ratio
    # and isn't accidentally stripped to 0x2C (plain comma).
    data = data.replace(b'\xac', b'\x0d')
    return normalize(data)


# ---------------------------------------------------------------------------
# Record iteration
# ---------------------------------------------------------------------------

def _split_record(chunk: bytes) -> list[str]:
    """
    Split a raw record chunk into fields.
    Strips null bytes, splits on CR (0x0D), strips whitespace from each field.
    Returns only non-empty fields.
    Note: 0xAC (high-bit comma) separators are replaced with CR in
    read_file() before records are split, so they don't need handling here.
    """
    logging.debug("Raw chunk: %s", chunk.hex(' '))
    clean = chunk.replace(b'\x00', b'')
    fields = clean.split(b'\x0d')
    result = [f.decode('ascii', errors='replace').strip()
              for f in fields if f.strip(b'\x00\x0d\x20')]
    logging.debug("Fields: %r", result)
    return result


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
# Convenience: look up record info by filename
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