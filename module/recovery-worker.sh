# Sourced only by the collector; no I/O until a function is called.
AUTO=/tmp/cellforge/auto
auto_init() {
    mkdir -p "$AUTO"
    chmod 700 "$AUTO"
    if ! test -e "$AUTO/used"; then
        if test -d "$AUTO/action1"; then echo 3 > "$AUTO/used"; : > "$AUTO/blocked"
        else echo 0 > "$AUTO/used"; fi
    fi
    test -e "$AUTO/last" || echo 0 > "$AUTO/last"
    test -e "$AUTO/state" || : > "$AUTO/state"
}
auto_read() {
    auto_used=$(cat "$AUTO/used" 2>/dev/null || echo 3)
    case "$auto_used" in 0|1|2|3) ;; *) auto_used=3;; esac
    auto_last=$(cat "$AUTO/last" 2>/dev/null || echo 0)
    case "$auto_last" in ''|*[!0-9]*) auto_last=$(clock);; esac
    auto_blocked=0; test ! -e "$AUTO/blocked" || auto_blocked=1
    auto_busy=0; auto_number=; auto_phase=none; auto_deadline=0; auto_done=0; auto_guard_done=0
    if test -f "$AUTO/current"; then
        auto_number=$(cat "$AUTO/current")
        case "$auto_number" in 1|2|3)
            auto_busy=1; auto_work=$AUTO/action$auto_number
            auto_phase=$(cat "$auto_work/phase" 2>/dev/null || echo failed)
            case "$auto_phase" in preparing|disconnecting|connecting|waiting|confirmed|failed|aborted|drift) ;; *) auto_phase=failed;; esac
            auto_deadline=$(cat "$auto_work/deadline" 2>/dev/null || echo 0)
            case "$auto_deadline" in ''|*[!0-9]*) auto_deadline=0;; esac
            test ! -e "$auto_work/done" || auto_done=1
            test ! -e "$auto_work/guard.done" || auto_guard_done=1
        ;; *) auto_busy=1; auto_phase=failed; auto_deadline=0;; esac
    fi
}
auto_launch() {
    test "$auto_busy" = 0 && test "$auto_blocked" = 0 && test "$auto_used" -lt 3 || return 1
    next=$((auto_used + 1)); work=$AUTO/action$next
    mkdir "$work" || return 1
    printf '%s\n' "$TOKEN" > "$work/token"
    printf '%s\n' "$((now + 150))" > "$work/deadline"
    echo preparing > "$work/phase"
    printf '%s\n' "$next" > "$AUTO/used.new" && mv "$AUTO/used.new" "$AUTO/used" || return 1
    printf '%s\n' "$now" > "$AUTO/last.new" && mv "$AUTO/last.new" "$AUTO/last" || return 1
    : > "$AUTO/blocked"
    printf '%s\n' "$next" > "$AUTO/current.new" && mv "$AUTO/current.new" "$AUTO/current" || return 1
    # Discard all prior host evidence. Discovery after this point starts afresh.
    host_at=0; uplink_at=0; host_ip=; cached_peer=; peer_known=0; probe_result=missing
    nohup setsid sh "$BASE/auto-recover.sh" run "$next" "$TOKEN" </dev/null > "$work/executor.log" 2>&1 &
    auto_read
}
auto_step() {
    auto_read
    {
        printf 'now %s\nusb %s\nsleep %s\n' "$now" "$usb" "$asleep"
        printf 'host_at %s\nuplink_at %s\npeer_known %s\n' "$host_at" "$uplink_at" "$peer_known"
        printf 'sim %s\nradio %s\nalarm %s\n' "$sim" "$radio" "$radio_alarm"
        printf 'probe_seq %s\nprobe_result %s\n' "$probe_seq" "$probe_result"
        printf 'busy %s\nphase %s\ndeadline %s\ndone %s\nguard_done %s\n' "$auto_busy" "$auto_phase" "$auto_deadline" "$auto_done" "$auto_guard_done"
        printf 'used %s\nblocked %s\nlast_action %s\n' "$auto_used" "$auto_blocked" "$auto_last"
    } > "$AUTO/observation"
    awk -v state_out="$AUTO/state.new" -v decision_out="$AUTO/decision.new" -f "$BASE/recovery.awk" "$AUTO/state" "$AUTO/observation" || return 1
    mv "$AUTO/state.new" "$AUTO/state" && mv "$AUTO/decision.new" "$AUTO/decision" || return 1
    read -r auto_mode auto_reason auto_action auto_finish auto_clear < "$AUTO/decision"
    if test "$auto_clear" = 1; then rm -f "$AUTO/blocked"; fi
    if test "$auto_finish" = 1 && test -n "$auto_number"; then
        if test "$auto_phase" = waiting; then : > "$auto_work/confirmed"
        elif test "$auto_done" = 1 && test "$auto_guard_done" = 1 && test ! -e "$auto_work/pending"; then rm -f "$AUTO/current"; fi
    fi
    if test "$auto_action" = 1; then
        if ! auto_launch; then
            echo 3 > "$AUTO/used"; : > "$AUTO/blocked"
            auto_used=3; auto_mode=failed; auto_reason=reservation_failed
        fi
    fi
    attempts=$auto_used
    last_recovery=$auto_reason
    recovery_owned=$auto_busy
    probing=0
    case "$auto_mode" in recovering|confirming) probing=1;; esac
}
