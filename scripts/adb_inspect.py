#!/usr/bin/env python3
"""Bounded direct-USB ADB inspection; no host ADB server, keys or remote writes."""
import argparse
import ctypes as C
import json
import math
import struct
import sys
import time

if __package__:
    from . import cellforge as ecm
    from . import module_access as access
else:
    import cellforge as ecm
    import module_access as access


MAX_PAYLOAD = 4096
MAX_OUTPUT = 65536
INVENTORY = r'''
printf '\n[system]\n'
uname -s -r -m
printf '\n[runtimes]\n'
for name in busybox sh python3 python lua node gcc cc curl wget ip ifconfig ping httpd awk sed cat stat df free ps readlink ss netstat timeout flock start-stop-daemon; do
    command -v "$name" 2>/dev/null || true
done
printf '\n[memory]\n'
sed -n '/^MemTotal:/p;/^MemFree:/p;/^MemAvailable:/p' /proc/meminfo
printf '\n[mounts]\n'
awk '$2 == "/" || $2 == "/data" || $2 == "/tmp" || $2 == "/etc" || $2 == "/usr" || $2 == "/var" { split($4, opts, ","); print $2, $3, opts[1] }' /proc/mounts
df -k / /data /tmp 2>/dev/null
printf '\n[startup]\n'
readlink /proc/1/exe
ls -ld /data /tmp /etc/init.d /etc/rc5.d 2>/dev/null
printf '\n[usb]\n'
for key in state functions enable idVendor idProduct; do
    path=/sys/class/android_usb/android0/$key
    if test -r "$path"; then printf '%s=' "$key"; cat "$path"; fi
done
for path in /sys/class/udc/*; do
    test -d "$path" || continue
    printf 'controller=%s\n' "${path##*/}"
    ls "$path" 2>/dev/null
    for key in state current_speed maximum_speed is_a_peripheral is_selfpowered; do
        if test -r "$path/$key"; then printf '%s=' "$key"; cat "$path/$key"; fi
    done
done
printf '\n[power_controls]\n'
ls -l /sys/power/wake_lock /sys/power/wake_unlock /sys/power/state 2>/dev/null
printf '\n[interfaces]\n'
for path in /sys/class/net/*; do
    test -d "$path" || continue
    printf 'interface=%s\n' "${path##*/}"
    for key in operstate statistics/rx_bytes statistics/tx_bytes; do
        if test -r "$path/$key"; then printf '%s=' "$key"; cat "$path/$key"; fi
    done
done
ip -o -4 addr show 2>/dev/null | awk '{print $2, $4}'
ip route show 2>/dev/null
printf '\n[listening_ports_hex]\n'
for path in /proc/net/tcp /proc/net/tcp6; do
    test -r "$path" || continue
    printf '%s\n' "$path"
    awk '$4 == "0A" { print $2 }' "$path"
done
for path in /proc/net/udp /proc/net/udp6; do
    test -r "$path" || continue
    printf '%s\n' "$path"
    awk 'NR > 1 { print $2 }' "$path"
done
printf '\n[leds]\n'
for path in /sys/class/leds/*; do
    test -d "$path" || continue
    printf 'led=%s\n' "${path##*/}"
    ls "$path" 2>/dev/null
    for key in brightness max_brightness trigger delay_on delay_off; do
        if test -r "$path/$key"; then printf '%s=' "$key"; cat "$path/$key"; fi
    done
done
printf '\n[relevant_process_names]\n'
for path in /proc/[0-9]*/comm; do
    test -r "$path" || continue
    name=$(cat "$path" 2>/dev/null)
    case "$name" in
        *led*|*light*|*usb*|*qcm*|*net*|*dhcp*|*dns*|init) printf '%s %s\n' "$path" "$name" ;;
    esac
done
printf '\nCELLFORGE_INVENTORY_COMPLETE\n'
'''

