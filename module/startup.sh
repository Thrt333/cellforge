#!/bin/sh
# Cellforge-owned asynchronous SysV startup; factory networking remains independent.
set -u
BASE=/data/cellforge
FLAG=$BASE/autostart.enabled
case "${1:-start}" in
start)
    test -f "$FLAG" || exit 0
    nohup setsid sh "$BASE/startup.sh" wait </dev/null > /tmp/cellforge-boot.log 2>&1 &
;;
wait)
    count=0
    while test "$count" -lt 60 && test -f "$FLAG"; do
        if ip -o -4 addr show dev bridge0 2>/dev/null | grep -q '192\.168\.225\.1/24'; then
            exec sh "$BASE/current/cellforge.sh" start
        fi
        count=$((count + 1))
        sleep 2
    done
    echo 'Cellforge: USB LAN was not ready within startup deadline' >&2
    exit 1
;;
stop)
    if test -f "$BASE/current/cellforge.sh"; then sh "$BASE/current/cellforge.sh" stop; fi
;;
*) echo 'usage: startup.sh {start|stop}' >&2; exit 64;;
esac
