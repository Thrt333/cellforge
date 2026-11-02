#!/usr/bin/env python3
"""Stage and control the reviewed Cellforge module service, using direct USB ADB."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

if __package__:
    from . import adb_inspect as adb
else:
    import adb_inspect as adb


ROOT = Path(__file__).resolve().parent.parent
FILES = ("cellforge.sh", "policy.awk", "httpd.conf", "web/index.html")
REMOTE = "/data/cellforge"
INIT_PATH = "/etc/init.d/cellforge"
BOOT_LINKS = ("/etc/rc5.d/S99cellforge", "/etc/rc0.d/K01cellforge", "/etc/rc6.d/K01cellforge")
INIT_CONTENT = b'#!/bin/sh\n# Cellforge-owned startup shim\nexec /bin/sh /data/cellforge/startup.sh "$@"\n'


def package():
    content = {name: (ROOT / "module" / name).read_bytes() for name in FILES}
    digest = hashlib.sha256()
    for name, value in content.items():
        digest.update(name.encode() + b"\0" + value)
    return digest.hexdigest()[:16], content


def run(dev, command):
    marker = "CELLFORGE_COMMAND_STATUS"
    wrapped = "{ " + command + "; }; result=$?; printf '\\n" + marker + ":%s\\n' \"$result\""
    output = dev._shell(wrapped).decode("utf8", errors="replace").replace("\r", "")
    match = re.search(r"\n" + marker + r":([0-9]+)\n?$", output)
    if match is None:
        raise adb.ecm.ToolError("Module command did not return a status; no automatic retry")
    text = output[:match.start()].strip()
    if int(match[1]) != 0:
        raise adb.ecm.ToolError("Module command failed: " + text[-1200:])
    return text


def stage(dev):
    revision, files = package()
    target = REMOTE + "/releases/" + revision
    run(dev, "test ! -f /tmp/cellforge/current")
    run(dev, "set -e; mkdir -p " + target + "/web; chmod 700 " + REMOTE + " " + REMOTE + "/releases " + target)
    manifest = {}
    for name, value in files.items():
        destination = target + "/" + name
        # Bounded shell payloads; all paths are fixed by the manifest, never CLI input.
        run(dev, ": > " + destination + ".new")
        for offset in range(0, len(value), 1800):
            encoded = base64.b64encode(value[offset:offset + 1800]).decode("ascii")
            run(dev, "printf '%s' '" + encoded + "' | base64 -d >> " + destination + ".new")
        expected = hashlib.sha256(value).hexdigest()
        actual = run(dev, "sha256sum " + destination + ".new").split()[0]
        if actual != expected:
            raise adb.ecm.ToolError("Staged file hash mismatch; not activating")
        run(dev, "chmod 600 " + destination + ".new; mv " + destination + ".new " + destination)
        manifest[name] = expected
    run(dev, "sh -n " + target + "/cellforge.sh")
    # A running service must be stopped explicitly before changing its files.
    run(dev, "test ! -f /tmp/cellforge/current && ln -sfn releases/" + revision + " " + REMOTE + "/current")
    return {"revision": revision, "path": target, "files": manifest}


def put(dev, destination, value, mode):
    run(dev, ": > " + destination + ".new")
    for offset in range(0, len(value), 1800):
        encoded = base64.b64encode(value[offset:offset + 1800]).decode("ascii")
        run(dev, "printf '%s' '" + encoded + "' | base64 -d >> " + destination + ".new")
    expected = hashlib.sha256(value).hexdigest()
    if run(dev, "sha256sum " + destination + ".new").split()[0] != expected:
        raise adb.ecm.ToolError("Startup file hash mismatch")
    run(dev, "chmod " + mode + " " + destination + ".new; mv " + destination + ".new " + destination)


def boot_control(dev, enable):
    expected = hashlib.sha256(INIT_CONTENT).hexdigest()
    paths = " ".join((INIT_PATH,) + BOOT_LINKS)
    root_check = "test \"$(awk '$2==\"/\" && $3==\"ubifs\" {print $1,substr($4,1,2)}' /proc/mounts)\" = 'ubi0:rootfs ro'"
    if enable:
        run(dev, root_check + "; test -f " + REMOTE + "/current/cellforge.sh; for p in " + paths + "; do test ! -e \"$p\" && test ! -L \"$p\" || exit 1; done")
        put(dev, REMOTE + "/startup.sh", (ROOT / "module/startup.sh").read_bytes(), "700")
        put(dev, REMOTE + "/init.sh", INIT_CONTENT, "755")
        run(dev, "sh -n " + REMOTE + "/startup.sh")
        operations = "cp " + REMOTE + "/init.sh " + INIT_PATH + "; chmod 755 " + INIT_PATH + "; "
        operations += " ".join("ln -s ../init.d/cellforge " + path + ";" for path in BOOT_LINKS)
        operations += " test \"$(sha256sum " + INIT_PATH + " | awk '{print $1}')\" = " + expected + "; : > " + REMOTE + "/autostart.enabled;"
    else:
        run(dev, root_check + "; test \"$(sha256sum " + INIT_PATH + " | awk '{print $1}')\" = " + expected + "; for p in " + " ".join(BOOT_LINKS) + "; do test \"$(readlink \"$p\")\" = ../init.d/cellforge || exit 1; done")
        operations = "rm -f " + REMOTE + "/autostart.enabled " + paths + ";"
    # Always restore the original read-only root mount, including on an early exit.
    transaction = ("set -e; " + root_check + "; trap 'mount -o remount,ro /' EXIT; "
                   "mount -o remount,rw /; " + operations
                   + " sync; mount -o remount,ro /; trap - EXIT; " + root_check
                   + "; echo " + ("autostart_enabled" if enable else "autostart_disabled"))
    return run(dev, transaction)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "start", "stop", "status", "logs", "probe", "led-test", "enable-autostart", "disable-autostart"))
    args = parser.parse_args(argv)
    try:
        with adb.USBADB(timeout=40) as dev:
            if dev._shell("id -u").strip() != b"0":
                raise adb.ecm.ToolError("Module root not available")
            if args.action == "stage":
                print(json.dumps(stage(dev), indent=2))
            elif args.action in ("enable-autostart", "disable-autostart"):
                print(boot_control(dev, args.action == "enable-autostart"))
            elif args.action in ("start", "stop", "status"):
                print(run(dev, "sh " + REMOTE + "/current/cellforge.sh " + shlex.quote(args.action)))
            elif args.action == "logs":
                print(run(dev, "for p in /tmp/cellforge/control/launch.log /tmp/cellforge/control/*/*.log; do test -f \"$p\" || continue; echo \"$p\"; tail -n 20 \"$p\"; done"))
            elif args.action == "led-test":
                print(run(dev, "read -r up rest < /proc/uptime; token=$(cat /tmp/cellforge/current); case \"$token\" in ''|*[!0-9.]*) exit 1;; esac; printf '%s yellow_solid\\n' \"$((${up%%.*} + 2))\" > /tmp/cellforge/control/\"$token\"/led-test.new; mv /tmp/cellforge/control/\"$token\"/led-test.new /tmp/cellforge/control/\"$token\"/led-test; echo yellow_for_two_seconds"))
            else:
                print(run(dev, "curl --noproxy '*' --fail --silent --max-time 3 http://192.168.225.1:8080/status.json"))
        return 0
    except (adb.ecm.ToolError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
