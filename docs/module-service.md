# Cellforge 1.0.0 module service

Status: Cellforge 1.0.0 service on the tested QDC507. No custom firmware image is
flashed. See [the release evidence](cellforge-1.0.0-validation.md) and [source
installation](install.md) for supported scope and remaining limits.

2026-11-03 update: automatic USB recovery is implemented and running in release
`de31653675b5a757`. The [automatic recovery contract](automatic-recovery.md)
supersedes the earlier probe-only maintenance behavior. Field reports recorded on
2026-11-06 describe one successful iPad lock/unlock recovery, normal LEDs, stable
long-term use and normal manual unplug/reconnect. Mac actual system-sleep and
repeated mobile acceptance are deferred; no continuous screen-off internet is
claimed.

## Use

Connect the module to the device, wait for its USB Ethernet connection, then open:

    http://192.168.225.1:8080/

The module starts the service itself after boot. A Mac and an open dashboard are not
required for maintenance. The dashboard is static HTML/JavaScript and reads
`status.json`; it does not expose a command or configuration API. The HTTP server
binds specifically to the USB LAN address and runs as UID 65534.

Displayed data: cellular upload/download totals and bytes per second, host and module
LAN IP, cellular-interface IP, signal RSSI, network generation, session duration,
recovery status and accounting quality. A cellular-interface IP may be
carrier-private. Traffic includes the module's own probes; it is not a carrier
billing figure. The page marks missing data and stalled updates explicitly.

## Target implementation

The target uses existing shell, BusyBox, awk and httpd. It does not install Python, a
new runtime, a kernel module or a phone application. `cellforge/policy.py` remains a
host reference; `module/policy.awk` is the deployed target policy.

Native telemetry is a read-only, exact-build adapter. It checks the SHA-256 of
`/usr/bin/quectel_daemon`, identifies that process by name/start time and uses the
mapped ELF load base to read only the documented network/signal/SIM fields. It does
not open the already occupied local AT devices. Unknown binary/state reports missing
telemetry instead of guessing offsets for a different build.

For this exact binary, the RGB loop and logs support this mapping:

| GPIO | Color | Electrical active value |
| --- | --- | --- |
| 1013 | Red | 0 |
| 1015 | Green | 0 |
| 1017 | Blue | 0 |

The factory RGB loop checks `/tmp/factory_led_test` and pauses while it exists.
Cellforge uses a unique ownership token in that flag. Other factory daemon
responsibilities continue. Cellforge does not change GPIO direction or export unknown
pins. Yellow drives the confirmed red and green channels together. The field reports
recorded normal LED appearance on 2026-11-06; no per-pattern video or measured signal
threshold acceptance record is implied.

Only the following factory-state words are read relative to the verified ELF load
base: generation/RSSI at `0x13008` (8 bytes), SIM at `0x132b4` (4 bytes), and radio
alarm at `0x13bc0` (4 bytes). RSSI correlated with the separate AT CSQ observation on
this unit. The adapter is pinned to binary SHA-256
`8cad1634758bb373c61536e36436dd0972e75cfe5ad977b8fe8ab1d6464bb6b9`. These offsets are
not a public vendor ABI or a claim of other-build support.

## Connection maintenance and limits

- Hold a uniquely named local wake lock while USB is CONFIGURED; release it on
  disconnection, stop or independent watchdog cleanup.
- Resolve host candidates from complete USB-LAN ARP entries, never a guessed IP.
  Actively probe at most two candidates using ARP; probe the cellular outlet
  through its actual rmnet_data interface. Normal probe rounds are about 15 seconds.
- During observed USB sleep, do not force USB resets. After resume or suspected
  loss, use the observation grace and distinct actual host-probe failures defined
  in [automatic recovery](automatic-recovery.md). Reserve at most one enable
  cycle per incident and three per boot; keep collecting during execution.
- Packet transmission may engage the factory USB controller's wake behavior.
  No claim that this can force iOS to keep USB active is made without mobile tests.
- Do not write `android0/remote_wakeup` as if it triggered a wake request. Reference
  Android gadget code uses that attribute for wakeup advertisement; it was already
  enabled on the device. The running service may briefly re-enumerate USB via
  the specified bounded `android0/enable` cycle. It does not change USB composition,
  reset PDP or reboot the module.

The deployed command syntax is the verified BusyBox 1.23 form `timeout -t 2`. The
service uses `/proc/net/arp`; that build's `ip` lacks the `neigh` subcommand.
ARP/ping filtering can prevent a positive connectivity indication even when a
different protocol works. Unknown evidence is not reported as active.

Traffic reads one cellular interface, not the sum of overlapping rmnet/bridge
counters. Counter reset/replacement preserves known accumulated bytes but marks a
discontinuity and invalidates speed until a new consecutive sample. Suspend does not
clear the session. A sustained observed USB disconnection ends it; physical unplug
cannot always be distinguished from external re-enumeration. Module power loss or a
new service instance starts a new in-memory session.

## Supervision and handback

The supervisor runs in a separate `setsid` session, surviving closure of the
installing ADB session. It coordinates a collector, LED actuator, static HTTP server
and independent watchdog. Each managed PID is paired with its process start time. The
collector heartbeat has an 8-second lease; the watchdog checks every 2 seconds. A
dead supervisor or stale collector causes resource cleanup.

