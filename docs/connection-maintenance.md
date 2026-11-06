# Cellforge 1.0.0 design and implementation gates

Status: 1.0.0 implementation and original design history. The version is stored in
`VERSION`. Current behavior is in [the service guide](module-service.md) and
[automatic recovery](automatic-recovery.md); the 2026-11-06 release scope and
field-reported acceptance are in [the validation
record](cellforge-1.0.0-validation.md). The prototype and inspection statements below
are historical. Later implementation and current evidence supersede the earlier
deployment status.

## Outcome and delivery

The module should maintain a mobile device's USB network independently of a Mac or an
open browser page. Screen-off internet and automatic recovery after unlock are
separate acceptance criteria. A successful recovery must not be reported as proof of
continuous screen-off internet.

Prefer a service within the factory firmware. Kernel changes or a replacement
firmware require a separate implementation and recovery decision. There is no module
SDK, cross-build sysroot, firmware image or proven flash recovery in this repository.
The initial runtime uncertainty was resolved by inspecting and using the factory
shell/awk/BusyBox; Python remains a host tool, not a module runtime.

`cellforge/policy.py` is a hardware-independent executable policy prototype, tested
on host Python 3.9+. It issues action intents but performs no I/O and cannot keep a
phone connected, drive an LED or reset a module. It remains a reference prototype;
the deployed shell/awk adapter is documented separately.

## Initial evidence and observation boundary (historical)

- Field reports describe working iPad and iPhone internet access before locking, then
  failures after some locked interval even though the LED remains green. Device
  models, OS versions, connection arrangement and timing are not yet recorded.
- Read-only Mac USB inspection found configuration attributes
  `0xa0`, advertising remote wakeup; ECM interfaces were present and an ADB
  interface was absent. Advertisement does not prove the phone enables wakeup,
  that the controller can issue it successfully, or that iOS accepts it.
- The current host tool reads `QDC507GLEFM21`, mode 1 and composition
  `0x2CA3,0x4006,1,1,1,1,1,0,0`. Recheck with `make probe-module` before a change.
- A restricted USB query is not proof that no module is connected; cross-check host enumeration and access permissions. It claims AT interface 2;
  other management tools must not use that interface concurrently.
- The initial ADB-bit attempt did not produce the target readback; no restart
  or retry followed. A bounded legacy authorization then succeeded:
  ADB root, Linux 3.18.44/armv7l and the runtime/power-node inventory are confirmed
  in the [module baseline](module-runtime-baseline.md). Exact compiler ABI and
  LED mapping/ownership/yellow output remain unverified. No service is deployed.

The upstream DJOneHub v1.2.10 implementation holds a module wake lock and pings the
local host and an internet destination. Its release notes explicitly leave
long-duration mobile lock-screen validation outstanding. That is a research input,
not acceptance evidence for Cellforge.

## State and evidence matrix

All policy timestamps use one monotonic clock. An adapter must timestamp actual
observations, not the moment it replays cached data. Counter traffic, a DHCP lease,
an interface name, and a queued USB write alone do not establish a live mobile host.
A missing observation must not be converted into a negative one.

| Boundary | Meaning | Policy behavior |
| --- | --- | --- |
| available | Fresh two-way host evidence and verified module cellular outlet | Active, blue solid |
| limited | Confirmed failure, unsupported recovery, unarmed wakeup or exhausted budget | Show known radio fallback and limitation; no destructive fallback |
| missing | No trustworthy attachment, SIM, signal or communication evidence | Report unknown; do not invent a color or start recovery |
| not_applicable | Confirmed no attached device | Display known radio state; stop recovery and release resources |
| cutoff | Success evidence expired, or predates a detach/fault/suspend | Recheck; prior blue indication lasts only a bounded grace period |

The host reference prototype uses 30 seconds evidence TTL, a 5 second check grace, a
5 second action deadline, 15 seconds between wakeup attempts, and at most 3 attempts.
These are testable prototype parameters, not validated device tuning or the final
release contract. The attempt budget resets on confirmed healthy state or confirmed
detach, not simply because an elapsed timer starts a new cycle.

After suspend or a definite fault, require fresh evidence from after the event. A
successful wakeup dispatch is not proof that the device resumed. Each intent has a
unique token and deadline; a late or duplicate completion is ignored. No successful
evidence means no permanent blue solid indication.

## Original maintenance and recovery proposal

