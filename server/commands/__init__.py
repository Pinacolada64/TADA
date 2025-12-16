"""
Commands package for TADA server.

This package provides a command system for the TADA server. To avoid expensive
imports and circular import problems during unit tests, submodules are not
imported automatically on package import; import the specific modules you
need (e.g. `commands.command_processor`) directly.
"""

__all__ = [
    # explicit exports are available by importing the submodules directly
]
