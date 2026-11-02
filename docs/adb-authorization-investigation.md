# ADB authorization investigation

Date: 2026-11-02. Scope: read-only investigation after an ADB-bit transaction failed
its exact-readback check. The investigation issued no unlock write.

## Device observations

The specified transaction sent one composition write targeting only the ADB bit. The
transport received a terminal success response, but the following state query did not
equal the target. The helper stopped before issuing any restart. A subsequent
independent `make probe-module` query still read the original composition and found
no ADB descriptor. There was no retry or automatic rollback.

Further read-only `AT+QGMR` and `AT+QADBKEY?` queries established:

| Item | Result |
| --- | --- |
| Full firmware | `QDC507GLEFM21_01.001.02.004` |
| QADBKEY query | Accepted |
| Challenge format | Eight decimal digits |
| Raw challenge | Used transiently for classification, not logged or saved |
| Configuration before/after queries | Equal |
| USB network mode | 1, ECM |
| ADB configuration bit | 0 |

`make probe-module` now includes these two read-only capability queries. It exports
only revision and challenge format/length, never the challenge or raw AT replies.
Unsupported-command responses are reported distinctly from transport errors.
Transport failure still stops inspection without an automatic retry.

The unchanged readback is not proof of every internal persistent state or a pending
state across reboot. No restart has been performed to test that question.

## Evidence comparison

1. The QDC507 upstream research describes authorization through an eight-digit
   QADBKEY challenge before changing the ADB bit. It explicitly treats the
   authorization as a persistent security state, distinct from USB composition.
   It reports success on another module but does not establish the complete
   revision of this unit or compatibility with every firmware build.
2. The inspected DJOneHub enhanced setup source explicitly notes that some
   firmware returns OK while retaining its ADB bit. This matches the observed
   symptom but does not establish its root cause on this unit.
3. A Quectel community thread names the exact full revision observed here.
   Its author reports the public 15-character MD5-derived method returned ERROR,
   and later reports a supplied authorization also returned ERROR. The thread
   does not provide a confirmed working resolution. The auto-reply bot is not
   treated as an engineering determination.
4. Quectel's EC25-AF security note describes other secure-debug mechanisms on
   that model. It does not list this QDC507 revision as a supported target, so
   its password/security-setting commands are not applied to this device.

## Initial conclusion and subsequent candidate

An authorization prerequisite is a plausible explanation, not a confirmed lock
diagnosis. An eight-digit challenge proves the query surface, not compatibility with
an old generator or permission to mutate the security state. No validated
authorization method for this exact unit has yet been established.

Before an unlock transaction is proposed, obtain a supplier-confirmed method for this
revision or independently verifiable matching implementation evidence. Then document
the precise command, secret handling, attempt limit, success evidence, persistence
and whether relocking is supported. Do not promise that restoring the original
composition reverses an authorization write.

Keep device identifiers and challenge values local. Do not log secrets, guess
credentials, try multiple algorithms or weaken the exact-readback check. The original
enablement path cannot issue QADBKEY writes.

Subsequent source inspection of DJOneHubNative at `7194ae8` confirmed an actual
legacy compatibility implementation, three published vectors, and a controlled
pre-reboot pending-bit rule. Cellforge reproduced those vectors and independently
cross-checked the full MD5-crypt result using LibreSSL, without device access. This
establishes an auditable candidate, not support for this exact unit. The subsequent
bounded transaction used the revised ADB-only pending-bit rule, one restart and
read-only internal inspection. See [the specified
transaction](legacy-adb-transaction.md). Earlier exact-readback failure alone must
not be treated as proof of an authorization lock.

The bounded candidate has now succeeded on this unit: authorization accepted, one
ADB-only write and restart, exact post-restart configuration and direct ADB UID 0.
See [the runtime baseline](module-runtime-baseline.md). That result supersedes the
initial access blocker, while the limits on general compatibility and unverified
relocking still apply.

## Sources

- [QDC507 upstream research, authorization and persistence](https://github.com/cr-zhichen/DJOneHubNative/blob/main/docs/MODULE_RESEARCH.md).
- [Inspected enhanced setup source at fixed revision](https://github.com/rogerbush007-a11y/DJOneHub-mac-enhanced/blob/5b15eaec0e97dd9fa7b2abe54d0d1289c1e93054/cmd/djonehub-macos/module_setup.go).
- [Quectel community report for the exact full revision](https://forumschinese.quectel.com/t/topic/15274).
- [Quectel EC25-AF security note, another model](https://quectel.com/content/uploads/2024/02/Quectel_EC25-AF_Security_Feature_Application_Note_V1.0.pdf).
