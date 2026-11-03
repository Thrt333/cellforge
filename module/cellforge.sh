#!/bin/sh
# Target: verified QDC507 3.18.44 factory runtime. No module Python required.
set -u
umask 077
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SELF=$BASE/cellforge.sh
RUN=/tmp/cellforge
USB=/sys/class/android_usb/android0
FLAG=/tmp/factory_led_test
FACTORY_HASH=8cad1634758bb373c61536e36436dd0972e75cfe5ad977b8fe8ab1d6464bb6b9
TOKEN=${2:-}
GEN=$RUN/control/$TOKEN
. "$BASE/recovery-worker.sh"
clock() { read -r uptime rest < /proc/uptime; echo "${uptime%%.*}"; }
start_time() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }
record() { printf '%s %s\n' "$1" "$(start_time "$1")" > "$GEN/$2.pid"; }
valid() {
    test -r "$GEN/$1.pid" || return 1
    read -r pid born < "$GEN/$1.pid"
    case "$pid:$born" in *[!0-9:]*|:*) return 1;; esac
    test -n "$born" && test "$(start_time "$pid")" = "$born"
}
stop_child() { if valid "$1"; then read -r pid born < "$GEN/$1.pid"; kill -TERM "$pid" 2>/dev/null || true; fi; }
owns_led() { test -f "$FLAG" && test "$(cat "$FLAG" 2>/dev/null)" = "$TOKEN"; }
restore_led() {
    if owns_led; then
        for pin in 1013 1015 1017; do
            test -r "$GEN/gpio$pin" || continue
            cat "$GEN/gpio$pin" > "/sys/class/gpio/gpio$pin/value" || true
        done
        if owns_led; then rm -f "$FLAG"; fi
    fi
}
release_wake() {
    if test -f "$GEN/wakelock"; then
        printf '%s\n' "cellforge_$TOKEN" > /sys/power/wake_unlock 2>/dev/null || true
        rm -f "$GEN/wakelock"
    fi
}
cleanup() {
    if test -f "$AUTO/current"; then
        number=$(cat "$AUTO/current")
        case "$number" in 1|2|3)
            if test "$(cat "$AUTO/action$number/token" 2>/dev/null)" = "$TOKEN"; then : > "$AUTO/action$number/cancel"; fi
        ;; esac
    fi
    for child in worker led httpd; do stop_child "$child"; done
    restore_led
    release_wake
    if test -r "$RUN/current" && test "$(cat "$RUN/current")" = "$TOKEN"; then rm -f "$RUN/current"; fi
}
heartbeat() { clock > "$GEN/heartbeat"; }
snapshot() {
    now=$(clock)
    tx=none; rx=none; epoch=none; cell_ip=
    cell_if=$(ip route show 2>/dev/null | awk '$1=="default" {for(i=1;i<NF;i++) if($i=="dev") print $(i+1); exit}')
    case "$cell_if" in rmnet_data[0-9])
        tx=$(cat "/sys/class/net/$cell_if/statistics/tx_bytes" 2>/dev/null || echo none)
        rx=$(cat "/sys/class/net/$cell_if/statistics/rx_bytes" 2>/dev/null || echo none)
        epoch=$(cat "/sys/class/net/$cell_if/ifindex" 2>/dev/null || echo none)
        cell_ip=$(ip -o -4 addr show dev "$cell_if" 2>/dev/null | awk '{split($4,a,"/");print a[1];exit}')
    ;; esac
    usb=$(cat "$USB/state" 2>/dev/null || echo UNKNOWN)
    case "$usb" in CONFIGURED|DISCONNECTED|CONNECTED) ;; *) usb=UNKNOWN;; esac
    asleep=$(cat "$USB/usb_sleep" 2>/dev/null || echo none)
    case "$asleep" in 0|1) ;; *) asleep=none;; esac
    owned=0; owns_led && owned=1
    auto_step || return 1
    {
        printf 'now %s\ntx %s\nrx %s\nepoch %s\n' "$now" "$tx" "$rx" "$epoch"
        printf 'usb %s\nsleep %s\nsim %s\nradio %s\nrssi %s\nradio_alarm %s\n' "$usb" "$asleep" "$sim" "$radio" "$rssi" "$radio_alarm"
        printf 'host_at %s\nuplink_at %s\nprobing %s\nattempts %s\n' "$host_at" "$uplink_at" "$probing" "$attempts"
        printf 'host_ip %s\ncell_ip %s\nlast_recovery %s\nled_owned %s\n' "$host_ip" "$cell_ip" "$last_recovery" "$owned"
        printf 'recovery_mode %s\nrecovery_reason %s\nrecovery_owned %s\n' "$auto_mode" "$auto_reason" "$recovery_owned"
    } > "$GEN/observation"
    awk -v state_out="$GEN/policy.new" -v led_out="$GEN/led.new" -f "$BASE/policy.awk" "$GEN/policy.state" "$GEN/observation" > "$RUN/www/status.new" || return 1
    mv "$GEN/policy.new" "$GEN/policy.state"
    mv "$GEN/led.new" "$GEN/led"
    chmod 644 "$RUN/www/status.new"
    mv "$RUN/www/status.new" "$RUN/www/status.json"
}
factory_state() {
    sim=none; radio=none; rssi=none; radio_alarm=none
    if test -z "$factory_pid" || test "$(cat "/proc/$factory_pid/comm" 2>/dev/null)" != quectel_daemon || test "$(start_time "$factory_pid")" != "$factory_start"; then
        factory_pid=; factory_start=; factory_base=
        test "$(sha256sum /usr/bin/quectel_daemon | awk '{print $1}')" = "$FACTORY_HASH" || return 0
        for path in /proc/[0-9]*/comm; do
            test "$(cat "$path" 2>/dev/null)" = quectel_daemon || continue
            factory_pid=${path#/proc/}; factory_pid=${factory_pid%/comm}; break
        done
        test -n "$factory_pid" || return 0
        factory_start=$(start_time "$factory_pid")
        hex=$(awk '$NF=="/usr/bin/quectel_daemon" && $3=="00000000" {split($1,a,"-");print a[1];exit}' "/proc/$factory_pid/maps")
        case "$hex" in ''|*[!0-9a-f]*) factory_pid=; return 0;; esac
        factory_base=$((0x$hex))
    fi
    set -- $(dd if="/proc/$factory_pid/mem" bs=4 skip=$(((factory_base + 77832)/4)) count=2 2>/dev/null | od -An -tu4)
    test "$#" = 2 || return 0
    radio=$1; rssi=$2
    if test "$rssi" -gt 2147483647; then rssi=$((rssi - 4294967296)); fi
    set -- $(dd if="/proc/$factory_pid/mem" bs=4 skip=$(((factory_base + 78516)/4)) count=1 2>/dev/null | od -An -tu4)
    test "$#" = 1 || return 0
    case "$1" in 0|1) sim=$1;; esac
    set -- $(dd if="/proc/$factory_pid/mem" bs=4 skip=$(((factory_base + 80832)/4)) count=1 2>/dev/null | od -An -tu4)
    test "$#" = 1 || return 0
    case "$1" in 0|1) radio_alarm=$1;; esac
    case "$radio" in 3|4|6) ;; *) radio=none;; esac
    if test "$rssi" -lt -140 || test "$rssi" -gt -20; then rssi=none; fi
}
worker() {
    exec 9>&-
    host_at=0; uplink_at=0; attempts=0; probing=0; host_ip=; last_recovery=none
    cached_peer=; peer_known=0; probe_seq=0; probe_result=missing; sleep_probes=0; previous_sleep=none
    sim=none; radio=none; rssi=none; radio_alarm=none
    factory_pid=; factory_start=; factory_base=; due=0
    auto_init
    : > "$GEN/policy.state"
    while :; do
        heartbeat
        now=$(clock)
        usb=$(cat "$USB/state" 2>/dev/null || echo UNKNOWN)
        asleep=$(cat "$USB/usb_sleep" 2>/dev/null || echo none)
        auto_read
        if test "$previous_sleep" = 1 && test "$asleep" = 0; then sleep_probes=0; fi
        previous_sleep=$asleep
        if test "$usb" = CONFIGURED; then
            if ! test -f "$GEN/wakelock"; then
                printf '%s\n' "cellforge_$TOKEN" > /sys/power/wake_lock || exit 1
                : > "$GEN/wakelock"
            fi
        else
            release_wake; host_at=0; uplink_at=0; host_ip=
            if test "$auto_busy" = 0; then cached_peer=; peer_known=0; probe_result=missing; fi
        fi
        if test "$now" -ge "$due"; then
            factory_state
            if test "$usb" = CONFIGURED; then
                probe_result=missing
                if test "$asleep" = 0 || { test "$asleep" = 1 && test "$sleep_probes" -lt 3; }; then
                    candidates=$(awk -v cached="$cached_peer" -f "$BASE/peers.awk" /proc/net/arp)
                    host_at=0
                    if test -n "$candidates"; then
                        probe_seq=$((probe_seq + 1)); probe_result=fail; peer_known=1
                        if test "$asleep" = 1; then sleep_probes=$((sleep_probes + 1)); fi
                    else peer_known=0; fi
                    for peer in $candidates; do
                        if timeout -t 2 arping -c 1 -w 1 -I bridge0 "$peer" >/dev/null 2>&1; then
                            host_ip=$peer; host_at=$(clock); cached_peer=$peer; probe_result=ok; break
                        fi
                    done
                fi
                cell_if=$(ip route show 2>/dev/null | awk '$1=="default" {for(i=1;i<NF;i++) if($i=="dev") print $(i+1);exit}')
                uplink_at=0
                case "$cell_if" in rmnet_data[0-9])
                    if timeout -t 2 ping -I "$cell_if" -c 1 -w 1 1.1.1.1 >/dev/null 2>&1; then uplink_at=$(clock); fi
                ;; esac
            fi
            due=$(($(clock) + 15))
        fi
        heartbeat
        snapshot || exit 1
        sleep 1
    done
}
led_loop() {
    exec 9>&-
    phase=0
    while :; do
        pattern=$(cat "$GEN/led" 2>/dev/null || echo factory)
        if test -r "$GEN/led-test"; then
            read -r until override < "$GEN/led-test"
            case "$until" in ''|*[!0-9]*) ;; *)
                if test "$override" = yellow_solid && test "$(clock)" -le "$until"; then pattern=$override; fi
            ;; esac
        fi
        if test "$pattern" = factory; then restore_led; sleep 0.5; continue; fi
        if ! owns_led; then
            if test -e "$FLAG"; then sleep 0.5; continue; fi
            for pin in 1013 1015 1017; do cat "/sys/class/gpio/gpio$pin/value" > "$GEN/gpio$pin" || exit 1; done
            (set -C; printf '%s\n' "$TOKEN" > "$FLAG") 2>/dev/null || continue
            sleep 1.2
        fi
        red=1; green=1; blue=1
        case "$pattern:$phase" in
            red_solid:*|red_blink:0) red=0;;
            green_solid:*|green_blink:0) green=0;;
            blue_solid:*|blue_blink:0) blue=0;;
            yellow_solid:*|yellow_blink:0) red=0; green=0;;
        esac
        owns_led || exit 1
        printf '%s\n' "$red" > /sys/class/gpio/gpio1013/value || exit 1
        printf '%s\n' "$green" > /sys/class/gpio/gpio1015/value || exit 1
        printf '%s\n' "$blue" > /sys/class/gpio/gpio1017/value || exit 1
        phase=$((1 - phase))
        sleep 0.5
    done
}
watchdog() {
    exec 9>&-
    while :; do
        sleep 2
        now=$(clock); beat=$(cat "$GEN/heartbeat" 2>/dev/null || echo 0)
        if ! valid supervisor || test $((now - beat)) -gt 8; then cleanup; exit; fi
    done
}
supervise() {
    exec 9> "$RUN/control/singleton.lock"
    flock -n 9 || exit 1
    mkdir -p "$GEN"
    record "$$" supervisor
    printf '%s\n' "$TOKEN" > "$RUN/current"
    trap 'trap - EXIT INT TERM HUP; cleanup; exit' EXIT INT TERM HUP
    heartbeat
    sh "$SELF" watchdog "$TOKEN" </dev/null >> "$GEN/watchdog.log" 2>&1 &
    sh "$SELF" worker "$TOKEN" </dev/null >> "$GEN/worker.log" 2>&1 & record "$!" worker
    sh "$SELF" led "$TOKEN" </dev/null >> "$GEN/led.log" 2>&1 & record "$!" led
    /sbin/httpd -f -p 192.168.225.1:8080 -u 65534 -h "$RUN/www" -c "$RUN/www/httpd.conf" </dev/null >> "$GEN/httpd.log" 2>&1 & record "$!" httpd
    sleep 1
    while valid worker && valid led && valid httpd; do sleep 1; done
    exit 1
}
case "${1:-status}" in
start)
    mkdir -p "$RUN/control" "$RUN/www"
    chmod 755 "$RUN" "$RUN/www"; chmod 700 "$RUN/control"
    if test -r "$RUN/current"; then
        TOKEN=$(cat "$RUN/current"); GEN=$RUN/control/$TOKEN
        if valid supervisor; then echo already_running; exit 0; fi
    fi
    ip -o -4 addr show dev bridge0 | grep -q '192\.168\.225\.1/24' || { echo unexpected_USB_LAN >&2; exit 1; }
    if awk '$4=="0A" && $2 ~ /:1F90$/ {found=1} END {exit !found}' /proc/net/tcp /proc/net/tcp6; then echo port_8080_in_use >&2; exit 1; fi
    test "$(sha256sum /usr/bin/quectel_daemon | awk '{print $1}')" = "$FACTORY_HASH" || { echo unsupported_factory_binary >&2; exit 1; }
    for pin in 1013 1015 1017; do test "$(cat /sys/class/gpio/gpio$pin/direction)" = out || exit 1; done
    test ! -e "$FLAG" || { echo factory_LED_override_already_owned >&2; exit 1; }
    cp "$BASE/web/index.html" "$RUN/www/index.html"
    cp "$BASE/httpd.conf" "$RUN/www/httpd.conf"
    chmod 644 "$RUN/www/index.html" "$RUN/www/httpd.conf"
    TOKEN="$(clock).$$"; GEN=$RUN/control/$TOKEN
    nohup setsid sh "$SELF" supervise "$TOKEN" </dev/null > "$RUN/control/launch.log" 2>&1 &
    sleep 2
    if valid supervisor && valid worker && valid httpd; then echo started; else echo start_failed >&2; exit 1; fi
;;
stop)
    if test -r "$RUN/current"; then
        TOKEN=$(cat "$RUN/current"); GEN=$RUN/control/$TOKEN
        stop_child supervisor
        sleep 2
        cleanup
    fi
    echo stopped
;;
status)
    if test -r "$RUN/current"; then
        TOKEN=$(cat "$RUN/current"); GEN=$RUN/control/$TOKEN
        if valid supervisor && valid worker && valid httpd; then echo running; cat "$RUN/www/status.json"; exit 0; fi
    fi
    echo stopped
;;
supervise) supervise;;
worker) worker;;
led) led_loop;;
watchdog) watchdog;;
*) echo 'usage: cellforge.sh {start|stop|status}' >&2; exit 64;;
esac
