#!/bin/sh
# One explicitly armed trial. Never included in the ordinary service package.
set -u
umask 077
TRIAL=/data/cellforge/recovery-trial
USB=/sys/class/android_usb/android0
SELF=$TRIAL/executor.sh
JOURNAL=$TRIAL/journal.sh
MODE=${1:-status}
TICKET=${2:-}

trial_clock() { read -r up rest < /proc/uptime; printf '%s\n' "${up%%.*}"; }
trial_note() { sh "$JOURNAL" record "$TICKET" "$1" "$2"; }
trial_control_matches() {
    test "$(cat "$USB/enable")" = 1 &&
    test "$(cat "$USB/functions")" = diag,serial,ecm,ffs &&
    test "$(cat "$USB/idVendor")" = 2ca3 && test "$(cat "$USB/idProduct")" = 4006
}
trial_snapshot() {
    for name in adbd qti netmgrd quectel_daemon; do
        found=0
        for path in /proc/[0-9]*/comm; do
            test "$(cat "$path" 2>/dev/null)" = "$name" || continue
            pid=${path#/proc/}; pid=${pid%/comm}
            born=$(awk '{print $22}' "/proc/$pid/stat") || return 1
            printf '%s %s\n' "$name" "$born"
            found=$((found + 1))
        done
        test "$found" = 1 || return 1
    done
}
trial_preflight() {
    trial_control_matches && test "$(cat "$USB/state")" = CONFIGURED &&
    test "$(cat "$USB/usb_sleep")" = 0 || return 1
    test "$(sha256sum /usr/bin/ql_usbcfg | awk '{print $1}')" = 2350af7e14220758726a87a9b0c51b6e20136c27ae10d7c784973f64bd276b04 || return 1
    test "$(sha256sum /usr/lib/libql_usb.so.1 | awk '{print $1}')" = 78448a4de2dfbefbf3023e6a44c992d687340a342c6ba31b5d6ccce2aa578ccd || return 1
    test -w "$USB/enable" && test -e /dev/usb-ffs/adb/ep0 &&
    test -e /dev/usb-ffs/adb/ep1 && test -e /dev/usb-ffs/adb/ep2 || return 1
    test "$(trial_snapshot)" = "$(cat "$TRIAL/factory.before")"
}
trial_write() {
    # The only writable USB node; a timed-out write is an unknown outcome.
    case "$1" in 0|1) ;; *) return 64;; esac
    timeout -t 5 sh -c 'printf "%s\n" "$1" > /sys/class/android_usb/android0/enable' sh "$1"
}
trial_result() {
    case "$1" in 0) echo ok;; 124|137|143) echo timeout;; *) echo unknown;; esac
}
trial_guard_alive() {
    read -r guard_pid guard_born < "$TRIAL/guard.identity" || return 1
    test -n "$guard_born" && test "$(awk '{print $22}' "/proc/$guard_pid/stat" 2>/dev/null)" = "$guard_born" &&
    test ! -e "$TRIAL/guard.result"
}
trial_restore() {
    test -f "$TRIAL/issued" || return 0
    test ! -f "$TRIAL/restore-attempted" || return 0
    # Restoring after a possibly successful disable outranks journal errors.
    : > "$TRIAL/restore-attempted"
    trial_note connect_requested pending || printf '%s\n' journal_unavailable > "$TRIAL/emergency-main"
    trial_write 1
    restore_code=$?
    trial_note connect_returned "$(trial_result "$restore_code")" || printf '%s\n' journal_unavailable > "$TRIAL/emergency-main"
    if test "$restore_code" = 0 && trial_control_matches; then
        printf '%s\n' control_matches > "$TRIAL/control.result"
    else
        printf '%s\n' restore_unconfirmed > "$TRIAL/control.result"
    fi
    return "$restore_code"
}
trial_execute() (
    exec 8> "$TRIAL/operation.lock"
    flock -n 8 || exit 1
    test ! -e "$TRIAL/issued" || exit 1
    trial_preflight || exit 1
    trial_note disconnect_requested pending || exit 1
    trial_guard_alive || exit 1
    trap 'trial_restore' EXIT
    trap 'exit 1' HUP INT TERM
    trial_clock > "$TRIAL/issued"
    trial_write 0
    disable_code=$?
    trial_note disconnect_returned "$(trial_result "$disable_code")" || printf '%s\n' journal_unavailable > "$TRIAL/emergency-main"
    if test "$disable_code" = 0; then sleep 2; fi
    trial_restore
    restore_code=$?
    test "$disable_code" = 0 && test "$restore_code" = 0 && trial_control_matches || exit 1
)
trial_guard() (
    printf '%s\n' ready > "$TRIAL/guard.ready"
    deadline=$(($(trial_clock) + 60))
    while ! test -f "$TRIAL/issued"; do
        test ! -e "$TRIAL/abort" || exit 0
        test "$(trial_clock)" -lt "$deadline" || { echo no_action > "$TRIAL/guard.result"; exit 0; }
        sleep 1
    done
    issued=$(cat "$TRIAL/issued")
    case "$issued" in ''|*[!0-9]*) exit 1;; esac
    while test "$(trial_clock)" -lt "$((issued + 10))"; do sleep 1; done
    exec 9> "$TRIAL/operation.lock"
    if ! flock -n 9; then echo operation_busy > "$TRIAL/guard.result"; exit 0; fi
    if trial_control_matches; then echo control_already_matches > "$TRIAL/guard.result"; exit 0; fi
    trial_write 1
    code=$?
    printf 'restore_call_%s\n' "$(trial_result "$code")" > "$TRIAL/guard.result"
    sync
)
trial_wait() (
    # Own session survives closing the host's ADB shell.
    nohup setsid sh "$SELF" safeguard "$TICKET" </dev/null > "$TRIAL/guard.log" 2>&1 &
    guard_pid=$!
    printf '%s %s\n' "$guard_pid" "$(awk '{print $22}' /proc/$guard_pid/stat)" > "$TRIAL/guard.identity"
    count=0
    while ! test -f "$TRIAL/guard.ready"; do
        count=$((count + 1)); test "$count" -lt 10 || exit 1; sleep 1
    done
    trial_note executor_ready ok || exit 1
    printf '%s\n' ready > "$TRIAL/executor.ready"
    deadline=$(($(trial_clock) + 20))
    while ! test -f "$TRIAL/go"; do
        test ! -e "$TRIAL/abort" || exit 0
        test "$(trial_clock)" -lt "$deadline" || exit 1
        sleep 1
    done
    sleep 3
    trial_execute
    code=$?
    printf '%s\n' "$code" > "$TRIAL/executor.exit"
    if trial_control_matches && test "$(trial_snapshot)" = "$(cat "$TRIAL/factory.before")"; then
        echo identities_match > "$TRIAL/factory.result"
    else
        echo preflight_changed > "$TRIAL/factory.result"
    fi
    sync
    exit "$code"
)

