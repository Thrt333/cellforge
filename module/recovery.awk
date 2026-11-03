# Automatic recovery decision only. No device writes. State survives service restart.
FILENAME == ARGV[1] { s[$1]=$2; next }
{ o[$1]=$2 }
function keep(k,v) { print k,v > state_out }
function fresh(t) { return t+0 > 0 && now-t >= 0 && now-t <= 30 }
END {
    now=o["now"]+0; armed=s["armed"]==1; failures=s["failures"]+0
    since=s["healthy_since"]+0; grace=s["grace"]+0
    if (now-s["now"] > 6 || now < s["now"]) since=0
    radio=o["sim"]==1 && o["alarm"]==0 && (o["radio"]==3 || o["radio"]==4 || o["radio"]==6)
    healthy=o["usb"]=="CONFIGURED" && o["sleep"]==0 && radio && fresh(o["host_at"]) && fresh(o["uplink_at"])
    busy=o["busy"]==1; blocked=o["blocked"]==1; used=o["used"]+0
    action=finish=clear=0; mode="unknown"; reason="missing_evidence"
    if (healthy) {
        if (!since) since=now
        armed=1; failures=0; grace=0
    } else since=0
    if (busy) {
        phase=o["phase"]
        if (phase=="confirmed") {
            mode="cooldown"; reason="stable_response"
            if (o["done"]==1 && o["guard_done"]==1) finish=1
        } else if (phase=="failed" || phase=="aborted" || phase=="drift") {
            mode="failed"; reason=phase
            if (o["done"]==1 && o["guard_done"]==1) finish=1
        } else if (now >= o["deadline"]+0) {
            mode="failed"; reason="response_timeout"
            if (o["done"]==1 && o["guard_done"]==1) finish=1
        } else if (healthy && since && now-since>=30 && phase=="waiting") {
            mode="confirming"; reason="stable_response"; finish=1
        } else {
            mode=healthy ? "confirming" : "recovering"; reason=phase
        }
    } else if (healthy) {
        mode="active"; reason="fresh_response"
        if (blocked) {
            if (now-since>=30 && now-o["last_action"]>=120) clear=1
            else { mode="cooldown"; reason="stable_or_cooldown_pending" }
        }
    } else if (o["usb"]=="DISCONNECTED") {
        armed=0; failures=0; grace=0; mode="detached"; reason="usb_detached"
    } else if (o["usb"]!="CONFIGURED") {
        armed=0; failures=0; grace=0
    } else if (o["sleep"]!=0 && o["sleep"]!=1) {
        failures=0
    } else if (o["sleep"]==1) {
        mode="sleeping"; reason="usb_suspended"; failures=0; grace=0
    } else {
        if (s["sleep"]==1 || s["usb"]!="CONFIGURED" || !grace) {
            grace=now+30; failures=0
        }
        if (!armed) { mode="checking"; reason="no_healthy_baseline"; failures=0 }
        else if (now<grace) { mode="observing"; reason="resume_grace"; failures=0 }
        else if (o["peer_known"]!=1 || o["probe_result"]=="missing") {
            mode="unknown"; reason="no_probe_target"; failures=0
        } else if (!radio || !fresh(o["uplink_at"])) {
            mode="limited"; reason="uplink_unconfirmed"; failures=0
        } else if (used>=3) { mode="exhausted"; reason="boot_limit" }
        else if (blocked) { mode="failed"; reason="incident_already_attempted" }
        else {
            if (o["probe_seq"]!=s["probe_seq"]) {
                if (o["probe_result"]=="fail") failures++
                else failures=0
            }
            mode="observing"; reason="host_probe_failed"
            if (failures>=3) { action=1; mode="recovering"; reason="reenumeration_requested"; failures=0 }
        }
    }
    keep("now",now); keep("armed",armed?1:0); keep("failures",failures)
    keep("healthy_since",since); keep("grace",grace); keep("probe_seq",o["probe_seq"])
    keep("usb",o["usb"]); keep("sleep",o["sleep"])
    printf "%s %s %d %d %d\n",mode,reason,action,finish,clear > decision_out
    close(state_out); close(decision_out)
}