Cleanup terminates only recorded Cellforge children, restores captured GPIO values,
removes only its own factory pause token, and releases its named wake lock. The
factory loop then resumes normal radio indication. Service state staleness is also
shown by the browser rather than leaving a cached healthy label.

## Installed paths

The 1.0.0 immutable payload is `/data/cellforge/releases/de31653675b5a757`, selected
by `/data/cellforge/current` in the last recorded deployment. The earlier payload
`df1c05e2aa719e6c` belongs to the 2026-11-02 historical resource snapshot.

Persistent data-owned files:

- Each payload contains `cellforge.sh`, `policy.awk`, `recovery.awk`,
  `recovery-worker.sh`, `auto-recover.sh`, `peers.awk`, `httpd.conf`, `web/index.html`.
- `/data/cellforge/startup.sh`: wait for USB LAN, launch asynchronously.
- `/data/cellforge/init.sh`: retained copy of the owned init shim.
- `/data/cellforge/autostart.enabled`: enables the startup hook.

New root-filesystem entries:

- `/etc/init.d/cellforge`.
- `/etc/rc5.d/S99cellforge` -> `../init.d/cellforge`.
- `/etc/rc0.d/K01cellforge` -> `../init.d/cellforge`.
- `/etc/rc6.d/K01cellforge` -> `../init.d/cellforge`.

These paths were absent before installation. The root UBIFS mount was temporarily
made writable for these entries and restored to read-only. Existing factory startup
files were not overwritten. The startup script waits up to 120 seconds for the
verified bridge address without blocking the factory boot sequence.

Runtime files live under `/tmp/cellforge`, plus the owned factory LED pause flag and
`/tmp/cellforge-boot.log`. Old independent payload versions are retained for
traceability; they are not started in parallel and were not automatically deleted.

## Resource snapshot

Historical read-only measurements on 2026-11-02, before automatic recovery was added.
These sizes are not the 1.0.0 payload sizes; the later 56 KiB payload and 2026-11-03
RAM snapshot are in [automatic recovery](automatic-recovery.md):

| Item | Observed size (KiB) |
| --- | ---: |
| `/data/cellforge`, including three retained releases | 104 |
| Current release | 32 |
| Current dashboard web directory | 8 |
| `/tmp/cellforge` runtime files | 64 |
| Writable data backing filesystem total / free | 15,712 / 15,440 |
| Root filesystem total / free | 58,948 / 8,688 |
| Temporary filesystem total / free | 21,728 / 21,568 |
| RAM total / free (`free -k`) | 43,460 / 7,716 |

`df -k /data` reports the backing filesystem mounted at `/cache`. These are
filesystem block usage and a point-in-time RAM reading, not isolated process memory
consumption or a sustained resource/power acceptance test. Payloads are small
relative to remaining writable storage. Installation targets the module; the Mac is
the USB installation/control host and needs no resident application.

## Control and rollback

With the module attached to the Mac:

    python3 -B scripts/module_runtime.py status
    python3 -B scripts/module_runtime.py stop
    python3 -B scripts/module_runtime.py start
    python3 -B scripts/module_runtime.py logs

Disable persistent startup separately:

    python3 -B scripts/module_runtime.py disable-autostart

That operation checks the owned shim/hash and symlink targets before removing the
Cellforge startup entries, restoring root read-only afterwards. It leaves payload
versions for inspection. `stop` hands back lights and wake locks; it does not disable
future boot startup. Removing retained data files is a separate cleanup action with
an exact candidate list, not an automatic rollback.

USB ADB authorization remains independent: stopping or removing this service does not
revoke the separately accepted authorization or close its USB function.

## Evidence from deployment

- Five new target policy fixtures passed; dashboard JS and target shell syntax
  passed. Previously passed unrelated tests were not rerun during startup repair.
- `nohup` alone did not survive the ADB session; the service stopped and handed
  back its resources. `setsid` fixed the launch/session boundary.
- The old timeout argument form initially prevented probes from launching. One
  invocation correction to `-t 2` produced fresh host/outlet success and blue solid.
- One intentional supervisor SIGKILL exercised the independent watchdog. After
  3 seconds all Cellforge children were gone, the pause flag was absent and its
  wake lock was released. Service was then restored.
- After installing startup, one module restart automatically restored the
  service without a host start command. The returned state was `active`,
  `blue_solid`, telemetry available, both connectivity evidence ages 10 seconds,
  and live cellular byte deltas. MAC/phone-independent startup is thus observed
  on this unit; this restart test did not establish locked-mobile behavior.
- A direct Mac request to the dashboard returned HTTP 200 with the actual page.

2026-11-06 field report: one iPad lock/unlock recovery succeeded, manual
unplug/reconnect and LEDs are normal, and long-term use is stable. No device/OS
matrix, lock duration or recovery-event correlation was supplied. Repeated cycles,
continuous screen-off internet, quantified power/thermal impact and complete
uninstall are not established. These are disclosed limits of the documented 1.0.0
scope, rather than claims of completed broad acceptance.

Reference for the wakeup attribute distinction: [Android gadget remote_wakeup
implementation](https://android.googlesource.com/kernel/msm/+/911cc4cde9b6c237aed0b3427d1577b16b61ee54/drivers/usb/gadget/android.c).