case "$MODE" in
library) ;; # Isolated host fixtures source functions, then replace I/O seams.
*)
    case "$TICKET" in ''|*[!0-9.]*|.*|*.) exit 64;; esac
    test "${#TICKET}" -le 48 || exit 64
    test "$(awk 'NR==1 {print $2}' "$TRIAL/events.tsv" 2>/dev/null)" = "$TICKET" || exit 1
    case "$MODE" in
    check)
        trial_preflight || exit 1
        sleep 10
        trial_preflight || exit 1
        echo stable_preflight
    ;;
    arm)
        test ! -e "$TRIAL/claimed" || exit 1
        mkdir "$TRIAL/claimed" || exit 1
        trial_preflight || exit 1
        nohup setsid sh "$SELF" await "$TICKET" </dev/null > "$TRIAL/executor.log" 2>&1 &
        count=0
        while ! test -f "$TRIAL/executor.ready"; do
            count=$((count + 1))
            if test "$count" -ge 10; then : > "$TRIAL/abort"; exit 1; fi
            sleep 1
        done
        echo executor_and_safeguard_ready
    ;;
    release)
        test -f "$TRIAL/executor.ready" && test -f "$TRIAL/guard.ready" && test ! -e "$TRIAL/issued" && test ! -e "$TRIAL/go" || exit 1
        : > "$TRIAL/go"
        echo single_trial_released
    ;;
    await) trial_wait;;
    safeguard) trial_guard;;
    *) exit 64;;
    esac
;;
esac
