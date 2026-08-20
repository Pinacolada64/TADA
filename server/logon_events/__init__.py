"""logon_events — small, focused login-time event modules.

Mirrors ally_events/'s package-of-small-focused-modules convention.
First concrete module: birthday.py, since joined by unconscious_wake.py,
ally_greeting.py, and news.py. See TODO.md's "Modular logon/logoff
event system" entry for the larger, not-yet-built idea this is a first
step toward (auto-discovery, scheduling, a matching logoff_events/
package) -- for now, each module here is wired in directly by its
caller (commands/connect.py), not auto-discovered.
"""
