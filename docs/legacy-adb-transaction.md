# Legacy ADB authorization transaction

Date: 2026-11-02. The legacy compatibility method was inspected in DJOneHubNative at
`7194ae8cd71da34e0ab3727874dafb82ffd2537b`. This is a bounded compatibility attempt,
not a guarantee of firmware support.

## Scope

Use only on the single QDC507, USB 2ca3:4006, full revision
`QDC507GLEFM21_01.001.02.004`, network mode 1, ECM present and composition
`0x2CA3,0x4006,1,1,1,1,1,0,0`.

The command is `python3 -B scripts/module_access.py authorize-adb --yes`. It performs
at most one authorization write, one ADB-bit composition write and one restart
request. No secret is provided through argv, environment variables, files, logs or
status. Values exist in ordinary Python memory, for which secure erasure is not
guaranteed. Device identity challenges are not sent externally.

1. Recheck the exact baseline and full revision before confirmation and again
   before writing. Refuse state drift, another revision or another composition.
2. Query one current eight-digit challenge after confirmation. Derive the
   legacy response locally using Unix MD5-crypt and the compatibility constant;
   use the first 15 encoded characters. Unknown or ambiguous formats stop.
3. Submit one QADBKEY authorization through the existing AT interface.
   Rejection or an uncertain result stops without a retry, composition write
   or restart. Its acceptance is not proof of actual ADB root access.
4. If accepted, confirm the observed module configuration is still original;
   write only the ADB bit to produce
   `0x2CA3,0x4006,1,1,1,1,1,1,0`.
5. Before restarting, permit only the exact original or exact target state.
   Model, firmware, mode, identity and all unrelated function bits must remain
   unchanged. Request one restart only after that check succeeds.
6. After reconnecting, independently require exact target composition, mode 1,
   full revision and ECM. Confirm a unique `ff/42/01` ADB interface and actual
   root before inventory. Failure stops; there is no automatic reauthorization,
   retry of a mutation, reset, firmware change or rollback.

This revised pending-bit rule applies only to `authorize-adb`. The original
`enable-adb` and `restore-usb` commands retain strict immediate target readback. No
UAC, IMS, VoLTE, APN, SIM or network routing changes are included.

## Security-state boundary

QADBKEY authorization may persist independently of the USB ADB function bit.
Restoring the original composition can close the interface but does not prove
authorization has been revoked. No supported relock procedure has been established.
An ambiguous authorization response may still mean it took effect.

The exact firmware has a public report of failed legacy authorization; the current
eight-digit format does not override that uncertainty. A failure must not trigger
another algorithm, vendor-password attempt or wider debug bypass.

## Inspection without host ADB side effects

`python3 -B scripts/adb_inspect.py` uses libusb and a minimal ADB wire protocol. It
does not start `adb`, create a host key, push a file or expose a TCP listener. It
checks exact post-restart configuration/full revision and exclusively claims the
uniquely identified ADB interface. A device AUTH request stops inspection. An overall
25-second handshake/inventory deadline and output size limits apply.

The only exposed shell requests are `id -u` and a fixed read-only inventory:
kernel/architecture, command availability, memory, mount mode/free space, init entry,
USB/controller/power nodes, interface state/counters/IPs, bound port addresses, LED
nodes/triggers and relevant process names (not command lines). No full environments,
credentials, SIM identifiers, partition dumps, writes, service startup or writable
mounts are requested. Missing optional entries do not prove absence on other
firmware. Shell execution itself is transient runtime activity; this is not a
forensic zero-footprint guarantee.

## Validation

The algorithm matches three published vectors and was independently compared with
LibreSSL's full MD5-crypt output on those public inputs. Fake transports cover
cancellation, wrong revision/challenge, one-attempt failure behavior, secret
redaction, pending-bit invariants, ADB framing/fragmentation, packet bounds, AUTH
refusal, stream identity and the fixed read-only shell allowlist. These checks do not
establish compatibility or successful authorization on the physical module.
Real-device results must be recorded separately.

Run affected checks `make check-authorization` and `make check-adb`, then `make
check`, `make check-workspace` and `make check-diff` before device writes.

## References

- [Legacy compatibility implementation](https://github.com/cr-zhichen/DJOneHubNative/blob/7194ae8cd71da34e0ab3727874dafb82ffd2537b/backend/cmd/djonehub-macos/qadbkey.go).
- [Authorization and pending-bit validation](https://github.com/cr-zhichen/DJOneHubNative/blob/7194ae8cd71da34e0ab3727874dafb82ffd2537b/backend/cmd/djonehub-macos/call_mode.go).
- [Published test vectors](https://github.com/cr-zhichen/DJOneHubNative/blob/7194ae8cd71da34e0ab3727874dafb82ffd2537b/backend/cmd/djonehub-macos/call_mode_test.go).
- [Exact revision failure report](https://forumschinese.quectel.com/t/topic/15274).
