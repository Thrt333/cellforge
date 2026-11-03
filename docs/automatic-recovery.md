# Automatic USB recovery contract and deployment

Design recorded 2026-11-02; deployed 2026-11-03. Exact-build QDC507, factory USB
composition retained. The successful awake-Mac enable trial establishes a candidate
action, not sleep acceptance. No host program/dashboard is required by the automatic
design.

| Observation | Decision |
| --- | --- |
| No previous healthy connection | checking; no reset |
| Confirmed USB sleep | sleeping; no reset |
| Missing/unsupported USB sleep or host candidate | unknown; no reset |
| Resume / newly suspected loss | 30-second observation grace |
| Radio or cellular probe missing/failed | limited; no USB reset |
| Three distinct actual host-probe failures after grace | at most one enable cycle |
| Repeated snapshot of one failed probe | no extra failure count |
| Current recovery / uncertain call | preserve budget; wait for new evidence |
| Fresh responses sustained for 30 seconds | recovery confirmed |
| Incident already attempted / boot limit reached | no further disconnect |
| Healthy 30 seconds and 120 seconds since action | end incident; boot budget retained |
| Self-generated detach | preserve accounting; mark discontinuity/uncertainty |
| Ordinary observed detach | invalidate host binding; normal session boundary |

Budget/state live outside a service generation under /tmp/cellforge/auto so service
stop/start does not reset them. Boot budget is three, one cycle per incident.
Missing/corrupt budget data after prior actions fails closed. USB sleep=0 is not
proof that the host is awake; limited best-effort recovery cannot force a host to
service USB. Completed actions are not proof of restored traffic.

The collector is the sole decision writer; a detached executor owns USB writes and
one independent safeguard makes a bounded best-effort restoration if needed. No
shared exclusive lock with factory software is claimed. No daemon is stopped, no
composition/PDP/reboot operation is performed. Actual sleep and mobile acceptance
remain separate gates.

## Implementation and ownership

- `recovery.awk` makes decisions; a snapshot is not a probe round. The collector
  records a new sequence only when it actually has a target and sends ARP.
  An initial healthy baseline is required. Unknown sleep state, missing target,
  radio alarm or unconfirmed uplink cannot request a new USB reset.
- `peers.awk` selects at most two in-subnet targets. A successfully probed peer
  is cached only within the current observed attachment; this survives an ARP
  entry becoming incomplete. Ordinary detach invalidates the binding. Launching
  recovery clears cached peer, displayed host IP and all prior health timestamps;
  subsequent discovery/probes must generate new evidence.
- `recovery-worker.sh` reserves an action slot before starting the executor.
  /tmp/cellforge/auto/used, last, blocked and state outlive service generations.
  Slots action1..action3 are never reused in that boot. Missing budget after an
  existing action, invalid budget, or failed reservation refuses further resets.
  A restarted worker has no cached peer and must relearn evidence.
- `auto-recover.sh` is a separately detached production executor, not the trial
  tool. It rechecks the pinned factory files, USB functions/IDs, supervisor PID
  start identity and live collector heartbeat before mutation. One operation
  lock serializes writes; each action has an exclusive executor claim and an
  issued marker, preventing duplicate disables.
- It arms a detached safeguard before a single enable=0, waits two seconds on
  call success, then attempts enable=1. Each write uses a five-second process
  timeout. Uncertain disable results still lead to one restoration attempt.
  The safeguard acts once after ten seconds if control is not restored and
  the operation lock is available; it never steals a held lock. Neither process
  guarantees recovery from a stuck controller/kernel.
- Normal collection/heartbeats continue while USB operations run. Stop/watchdog
  cleanup cancels the owning action rather than killing its restoration process.
  A separately owned recovery wake lock protects the operation. A pending restore
  prevents dropping the action ownership or staging another service payload.
- The executor reports waiting after calls return; only new two-sided healthy
  observations sustained for 30 seconds confirm it. An action has a 150-second
  lease from reservation. Failure/timeout blocks another action for that incident.
  A completed action can leave cooldown only after 30 seconds of observed health
  and 120 seconds since reservation; the boot count is never cleared by health.

