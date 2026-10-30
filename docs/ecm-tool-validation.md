# ECM tool verification record

Date: 2026-10-30.

## Current revision

The simplified tool provides status, enable-ecm and disable-ecm.
Backup/device binding, backup-based restore, reconnect polling and network
verification have been removed. Exact firmware/composition locks have also
been removed; USB identity, model and AT interface checks remain.

The standard host entry point, make check, passed all 15 tests under Python
3.9.6. CLI help and Git whitespace checks also passed. Tests simulate AT
transport and CLI calls, including both switch directions, cancellation/no-op, unsupported
models/modes, differing firmware/composition, state changes during confirmation,
uncertain writes and readback mismatch. They do not use real USB or networking.

This revision was checked without connecting to the module or changing its
settings. The actual write/restart paths in either direction still require
hardware validation. Different firmware/composition fixtures demonstrate acceptance by
the code, not compatibility with those devices.

## Earlier real-device evidence

The earlier tool reported mode 1 and an ECM descriptor on the QDC507 running
QDC507GLEFM21, USB 2ca3:4006. Its enable-ecm command was a no-op.

Its former network verifier initially found an inactive Ethernet link.
Independent host observations also found the link and DHCP inactive. After the
user physically reconnected the module, macOS acquired a lease and the former
verifier completed an interface-bound HTTPS request with HTTP 200 and successful
TLS verification. The tool issued no configuration write or restart to recover
that link.

Those are historical observations; the current script has no network verifier.
They do not establish long-term stability or the cause of the disconnect.
The earlier manual mode change and networking checks are documented separately
in the [hardware baseline](hardware-baseline.md).

iPad networking, lock/wake behavior, prolonged operation and throughput remain
unverified. No private module identifier or raw system log is included here.
