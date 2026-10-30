# QDC507 ECM tool

A small macOS tool for the DJI first-generation 4G dongle (Baiwang QDC507).
It queries the USB network mode or switches between mode 0 (QMI) and mode 1
(CDC ECM). It identifies USB 2ca3:4006, checks the QDC507 model and uses its
existing AT interface 2. Multiple matching devices are refused.

Firmware and USB composition are displayed without requiring an exact version
or factory composition. This does not establish compatibility with every
firmware; the tested device is recorded in [the baseline](hardware-baseline.md).

## Requirements

Python 3.9 or newer, macOS and an existing libusb 1.0 library.
Standard Apple Silicon and Intel Homebrew library paths are detected. For a
different location, place --libusb PATH before the subcommand. The tool installs
no dependencies. Close other module-management tools before running it.

USB visibility and access can be restricted in an agent sandbox. An access
failure there does not prove the device is absent on the host.

## Commands

Run from the repository root. Read-only inspection is the default:

    python3 scripts/cellforge.py
    python3 scripts/cellforge.py status

Enable USB ECM:

    python3 scripts/cellforge.py enable-ecm

Switch back to mode 0:

    python3 scripts/cellforge.py disable-ecm

Mode 0 selects QMI; it does not turn off the cellular radio. The Mac may lose
the Ethernet connection when switching back.

Changes require typing YES, or an explicit --yes flag for noninteractive use.
If already in the requested mode, there is no prompt, configuration write or
restart.

For a change, the tool checks the state again after confirmation, writes only
usbnet once, reads it back, requests one restart and exits. It does not wait for
reconnection or test networking. A successful result confirms readback and a
restart request, not persistence after reboot or internet access.

## Boundaries

| State | Behavior |
| --- | --- |
| No accessible module or multiple matching modules | Stop without configuration writes |
| Wrong model or missing expected AT interface | Refuse operation |
| Mode 0 or 1 | Allow confirmed switching; target mode is a no-op |
| Mode 2 or 3 | Report in status; refuse switching |
| State changes during confirmation | Stop before writing |
| Uncertain write response or mismatched readback | Stop; no retry or restart |
| Restart requested | Exit; no reconnect polling or automatic repair |

The script reads no IMEI, creates no backup and provides no backup-based restore.
It does not flash firmware, change USB composition/APN/Mac routes, enable ADB,
or install a service. Configuration writes and restart requests are never
automatically retried or reversed.

Keep the module connected during writing and readback. Disconnection following
a restart request is expected. If an operation fails, inspect status before
deciding what to do; an uncertain write may already have taken effect.

## Validation

    make check

Tests use fake AT transport and CLI calls: no hardware, network or firmware
write. They cover both switch directions, no-op, cancellation, basic device
checks, different firmware/composition values, state changes during confirmation,
uncertain writes and readback mismatch.

See the [verification record](ecm-tool-validation.md) for the limits of the
actual device evidence.

## References

- [libusb device handling](https://libusb.sourceforge.io/api-1.0/group__libusb__dev.html)
- [libusb synchronous I/O](https://libusb.sourceforge.io/api-1.0/group__libusb__syncio.html)
