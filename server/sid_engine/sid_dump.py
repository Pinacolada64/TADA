"""sid_engine/sid_dump.py — run a PSID tune's init/play routines on a
6502 emulator and record every SID register write as a per-tick frame.

A .sid file isn't audio -- it's 6502 machine code plus a header naming an
init routine (called once, per subtune) and a play routine (called once
per frame, normally by an IRQ on real hardware). To get a register-write
log out of it, the code actually has to run. This uses py65 (a pure-
Python 6502 emulator, see requirements.txt) rather than a hand-written
CPU core or scripting VICE's remote monitor -- py65's ObservableMemory
lets a write-callback sit directly on the SID register range, so each
play() call's writes are captured as they happen with no memory diffing.

Scope: PSID only, using the "call init/play as plain subroutines"
convention (sid_file.py already rejects RSID files and play_address==0
tunes, which both need a real IRQ-driven environment this module doesn't
provide). Only official 6502 opcodes are emulated; py65's handling of an
undocumented opcode is to silently treat it as a 1-byte no-op (advance pc
by 1) rather than raise -- it will not crash, but a tune that leans on
illegal-opcode tricks will most likely just run off the rails and either
produce garbage or trip the max_cycles safety net below, not fail
cleanly with a clear error.
"""
from __future__ import annotations

from typing import Iterator, Mapping

from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

from sid_engine.sid_file import SidFile

SID_BASE = 0xd400
SID_END  = 0xd419  # exclusive -- 25 registers, $D400-$D418

_CALL_SENTINEL = 0x0001


class SidEmulationError(Exception):
    """A tune's init/play routine misbehaved (never returned inside the
    cycle budget) -- distinct from SidFileError (a bad/unsupported file)."""


def _build_memory(sid: SidFile, writes: list) -> ObservableMemory:
    mem = ObservableMemory()
    mem.write(sid.load_address, sid.data)

    def on_write(address, value):
        writes.append((address - SID_BASE, value))

    mem.subscribe_to_write(range(SID_BASE, SID_END), on_write)
    return mem


def _call(mpu: MPU, address: int, *, a: int = 0, x: int = 0, y: int = 0,
          max_cycles: int = 1_000_000) -> None:
    """Run *address* as a subroutine (like JSR, but waits for the matching
    RTS instead of returning to real caller code) by pushing a sentinel
    return address onto the stack first. RTS does `pc = pop_word() + 1`
    (py65's mpu6502.py, inst_0x60), so pushing sentinel-1 makes the
    routine's own RTS land pc exactly on sentinel once it's done.
    """
    mpu.stPushWord(_CALL_SENTINEL - 1)
    mpu.pc = address
    mpu.a, mpu.x, mpu.y = a, x, y
    start_cycles = mpu.processorCycles
    while mpu.pc != _CALL_SENTINEL:
        mpu.step()
        if mpu.processorCycles - start_cycles > max_cycles:
            raise SidEmulationError(
                f'routine at ${address:04x} did not return within '
                f'{max_cycles} cycles -- infinite loop, or code that never '
                'reaches an RTS')


def convert(sid: SidFile, *, song: int | None = None, num_frames: int,
            max_cycles_per_call: int = 1_000_000) -> Iterator[Mapping[int, int]]:
    """Yield one frame dict per emulated play() call: register offset
    (0-24) -> the last value written to it during that call, in the same
    shape sid_engine.frames.encode_stream() expects.

    song is 1-based, defaulting to sid.start_song. There's no attempt to
    detect "song end" here -- most SID tunes loop forever by design, so
    num_frames (how much playback time to render) is the caller's call.
    """
    song_number = song if song is not None else sid.start_song

    writes: list[tuple[int, int]] = []
    mem = _build_memory(sid, writes)
    mpu = MPU(memory=mem)

    _call(mpu, sid.init_address, a=song_number - 1, max_cycles=max_cycles_per_call)

    for _ in range(num_frames):
        writes.clear()
        _call(mpu, sid.play_address, max_cycles=max_cycles_per_call)
        yield dict(writes)
