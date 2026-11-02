#!/usr/bin/env python3
"""Separately approved QDC507 ADB-bit transaction; read-only by default."""
import argparse
import dataclasses
import json
import re
import sys

if __package__:
    from . import cellforge as ecm
    from . import qadbkey
else:
    import cellforge as ecm
    import qadbkey


ORIGINAL = (0x2CA3, 0x4006, 1, 1, 1, 1, 1, 0, 0)
WITH_ADB = (0x2CA3, 0x4006, 1, 1, 1, 1, 1, 1, 0)
FULL_REVISION = "QDC507GLEFM21_01.001.02.004"


def composition_command(value):
    if value not in (ORIGINAL, WITH_ADB):
        raise ecm.ToolError("Only the recorded ADB-bit change is permitted")
    return 'AT+QCFG="usbcfg",0x2CA3,0x4006,' + ",".join(str(x) for x in value[2:])


class USB(ecm.USB):
    def command(self, cmd, reset=False):
        if cmd in {"AT+QGMR", "AT+QADBKEY?"} and not reset:
            return self._exchange(cmd)
        if cmd in (composition_command(ORIGINAL), composition_command(WITH_ADB)):
            if reset:
                raise ecm.ToolError("Composition command cannot be a restart")
            return self._exchange(cmd)
        return super().command(cmd, reset)

    def submit_authorization(self, password):
        if getattr(self, "authorization_attempted", False):
            raise ecm.ToolError("Authorization already attempted; no retry")
        if not re.fullmatch(r"[./0-9A-Za-z]{15}", password):
            raise ecm.ToolError("Invalid derived authorization format")
        self.authorization_attempted = True
        try:
            # Never place this command in argv, logs, exceptions or status.
            self._exchange('AT+QADBKEY="' + password + '"')
        except Exception:
            raise ecm.ToolError("ADB authorization rejected or uncertain; no retry, composition write or restart") from None


def read_full_revision(dev):
    records = [x.strip() for x in dev.command("AT+QGMR").splitlines()
               if x.strip().startswith("QDC507")]
    if records != [FULL_REVISION]:
        raise ecm.ToolError("Full firmware revision differs from the approved baseline")


def validate_pending(before, after):
    expected = dataclasses.replace(before, composition=WITH_ADB)
    if after not in (before, expected):
        raise ecm.ToolError("Unexpected pre-restart state drift; no restart")


def authorize_and_enable(dev, confirm):
    """One separately approved legacy authorization, ADB-bit write and restart.

    Only this path permits the intended ADB bit to remain pending until reboot.
    The original transition() keeps its exact immediate-readback requirement.
    """
    before = ecm.read_state(dev)
    read_full_revision(dev)
    if (before.mode != 1 or before.composition != ORIGINAL or not dev.has_ecm):
        raise ecm.ToolError("Authorization requires the recorded original ECM composition")
    print("Persistent ADB authorization may not be revocable by restoring USB composition.")
    if not confirm():
        print("Cancelled; no authorization write, configuration write or restart")
        return False
    if ecm.read_state(dev) != before:
        raise ecm.ToolError("State changed during confirmation; no write")
    read_full_revision(dev)
    try:
        challenge = qadbkey.parse_challenge(dev.command("AT+QADBKEY?"))
        password = qadbkey.derive(challenge)
    except ValueError:
        raise ecm.ToolError("Unsupported or ambiguous challenge; no authorization write") from None
    challenge = None
    dev.submit_authorization(password)
    password = None  # Drop reference; Python does not guarantee secure erasure.
    print("One authorization request accepted; actual ADB access remains unverified.")
    if ecm.read_state(dev) != before:
        raise ecm.ToolError("State changed after authorization; no composition write or restart")
    dev.command(composition_command(WITH_ADB))
    validate_pending(before, ecm.read_state(dev))
    dev.command("AT+CFUN=1,1", reset=True)
    print("One restart requested. Require exact post-restart composition before ADB inspection.")
    return True


def transition(dev, target, confirm):
    if target not in (ORIGINAL, WITH_ADB):
        raise ecm.ToolError("Unsupported target composition")
    before = ecm.read_state(dev)
    if (before.firmware != "QDC507GLEFM21" or before.mode != 1
            or before.composition not in (ORIGINAL, WITH_ADB) or not dev.has_ecm):
        raise ecm.ToolError("Device differs from the recorded baseline; refusing change")
    if before.composition == target:
        print("Already in target composition; no write or restart")
        return False
    print("Current composition:", before.composition)
    print("Proposed composition:", target)
    if not confirm():
        print("Cancelled; no write or restart")
        return False
    if ecm.read_state(dev) != before:
        raise ecm.ToolError("State changed during confirmation; no write")
    # Authorization is firmware-specific. A rejection stops here. Never guess
    # an unlock credential, retry a write or automatically roll it back.
    dev.command(composition_command(target))
    if ecm.read_state(dev) != dataclasses.replace(before, composition=target):
        raise ecm.ToolError("Composition readback mismatch; no restart or retry")
    dev.command("AT+CFUN=1,1", reset=True)
    print("Exact composition read back; one restart requested. Re-enumeration and ADB access are not verified.")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="status",
                        choices=("status", "enable-adb", "restore-usb", "authorize-adb"))
    parser.add_argument("--yes", action="store_true",
                        help="Explicitly confirm the separate device change and restart")
    args = parser.parse_args(argv)

    def confirm():
        if args.yes:
            return True
        try:
            return input("Change USB composition and restart? Type YES: ").strip() == "YES"
        except EOFError:
            return False

    try:
        with USB() as dev:
            if args.action == "status":
                print(json.dumps(dataclasses.asdict(ecm.read_state(dev))))
            elif args.action == "authorize-adb":
                authorize_and_enable(dev, confirm)
            else:
                transition(dev, WITH_ADB if args.action == "enable-adb" else ORIGINAL, confirm)
        return 0
    except (ecm.ToolError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; inspect state before retrying a change", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
