#!/bin/sh
# Trial evidence only. USB mutation stays disabled; not in the active package.
set -u
umask 077
JOURNAL_DIR=/data/cellforge/recovery-trial
JOURNAL_LIMIT=32
journal_valid_ticket() {
    case "$1" in ''|*[!0-9.]*|.*|*.) return 1;; esac
    test "${#1}" -le 48
}
journal_uptime() {
    read -r journal_up journal_rest < /proc/uptime 2>/dev/null || { echo unknown; return; }
    printf '%s\n' "${journal_up%%.*}"
}
journal_commit() {
    test "$(wc -c < "$JOURNAL_DIR/events.new")" -le 8192 || return 1
    sync || return 1
    mv "$JOURNAL_DIR/events.new" "$JOURNAL_DIR/events.tsv" || return 1
    sync
}
journal_valid_file() {
    test ! -L "$JOURNAL_DIR/events.tsv" || return 1
    test "$(wc -c < "$JOURNAL_DIR/events.tsv")" -le 8192 || return 1
    awk -F '\t' '
        NF != 6 || $1 != NR || $2 !~ /^[0-9.]+$/ {bad=1}
        NR==1 {ticket=$2; if ($5 != "prepared" || $6 != "ok") bad=1}
        $2 != ticket {bad=1}
        END {exit (bad || NR < 1 || NR > 32)}' "$JOURNAL_DIR/events.tsv"
}
journal_lock() {
    test ! -L "$JOURNAL_DIR" || return 1
    mkdir -p "$JOURNAL_DIR" || return 1
    chmod 700 "$JOURNAL_DIR" || return 1
    mkdir "$JOURNAL_DIR/lock" 2>/dev/null || {
        echo 'Trial journal locked; preserve evidence and inspect manually' >&2
        return 1
    }
    trap 'rmdir "$JOURNAL_DIR/lock" 2>/dev/null || true' EXIT
    trap 'exit 1' HUP INT TERM
}
journal_begin() (
    journal_valid_ticket "$1" || exit 64
    journal_lock || exit 1
    test ! -e "$JOURNAL_DIR/events.tsv" && test ! -e "$JOURNAL_DIR/events.new" || {
        echo 'Existing trial evidence retained; no automatic replacement' >&2
        exit 1
    }
    printf '1\t%s\t%s\t%s\tprepared\tok\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(journal_uptime)" > "$JOURNAL_DIR/events.new" || exit 1
    journal_commit
)
journal_record() (
    journal_valid_ticket "$1" || exit 64
    case "$2:$3" in
        executor_ready:ok|disconnect_requested:pending|connect_requested:pending|\
        disconnect_returned:ok|disconnect_returned:error|disconnect_returned:timeout|disconnect_returned:unknown|\
        connect_returned:ok|connect_returned:error|connect_returned:timeout|connect_returned:unknown|\
        enumeration_observed:ok|enumeration_observed:timeout|enumeration_observed:unknown|\
        address_observed:ok|address_observed:timeout|address_observed:unknown|\
        communication_observed:ok|communication_observed:timeout|communication_observed:unknown|\
        failed:error|aborted:unknown) ;;
        *) exit 64;;
    esac
    journal_lock || exit 1
    test -f "$JOURNAL_DIR/events.tsv" && test ! -L "$JOURNAL_DIR/events.tsv" || exit 1
    journal_valid_file || exit 1
    set -- "$1" "$2" "$3" "$(awk 'NR==1 {print $2}' "$JOURNAL_DIR/events.tsv")" \
        "$(awk 'END {print $1}' "$JOURNAL_DIR/events.tsv")" \
        "$(awk 'END {print $5 ":" $6}' "$JOURNAL_DIR/events.tsv")"
    test "$1" = "$4" || exit 1
    test "$5" -lt "$JOURNAL_LIMIT" || { echo 'Trial journal cutoff; no further action' >&2; exit 1; }
    # Unknown disconnect outcome still permits a recorded restoration attempt.
    case "$6>$2" in
        prepared:ok\>executor_ready|executor_ready:ok\>disconnect_requested|\
        disconnect_requested:pending\>disconnect_returned|disconnect_requested:pending\>connect_requested|\
        disconnect_returned:*\>connect_requested|connect_requested:pending\>connect_returned|\
        connect_returned:*\>enumeration_observed|enumeration_observed:ok\>address_observed|\
        address_observed:ok\>communication_observed) ;;
        failed:*\>*|aborted:*\>*|communication_observed:ok\>*) exit 1;;
        *\>failed|*\>aborted) ;;
        *) echo 'Invalid trial phase transition' >&2; exit 1;;
    esac
    test ! -e "$JOURNAL_DIR/events.new" || exit 1
    cat "$JOURNAL_DIR/events.tsv" > "$JOURNAL_DIR/events.new" || exit 1
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(($5 + 1))" "$1" \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(journal_uptime)" "$2" "$3" >> "$JOURNAL_DIR/events.new" || exit 1
    journal_commit
)
journal_status() {
    if ! test -f "$JOURNAL_DIR/events.tsv"; then echo no_trial_record; return; fi
    journal_valid_file || { echo 'outcome=invalid_record'; return 1; }
    cat "$JOURNAL_DIR/events.tsv"
    journal_last=$(awk 'END {print $5 ":" $6}' "$JOURNAL_DIR/events.tsv")
    case "$journal_last" in
        communication_observed:ok) echo 'outcome=communication_restored';;
        failed:*|aborted:*) echo 'outcome=trial_stopped';;
        *) echo 'outcome=recovery_unconfirmed';;
    esac
}
case "${1:-status}" in
    library) ;; # Source functions for isolated fixtures; no I/O here.
    begin) test "$#" = 2 || exit 64; journal_begin "$2";;
    record) test "$#" = 4 || exit 64; journal_record "$2" "$3" "$4";;
    status) test "$#" -le 1 || exit 64; journal_status;;
    launch|delayed|run|guard)
        echo 'USB mutation disabled: a reviewed device-specific trial is required' >&2
        exit 64;;
    *) echo 'usage: usb-recover.sh {begin TICKET|record TICKET PHASE RESULT|status}' >&2; exit 64;;
esac