The table below describes the reference prototype. The deployed bounded USB enable
executor and its different trigger/budget rules are authoritative in [automatic
recovery](automatic-recovery.md); do not apply prototype retries to the production
executor.

One coordinator owns all AT, USB, cellular and LED operations. Observers and
dashboard consumers cannot perform mutations or compete for control channels.

| Condition | Operation | Stop condition |
| --- | --- | --- |
| Fresh communication, no user traffic | Maintain low-cost observation; zero speed is normal | Detach, disable or fault |
| Evidence expired or unavailable | Collect new host and cellular evidence | Deadline; report uncertainty |
| Confirmed USB suspend, supported and armed wakeup | Request one wakeup and check fresh communication | Deadline, detach, red fault or attempt budget |
| Wakeup unavailable or host did not arm it | Report limited capability | Await new evidence or explicit intervention |
| Wakeup request completes but no success evidence | Back off before any further attempt | Budget exhausted |
| Cellular or host probe fails | Report the failed layer and collect diagnostics | No automatic PDP reset, USB re-enumeration or reboot in the prototype |

The prototype emits only `request_usb_wakeup`. No executor is yet connected. Cellular
repair, USB re-enumeration and reboot remain disabled until their specific
preconditions, action limits, postconditions and recovery procedure are documented
and specified. The adapter must independently enforce the deadline, validate current
permission and recheck the active intent immediately before dispatch. Cancelling an
intent does not undo an already sent request.

Do not interpret browser traffic as the sole host proof. The future adapter must
demonstrate a supported two-way probe for the real phone and distinguish a filtered
probe from an actual broken connection. ICMP timeout alone cannot justify a
destructive repair. Local heartbeat traffic stays on USB; any cellular probe must be
explicitly routed through the cellular outlet and metered.

## LED contract

| Pattern | Meaning |
| --- | --- |
| Blue solid | Recent device-side communication evidence and healthy module cellular outlet |
| Blue blink | An active bounded connection establishment or recovery operation |
| Green solid / blink | Device activation not established or recovery failed; strong / weak 4G signal |
| Yellow solid / blink | Device activation not established or recovery failed; strong / weak 2G/3G signal |
| Red solid | SIM not detected, unchanged |
| Red blink | SIM present but no network signal, unchanged |

Red faults override other indications. Backoff uses the known radio color; retry
execution uses blue blink. A detached device is not counted as a recovery failure. An
unknown input has no fabricated LED decision; dashboard and logs must mark it
unavailable. A hardware adapter must define a fail-safe handback instead of leaving
an old blue output latched indefinitely.

During blue indication, radio generation and signal remain visible in the dashboard.
Blue does not certify the phone's DNS, routing, every application or public internet
access from the phone itself.

Identify the factory LED owner and its handback mechanism before writing LED
controls. A single instance lock must prevent competing coordinators. An independent
supervisor or bounded hardware indication must cover SIGKILL or a crash; an exit
handler alone is insufficient. No LED takeover ships without tested normal-stop and
crash cleanup. Verify physical yellow output first.

## Dashboard and accounting

The dashboard reads a single coordinator snapshot: cellular upload/download totals
and bytes per second, local device IP, cellular-interface IP, generation, signal, USB
state, host evidence age, outlet evidence age, latest recovery and backoff. A
cellular-interface IP is not necessarily a public IP. No extra external public-IP
service is needed for 1.0.0.

Use user-oriented upload/download names. Keep cellular accounting separate from USB
dashboard/heartbeat bytes. Module probes count toward cellular usage and must be
disclosed; module counters are not carrier billing evidence.

| Counter sample | Total | Speed |
| --- | --- | --- |
| First known sample | Establish baseline | Unavailable |
| Consecutive valid sample, same counter epoch | Add nonnegative delta | Delta / monotonic elapsed time |
| Valid unchanged counter | Preserve | Zero |
| Missing or partial sample | Preserve | Unavailable |
| First sample after gap, same epoch | Add known delta | Unavailable; do not invent instantaneous speed |
| Reset, wrap or interface/epoch replacement | Preserve, rebaseline, mark discontinuity | Unavailable |

An epoch must identify the counter source and its reset lifetime, not merely an
interface name. A reset that exceeds the previous value cannot be detected from two
byte samples alone; uncertainty must be exposed by the adapter.

