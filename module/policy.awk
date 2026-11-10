# Cellforge device policy. Inputs: saved key/value state, then current observation.
FILENAME == ARGV[1] { saved[$1] = $2; next }
{ obs[$1] = $2 }
function number(x) { return x ~ /^[0-9]+$/ && x + 0 < 9007199254740992 }
function persist(k, v) { print k, v > state_out }
function nullable(v) { return v == "" || v == "none" ? "null" : v }
END {
    now = obs["now"] + 0
    total_tx = saved["total_tx"] + 0; total_rx = saved["total_rx"] + 0
    breaks = saved["breaks"] + 0
    started = saved["started"] + 0
    if (!started) started = now
    active = saved["session_active"] == "1"
    detached_at = saved["detached_at"] + 0
    self_recovery = saved["self_recovery"]=="1"
    if (obs["recovery_owned"]=="1" && !self_recovery) { self_recovery=1; breaks++ }
    if (obs["usb"] == "DISCONNECTED") {
        if (!detached_at) detached_at = now
        if (now - detached_at >= 3 && !self_recovery) active = 0
    } else if (obs["usb"] == "CONFIGURED") {
        if (!active && saved["had_session"] == "1") {
            total_tx = total_rx = 0; started = now
            saved["epoch"] = ""; saved["previous_time"] = ""
        }
        active = 1; detached_at = 0
        saved["had_session"] = 1
    }
    rate_tx = rate_rx = "null"; quality = "missing"
    if (number(obs["tx"]) && number(obs["rx"]) && obs["epoch"] != "none") {
        quality = "limited"
        if (saved["epoch"] == obs["epoch"] && saved["previous_time"] != "") {
            if (obs["tx"] + 0 >= saved["previous_tx"] + 0 && obs["rx"] + 0 >= saved["previous_rx"] + 0) {
                delta_tx = obs["tx"] - saved["previous_tx"]
                delta_rx = obs["rx"] - saved["previous_rx"]
                total_tx += delta_tx; total_rx += delta_rx
                elapsed = now - saved["previous_time"]
                if (elapsed > 0 && saved["gap"] != "1") {
                    rate_tx = sprintf("%.1f", delta_tx / elapsed)
                    rate_rx = sprintf("%.1f", delta_rx / elapsed)
                    quality = "available"
                }
            } else breaks++
        } else if (saved["epoch"] != "") breaks++
        persist("epoch", obs["epoch"]); persist("previous_time", now)
        persist("previous_tx", obs["tx"]); persist("previous_rx", obs["rx"])
        persist("gap", 0)
    } else {
        persist("epoch", saved["epoch"]); persist("previous_time", saved["previous_time"])
        persist("previous_tx", saved["previous_tx"]); persist("previous_rx", saved["previous_rx"])
        persist("gap", 1)
    }
    host_age = obs["host_at"] + 0 > 0 ? now - obs["host_at"] : -1
    uplink_age = obs["uplink_at"] + 0 > 0 ? now - obs["uplink_at"] : -1
    host_fresh = host_age >= 0 && host_age <= 30
    uplink_fresh = uplink_age >= 0 && uplink_age <= 30
    if (self_recovery && obs["recovery_owned"]!="1" && obs["usb"]=="CONFIGURED" && host_fresh && uplink_fresh) self_recovery=0
    if (self_recovery) { quality="limited"; rate_tx=rate_rx="null" }
    radio = obs["radio"]
    network = radio == "4" ? "4G" : (radio == "3" || radio == "6" ? "2G/3G" : "unknown")
    led = "factory"; state = "checking"
    if (obs["sim"] == "0") { led = "red_solid"; state = "radio_fault" }
    else if (obs["sim"] == "1" && obs["radio_alarm"] == "1") { led = "red_blink"; state = "radio_fault" }
    else if (obs["recovery_mode"]=="recovering" || obs["recovery_mode"]=="confirming") { led="blue_blink"; state="recovering" }
    else if (obs["usb"] == "CONFIGURED" && obs["sleep"] == "0" && host_fresh && uplink_fresh && obs["sim"] == "1" && obs["radio_alarm"]=="0" && network != "unknown") {
        led = "blue_solid"; state = "active"
    } else if (obs["probing"] == "1") { led = "blue_blink"; state = "recovering" }
    else if (obs["sim"] == "1" && network != "unknown" && obs["rssi"] ~ /^-[0-9]+$/) {
        led = (network == "4G" ? "green" : "yellow") (obs["rssi"] + 0 >= -69 ? "_solid" : "_blink")
        state = obs["usb"] == "DISCONNECTED" ? "detached" : "limited"
    }
    if (obs["attempts"] + 0 >= 3 && obs["sleep"] == "1" && state != "radio_fault") state = "backoff"
    if (state!="radio_fault" && state!="active" && state!="recovering") {
        if (obs["recovery_mode"]=="sleeping") state="sleeping"
        else if (obs["recovery_mode"]=="observing") state="observing"
        else if (obs["recovery_mode"]=="failed" || obs["recovery_mode"]=="exhausted") state="backoff"
    }
    if (host_age < 0) host_age = "null"
    if (uplink_age < 0) uplink_age = "null"
    printf "{\"version\":\"1.1.0\",\"state\":\"%s\",\"led\":\"%s\",", state, led
    printf "\"usb_state\":\"%s\",\"usb_sleep\":%s,\"updated_uptime\":%.0f,", obs["usb"], nullable(obs["sleep"]), now
    printf "\"local_ip\":\"192.168.225.1\",\"device_ip\":\"%s\",\"cellular_ip\":\"%s\",", obs["host_ip"], obs["cell_ip"]
    printf "\"network_type\":\"%s\",\"signal_dbm\":%s,\"host_age\":%s,\"uplink_age\":%s,", network, nullable(obs["rssi"]), host_age, uplink_age
    printf "\"session_seconds\":%.0f,\"upload_bytes\":%.0f,\"download_bytes\":%.0f,", now-started, total_tx, total_rx
    printf "\"upload_Bps\":%s,\"download_Bps\":%s,\"accounting_quality\":\"%s\",\"discontinuities\":%.0f,", rate_tx, rate_rx, quality, breaks
    printf "\"recovery_attempts\":%d,\"last_recovery\":\"%s\",\"led_control\":%s,\"telemetry_quality\":\"%s\",", obs["attempts"], obs["last_recovery"], (obs["led_owned"] == "1" ? "true" : "false"), (obs["sim"] == "none" ? "missing" : "available")
    printf "\"recovery_mode\":\"%s\",\"recovery_reason\":\"%s\",\"session_uncertain\":%s}\n",obs["recovery_mode"],obs["recovery_reason"],self_recovery?"true":"false"
    persist("total_tx", sprintf("%.0f", total_tx)); persist("total_rx", sprintf("%.0f", total_rx))
    persist("breaks", breaks); persist("started", started); persist("session_active", active ? 1 : 0)
    persist("had_session", saved["had_session"]); persist("detached_at", detached_at)
    persist("self_recovery",self_recovery?1:0)
    print led > led_out
    close(state_out); close(led_out)
}
