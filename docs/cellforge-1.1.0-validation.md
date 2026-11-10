# Cellforge 1.1.0 verification

Release date: 2026-11-10. Scope: Dashboard interface optimization and source
staging durability. The module retains its factory-firmware installation model.

## Release scope

The Dashboard uses a responsive layout, stable speed alignment, revised session
usage cards, compact telemetry and self-contained visual assets. It continues to
read status JSON from the existing USB-LAN HTTP service. No remote command or
configuration API is introduced.

The policy's version field is updated to 1.1.0. Maintenance, accounting and LED
decisions retain the 1.0.0 implementation. Wi-Fi/module traffic selection is
deferred and is not included.

Module payload: `630ff04b2567dd24`. Installation and upgrade use
[the tagged source guide](install.md).

## Software verification

The GitHub Release notes identify the final source SHA, environment, outcomes and
exact clean-checkout verification sequence:

1. `make check-module-syntax check-module-assets`
2. `make check`
3. `make check-workspace`
4. `make check-diff`

Staging fixtures cover successful flush ordering, refusal to activate after a file
hash mismatch or initial flush failure, and reporting a final flush failure without
retry. These are simulated command/transport boundaries, not hardware power-loss
tests. Dashboard rendering checks use simulated frames/events;
multi-device visual and touch acceptance is not established by those checks.

## Module observations and limits

Dashboard updates on the tested module were checked for exact HTTP content hashes,
advancing telemetry, configured USB and unchanged backend processes.

The final 1.1.0 payload was installed on the tested module using the source
stop/stage/start sequence. All eight persistent file hashes matched the source;
the service reported version 1.1.0, active state and blue solid, with advancing
telemetry and USB CONFIGURED. The source staging path completed synchronization
before and after activation. The service restart began a new in-memory accounting
session; no USB interface toggle or module reboot was requested.

Served Dashboard SHA-256:

`b7fb989754332e8d032cbdb9bb10b906663bae19265e714a8546c9bf03451145`

These runtime observations are also recorded in the GitHub Release notes. The
sealed payload was not subjected to a new physical unplug or power-loss test.

An earlier UI revision survived one field-reported unplug/reconnect. An empty
deployment directory had previously prevented startup after reboot; file and link
synchronization is now explicit in source staging. The exact trigger of that file
loss was not proven, and no power-loss fault-injection campaign is claimed.

The [1.0.0 hardware evidence](cellforge-1.0.0-validation.md) remains historical.
Mac actual system-sleep recovery, repeated/multiple-device acceptance, continuous
screen-off internet, quantified power/thermal impact and full uninstall/debug
reversal remain unestablished. Fresh installation on another module has not been
acceptance-tested. A successful Dashboard request does not prove host internet
routing or recovery success.

Delivery is a version tag, GitHub Release and source installation. No separate
installer or replacement firmware image is produced. License selection remains
deferred.
