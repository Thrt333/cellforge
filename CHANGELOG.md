# Changelog

## 1.1.0 - 2026-11-10

### Dashboard interface optimization

- Refresh the responsive Dashboard layout, connection indication, typography and
  visual styling.
- Keep upload/download speed alignment stable as values change, refine session
  usage cards and compact device information.
- Refine globe rendering, animation depth and color transitions without external
  runtime assets or libraries.
- Synchronize module and Dashboard version reporting at 1.1.0.

### Deployment

- Flush staged payload files before activation and flush the release selection
  before reporting success. Synchronization failures stop staging without retry.
- Retain the existing source installation and owned startup model.

### Evidence and limits

- Module payload: `630ff04b2567dd24`.
- Exact source SHA, clean-checkout verification results and module observations are
  recorded in the GitHub Release notes.
- Network maintenance, accounting and LED behavior retain the 1.0.0 design.
  Existing hardware acceptance limits still apply; no broader compatibility or
  lock-screen acceptance is claimed.
- Wi-Fi/module traffic selection remains deferred and is not included.
- Tag + GitHub Release + source installation; no separate installer or firmware
  package. License selection remains deferred.

## 1.0.0 - 2026-11-06

### Features

- Exact-build QDC507 service within factory firmware, supervised shell/awk
  workers and owned boot startup; no replacement firmware image.
- USB-LAN dashboard at `http://192.168.225.1:8080/` with session cellular traffic,
  rates, IPs, signal, network generation and recovery/accounting state.
- Blue connection/recovery indications, green 4G fallback, yellow 2G/3G fallback
  and unchanged red fault meanings, with factory LED/wake-lock handback.
- Bounded automatic USB recovery using the factory Android USB enable path,
  one action per incident, at most three per boot, cooldown and fresh evidence
  confirmation. Restoration takes priority over event logging.
- macOS source tools for ECM configuration, exact-build ADB access, hash-verified
  staging, service control and owned startup management.
- Source installation, upgrade and stop guide.

### Evidence and limits

- Module payload: `de31653675b5a757`; the release documentation does not change
  the module's deployed runtime code.
- Prior software checkpoint: 102 tests and shell/JavaScript/workspace checks
  passed. Final release SHA and clean-checkout results are recorded in the
  GitHub Release notes, not inferred from the prior checkpoint.
- Field reports describe one successful iPad lock/unlock recovery, stable long-term use,
  normal LEDs and normal manual unplug/reconnect. Device/OS/duration and recovery
  event correlation for that iPad cycle are not recorded.
- Mac actual system sleep, repeated/multiple-device acceptance and hardware
  recovery fault injection are deferred. No claim of uninterrupted screen-off
  internet, quantified power/thermal acceptance or full uninstall validation.
- Traffic includes module probes, is not carrier billing data, and in-memory
  session totals reset on service restart or module power loss.
- Tag + GitHub Release + source installation; no separate install package.
  License selection is deferred; no open-source license is granted by this release.

## Deferred

- Dashboard selection of Wi-Fi versus module internet remains design work and is
  not included in 1.1.0.
