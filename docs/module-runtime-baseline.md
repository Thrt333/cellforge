# Module runtime baseline after ADB authorization

Observed on 2026-11-02 on the same connected QDC507. These are device-specific
observations through direct USB ADB, not acceptance of Cellforge 1.0.0. This is the
pre-service snapshot. Later deployed-service observations and changed installed paths
are recorded in [the service guide](module-service.md).

## Configuration change and outcome

The transaction is documented in
[legacy-adb-transaction.md](legacy-adb-transaction.md). One locally derived QADBKEY
authorization request was accepted. One ADB-only composition write followed, then one
module restart request. No alternate algorithm, additional authorization, mutation
retry or rollback was attempted.

Independent post-restart inspection confirmed:

| Item | Observed |
| --- | --- |
| Full revision | `QDC507GLEFM21_01.001.02.004` |
| USB identity | `2ca3:4006` |
| Network mode | 1, ECM |
| Full composition | `0x2CA3,0x4006,1,1,1,1,1,1,0` |
| ADB interface | 6, class/subclass/protocol `ff/42/01`, bulk endpoints |
| ECM interface | Present |
| Direct ADB handshake | Accepted |
| Effective ADB shell UID | 0 |

The root shell worked without a second, post-restart authorization. This establishes
that the selected legacy method worked on this unit, despite the public failure
report for the same revision. It does not establish compatibility with every module
or explain the other report's failure.

No service, file, startup hook, custom firmware or kernel module was installed or
pushed. No UAC, IMS, VoLTE, SIM, APN or routing setting was changed. ADB
authorization itself is a persistent security change; its reversibility remains
unverified. Merely closing the ADB function does not prove authorization revoked.

## Runtime and resources

| Item | Observed |
| --- | --- |
| OS/kernel/architecture | Linux 3.18.44, armv7l |
| Init | `/sbin/init.sysvinit`, `/etc/init.d`, `/etc/rc5.d` |
| Factory root filesystem | UBIFS reported read-only |
| Data storage | `/data`, UBIFS reported writable |
| Temporary storage | `/tmp` -> `/var/tmp` -> `/var/volatile/tmp` |
| AP MemTotal | 43460 KiB, about 42.4 MiB |
| AP MemAvailable snapshot | 16064 KiB, about 15.7 MiB |
| Data free-space snapshot | 15488 KiB; `df /data` labels the underlying volume `/cache` |
| Temporary backing free-space snapshot | About 21 MiB on tmpfs |

Existing commands found include BusyBox/sh, awk/sed, curl/wget, ip/ifconfig, ping,
httpd, timeout, flock, start-stop-daemon, strings and standard proc/sysfs readers.
`httpd` resolves to `/usr/lib/busybox/sbin/httpd`. The command lookup did not find
Python, Python 3, Lua, Node, gcc or cc in the shell's PATH; this is not a complete
filesystem search for all possible runtimes. Float ABI, target libc/linker and a
cross-build sysroot have not been inspected. The host Python policy prototype is not
a deployed module service.

## Networking and ownership

- USB functions read `diag,serial,ecm,ffs`; USB state was CONFIGURED/high-speed.
- USB local address was on `bridge0` (`192.168.225.1/24`); `ecm0` was up.
- The observed default cellular route used `rmnet_data0`, with a carrier-private
  address. No cellular address or neighboring hardware identifier is published.
- Byte counters were readable for bridge0, ecm0, rmnet0 and rmnet_data0.
  These overlap; do not sum them as independent traffic. Counter-source mapping
  and epochs still require validation before billing-style totals are displayed.
- Factory `dnsmasq`, `netmgrd`, `quectel_daemon`, `ql_manager_server`, `qti` and
  `adbd` were running. Their services were not stopped or reconfigured.
- The listener snapshot showed USB LAN DNS, DHCP and a loopback TCP listener;
  no dashboard listener was started. A deployment must recheck current ports.

Presence of ECM and a default route is not a fresh independent internet test after
restart. No host network settings or Wi-Fi state were changed.

## Power and wakeup controls

Observed paths, read only or inspected for metadata:

- `/sys/power/wake_lock` and `/sys/power/wake_unlock`: root-writable nodes.
- `/sys/class/android_usb/android0/remote_wakeup`: root-writable node.
- `/sys/class/android_usb/android0/usb_sleep`: read-only node.
- `/sys/class/android_usb/android0/state`: read-only node.
- `/sys/class/udc/msm_hsusb`: controller state and speed.

`remote_wakeup` was not written or invoked. Its accepted input, exact kernel
semantics, phone authorization and actual mobile-host behavior remain untested. The
vendor USB library contains a `remote_wakeup` symbol/string, which is a research lead
rather than proof of a usable service API.

The UDC and android_usb runtime-PM nodes reported `control=auto` and
`runtime_status=unsupported`. A host-style autosuspend setting must not be assumed to
control this device-side controller. Holding a local wake lock alone does not
establish that a locked phone keeps servicing USB.

## LED control remains an implementation gate

The inspected module namespace had no standard `/sys/class/leds` entry. A bounded
`/sys/devices` name search did not locate RGB controls. That does not prove that the
physical lights cannot be controlled.

GPIO debug metadata showed existing sysfs exports including 1013, 1015, 1017 and
1018, but no verified color mapping or safe ownership transfer. No GPIO was exported,
unexported or written.

Factory `quectel_daemon` contains `quectel_qmi_set_nw_status_light_gpio_ind` and
GPIO-processing symbols, and references GPIO1018 and android_usb sleep state. This
suggests factory involvement but does not prove which component owns each color or
that GPIO1018 is a safe LED control. Do not stop the entire factory daemon merely to
test lights; its other responsibilities are not established.

The read-only QCFG capability catalog advertises `ledmode` values 0-2; the current
query returned 0. No mode was changed. This does not establish an RGB color-selection
API, yellow support, or a factory handback procedure.

## Next implementation gates

1. Confirm read semantics and state transitions of USB sleep/remote wakeup,
   then define a bounded, bounded functional test.
2. Identify LED mapping and its current owner before proposing a takeover test.
3. Choose a lightweight target implementation using verified runtime/toolchain
   capability; retain host fixtures as policy evidence rather than runtime proof.
4. Prepare exact staging/start/stop/cleanup and resource limits before any
   temporary service trial. Persistent installation/startup remains separate.
5. Validate screen-off traffic and unlock recovery on the actual mobile devices.

## Reproduction

- `make probe-module`: read-only USB/AT descriptor and authorization summary.
- `python3 -B scripts/adb_inspect.py`: fixed root and environment inventory.
- `python3 -B scripts/adb_inspect.py --details`: fixed process-name/init/power inventory.
- `python3 -B scripts/adb_inspect.py --controls`: GPIO ownership and control-library paths.
- `python3 -B scripts/adb_inspect.py --factory-controls`: selected source references,
  public control symbols and USB-node permissions; scripts are read, never executed.

These tools use no host ADB server, host key generation, arbitrary shell argument,
file push or external device-identification service. Metadata and inventory output
are not full raw device backups and do not establish flash recovery.