DETAILS = r'''
printf '\n[sysfs_classes]\n'
ls /sys/class
printf '\n[led_and_gpio_paths]\n'
find /sys/devices -maxdepth 5 -iname '*led*' -print 2>/dev/null
ls -ld /sys/class/leds /sys/class/led_class /sys/class/gpio /sys/kernel/debug 2>/dev/null
for path in /sys/class/gpio/gpiochip*; do
    test -d "$path" || continue
    printf '%s\n' "$path"
    for key in label base ngpio; do
        if test -r "$path/$key"; then printf '%s=' "$key"; cat "$path/$key"; fi
    done
done
printf '\n[usb_power_controls]\n'
for path in /sys/class/udc/msm_hsusb/device/power /sys/class/udc/msm_hsusb/power /sys/class/android_usb/android0/power /sys/devices/platform/msm_hsusb/power; do
    test -d "$path" || continue
    printf '%s\n' "$path"
    ls "$path"
    for key in control wakeup runtime_status runtime_active_time runtime_suspended_time; do
        if test -r "$path/$key"; then printf '%s=' "$key"; cat "$path/$key"; fi
    done
done
printf '\n[device_node_names]\n'
ls /dev | grep -i -E 'led|gpio|smd|tty|at_mdm|diag'
printf '\n[startup_names]\n'
ls /etc/init.d /etc/rc5.d
printf '\n[process_names_only]\n'
for path in /proc/[0-9]*/comm; do
    test -r "$path" || continue
    printf '%s ' "$path"
    cat "$path"
done
printf '\n[httpd_and_temp_paths]\n'
ls -l /sbin/httpd /bin/busybox /tmp /var/tmp /data 2>/dev/null
readlink -f /sbin/httpd
readlink -f /tmp
readlink -f /data
printf '\nCELLFORGE_DETAILS_COMPLETE\n'
'''

CONTROLS = r'''
printf '\n[gpio_ownership]\n'
if test -r /sys/kernel/debug/gpio; then sed -n '1,140p' /sys/kernel/debug/gpio; fi
printf '\n[usb_debug_names]\n'
ls /sys/kernel/debug/usb /sys/kernel/debug/msm_otg /sys/kernel/debug/msm_hsusb 2>/dev/null
printf '\n[control_libraries_and_headers]\n'
find /usr/lib -maxdepth 2 \( -iname '*quectel*' -o -iname '*gpio*' -o -iname '*led*' -o -iname 'libql*' \) -print 2>/dev/null
find /usr/include -maxdepth 2 \( -iname '*gpio*' -o -iname '*led*' -o -iname '*ql*' \) -print 2>/dev/null
printf '\n[factory_daemon_paths]\n'
for name in quectel_daemon quectel_monitor ql_manager_server atfwd_daemon strings nm readelf; do
    command -v "$name" 2>/dev/null || true
done
printf '\n[init_scripts_referencing_led]\n'
grep -il -E 'led|gpio' /etc/init.d/* 2>/dev/null
printf '\nCELLFORGE_CONTROLS_COMPLETE\n'
'''

FACTORY = r'''
printf '\n[usb_control_node_metadata]\n'
ls -l /sys/class/android_usb/android0/ 2>/dev/null | grep -E 'wake|sleep|power|state|functions|enable'
printf '\n[factory_gpio_power_references]\n'
for path in /etc/init.d/data-init /etc/init.d/power_config /etc/init.d/usb /etc/init.d/quectel_daemon; do
    test -r "$path" || continue
    printf '%s\n' "$path"
    grep -n -i -E 'gpio|1013|1015|1017|led|wake|/sys/power|quectel' "$path" | head -n 60
done
printf '\n[public_control_symbols_and_sysfs_paths]\n'
for path in /usr/bin/quectel_daemon /usr/bin/ql_manager_server /usr/lib/libql_misc.so.1 /usr/lib/libql_usb.so.1 /usr/lib/libql_utils.so.1; do
    test -r "$path" || continue
    printf '%s\n' "$path"
    strings "$path" | grep -E '^([A-Za-z_][A-Za-z0-9_]*(led|LED|gpio|GPIO|wake|Wake)[A-Za-z0-9_]*|/sys/[A-Za-z0-9_/.-]+)$' | head -n 100
done
printf '\nCELLFORGE_FACTORY_COMPLETE\n'
'''


