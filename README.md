# Cellforge

Version: **1.1.0**. Delivery: version tag + GitHub Release + source installation. See
the [installation guide](docs/install.md), [changelog](CHANGELOG.md) and [source
verification](docs/install.md#verify-a-source-checkout). No separate installer
package or custom firmware image is provided.

Minimal tooling for cellular modules, starting with the DJI first-generation 4G
dongle (Baiwang QDC507).

The initial goal is to provide USB cellular internet to a Wi-Fi-only iPad, then add
module-level data usage and upload/download speed monitoring. This is an independent
project and is not affiliated with DJI, Quectel, or any carrier.

## Current status

The tested module now runs a supervised connection/LED/accounting service and USB-LAN
dashboard, installed within the factory firmware. No custom firmware image is
flashed. The host tools provide narrow ECM configuration, read-only inspection,
bounded ADB authorization, versioned staging and startup control. The host Python
policy remains a reference; the device runs shell/awk.

The service includes bounded automatic USB recovery using the successfully trialed
factory Android USB enable path. Its trigger/budget/accounting rules and live
deployment evidence are in [automatic recovery](docs/automatic-recovery.md). Field
reports describe one successful iPad lock/unlock recovery, stable long-term use,
normal LEDs and normal manual unplug/reconnect. Mac actual system-sleep recovery and
repeated/multiple-device acceptance are deferred beyond the current evidence. An iPad
recovery success does not establish continuous screen-off internet or prove that the
automatic USB-reset branch was used.

Connect the module and open **http://192.168.225.1:8080/**. The service starts
automatically after boot. See the [service guide](docs/module-service.md) for
behavior, installed paths, stop/start, handback and evidence limits.

The Dashboard now provides a refreshed responsive layout, clearer connection status,
stable speed alignment and revised visual styling. See the [1.1.0 verification
record](docs/cellforge-1.1.0-validation.md) for current scope and checks. An initial
ADB-bit attempt failed exact readback without a restart. The subsequent [legacy authorization
transaction](docs/legacy-adb-transaction.md) succeeded on this unit: exact
post-restart USB composition and real ADB root access were verified. See the [module
runtime baseline](docs/module-runtime-baseline.md). Deployment, independent crash
cleanup and restart/autostart were verified on this unit. Field-reported stable
operation is not a quantified power/thermal benchmark. Hardware fault-injection,
complete uninstall and universal phone compatibility are not claimed. See the
validation record for the current evidence boundary.

## Source installation

Follow [the installation guide](docs/install.md) from the `v1.1.0` source.
Installation uses a Mac as the USB control host, with Python, existing libusb, the
exact supported firmware, ECM and root ADB access. It does not install a resident Mac
application. Once installed, the module works independently. Fresh installation on
another user's module has not been acceptance-tested.

## Software checks

During development, run the affected target. The verification sequence is in [source
verification](docs/install.md#verify-a-source-checkout):

    make check-module-syntax check-module-assets
    make check
    make check-workspace
    make check-diff

Explicit read-only hardware inspection: `make probe-module`.

On one QDC507 running `QDC507GLEFM21`, we have verified:

- Changing the existing USB network setting from mode 0 to mode 1 (CDC ECM)
  exposes a USB Ethernet adapter without replacing the factory firmware.
- macOS acquires an IPv4 address, gateway and DNS through DHCP.
- HTTPS access explicitly bound to that adapter succeeds with Wi-Fi disabled.
- The module answers native sent/received-byte counter queries.

These instrumented observations apply to the tested module only. The later
field-reported mobile results are recorded separately from controlled tests. See [the
hardware baseline](docs/hardware-baseline.md) for the evidence and limits.

Earlier field reports described working iPad/iPhone access but loss of networking
after locking while the LED stayed green. The bounded recovery implementation and
later single iPad success followed that report; model/OS details and broad
lock-screen acceptance have not been recorded.

## ECM configuration tool

Read the [usage guide](docs/ecm-tool.md) before changing a device.

    python3 scripts/cellforge.py status
    python3 scripts/cellforge.py enable-ecm
    python3 scripts/cellforge.py disable-ecm

The default is read-only. Changes require explicit confirmation, one mode write,
readback and one restart request. Already in the target mode is a no-op. The tool
does not wait for reconnection or verify networking. disable-ecm selects mode 0
(QMI); it does not turn off cellular service. Run host checks with `make check`.

## Intended use

The iPad connects to the dongle over USB; the dongle connects to the carrier over
LTE. The iPad sees an Ethernet connection rather than gaining native iPadOS cellular
hardware or settings.

Previously identified candidate devices for further validation:

- iPad mini (A17 Pro), commonly called iPad mini 7.
- iPad Pro 12.9-inch (2020).

The iPadOS versions have not yet been recorded. The single reported lock/unlock
success has not been tied to either candidate model, so neither is listed as a fully
tested model/OS combination.

## Direction

1. Preserve the working factory firmware and CDC ECM connection.
2. Extend validation on the intended iPads and iPhones, with recorded
   OS versions and separate screen-off/unlock-recovery criteria.
3. Measure resource use, accounting continuity and factory handback during
   repeated connection and lock cycles.
4. Revisit Mac actual system-sleep recovery and remaining hardware evidence in
   later work; revisit dashboard traffic selection separately.

The first version excludes SMS, calls, eSIM management and a resident Mac management
application. There is no decision to fork the full DJOneHub platform.

## Source permissions

License selection is deferred. This repository publishes source without granting an
open-source license; publication and a GitHub Release are not a license grant.

## References

- [DJOneHub](https://github.com/ZenGeekLabs/DJOneHub)
- [DJOneHub mac enhanced](https://github.com/rogerbush007-a11y/DJOneHub-mac-enhanced)
- [Apple: USB-C connections on iPad](https://support.apple.com/en-ie/108894)

The referenced projects are research inputs. Their source and runtime binaries are
not included in this repository.
