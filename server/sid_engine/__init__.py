"""sid_engine — SID register-write streaming for the C64 client.

A "tune" here is a sequence of frames, one per playback tick, where each
frame is a dict[int, int] mapping SID register offset (0-24, i.e. an
offset from $D400) to the byte value written that tick. frames.py encodes
that representation into the wire format tada-client.asm's IRQ-driven
sid_play consumes; stub_tune.py is a hand-built placeholder tune used
until real SID emulation/rendering exists.
"""
