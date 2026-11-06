# Changelog

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

## Planned 1.1.0

- Dashboard selection of Wi-Fi versus module internet, preserving USB management
  connectivity and the user's last choice through recovery. Design only; not
  implemented or included in 1.0.0.