def encode(command, arg0=0, arg1=0, payload=b""):
    number = int.from_bytes(command, "little")
    return struct.pack("<6I", number, arg0, arg1, len(payload),
                       sum(payload) & 0xffffffff, number ^ 0xffffffff) + payload


class USBADB(ecm.USB):
    def __init__(self, timeout=25):
        super().__init__()
        self.timeout = timeout
        self.adb_claimed = False
        self.buffer = b""
        self.deadline = None
        self.local_id = 0

    def command(self, cmd, reset=False):
        if cmd == "AT+QGMR" and not reset:
            return self._exchange(cmd)
        return super().command(cmd, reset)

    def __enter__(self):
        super().__enter__()
        try:
            state = ecm.read_state(self)
            if state.mode != 1 or state.composition != access.WITH_ADB or not self.has_ecm:
                raise ecm.ToolError("Post-restart USB composition is not the exact approved target")
            access.read_full_revision(self)
            get_device = self.lib.libusb_get_device
            get_device.argtypes, get_device.restype = [C.c_void_p], C.c_void_p
            config = C.POINTER(ecm.Configuration)()
            if self.lib.libusb_get_active_config_descriptor(get_device(self.handle), C.byref(config)):
                raise ecm.Unavailable("Cannot read post-restart USB descriptors")
            candidates = []
            try:
                for i in range(config.contents.ifs):
                    interface = config.contents.interface[i]
                    for j in range(interface.count):
                        alt = interface.alts[j]
                        if (alt.cls, alt.sub, alt.proto, alt.alt) != (255, 66, 1, 0):
                            continue
                        eps = [alt.endpoint[k].addr for k in range(alt.eps)
                               if alt.endpoint[k].attrs & 3 == 2]
                        ins, outs = [x for x in eps if x & 128], [x for x in eps if not x & 128]
                        if len(ins) == len(outs) == 1:
                            candidates.append((alt.number, ins[0], outs[0]))
            finally:
                self.lib.libusb_free_config_descriptor(config)
            if len(candidates) != 1:
                raise ecm.ToolError("Expected exactly one ff/42/01 ADB interface")
            self.adb_interface, self.adb_in, self.adb_out = candidates[0]
            if self.lib.libusb_claim_interface(self.handle, self.adb_interface):
                raise ecm.Unavailable("Cannot exclusively claim the ADB interface")
            self.adb_claimed = True
            self.deadline = time.monotonic() + self.timeout
            self.connect()
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.adb_claimed and self.handle:
            self.lib.libusb_release_interface(self.handle, self.adb_interface)
        self.adb_claimed = False
        super().close()

    def _remaining(self, limit):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ecm.Unavailable("Read-only ADB inspection deadline expired")
        return max(1, min(limit, int(remaining * 1000)))

    def _write(self, data):
        buf, sent = C.create_string_buffer(data), C.c_int()
        rc = self.lib.libusb_bulk_transfer(self.handle, self.adb_out, buf,
                                          len(data), C.byref(sent), self._remaining(1500))
        if rc or sent.value != len(data):
            raise ecm.Unavailable("ADB protocol write incomplete; no retry")

    def _read_chunk(self):
        buf, got = C.create_string_buffer(MAX_PAYLOAD), C.c_int()
        rc = self.lib.libusb_bulk_transfer(self.handle, self.adb_in, buf,
                                          len(buf), C.byref(got), self._remaining(300))
        if rc not in (0, -7):
            raise ecm.Unavailable("ADB protocol read unavailable")
        return buf.raw[:got.value]

    def _exact(self, length):
        while len(self.buffer) < length:
            self.buffer += self._read_chunk()
        value, self.buffer = self.buffer[:length], self.buffer[length:]
        return value

    def _send(self, command, arg0=0, arg1=0, payload=b""):
        data = encode(command, arg0, arg1, payload)
        self._write(data[:24])
        if payload:
            self._write(payload)

    def _receive(self):
        command, arg0, arg1, length, checksum, magic = struct.unpack("<6I", self._exact(24))
        if magic != command ^ 0xffffffff or length > MAX_PAYLOAD:
            raise ecm.ToolError("Invalid ADB packet header")
        payload = self._exact(length)
        if sum(payload) & 0xffffffff != checksum:
            raise ecm.ToolError("Invalid ADB packet checksum")
        return command.to_bytes(4, "little"), arg0, arg1, payload

    def connect(self):
        self._send(b"CNXN", 0x01000000, MAX_PAYLOAD, b"host::cellforge\0")
        command, _, maximum, _ = self._receive()
        if command == b"AUTH":
            raise ecm.ToolError("ADB host authentication required; no key generation or authorization retry")
        if command != b"CNXN" or maximum == 0:
            raise ecm.ToolError("Device did not accept the ADB connection")
        self.remote_max = min(maximum, MAX_PAYLOAD)

    def shell(self, command):
        # Only these fixed read-only commands are exposed; no arbitrary shell CLI.
        if command not in ("id -u", INVENTORY, DETAILS, CONTROLS, FACTORY):
            raise ecm.ToolError("Shell command is outside the inspection allowlist")
        return self._shell(command)

    def _shell(self, command):
        """Transport shared by separately scoped tools; no arbitrary shell CLI."""
        payload = b"shell:" + command.encode("ascii") + b"\0"
        if len(payload) > self.remote_max:
            raise ecm.ToolError("Inspection command exceeds negotiated ADB payload")
        self.local_id += 1
        local = self.local_id
        self._send(b"OPEN", local, 0, payload)
        kind, remote, target, data = self._receive()
        if kind != b"OKAY" or not remote or target != local or data:
            raise ecm.ToolError("ADB shell open was not acknowledged")
        output = bytearray()
        while True:
            kind, source, target, data = self._receive()
            if source != remote or target != local:
                raise ecm.ToolError("Unexpected ADB stream identifier")
            if kind == b"WRTE":
                output.extend(data)
                if len(output) > MAX_OUTPUT:
                    raise ecm.ToolError("ADB inventory output exceeded size limit")
                self._send(b"OKAY", local, remote)
            elif kind == b"CLSE" and not data:
                self._send(b"CLSE", local, remote)
                return bytes(output)
            else:
                raise ecm.ToolError("Unexpected ADB shell packet")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=25,
                        help="Total ADB handshake and inventory deadline, 1-40 seconds")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--details", action="store_true",
                        help="Read additional fixed USB power, LED, init and process-name inventory")
    group.add_argument("--controls", action="store_true",
                       help="Read GPIO ownership and list factory control library/header paths")
    group.add_argument("--factory-controls", action="store_true",
                       help="Read selected init GPIO references and public control symbols/paths")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 40:
        parser.error("timeout must be between 1 and 40 seconds")
    try:
        with USBADB(args.timeout) as dev:
            if dev.shell("id -u").strip() != b"0":
                raise ecm.ToolError("ADB root access was not confirmed")
            command, marker = INVENTORY, b"CELLFORGE_INVENTORY_COMPLETE"
            if args.details:
                command, marker = DETAILS, b"CELLFORGE_DETAILS_COMPLETE"
            elif args.controls:
                command, marker = CONTROLS, b"CELLFORGE_CONTROLS_COMPLETE"
            elif args.factory_controls:
                command, marker = FACTORY, b"CELLFORGE_FACTORY_COMPLETE"
            output = dev.shell(command)
            if not output.rstrip().endswith(marker):
                raise ecm.ToolError("Read-only inventory did not complete")
            print(json.dumps({"adb_root": True, "remote_writes": False,
                              "host_adb_server": False, "host_keys_created": False}))
            print(output.decode("utf-8", errors="replace"))
        return 0
    except (ecm.ToolError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Read-only inspection interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
