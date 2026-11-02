# Cellforge

Version target: **1.0.0**, deployed preview on one module, not a published release.
See the [connection maintenance design](docs/connection-maintenance.md) for the
specified service, dashboard, LED contract, implementation and release gates.

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

Connect the module and open **http://192.168.225.1:8080/**. The service starts
automatically after boot. See the [service guide](docs/module-service.md) for
behavior, installed paths, stop/start, handback and evidence limits.

Host policy tests pass; see the [1.0.0 verification
record](docs/cellforge-1.0.0-validation.md). An initial ADB-bit attempt failed exact
readback without a restart. The subsequent [legacy authorization
transaction](docs/legacy-adb-transaction.md) succeeded on this unit: exact
post-restart USB composition and real ADB root access were verified. See the [module
runtime baseline](docs/module-runtime-baseline.md). Deployment, independent crash
cleanup and restart/autostart were verified on this unit. Locked-mobile connectivity,
visual yellow output and sustained resource impact remain pending; they are not
implied by a healthy dashboard or blue LED.

    make check-policy
    make check-access
    make check-probe
    make check-authorization
    make check-adb
    make check-module
    make check-module-assets
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

These observations apply to the tested device only. iPad compatibility, lock and wake
behavior, power consumption, and long-term stability remain unverified. See [the
hardware baseline](docs/hardware-baseline.md) for the evidence and limits.

Subsequent field reports described working iPad/iPhone access and loss of networking
after a locked interval while the module LED remained green. This is field-reported
evidence; model/OS details and controlled lock-screen validation are pending.

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

Target devices for upcoming validation:

- iPad mini (A17 Pro), commonly called iPad mini 7.
- iPad Pro 12.9-inch (2020).

The iPadOS versions have not yet been recorded.

## Direction

1. Preserve the working factory firmware and CDC ECM connection.
2. Validate the deployed preview on the intended iPads and iPhones, with recorded
   OS versions and separate screen-off/unlock-recovery criteria.
3. Measure resource use, accounting continuity and factory handback during
   repeated connection and lock cycles.
4. Tune connection maintenance from those observations before release.

The first version excludes SMS, calls, eSIM management and a resident Mac management
application. There is no decision to fork the full DJOneHub platform.

## References

- [DJOneHub](https://github.com/ZenGeekLabs/DJOneHub)
- [DJOneHub mac enhanced](https://github.com/rogerbush007-a11y/DJOneHub-mac-enhanced)
- [Apple: USB-C connections on iPad](https://support.apple.com/en-ie/108894)

The referenced projects are research inputs. Their source and runtime binaries are
not included in this repository.
