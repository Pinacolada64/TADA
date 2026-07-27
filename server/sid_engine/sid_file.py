"""sid_engine/sid_file.py — parse a PSID/RSID (.sid) file header.

A .sid file is a small big-endian header (magic, version, load/init/play
addresses, subtune count, etc. -- see the High Voltage SID Collection's
SIDPLAY_FILEFORMAT.txt for the full spec) followed by the raw C64
memory image to load, starting at the header's load address.

Only PSID files are supported -- see sid_dump.py's module docstring for
why RSID (and PSID files with play_address == 0, which behave the same
way RSID does: the tune installs its own IRQ handler rather than
exposing a plain play() subroutine) are out of scope.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class SidFileError(Exception):
    """The file isn't a valid/supported .sid file."""


@dataclass
class SidFile:
    version:      int
    load_address: int
    init_address: int
    play_address: int
    num_songs:    int
    start_song:   int   # 1-based
    speed:        int   # bit i = 1 -> song i+1 uses CIA timing, 0 -> 50Hz VBI
    name:         str
    author:       str
    released:     str
    data:         bytes  # C64 memory image, load it at load_address


_HEADER_MIN_LEN = 0x76


def parse(raw: bytes) -> SidFile:
    if len(raw) < _HEADER_MIN_LEN:
        raise SidFileError(f'file too short ({len(raw)} bytes) to be a valid PSID header')

    magic = raw[0:4]
    if magic == b'RSID':
        raise SidFileError(
            'RSID files are not supported -- they assume a real KERNAL/IRQ '
            'environment (own CIA timer setup, real hardware banking) rather '
            "than sid_dump.py's plain call-init-then-call-play convention.")
    if magic != b'PSID':
        raise SidFileError(f'not a PSID/RSID file (magic bytes were {magic!r})')

    (version, data_offset, load_address, init_address, play_address,
     num_songs, start_song) = struct.unpack_from('>7H', raw, 4)
    speed, = struct.unpack_from('>I', raw, 0x12)

    name     = raw[0x16:0x36].split(b'\x00', 1)[0].decode('latin-1')
    author   = raw[0x36:0x56].split(b'\x00', 1)[0].decode('latin-1')
    released = raw[0x56:0x76].split(b'\x00', 1)[0].decode('latin-1')

    if data_offset > len(raw):
        raise SidFileError(f'data offset ${data_offset:04x} is past end of file')
    data = raw[data_offset:]

    if load_address == 0:
        # Load address 0 means the real load address is embedded as the
        # first two (little-endian) bytes of the data, same as a raw .prg.
        if len(data) < 2:
            raise SidFileError('data too short for an embedded load address')
        load_address = data[0] | (data[1] << 8)
        data = data[2:]

    if init_address == 0:
        init_address = load_address  # per spec: 0 means "same as load address"

    if play_address == 0:
        raise SidFileError(
            'play address is 0 -- this tune installs its own IRQ handler '
            'instead of exposing a plain play() routine, which needs full '
            'CIA/IRQ emulation sid_dump.py does not provide (same class of '
            'tune as RSID, see above).')

    if not (1 <= start_song <= max(num_songs, 1)):
        start_song = 1

    return SidFile(
        version=version, load_address=load_address, init_address=init_address,
        play_address=play_address, num_songs=num_songs, start_song=start_song,
        speed=speed, name=name, author=author, released=released, data=data,
    )


def load(path: str | Path) -> SidFile:
    return parse(Path(path).read_bytes())
