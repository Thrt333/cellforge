# Cellforge 1.0.0 implementation verification

Date: 2026-11-02. Version target: 1.0.0, not released. Branch:
`feature/cellforge-1.0.0`, based on `2abdb34`.

Later sleep/resume failure and disabled trial/evidence preparation are recorded in
[the recovery investigation](usb-recovery-investigation.md). Automatic USB resume
recovery is not fixed; the deployed preview remains unchanged. One bounded
android0/enable capability trial subsequently passed without manual unplug; see its
[result](usb-enable-trial-plan.md#execution-result). It does not establish automatic
sleep recovery or mobile acceptance.

2026-11-03: the automatic state machine/executor was implemented and deployed as
release `de31653675b5a757`, with 102 tests passing and healthy live normal operation.
See [automatic recovery](automatic-recovery.md) for precise evidence and limits. Real
system-sleep acceptance remains pending.

The later service deployment, startup repair and actual device outcomes are recorded
in [the module service guide](module-service.md). The host checks below describe the
earlier access/policy stage; they were not all repeated for the one-line startup
repair. Five target-policy fixtures and new asset/shell syntax checks passed for the
deployed service.

## Completed host checks

Host: macOS 15.6.1, Python 3.9.6, existing libusb. No dependencies installed.

Executed in sequence:

1. `make check-policy`: 17 policy/accounting tests passed.
2. `make check-access`: 6 fake-transport access transaction tests passed.
3. `make check-probe`: 5 authorization metadata/privacy/transport tests.
4. `make check-authorization`: 3 vector/parser and 5 authorization transaction tests passed.
5. `make check-adb`: 6 direct ADB framing/allowlist/size-bound tests passed.
6. `make check`: 57 tests, including the existing 15 ECM tests.
7. `make check-workspace`: fifteen Python sources compiled in memory, version
   and whitespace checks passed, original CLI help passed.
8. `make check-diff`: whitespace validation.

These tests simulate observations, clock progression and counter samples. They do not
execute real USB wakeup, LED, power or network recovery. The direct ADB inspection
adapter was subsequently validated on the module. At that earlier access/policy
checkpoint no connection-maintenance service was deployed; the later deployment is
recorded below.

The separate access helper defaults to read-only status. Its fake-transport tests
cover both exact composition directions, cancellation/no-op, state drift, baseline
refusal, command restrictions, uncertain writes and readback mismatch. The existing
USB transport was extracted behind a private exchange method; the original ECM
command allowlist and CLI behavior remain intact. Actual ADB enablement was
subsequently attempted once as recorded below; rollback remains unexercised.

## Real-device read-only observation

`make probe-module` ran with host USB access after restricted enumeration did not
match the host inventory. It used the existing AT interface for model, firmware, mode
and composition queries, and read configuration descriptors.

Observed QDC507GLEFM21, USB 2ca3:4006, mode 1, composition
`0x2CA3,0x4006,1,1,1,1,1,0,0`, ECM present, ADB absent, and `0xa0` attributes
advertising remote wakeup. Mobile host authorization was not observed.

The initial preflight issued no configuration write. A subsequent single ADB-bit
write was attempted: its response terminated successfully but exact readback remained
original, so the helper halted. No restart, retry, unlock write, installed file,
startup hook, LED or firmware change was issued. The readback is an observation, not
proof about all internal pending state.

Read-only investigation established full revision `QDC507GLEFM21_01.001.02.004` and
an eight-digit QADBKEY challenge format, without logging or saving the challenge.
Before/after configuration queries matched. See [the authorization
investigation](adb-authorization-investigation.md) for the evidence limits and
remaining prerequisite.

## Bounded legacy transaction and internal inspection

The [legacy transaction](legacy-adb-transaction.md) submitted one locally derived
authorization, one ADB-bit composition write and one restart. Post-restart inspection
exactly matched the target composition `0x2CA3,0x4006,1,1,1,1,1,1,0`, retained mode 1
and ECM, and found ADB interface 6. Direct USB ADB confirmed UID 0 and completed
fixed read-only inventories. No second authorization was needed after restart. The
legacy algorithm is now verified on this particular unit; general compatibility is
not.

The kernel is Linux 3.18.44/armv7l. Runtime, memory/storage, networking, power nodes
and LED evidence limits are recorded in the sanitized [runtime
baseline](module-runtime-baseline.md). No challenge, derived password, SIM
identifier, full process command line or raw binary is stored in the repo. At that
access-only checkpoint no file, module service, LED change, power-control write or
startup hook was installed. Authorization persistence and the ADB function bit are
distinct.

## Deployed service follow-up

The module service and dashboard are installed and running, with owned SysV
startup entries and the root filesystem restored read-only. The target uses
verified shell/awk/BusyBox rather than requiring a cross compiler. Exact-build
native telemetry, factory RGB pause/handback, local wake-lock ownership, bounded
host probes and static USB-LAN HTTP are implemented. One supervisor crash-cleanup
test and one post-install restart/autostart test passed. Direct Mac HTTP returned
200. See [the service record](module-service.md) for the exact bounds and paths.

## Software validation

The preview source passed these software checks:

- `make check-module-syntax check-module-assets`: both shell scripts and dashboard
  JavaScript syntax passed.
- `make check`: all 62 tests passed, including the five target-policy fixtures.
- `make check-workspace`: 18 Python sources compiled in memory; version,
  whitespace and CLI checks passed.
- `make check-diff` and the staged diff whitespace check passed.

No device write, restart or repeat hardware test was performed for this commit. The
service guide includes the subsequent live storage/RAM snapshot. This is a
source/deployment checkpoint; the acceptance items below remain open.

## Pending device acceptance

- Verify actual phone-side USB sleep/resume and host response to maintenance traffic.
- Visually confirm yellow and blink appearance; electrical mapping and crash handback
  have code/device evidence, not a completed visual mobile acceptance.
- Fix numeric mobile/resource acceptance criteria and supported device/OS matrix.
- Complete real-device lock/unlock, screen-off traffic, repeated recovery,
  accounting, yellow LED, power/thermal, startup-removal and long-duration validation.

the field report of working mobile internet is retained separately from controlled
acceptance. This implementation is being committed as a deployed preview; version
1.0.0 is the target, not a completed release. No release tag, push or publication is
included. iPad lock-screen acceptance was pending at this stage.
