# Install Cellforge 1.1.0 from source

Cellforge installs a small service and dashboard inside the existing factory
firmware. It does not flash a firmware image or install a resident Mac app. There is
no separate installation package. Use the source at tag `v1.1.0` from the [GitHub
Release](https://github.com/Thrt333/cellforge/releases/tag/v1.1.0).

## Supported installation boundary

- Installation/control host: macOS, Python 3.9 or newer and an existing libusb
  1.0 library in a detected Homebrew location. The recorded host is macOS 15.6.1
  with Python 3.9.6; other host environments are not installation-tested.
- Module: one DJI first-generation QDC507, USB `2ca3:4006`, factory revision
  `QDC507GLEFM21_01.001.02.004`, CDC ECM mode 1 and root USB ADB access.
- Native telemetry and recovery are pinned to exact factory files. Another
  firmware is not supported just because the USB identifier matches.
- The USB composition must be the exact target recorded in the
  [ADB access record](legacy-adb-transaction.md). Stop if a check rejects it.
- Close competing module-management tools. Keep the module powered during writes.
  Installation and stop/start interrupt the service; do not stage during recovery.

The module runs independently after installation. iPad/iPhone use does not require a
Mac or an open dashboard, but direct installation from those devices is not provided.
Windows/Linux installers are not provided.

## Obtain the exact source

Download and extract the source ZIP from the Release, or use Git:

```sh
git clone --branch v1.1.0 --single-branch https://github.com/Thrt333/cellforge.git
cd cellforge
```

Run all following commands from that source directory. These scripts use direct
USB/libusb; they do not start a host ADB server or create host ADB keys. Node is
needed for contributor JavaScript checks, not module installation. No script
automatically installs dependencies.

## Check access before installation

Connect only the intended module to the Mac and inspect it:

```sh
python3 -B scripts/cellforge.py status
```

This command is read-only. If mode 1 or ADB/root is not already available, do not run
the service installation commands yet. ECM enablement and legacy ADB authorization
are separate device-changing procedures, documented in [ECM
configuration](ecm-tool.md) and the [exact-build authorization
transaction](legacy-adb-transaction.md). They can restart the module and
authorization may persist independently of the ADB bit. Do not blindly retry a failed
authorization or apply it to another firmware.

Once the exact target composition is present, verify root and runtime:

```sh
python3 -B scripts/adb_inspect.py
```

Stop on an error. Cross-check host USB enumeration and access permissions before
repeating a device operation.

## First installation

For a module that does not already have Cellforge installed:

```sh
python3 -B scripts/module_runtime.py stage
python3 -B scripts/module_runtime.py start
python3 -B scripts/module_runtime.py status
python3 -B scripts/module_runtime.py probe
```

Run each command separately and continue only after success. `stage` uploads eight
fixed files, verifies SHA-256 hashes, flushes the complete payload, selects it via
`/data/cellforge/current`. For the 1.1.0 source, the payload identifier is
`630ff04b2567dd24`. The release selection is also flushed before success is
reported. A different result requires investigation, not blind activation.

`start` launches the supervised service. `status` reports process/control state;
`probe` reads its current dashboard JSON. Neither alone proves the terminal's
internet access or lock-screen behavior. Open `http://192.168.225.1:8080/` and check
ordinary terminal internet access separately.

After confirming normal operation, enable boot startup once:

```sh
python3 -B scripts/module_runtime.py enable-autostart
```

This uploads the owned startup shim, temporarily remounts the verified factory root
writable, creates only Cellforge's startup entries and restores root read-only.
Existing entries cause refusal; do not delete unknown entries to force installation.
The full owned path list is in [the service guide](module-service.md).

If a Mac browser cannot reach the dashboard while command-line access works, check
that browser's macOS Local Network permission. Wi-Fi priority by itself does not
establish whether browser access is permitted.

## Upgrade an existing installation

Obtain the intended tagged source first. With the module attached, inspect status and
make sure no automatic recovery or pending USB restoration is running:

```sh
python3 -B scripts/module_runtime.py status
python3 -B scripts/module_runtime.py probe
```

Then run separately:

```sh
python3 -B scripts/module_runtime.py stop
python3 -B scripts/module_runtime.py stage
python3 -B scripts/module_runtime.py start
python3 -B scripts/module_runtime.py status
python3 -B scripts/module_runtime.py probe
```

On any error, stop and inspect logs/status. Staging refuses running service or
recovery ownership; it is not an automatic rollback mechanism. Prior payloads are
retained. A service restart resets in-memory session totals. Existing autostart
selects `current`; do not repeat `enable-autostart` on every upgrade. This sequence
documents existing tools, not a fresh-install/upgrade acceptance test on a second
module. Changes to the startup implementation require a separate review of the
existing owned shim rather than overwriting it blindly.

## Stop, disable startup and recovery boundaries

To hand back the service's LEDs and wake locks now:

```sh
python3 -B scripts/module_runtime.py stop
```

To also prevent startup on future boots, run separately:

```sh
python3 -B scripts/module_runtime.py disable-autostart
```

Stopping alone does not disable boot startup. Disabling startup verifies owned
hashes/symlinks before removing those entries and restores root read-only. It retains
`/data/cellforge` payloads and records; there is no blanket data-deletion
uninstaller. Data removal needs an exact, separately reviewed candidate list.

Neither operation revokes ADB authorization or restores USB composition. Manual
unplug/reconnect working is not proof of complete uninstall or debug reversal. Do not
use ECM disablement as an internet-flow switch: mode 0 selects QMI and can remove the
Mac Ethernet connection. Dashboard traffic selection remains deferred and is not
included in this release.

For failure investigation:

```sh
python3 -B scripts/module_runtime.py logs
```

Keep logs local and sanitize before sharing. Read the [release evidence and
limits](cellforge-1.1.0-validation.md): one iPad lock/unlock success is
field-reported; Mac actual system-sleep recovery and broad mobile compatibility are
not established. Current release checks and module observations are recorded in the
1.1.0 verification record and GitHub Release notes.

## Verify a source checkout

In a clean checkout of the intended source revision, with Python, Node.js,
make and a POSIX shell available, run these checks in order:

```sh
make check-module-syntax check-module-assets
make check
make check-workspace
make check-diff
```

These checks do not access the module. They validate software fixtures and
source syntax, not USB behavior, sleep recovery or mobile compatibility.
The Release notes identify the checked source revision and results.
