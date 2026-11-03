# USB resume recovery: evidence preparation and read-only investigation

Date: 2026-11-02. Base: preview commit `449d09c`. Status: automatic sleep recovery is
not fixed; the deployed service preview is unchanged. Preparation/read-only findings
below preceded a bounded single android0/enable trial, which subsequently passed. Its
[execution result](usb-enable-trial-plan.md#execution-result) records the bounded
evidence. No automatic reset path or replacement service is enabled.

## Observed failure and evidence limits

- After a reported lock/absence interval, the module still reported CONFIGURED,
  usb_sleep=0 and working cellular probes; Mac en7 was inactive without IPv4.
  Lock alone versus actual system sleep was not established.
- The original worker uses only complete ARP entries as host candidates. A
  failed/incomplete entry can leave no candidates, although the worker briefly
  marks itself probing. Existing blue flashes do not prove a packet was sent.
- The first trial launcher left no executor evidence. A launch handshake was
  added; a subsequent trial then made both ADB and the network device disappear.
- That trial used UDC soft_connect disconnect/connect. The independent process
  used the same interface; neither independent execution nor a returned write
  guarantees control-plane recovery. Host USB enumeration and network-interface
  checks both failed to find the module afterwards.
- Manual removal/reinsertion restored USB, DHCP, the original service and
  communication. Power cycling also cleared all temporary trial evidence, so
  the exact failing internal stage is unknown. Do not label the kernel, driver,
  connect call or host sleep policy as the established cause.
- Browser access also depends on the host network and application permissions: ordinary
  route/curl checks could work while browser access failed until service order changed. Page availability alone is not a USB-reset trigger.

## Disabled trial tool and bounded evidence

`module/usb-recover.sh` now contains only record functions. The former launch,
delayed, run and guard commands refuse before any filesystem or device mutation.
There are no USB node writes or recovery processes. `scripts/module_runtime.py` does
not include this tool in its package, so staging the ordinary service does not
silently activate it. It has not been copied to the module in this phase.

Trial records target the fixed private directory `/data/cellforge/recovery-trial`,
mode 0700, files mode 0600. A journal contains at most 32 rows and 8192 bytes. Its
update file has the same bound. A maximum of two bounded files can exist after an
interrupted update; no unbounded history, automatic rotation, overwrite or
old-evidence deletion is provided.

Each row contains sequence, local trial ticket, UTC time, monotonic uptime, phase and
result. Neither arbitrary messages nor command output/identifiers are accepted. The
fixed vocabulary separates executor readiness, disconnect/connect requests, call
returns, observed enumeration, observed address and observed communication. These
observations must be supplied by the future executor/host observer; the journal
itself does not detect or prove network behavior.

Atomic directory locking allows one writer. A held/orphan lock, prior evidence,
interrupted update, invalid record or capacity cutoff refuses further updates; there
is no automatic stale-lock takeover. Each successful update syncs the new file before
rename and syncs after rename. This is a requested flush using the module's existing
utility, not proof of power-loss durability on this hardware. It runs only at trial
boundaries, never each normal collection tick. Future actions must not begin if their
pre-action evidence cannot be committed.

| Evidence boundary | Meaning |
| --- | --- |
| missing | No trial file; no inference about prior volatile trials |
| limited | Requests/call returns only; recovery remains unconfirmed |
| available | Enumeration, address and communication observations supplied in order |
| unknown/timeout | No success inferred; a restoration attempt may still be recorded |
| not applicable | USB actions disabled in this preparation phase |
| cutoff/invalid/locked | Stop adding evidence and block any future dependent action |

Only the final communication observation with result ok reports
`communication_restored`. In particular connect_returned=ok never does. This is a
single-trial diagnostic record, not the automatic-recovery budget/state machine,
accounting adapter or heartbeat integration.

## Read-only factory findings

The fixed init file `/etc/init.d/usb` calls `/usr/bin/ql_usbcfg n`. It also mounts
filesystems and configures ADB/composition-related state. Its stop branch merely
prints a message. The whole start/restart script is not a recovery command.

Observed file SHA-256:

- `/usr/bin/ql_usbcfg`:
  `2350af7e14220758726a87a9b0c51b6e20136c27ae10d7c784973f64bd276b04`
- `/usr/lib/libql_usb.so.1` (resolved file):
  `78448a4de2dfbefbf3023e6a44c992d687340a342c6ba31b5d6ccce2aa578ccd`

The existing offline library copy matches the device hash. Its dynamic symbols
include config load/read/write, rawdata write and recovery-load paths; strings
include pkill adbd, ADB startup, functions, IDs and remote_wakeup. These are evidence
that full initialization can have broad effects, not proof that every branch performs
every operation.

Offline ARM disassembly of quectel_usb_enable at 0x2fa0 (size 0x150) is narrower: it
saves the first two arguments, formats a node with the first as USB index, and passes
the second as a decimal value to quectel_file_write_int. Resolved PC-relative string
addresses are 0x3578 (enable) and 0x3350 (/sys/class/android_usb/android%d/%s). The
imported write function is called at 0x300c. Thus the observed factory primitive
targets android_usb/androidN/enable, not UDC soft_connect. The wrapper also logs and
does not provide a trustworthy connection-restored return value. No native function
has been called.

This makes android0/enable a candidate for further analysis, not a validated
replacement. Disassembly does not establish vendor-kernel callback semantics,
coordination with qti/adbd, or whether the host will recover. The installed functions
remain diag,serial,ecm,ffs and enable=1. No existing USB config, factory process,
sysfs node or startup hook was changed during this phase.

A subsequent read-only follow-up checked the public Android 3.18 function lifecycle
and current FunctionFS/process prerequisites. The bounded proposed experiment, source
limitations and observation deadlines are specified in the [single enable-trial
plan](usb-enable-trial-plan.md). That plan now also records the subsequent successful
one-cycle capability trial.

## Gate before another USB trial

1. Establish the candidate's enable/disable semantics and factory ownership;
   do not invoke ql_usbcfg or whole initialization as a shortcut.
2. Specify the exact operation, preconditions, original-state restoration,
   independently executing best-effort safeguard and deadlines. A process using
   the same controller remains in the same failure domain.
3. Install/verify evidence preparation and record baseline before any action.
4. Require a concrete operation, preflight and restoration plan before disconnecting; this preparation phase performed no new disconnect.
5. Judge command completion, USB enumeration, DHCP and USB-bound communication
   independently; record failure/unknown at the stage actually observed.
6. Only after that succeeds, implement bounded automatic decisions, retries,
   cooldown, accounting continuity, watchdog coordination and separate Mac and
   iPad/iPhone sleep/resume acceptance. No such automatic change is deployed.

## Verification

`make check-recovery` checks target shell syntax and isolated journal fixtures.
Fixtures use only temporary host files, stub sync, and do not access USB or write
/data. They cover call-vs-communication success, uncertain outcomes, phase ordering,
cutoff, interrupted/corrupt records, prior evidence, writer ownership and refusal of
all former mutation commands. They are not a module power-loss, BusyBox-runtime or
USB-recovery acceptance test.

Final preparation checkpoint: 7 targeted fixtures passed, then all 69 repository
tests passed once, followed by workspace checks (19 Python sources), shell syntax and
diff checks. The dashboard/service payload was unchanged. Browser, USB-reset and
autostart behavior were not tested in this preparation stage. Actual module log
storage and persistence have not been exercised.
