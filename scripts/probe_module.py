#!/usr/bin/env python3
"""Read-only QDC507 preflight; no ADB enablement, installation or reset."""
import ctypes as C
import dataclasses
import json
import re
import sys

if __package__:
    from . import cellforge as ecm
else:
    import cellforge as ecm


class InspectionUSB(ecm.USB):
    def command(self, cmd, reset=False):
        if cmd in {"AT+QGMR", "AT+QADBKEY?"} and not reset:
            return self._exchange(cmd)
        return super().command(cmd, reset)


def authorization_summary(dev):
    """Return capability metadata; never expose a raw challenge or response."""
    report = {}
    for cmd, label in (("AT+QGMR", "full_revision"), ("AT+QADBKEY?", "adb_challenge")):
        try:
            reply = dev.command(cmd)
        except ecm.ToolError as exc:
            if str(exc) != "Module rejected the AT command; no automatic retry.":
                raise
            report[label] = {"status": "command_rejected"}
            continue
        if label == "full_revision":
            versions = [x.strip() for x in reply.splitlines()
                        if re.fullmatch(r"QDC507[A-Za-z0-9_.-]{0,100}", x.strip())]
            report[label] = {"status": "available" if len(versions) == 1 else "unrecognized",
                             "value": versions[0] if len(versions) == 1 else None}
        else:
            records = [x.split(":", 1)[1].strip().strip('"')
                       for x in reply.splitlines() if x.startswith("+QADBKEY:")]
            report[label] = {"status": "unrecognized", "raw_value": "not_logged"}
            if len(records) == 1:
                report[label].update(status="available", length=len(records[0]),
                                     eight_digit_numeric=bool(re.fullmatch(r"[0-9]{8}", records[0])))
    return report


def inspect(dev):
    get_device = dev.lib.libusb_get_device
    get_device.argtypes = [C.c_void_p]
    get_device.restype = C.c_void_p
    config = C.POINTER(ecm.Configuration)()
    if dev.lib.libusb_get_active_config_descriptor(get_device(dev.handle), C.byref(config)):
        raise ecm.Unavailable("Cannot read current USB configuration")
    try:
        cfg = config.contents
        interfaces = []
        for i in range(cfg.ifs):
            interface = cfg.interface[i]
            for j in range(interface.count):
                alt = interface.alts[j]
                interfaces.append({"number": alt.number, "alt": alt.alt,
                                   "class": alt.cls, "subclass": alt.sub,
                                   "protocol": alt.proto})
        result = {
            "identity": dataclasses.asdict(ecm.read_state(dev)),
            "usb_configuration_attributes": hex(cfg.attrs),
            "remote_wakeup_advertised": bool(cfg.attrs & 0x20),
            "adb_interface_present": any(
                (x["class"], x["subclass"], x["protocol"]) == (255, 66, 1)
                for x in interfaces),
            "ecm_interface_present": dev.has_ecm,
            "interfaces": interfaces,
            "host_wakeup_authorization": "not_observed_on_mobile_device",
            "module_runtime": "not_inspected",
            "led_control": "not_inspected",
        }
        result["authorization"] = authorization_summary(dev)
        if dataclasses.asdict(ecm.read_state(dev)) != result["identity"]:
            raise ecm.ToolError("Configuration changed during read-only inspection")
        return result
    finally:
        dev.lib.libusb_free_config_descriptor(config)


def main():
    try:
        with InspectionUSB() as dev:
            print(json.dumps(inspect(dev), indent=2))
        return 0
    except (ecm.ToolError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
