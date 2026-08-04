#!/bin/sh
# check_midnight_routines.sh — verify last night's anacron-driven
# tada-guild-maintenance job actually ran (see /etc/cron.daily/tada-guild-maintenance
# and tools/nightly_guild_maintenance.py).
#
# Run manually the morning after: ./tools/check_midnight_routines.sh

SERVER_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo '--- anacron/syslog entries ---'
grep -i tada-guild-maintenance /var/log/syslog 2>/dev/null \
    || journalctl -u anacron --since "1 day ago" | grep -i tada-guild-maintenance

echo
echo '--- tail of nightly_guild_maintenance.log ---'
tail -20 "$SERVER_DIR/run/server/nightly_guild_maintenance.log"

echo
echo '--- guild_control.json generated_at ---'
python3 -c "import json; print(json.load(open('$SERVER_DIR/run/server/guild_control.json'))['generated_at'])"
