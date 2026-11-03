# Proposed single android0/enable trial

Date: 2026-11-02. Status: the single awake-Mac capability trial passed. See the
execution result below. No automatic recovery is enabled. This is a capability
experiment, not an automatic sleep/resume fix. The previous UDC soft_connect
experiment failed and is not reused.

## Why this candidate, and what is still unknown

The matching factory libql_usb disassembly establishes that the narrow
quectel_usb_enable primitive writes androidN/enable. See the
[investigation](usb-recovery-investigation.md) for hash and instruction evidence. It
does not establish the proprietary kernel implementation or host behavior.

The public [Qualcomm Android 3.18 reference
driver](https://android.googlesource.com/kernel/msm/+/android-msm-marlin-3.18-nougat-dr1/drivers/usb/gadget/android.c)
provides a mechanism explanation, not an exact match for QDC507 firmware. The decoded
reference file SHA-256 is
`2f475b178211fc704d6d694bf874aa8ad1af26ea23fdde4e2079096d3cc25ca0`.

In that reference, enable_store serializes on the Android gadget mutex, invokes
function enable/disable callbacks, and uses android_disable/android_enable to
remove/add configurations and disconnect/connect. FunctionFS can hold the gadget
disabled until descriptors are ready. An android_enable error can still result in a
successful sysfs write and enabled=true. Consequently neither return code nor
enable=1 proves enumeration or recovery. Unlike generic UDC soft_connect, this
candidate goes through the Android composite/function lifecycle.

Current device preflight observed enable=1, functions=diag,serial,ecm,ffs,
VID/PID=2ca3:4006, CONFIGURED, usb_sleep=0, FunctionFS mounted at /dev/usb-ffs/adb
with ep0/ep1/ep2, and adbd/qti/netmgrd/quectel_daemon running. No native function or
kernel node was invoked. No exclusive lock shared with factory processes has been
established; Cellforge-only locking cannot provide that guarantee. This remains a
test risk, not a resolved ownership contract.

## Trial tooling

- Keep the ordinary service package and persistent startup unchanged. Do not
  install an automatic USB reset path or modify USB composition.
- Add a separate trial executor and bounded host observer. Their interface
  exposes only this fixed single experiment, not arbitrary shell or node paths.
- Use the existing bounded journal with a unique ticket. The main executor is
  its sole normal writer. An independently detached safeguard uses a separate
  fixed-size emergency result file, preventing writer-lock races. Do not store
  serial numbers, MACs, SIM identifiers, carrier IPs, raw logs or kernel dumps.
- Store trial assets/evidence in one fixed private /data/cellforge trial directory
  so manually power cycling cannot erase all evidence. Record the exact installed
  filenames/hashes. No boot hook is added. Existing evidence is never overwritten.
- Verify script syntax and phase/fault fixtures before any device write. On the
  device, first verify journal utilities and a committed pre-action record;
  install is not permission to disconnect without successful preflight.

## Preconditions immediately before execution

1. Exact specified identity/firmware/composition and both original binary hashes
   match. Root ADB works. All fixed paths exist; enable, functions and IDs have
   their expected values. CONFIGURED and usb_sleep=0 remain stable for 10 seconds.
2. Establish a fresh positive host+uplink baseline first. Locate the actual Mac
   USB interface from current hardware inventory, not a hard-coded en7. Confirm
   DHCP and a valid dashboard/status response bound to that interface. Treat a
   currently suspended or already failed link as a different experiment.
3. Capture the original control/function/ID values and factory process name/start
   identities locally; publish only match/mismatch results. No factory daemon
   is stopped, signalled or restarted. Do not invoke ql_usbcfg or init scripts.
4. Require no other Cellforge trial, no unresolved prior evidence and a successful
   journal flush. Verify detached executor readiness, independent safeguard
   readiness and a local countdown before the ADB session can disappear.
5. A host-side foreground observer runs over the trial window. It must keep
   observing if ADB disappears and may not issue a second disconnect.

## Exact operation

Only /sys/class/android_usb/android0/enable is a writable USB target. Write value
0 once, wait 2 seconds if that call completes, then restore the original value
1. Bound each sysfs-write process to 5 seconds using the verified BusyBox timeout
syntax. Timeout means unknown outcome; no repeated disable is allowed.

An independent module process is armed before the disable. At 10 seconds after
arming, it makes at most one best-effort restoration write of 1 if the primary
executor has not established the original control state. Serialize user-space
restoration attempts; do not steal a held operation lock or create retry loops. The
safeguard must remain runnable if the main service/executor terminates. It cannot
guarantee recovery from a stuck kernel or controller, or reliably infer host health
from enable=1. Record whether it acted, skipped or was blocked.

Once disable was requested, restoring the original enable state takes priority over
journal failure. A full/locked/broken journal blocks starting a new disable, but must
not block an already-needed best-effort restoration. Record uncertainty to the
emergency result file where possible; retain all pending evidence.

If functions, IDs, process identities or other captured state drift, classify the
trial as failed/uncertain and stop further experimentation. Do not try to repair the
drift by writing composition, restarting adbd, rebinding UDC or restarting the
module. These are outside this experiment.

## Deadlines and success evidence

All deadlines are conservative experiment limits, not measured hardware promises.

| Stage | Limit | Required evidence |
| --- | --- | --- |
| Disable / restore call | 5 seconds each | Return status or explicit timeout/unknown |
| USB enumeration | 60 seconds from restore attempt | Host sees expected USB identity again; module CONFIGURED alone is insufficient |
| Address recovery | A further 60 seconds | Actual USB interface active with DHCP address and module route |
| Communication | 15 seconds after address | USB-bound HTTP returns actual Cellforge page and fresh status, plus direct host/module response |
| Stability | A further 30 seconds | Repeated fresh two-sided observations without additional recovery action |

If a stage is not observed by its limit, record failure/unknown, stop the trial and
preserve evidence. No automatic second cycle. If control remains unavailable, manual
power cycling may be required to recover the test unit; this is a test failure and
must never be counted as automatic recovery. Persisted module records are read
afterwards and combined with bounded host observations.

## After the experiment

Report source tests, module command outcomes, host enumeration, DHCP and real
communication separately. Success on an awake Mac proves only this operation's basic
capability. It does not prove sleep recovery, iOS behavior or the ability to force a
sleeping host awake.

The automatic state machine needs a successful action-capability trial and: failure
classification, resume grace period, single-owner execution, per-incident/boot
budgets, cooldown, accounting continuity, watchdog coordination and distinct
Mac/iPad/iPhone sleep acceptance. Further USB experiments need their own preflight,
limits and restoration plan.

## Execution result

A host inventory preflight initially assumed an array root; the actual ioreg plist
root was a dictionary. No device write or USB action occurred in that failed
preflight. Parsing was then normalized and tested for both root formats, malformed
inventories, absence, multiple targets and a changed instance marker.

Before deployment: 13 executor/observer fault fixtures passed; then all 82 tests,
workspace checks (21 Python sources), target shell syntax and diff checks passed. The
real repaired observer found one target and a healthy USB-bound baseline. Then
prepare installed/verified the isolated assets, committed trial evidence using actual
module utilities, and passed the stable module preflight.

Exactly one cycle was released. The module journal recorded disable and enable calls
returning ok, separated by two monotonic seconds (2362 and 2364). Host observations,
measured from observation-loop entry after release, were:

| Observed stage | Elapsed seconds |
| --- | ---: |
| New USB instance / enumeration | 8.7 |
| USB interface active with IPv4 | 12.0 |
| Actual Cellforge page and healthy fresh status over USB | 20.0 |
| Continued fresh two-sided status for over 30 seconds | 50.4 |

Executor exit was 0; captured factory process identities and USB control values
matched. The safeguard reported control_already_matches and issued no fallback write.
No manual unplug, power cycle, module reboot, daemon restart, second disable or
USB-composition write occurred. The original service release remained
df1c05e2aa719e6c and its startup configuration was not changed. UBIFS root stayed
read-only. This is one healthy/awake Mac trial, not a sleep-recovery acceptance.

Installed trial assets under /data/cellforge/recovery-trial (private, no boot hook):

- journal.sh, 5073 bytes, SHA-256
  d9ed7efb89b8574d0c4e1e2bd3872a02a21afc6c0786ba8667dc5aeb489dbc4f.
- executor.sh, 6763 bytes, SHA-256
  92853889bf07eb5424eb32487182bcf2eb37dde36a6dbfa0b8f2328fb54a7889.
- manifest.json, factory.before, events.tsv (549 bytes), claimed/ marker,
  operation.lock, issued, restore-attempted, executor/guard readiness and result
  files, go, guard.identity, plus executor.log/guard.log (both empty). Files are
  bounded to one claimed trial; no automatic cleanup or further cycle is allowed.
  Factory process start metadata stays private on the module.

The local host evidence record contains baseline success, stage timings and final
success. Raw USB inventory and device identifiers were not persisted. Journal
observations were appended after the host stability window; their timestamps are
recording times, not the earlier host event times. The separate host timings above
are the event evidence.

The evidence flush path ran on the module, but power-loss durability and actual
fallback execution were not hardware-tested in this cycle. Host fixtures stub the
lock/sysfs/sleep seams; they prove bounded decisions, not controller recovery under
all faults. At this trial stage, automatic sleep classification/recovery, accounting
continuity and mobile acceptance were still untested. The subsequent
implementation/deployment and current acceptance boundary are recorded in [automatic
recovery](automatic-recovery.md).