Statistics belong to a usage session, not an interface object's lifetime. Suspend or
coordinator-requested recovery must not clear accumulated totals. A confirmed
physical detach ends the session. If physical detach cannot be distinguished from
re-enumeration, mark the boundary uncertain. Unobserved traffic during a reset means
totals are incomplete, not exactly measured. The prototype accumulator is in memory
and does not yet implement a session manager or persistence; process restart does not
preserve its totals.

The HTTP server must bind only to a verified USB LAN address/interface, never
wildcard or cellular WAN, and refuse to start if isolation is uncertain. Keep factory
DHCP, DNS, NAT and routing ownership intact. Inspect actual listeners before
selecting a port. The deployed server binds `192.168.225.1:8080` and exposes
read-only dashboard data. 1.1.0 traffic switching requires its own review of any
change to factory network ownership; it is not part of this release.

## Deployment and rollback

Complete inspection before choosing runtime, compiler target or startup method. An
existing host `adb` executable does not establish access to this module.

Before enabling debugging, present the exact current and proposed USB composition,
authorization procedure, restart requirement and rollback steps. Do not guess unlock
credentials, change IDs, expose an ADB TCP listener, flash generic firmware, or
install an upstream runtime as a substitute for inspection. USB identity and the
existing AT control path must remain recoverable.

Before persistent deployment, record every target path, original content/mode,
startup hook and port; stage and verify files before enabling startup. An uninstaller
removes only Cellforge-owned files and restores recorded factory ownership, without
deleting shared state. Confirm recovery through a separate control path before
testing USB repair. Flash recovery is not provided here.

## Verification and release gates

Run affected-scope targets (`make check-policy`, `make check-access`, `make
check-probe`), then `make check`, then `make check-workspace`, then `make
check-diff`, in that order. `make probe-module` is a separate, explicit hardware
read; it does not enable ADB, change mode or install anything.

The separately gated access helper and exact transaction are documented in [the ADB
access procedure](legacy-adb-transaction.md). Preparing that helper does not
authorize executing a composition write or restart.

The following is the comprehensive acceptance target. Uncompleted items remain
disclosed limitations, not passed experiments.

| Layer | Original target evidence |
| --- | --- |
| Policy fixtures | Evidence cutoff, future/missing samples, red priority, radio/strength matrix, retry ceiling, timeout, stale completion, counter gaps/resets |
| Module adapter | Actual runtime/ABI, supported probes and wakeup path, AT arbitration, yellow LED, factory handback, bounded resource consumption |
| Lifecycle | Single instance, normal stop, crash/SIGKILL cleanup, unplug, power loss, uninstall and rollback |
| Mobile | Recorded model/OS/cable/power, dashboard open and closed, multiple lock durations and repeated cycles; measure screen-off network separately from unlock recovery |
| Resource | Battery impact, temperature, probe bytes, memory and CPU |

Before acceptance, fix the supported-device matrix and numeric pass criteria (lock
duration, recovery deadline, repetitions and acceptable resource cost). Keep other
network paths controlled so Wi-Fi or native cellular cannot mask a USB failure. Use
independent traffic evidence for screen-off connectivity; an LED, ping dispatched by
the module, or dashboard refresh alone is insufficient. The 1.0.0 field evidence
consists of one reported iPad lock/unlock success, normal manual unplug/reconnect and
LEDs, and stable use. Mac actual sleep and repeated/multiple-device acceptance remain
untested. Continuous screen-off connectivity, hardware fault injection, quantitative
power/thermal acceptance and full uninstall are not established. Follow [source
verification](install.md#verify-a-source-checkout) for software verification,
publication and accurate disclosure.

## Research references

- [Linux USB Gadget API](https://docs.kernel.org/driver-api/usb/gadget.html): peripheral control and host-armed wakeup.
- [Linux interface statistics](https://docs.kernel.org/networking/statistics.html): local counter access.
- [Apple wired accessory policy](https://support.apple.com/en-ie/111806): accessory permission is distinct from continued execution.
- [Apple developer discussion](https://developer.apple.com/forums/thread/844516): relevant report, not a QDC507 guarantee.
- [DJOneHub v1.2.10](https://github.com/rogerbush007-a11y/DJOneHub-mac-enhanced/releases/tag/v1.2.10): unvalidated-on-mobile upstream approach; source inspected at `5b15eaec0e97dd9fa7b2abe54d0d1289c1e93054`.