The collector alone writes decision state and clears completed ownership. The
executor writes its phase/results and pending state. The safeguard writes its own
completion/result. Factory processes continue running; preflight checking and
Cellforge locks do not establish mutual exclusion with proprietary software.

## Accounting, UI and retained records

Self-generated detaches preserve the current session and accumulated bytes. The
policy records a discontinuity and marks accounting limited/rates unavailable while
recovery owns the link. If detach cause remains ambiguous after the lease, it retains
the uncertainty marker rather than inventing continuous measurement. Fresh configured
host/uplink evidence after ownership ends clears that marker; the discontinuity
remains visible. An ordinary detach still ends a session after three observed
seconds. Process restart/power loss still resets in-memory traffic totals; no
billing-grade or power-loss-persistent accounting claim is made.

Blue blinking now corresponds to an actual reserved recovery/confirmation process,
not empty-target polling. Red faults retain priority. New health after confirmation
permits blue solid; green/yellow radio fallback retains its meaning. Dashboard
exposes recovery phase, per-boot action count and accounting uncertainty. It does not
gain a control API or change host network priority.

Persistent event history is /data/cellforge/recovery-events.tsv: at most 32 rows,
8192 bytes plus a bounded update file. It contains UTC, uptime, action number, phase
and result, no device identifiers or raw output. Normal polling never syncs flash.
Pre-action evidence must commit before disable; no log flush occurs between disable
and re-enable. Restoration takes priority over logging failure. Temporary action
artifacts are limited to the three boot slots; an unknown pending restore is
retained, not automatically discarded.

The older /data/cellforge/recovery-trial records are retained independently and are
not read/replayed by automatic recovery. No trial script is in the ordinary service
package. No boot entries, USB composition, PDP settings or firmware image were
rewritten for this deployment.

## Verification and current deployment

- Fixed a test fixture that unintentionally rolled the counter back during a
  continuity test. Only the input sequence changed; expected totals remained.
- `make check-auto-recovery`: 18 decision/executor/peer/budget/log fixtures and
  7 device-policy/accounting fixtures passed.
- Full `make check`: 102 tests passed. Dashboard JS, shell syntax, workspace
  checks (22 Python sources) and diff checks passed. After making the issued
  timestamp atomic, the 25 affected fixtures passed again; unrelated tests were
  not repeated for that final metadata change.
- Host fixtures replace real sysfs/locks/sleep/flush seams with isolated files.
  They verify decisions and failure handling, not real USB/sleep/power behavior.
- Stopped the old service, uploaded eight hash-verified files, and started
  release `de31653675b5a757`. No module restart or forced disconnect was issued.
- Actual module status was active/blue_solid, new recovery_mode=active,
  fresh host/uplink responses, normal byte deltas, no accounting discontinuity,
  boot recovery count=0. Native telemetry and static HTTP remained available.
  Startup logs were empty; existing autostart still selects current payload.
- Runtime ledger showed armed=1, failures=0, healthy observations progressing,
  and no action slot created. No automatic reset was falsely triggered while
  the link was healthy. The new release occupied 56 KiB, boot auto state 20 KiB.
  Memory snapshot: MemTotal 43460 KiB, MemFree 2120 KiB, MemAvailable 14508 KiB,
  Cached 13600 KiB. Per-process RSS (shared pages included) was 844/880/824/604 KiB
  for supervisor/worker/LED/httpd; these are not isolated private-memory totals
  or sustained peak measurements during automatic recovery.

Actual system sleep was not tested. No sleep acceptance is claimed, no production
automatic USB cycle has been hardware-exercised yet, and the previous one-cycle
awake-Mac trial remains the action-capability evidence. Still pending: real automatic
trigger and recovery after system sleep, abnormal executor cleanup on hardware,
repeated incidents/boot budget, iPad/iPhone behavior, long-duration operation and
sustained power/thermal impact.

For acceptance, let the Mac enter actual system sleep (not only screen lock), wake it
without unplugging the module, and allow grace plus distinct probe rounds and
confirmation. Then inspect status, logs, boot auto state and persistent recovery
events. A successful native host resume with zero resets is also valid; it does not
exercise the automatic-reset branch. Any manual unplug is recorded as manual
recovery, not a passed automatic recovery.
