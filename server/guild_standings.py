"""guild_standings.py — Win/loss tally per guild, updated after PvP duels.

SPUR source: SPUR.DUEL2.S's `guild` label (~lines 316-336). After any
guild-vs-guild duel it tallies a win/loss counter per guild to a
`guild.standings` data file (`vv`/`yz` are the duelists' guild numbers,
`zz`/`yw` the running win/loss counts, position-addressed by guild slot
1/2/3). Civilian/Outlaw duelists don't participate in guild standings in
the original (`if (vv<3) or (yz<3) goto personal`), matching the guarded
call site here.

Storage schema (run/server/guild_standings.json):
  {
    "<Guild.value>": {"wins": N, "losses": N}
  }

MECHANICS.md lists this as a not-yet-implemented "Guild standings" stub;
this module is the persistence half of it. Not yet wired into a display
command -- see combat/duel.py's DuelCommand, which calls
record_duel_result() after every guild-vs-guild SPORT DUEL.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_STANDINGS_FILE = Path('run') / 'server' / 'guild_standings.json'


def load_standings() -> dict:
    """Return the standings dict (guild value -> {"wins": N, "losses": N})."""
    try:
        if _STANDINGS_FILE.exists():
            return json.loads(_STANDINGS_FILE.read_text())
    except Exception:
        log.exception('Failed to load guild standings')
    return {}


def save_standings(standings: dict) -> None:
    _STANDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STANDINGS_FILE.write_text(json.dumps(standings, indent=2))


def record_duel_result(winner_guild: str, loser_guild: str) -> None:
    """Increment winner_guild's win count and loser_guild's loss count.

    Caller's job to skip this for Civilian/Outlaw duelists (SPUR only
    tallies guild-vs-guild duels -- see module docstring).
    """
    standings = load_standings()
    win_entry  = standings.setdefault(winner_guild, {'wins': 0, 'losses': 0})
    lose_entry = standings.setdefault(loser_guild,  {'wins': 0, 'losses': 0})
    win_entry['wins']    += 1
    lose_entry['losses'] += 1
    save_standings(standings)
