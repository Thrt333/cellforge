#!/usr/bin/env python3
"""Explicit single USB-enable trial; bounded host observation, never auto-retry."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import time

if __package__:
    from . import module_runtime as runtime
else:
    import module_runtime as runtime


ROOT = Path(__file__).resolve().parent.parent
REMOTE = "/data/cellforge/recovery-trial"
ASSETS = {"journal.sh": "usb-recover.sh", "executor.sh": "enable-trial.sh"}
URL = "http://192.168.225.1:8080/"
Error = runtime.adb.ecm.ToolError


def usb_entries(value):
    """ioreg plist roots can be a dictionary or an array; never log properties."""
    if isinstance(value, dict):
        roots = [value]
    elif isinstance(value, list):
        roots = value
    else:
        raise Error("Unknown USB inventory root format")
    found = set()
    todo = list(roots)
    while todo:
        node = todo.pop()
        if not isinstance(node, dict):
            raise Error("Unknown USB inventory node format")
        children = node.get("IORegistryEntryChildren", [])
        if not isinstance(children, list):
            raise Error("Unknown USB inventory children format")
        todo.extend(children)
        if node.get("idVendor") == 0x2CA3 and node.get("idProduct") == 0x4006:
            entry = node.get("IORegistryEntryID")
            if not isinstance(entry, int) or isinstance(entry, bool):
                raise Error("USB inventory lacks a usable instance marker")
            found.add(entry)
    if len(found) > 1:
        raise Error("Multiple target modules; trial refused")
    return frozenset(found)


def usb_interface(text):
    devices = re.findall(r"^Hardware Port: Baiwang\nDevice: (en[0-9]+)$", text, re.M)
    if len(devices) > 1:
        raise Error("Ambiguous USB network interface")
    return devices[0] if devices else None


def host_command(args, timeout=5):
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise Error("Host observation command exceeded its deadline") from None


def inventory():
    result = host_command(["ioreg", "-p", "IOUSB", "-a", "-l"])
    if result.returncode:
        raise Error("Host USB inventory unavailable")
    try:
        return usb_entries(plistlib.loads(result.stdout))
    except (ValueError, plistlib.InvalidFileException):
        raise Error("Host USB inventory is not a valid plist") from None


def interface():
    result = host_command(["networksetup", "-listallhardwareports"])
    if result.returncode:
        raise Error("Host network inventory unavailable")
    return usb_interface(result.stdout.decode("utf8", errors="replace"))


def has_address(device):
    if not device:
        return False
    result = host_command(["ifconfig", device])
    text = result.stdout.decode("utf8", errors="replace")
    if result.returncode or "status: active" not in text:
        return False
    for raw in re.findall(r"\binet ([0-9.]+)\b", text):
        try:
            if ipaddress.ip_address(raw) in ipaddress.ip_network("192.168.225.0/24"):
                return True
        except ValueError:
            continue
    return False


def fetch(device, path):
    result = host_command(["curl", "-q", "--noproxy", "*", "--interface", device,
                           "--silent", "--fail", "--connect-timeout", "2",
                           "--max-time", "3", "-H", "Cache-Control: no-cache", URL + path])
    return result.stdout if result.returncode == 0 else None


def healthy(data):
    if not isinstance(data, dict):
        return False
    if (data.get("version"), data.get("state"), data.get("usb_state"), data.get("usb_sleep")) != (
            "1.0.0", "active", "CONFIGURED", 0):
        return False
    for key in ("updated_uptime", "host_age", "uplink_age"):
        value = data.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            return False
    return data["host_age"] <= 30 and data["uplink_age"] <= 30


def network_sample(device, page=False):
    if not has_address(device):
        return None
    if page:
        html = fetch(device, "")
        if html is None or b"<title>Cellforge</title>" not in html:
            return None
    raw = fetch(device, "status.json")
    try:
        value = json.loads(raw) if raw is not None else None
    except (ValueError, UnicodeDecodeError):
        return None
    return value if healthy(value) else None


def manifest():
    return {name: hashlib.sha256((ROOT / "module" / source).read_bytes()).hexdigest()
            for name, source in ASSETS.items()}


def prepare():
    if len(inventory()) != 1:
        raise Error("Healthy connected target required before preparing trial")
    device = interface()
    if not device or network_sample(device, page=True) is None:
        raise Error("USB-bound network baseline is not healthy; no trial prepared")
    ticket = str(int(time.time()))
    hashes = manifest()
    with runtime.adb.USBADB(timeout=40) as dev:
        if dev._shell("id -u").strip() != b"0":
            raise Error("Root ADB required")
        runtime.run(dev, "set -e; test ! -e " + REMOTE + "; mkdir -m 700 " + REMOTE)
        for name, source in ASSETS.items():
            runtime.put(dev, REMOTE + "/" + name, (ROOT / "module" / source).read_bytes(), "700")
        info = json.dumps({"ticket": ticket, "files": hashes}, sort_keys=True).encode()
        runtime.put(dev, REMOTE + "/manifest.json", info, "600")
        runtime.run(dev, "sh -n " + REMOTE + "/journal.sh && sh -n " + REMOTE + "/executor.sh")
        runtime.run(dev, "set -e; set -- library; . " + REMOTE + "/executor.sh; trial_snapshot > " + REMOTE + "/factory.before")
        runtime.run(dev, "sh " + REMOTE + "/journal.sh begin " + ticket)
        runtime.run(dev, "sh " + REMOTE + "/executor.sh check " + ticket)
    return {"prepared": True, "ticket": ticket, "files": hashes}


def report_save(path, report):
    payload = json.dumps(report, indent=2, sort_keys=True)
    if len(payload.encode()) > 8192:
        raise Error("Host evidence cutoff")
    path.write_text(payload + "\n")


def observe(original, baseline, progress, sample=network_sample, scan=inventory,
            locate=interface, address=has_address, clock=time.monotonic, pause=time.sleep):
    """Purely observes. No ADB writes or reset retries, even after stage timeout."""
    started = clock()
    deadline = started + 75  # 15s launch/write allowance + 60s enumeration window.
    absent = False
    stage = "enumeration"
    stable_at = None
    last_stamp = None
    last_advance = None
    while clock() < deadline:
        entries = scan()
        if not entries:
            absent = True
        if stage == "enumeration":
            if entries and (absent or entries != original):
                progress("enumeration", clock() - started)
                stage = "address"
                deadline = clock() + 60
        elif stage == "address":
            device = locate()
            if device and address(device):
                progress("address", clock() - started)
                stage = "communication"
                deadline = clock() + 15
        else:
            device = locate()
            data = sample(device, page=True) if device and entries else None
            valid = data is not None and data["updated_uptime"] > baseline
            if valid:
                stamp = data["updated_uptime"]
                if last_stamp is not None and stamp < last_stamp:
                    raise Error("Module clock regressed during trial")
                if stamp != last_stamp:
                    last_stamp, last_advance = stamp, clock()
                valid = clock() - last_advance <= 6
            if valid:
                if stable_at is None:
                    stable_at = clock()
                    deadline = stable_at + 40
                    progress("communication", clock() - started)
                if clock() - stable_at >= 30:
                    progress("stable", clock() - started)
                    return True
            elif stable_at is not None:
                progress("stability_lost", clock() - started)
                return False
        pause(0.5 if stage == "enumeration" else 1)
    progress(stage + "_timeout", clock() - started)
    return False


def run_trial():
    original = inventory()
    device = interface()
    baseline = network_sample(device, page=True) if device else None
    if len(original) != 1 or baseline is None:
        raise Error("Fresh healthy USB baseline required; no action issued")
    descriptor, raw_path = tempfile.mkstemp(prefix="cellforge-enable-trial-", suffix=".json", dir="/private/tmp")
    import os
    os.close(descriptor)
    path = Path(raw_path)
    report = {"baseline_healthy": True, "events": [], "success": False}
    def progress(event, elapsed):
        item = {"event": event, "elapsed_seconds": round(elapsed, 1)}
        report["events"].append(item)
        report_save(path, report)
        print(json.dumps(item), flush=True)
    report_save(path, report)
    print("host_evidence=" + str(path), flush=True)
    with runtime.adb.USBADB(timeout=40) as dev:
        info = json.loads(runtime.run(dev, "cat " + REMOTE + "/manifest.json"))
        ticket = info.get("ticket")
        if not isinstance(ticket, str) or not re.fullmatch(r"[0-9]{1,20}", ticket) or info.get("files") != manifest():
            raise Error("Trial manifest differs from reviewed local assets")
        for name, digest in manifest().items():
            if runtime.run(dev, "sha256sum " + REMOTE + "/" + name).split()[0] != digest:
                raise Error("Installed trial asset hash mismatch")
        runtime.run(dev, "sh " + REMOTE + "/executor.sh check " + ticket)
        print(runtime.run(dev, "sh " + REMOTE + "/executor.sh arm " + ticket), flush=True)
        print(runtime.run(dev, "sh " + REMOTE + "/executor.sh release " + ticket), flush=True)
    success = observe(original, baseline["updated_uptime"], progress)
    if not success:
        report_save(path, report)
        raise Error("Single trial failed; no retry issued; evidence=" + str(path))
    with runtime.adb.USBADB(timeout=25) as dev:
        code = runtime.run(dev, "cat " + REMOTE + "/executor.exit")
        identities = runtime.run(dev, "cat " + REMOTE + "/factory.result")
        control = runtime.run(dev, "cat " + REMOTE + "/control.result")
        safeguard = runtime.run(dev, "cat " + REMOTE + "/guard.result")
        print(json.dumps({"executor_exit": code, "factory": identities,
                          "control": control, "safeguard": safeguard}), flush=True)
        if code != "0" or identities != "identities_match" or control != "control_matches":
            raise Error("USB communications returned, but module trial postconditions failed")
        for phase in ("enumeration_observed", "address_observed", "communication_observed"):
            runtime.run(dev, "sh " + REMOTE + "/journal.sh record " + ticket + " " + phase + " ok")
        print(runtime.run(dev, "sh " + REMOTE + "/journal.sh status"), flush=True)
    report["success"] = True
    report_save(path, report)
    return {"single_trial_passed": True, "automatic_recovery_enabled": False, "host_evidence": str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            value = prepare()
        elif args.action == "run":
            value = run_trial()
        else:
            with runtime.adb.USBADB(timeout=25) as dev:
                value = runtime.run(dev, "sh " + REMOTE + "/journal.sh status")
        print(json.dumps(value, indent=2))
        return 0
    except (Error, OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
