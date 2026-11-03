#!/bin/sh
# Bounded production executor. Only enable 0/1; all decisions belong to collector.
set -u
umask 077
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
AUTO=/tmp/cellforge/auto
USB=/sys/class/android_usb/android0
LOG=/data/cellforge/recovery-events.tsv
MODE=${1:-}; NUMBER=${2:-}; TOKEN=${3:-}
WORK=$AUTO/action$NUMBER
auto_clock() { read -r up rest < /proc/uptime; echo "${up%%.*}"; }
auto_born() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }
auto_phase() { printf '%s\n' "$1" > "$WORK/phase.new" && mv "$WORK/phase.new" "$WORK/phase"; }
auto_event() (
    exec 7> "$AUTO/log.lock"
    flock -n 7 || exit 1
    # Closed vocabulary supplied only by this file. Keep 32 rows, <=8192 bytes.
    test ! -L "$LOG" || exit 1
    if test -f "$LOG"; then tail -n 31 "$LOG" > "$LOG.new"; else : > "$LOG.new"; fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(auto_clock)" "$NUMBER" "$1" "$2" >> "$LOG.new"
    test "$(wc -c < "$LOG.new")" -le 8192 || exit 1
    sync && mv "$LOG.new" "$LOG" && sync
)
auto_control() {
    test "$(cat "$USB/enable")" = 1 && test "$(cat "$USB/functions")" = diag,serial,ecm,ffs &&
    test "$(cat "$USB/idVendor")" = 2ca3 && test "$(cat "$USB/idProduct")" = 4006
}
auto_owner() {
    test ! -e "$WORK/cancel" && test "$(cat /tmp/cellforge/current 2>/dev/null)" = "$TOKEN" || return 1
    read -r owner_pid owner_born < "/tmp/cellforge/control/$TOKEN/supervisor.pid" || return 1
    test -n "$owner_born" && test "$(auto_born "$owner_pid")" = "$owner_born" || return 1
    beat=$(cat "/tmp/cellforge/control/$TOKEN/heartbeat" 2>/dev/null || echo 0)
    test "$(($(auto_clock) - beat))" -le 8
}
auto_check() {
    auto_owner && auto_control && test "$(cat "$USB/state")" = CONFIGURED && test "$(cat "$USB/usb_sleep")" = 0 || return 1
    test "$(sha256sum /usr/bin/ql_usbcfg | awk '{print $1}')" = 2350af7e14220758726a87a9b0c51b6e20136c27ae10d7c784973f64bd276b04 || return 1
    test "$(sha256sum /usr/lib/libql_usb.so.1 | awk '{print $1}')" = 78448a4de2dfbefbf3023e6a44c992d687340a342c6ba31b5d6ccce2aa578ccd || return 1
    test -e /dev/usb-ffs/adb/ep0 && test -e /dev/usb-ffs/adb/ep1 && test -e /dev/usb-ffs/adb/ep2
}
auto_write() {
    case "$1" in 0|1) ;; *) return 64;; esac
    timeout -t 5 sh -c 'printf "%s\n" "$1" > /sys/class/android_usb/android0/enable' sh "$1"
}
auto_code() { case "$1" in 0) echo ok;; 124|137|143) echo timeout;; *) echo unknown;; esac; }
auto_restore() {
    test -f "$WORK/pending" && test ! -f "$WORK/restore-attempted" || return 0
    : > "$WORK/restore-attempted"
    auto_phase connecting
    # Never wait for a flash/log operation while USB is disabled.
    auto_write 1
    restored=$?
    printf '%s\n' "$(auto_code "$restored")" > "$WORK/connect.result"
    if test "$restored" = 0 && auto_control; then rm -f "$WORK/pending"; fi
    return "$restored"
}
auto_release_wake() {
    if test -f "$WORK/wakelock"; then
        printf '%s\n' "cellforge_recovery_$NUMBER" > /sys/power/wake_unlock 2>/dev/null || true
        rm -f "$WORK/wakelock"
    fi
}
auto_guard_alive() {
    read -r guard_pid guard_born < "$WORK/guard.pid" || return 1
    test -n "$guard_born" && test "$(auto_born "$guard_pid")" = "$guard_born" && test ! -e "$WORK/guard.done"
}
auto_cycle() (
    exec 8> "$AUTO/operation.lock"
    flock -n 8 || exit 1
    test ! -e "$WORK/issued" || exit 1
    auto_check || exit 1
    auto_event requested pending || exit 1
    auto_owner && auto_guard_alive || exit 1
    trap 'auto_restore' EXIT
    trap 'exit 1' HUP INT TERM
    auto_clock > "$WORK/issued.new" && mv "$WORK/issued.new" "$WORK/issued" || exit 1
    : > "$WORK/pending"
    auto_phase disconnecting
    auto_write 0
    disabled=$?
    printf '%s\n' "$(auto_code "$disabled")" > "$WORK/disconnect.result"
    if test "$disabled" = 0; then sleep 2; fi
    auto_restore
    restored=$?
    test "$disabled" = 0 && test "$restored" = 0 && auto_control
)
auto_guard() {
    echo ready > "$WORK/guard.ready"
    until_time=$(($(auto_clock) + 60))
    while ! test -f "$WORK/issued"; do
        if test -e "$WORK/done" || test "$(auto_clock)" -ge "$until_time"; then
            echo no_action > "$WORK/guard.done"
            read -r actor_pid actor_born < "$WORK/actor.pid"
            test "$(auto_born "$actor_pid")" = "$actor_born" || auto_release_wake
            return
        fi
        sleep 1
    done
    issued=$(cat "$WORK/issued")
    while test "$(auto_clock)" -lt "$((issued + 10))"; do sleep 1; done
    (
        exec 9> "$AUTO/operation.lock"
        if ! flock -n 9; then echo operation_busy > "$WORK/guard.done"; exit; fi
        if auto_control; then
            rm -f "$WORK/pending"
            echo control_matches > "$WORK/guard.done"
        else
            auto_write 1
            result=$?
            printf 'restore_%s\n' "$(auto_code "$result")" > "$WORK/guard.done"
            if test "$result" = 0 && auto_control; then rm -f "$WORK/pending"; fi
            auto_event safeguard "$(auto_code "$result")" || true
        fi
    )
    read -r actor_pid actor_born < "$WORK/actor.pid"
    test "$(auto_born "$actor_pid")" = "$actor_born" || auto_release_wake
}
auto_run() {
    mkdir "$WORK/executor.claim" || return 1
    printf '%s %s\n' "$$" "$(auto_born "$$")" > "$WORK/actor.pid"
    trap 'auto_release_wake; : > "$WORK/done"' EXIT
    trap 'auto_phase aborted; exit 1' HUP INT TERM
    auto_check || { echo no_action > "$WORK/guard.done"; auto_phase aborted; return 1; }
    if ! printf '%s\n' "cellforge_recovery_$NUMBER" > /sys/power/wake_lock; then
        echo no_action > "$WORK/guard.done"; auto_phase aborted; return 1
    fi
    : > "$WORK/wakelock"
    nohup setsid sh "$BASE/auto-recover.sh" safeguard "$NUMBER" "$TOKEN" </dev/null > "$WORK/guard.log" 2>&1 &
    guard_pid=$!
    printf '%s %s\n' "$guard_pid" "$(auto_born "$guard_pid")" > "$WORK/guard.pid"
    tries=0
    while ! test -f "$WORK/guard.ready"; do
        tries=$((tries + 1)); test "$tries" -lt 10 || { auto_phase aborted; return 1; }
        sleep 1
    done
    if ! auto_cycle; then
        auto_phase failed
        auto_event calls failed || true
        return 1
    fi
    auto_phase waiting
    auto_event calls returned || true
    deadline=$(cat "$WORK/deadline")
    while test "$(auto_clock)" -lt "$deadline"; do
        if test -f "$WORK/confirmed"; then
            auto_phase confirmed; auto_event result confirmed || true; return 0
        fi
        if ! auto_owner; then auto_phase aborted; auto_event result collector_lost || true; return 1; fi
        sleep 1
    done
    auto_phase failed; auto_event result timeout || true
    return 1
}
case "$MODE" in
library) ;;
run|safeguard)
    case "$NUMBER" in 1|2|3) ;; *) exit 64;; esac
    case "$TOKEN" in ''|*[!0-9.]*) exit 64;; esac
    test "$(cat "$WORK/token" 2>/dev/null)" = "$TOKEN" || exit 1
    if test "$MODE" = run; then auto_run; else auto_guard; fi
;;
*) exit 64;;
esac
