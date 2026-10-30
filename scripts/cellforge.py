#!/usr/bin/env python3
"""Cellforge's narrowly scoped macOS/QDC507 ECM configuration tool."""
import argparse
import ctypes as C
import ctypes.util
import dataclasses
import json
import re
import sys
import time

VID, PID = 0x2CA3, 0x4006
MODEL = "QDC507"


class ToolError(Exception):
    pass


class Unavailable(ToolError):
    """The device or its USB interface is unavailable."""


class DeviceDescriptor(C.Structure):
    _fields_ = [
        ("length", C.c_uint8), ("dtype", C.c_uint8), ("usb", C.c_uint16),
        ("cls", C.c_uint8), ("sub", C.c_uint8), ("proto", C.c_uint8),
        ("packet", C.c_uint8), ("vid", C.c_uint16), ("pid", C.c_uint16),
        ("version", C.c_uint16), ("manufacturer", C.c_uint8),
        ("product", C.c_uint8), ("serial", C.c_uint8), ("configs", C.c_uint8),
    ]


class Endpoint(C.Structure):
    _fields_ = [
        ("length", C.c_uint8), ("dtype", C.c_uint8), ("addr", C.c_uint8),
        ("attrs", C.c_uint8), ("packet", C.c_uint16), ("interval", C.c_uint8),
        ("refresh", C.c_uint8), ("sync", C.c_uint8),
        ("extra", C.c_void_p), ("extra_len", C.c_int),
    ]


class InterfaceDescriptor(C.Structure):
    _fields_ = [
        ("length", C.c_uint8), ("dtype", C.c_uint8), ("number", C.c_uint8),
        ("alt", C.c_uint8), ("eps", C.c_uint8), ("cls", C.c_uint8),
        ("sub", C.c_uint8), ("proto", C.c_uint8), ("name", C.c_uint8),
        ("endpoint", C.POINTER(Endpoint)), ("extra", C.c_void_p),
        ("extra_len", C.c_int),
    ]


class Interface(C.Structure):
    _fields_ = [("alts", C.POINTER(InterfaceDescriptor)), ("count", C.c_int)]


class Configuration(C.Structure):
    _fields_ = [
        ("length", C.c_uint8), ("dtype", C.c_uint8), ("total", C.c_uint16),
        ("ifs", C.c_uint8), ("value", C.c_uint8), ("name", C.c_uint8),
        ("attrs", C.c_uint8), ("power", C.c_uint8),
        ("interface", C.POINTER(Interface)), ("extra", C.c_void_p),
        ("extra_len", C.c_int),
    ]


class Reply:
    """Bounded AT framing. Never print raw responses or unsolicited messages."""
    def __init__(self):
        self.data = b""

    def feed(self, chunk):
        self.data += chunk
        if len(self.data) > 65536:
            raise ToolError("AT response exceeds the size limit.")
        text = self.data.decode("ascii", errors="replace")
        lines = text.replace("\r", "\n").split("\n")
        # Only newline-terminated records count as terminal responses.
        complete = lines[:-1]
        if any(x == "ERROR" or x.startswith(("+CME ERROR:", "+CMS ERROR:"))
               for x in complete):
            raise ToolError("Module rejected the AT command; no automatic retry.")
        if "OK" in complete:
            return "\n".join(x for x in complete if x)
        return None


def single_device(matches):
    if not matches:
        raise Unavailable("No 2ca3:4006 module found.")
    if len(matches) != 1:
        raise ToolError("Multiple modules found. Disconnect all but the target.")
    return matches[0]


class USB:
    """Uses only libusb enumeration, interface claim and bulk I/O."""
    def __init__(self, library=None):
        self.library = library
        self.ctx = C.c_void_p()
        self.handle = C.c_void_p()
        self.claimed = False
        self.has_ecm = False

    def __enter__(self):
        if sys.platform != "darwin":
            raise ToolError("This version supports macOS only.")
        paths = [self.library] if self.library else [
            ctypes.util.find_library("usb-1.0"),
            "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
            "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
        ]
        self.lib = None
        for path in filter(None, paths):
            try:
                self.lib = C.CDLL(path)
                break
            except OSError:
                continue
        if self.lib is None:
            raise ToolError("libusb not found. See docs/ecm-tool.md; nothing was installed.")
        def bind(name, args, result=C.c_int):
            f = getattr(self.lib, "libusb_" + name)
            f.argtypes, f.restype = args, result
        bind("init", [C.POINTER(C.c_void_p)])
        bind("exit", [C.c_void_p], None)
        bind("get_device_list", [C.c_void_p, C.POINTER(C.POINTER(C.c_void_p))], C.c_ssize_t)
        bind("free_device_list", [C.POINTER(C.c_void_p), C.c_int], None)
        bind("get_device_descriptor", [C.c_void_p, C.POINTER(DeviceDescriptor)])
        bind("get_active_config_descriptor", [C.c_void_p, C.POINTER(C.POINTER(Configuration))])
        bind("free_config_descriptor", [C.POINTER(Configuration)], None)
        bind("open", [C.c_void_p, C.POINTER(C.c_void_p)])
        bind("close", [C.c_void_p], None)
        bind("claim_interface", [C.c_void_p, C.c_int])
        bind("release_interface", [C.c_void_p, C.c_int])
        bind("bulk_transfer", [C.c_void_p, C.c_ubyte, C.c_void_p, C.c_int,
                               C.POINTER(C.c_int), C.c_uint])
        if self.lib.libusb_init(C.byref(self.ctx)):
            raise ToolError("Cannot initialize libusb.")
        devices = C.POINTER(C.c_void_p)()
        try:
            count = self.lib.libusb_get_device_list(self.ctx, C.byref(devices))
            if count < 0:
                raise ToolError("Cannot enumerate USB devices.")
            matches = []
            for i in range(count):
                d = DeviceDescriptor()
                if self.lib.libusb_get_device_descriptor(devices[i], C.byref(d)) == 0:
                    if (d.vid, d.pid) == (VID, PID):
                        matches.append(devices[i])
            target = single_device(matches)
            cfg = C.POINTER(Configuration)()
            if self.lib.libusb_get_active_config_descriptor(target, C.byref(cfg)):
                raise Unavailable("USB configuration is not ready.")
            at_endpoints = None
            try:
                for i in range(cfg.contents.ifs):
                    interface = cfg.contents.interface[i]
                    for j in range(interface.count):
                        alt = interface.alts[j]
                        self.has_ecm |= alt.cls == 2 and alt.sub == 6
                        if alt.number == 2 and alt.alt == 0 and alt.cls == 255:
                            endpoints = [alt.endpoint[k].addr for k in range(alt.eps)
                                         if alt.endpoint[k].attrs & 3 == 2]
                            ins = [e for e in endpoints if e & 0x80]
                            outs = [e for e in endpoints if not e & 0x80]
                            if len(ins) == len(outs) == 1:
                                at_endpoints = ins[0], outs[0]
            finally:
                self.lib.libusb_free_config_descriptor(cfg)
            if at_endpoints is None:
                raise ToolError("Expected QDC507 AT interface 2 is missing; refusing to probe other ports.")
            self.ep_in, self.ep_out = at_endpoints
            if self.lib.libusb_open(target, C.byref(self.handle)):
                raise Unavailable("Cannot open module; check USB access and competing tools.")
            if self.lib.libusb_claim_interface(self.handle, 2):
                raise ToolError("Cannot exclusively claim AT interface; close other management tools.")
            self.claimed = True
            return self
        except BaseException:
            if devices:
                self.lib.libusb_free_device_list(devices, 1)
                devices = C.POINTER(C.c_void_p)()
            self.close()
            raise
        finally:
            if devices:
                self.lib.libusb_free_device_list(devices, 1)

    def close(self):
        if getattr(self, "lib", None):
            if self.handle:
                if self.claimed:
                    self.lib.libusb_release_interface(self.handle, 2)
                self.lib.libusb_close(self.handle)
            if self.ctx:
                self.lib.libusb_exit(self.ctx)
        self.handle, self.ctx = C.c_void_p(), C.c_void_p()
        self.claimed = False

    def __exit__(self, *_):
        self.close()

    def command(self, cmd, reset=False):
        allowed = {
            "AT", "AT+CGMM", "AT+CGMR",
            'AT+QCFG="usbnet"', 'AT+QCFG="usbcfg"',
            'AT+QCFG="usbnet",0', 'AT+QCFG="usbnet",1', "AT+CFUN=1,1",
        }
        if cmd not in allowed or reset != (cmd == "AT+CFUN=1,1"):
            raise ToolError("AT command is outside the tool's allowlist.")
        # Bound stale input draining; do not clear endpoints or change line state.
        deadline = time.monotonic() + 0.3
        while True:
            buf, got = C.create_string_buffer(4096), C.c_int()
            rc = self.lib.libusb_bulk_transfer(
                self.handle, self.ep_in, buf, len(buf), C.byref(got), 40)
            if rc == -7:
                break
            if rc:
                raise Unavailable("USB read unavailable before command.")
            if time.monotonic() >= deadline:
                raise ToolError("AT channel is not quiet; stop competing readers.")
        payload = (cmd + "\r").encode("ascii")
        buf, sent = C.create_string_buffer(payload), C.c_int()
        rc = self.lib.libusb_bulk_transfer(
            self.handle, self.ep_out, buf, len(payload), C.byref(sent), 1500)
        if rc or sent.value != len(payload):
            raise ToolError("AT write was not fully acknowledged by USB. State may be unknown; do not retry blindly.")
        reply = Reply()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            buf, got = C.create_string_buffer(4096), C.c_int()
            rc = self.lib.libusb_bulk_transfer(
                self.handle, self.ep_in, buf, len(buf), C.byref(got), 400)
            if rc == -4 and reset:
                return ""  # A disconnect after a complete reset request is expected.
            if rc not in (0, -7):
                raise Unavailable("USB response unavailable; configuration state may be unknown.")
            if got.value:
                result = reply.feed(buf.raw[:got.value])
                if result is not None:
                    return result
        if cmd in {"AT", "AT+CGMM", "AT+CGMR", 'AT+QCFG="usbnet"', 'AT+QCFG="usbcfg"'}:
            raise Unavailable("Read-only AT query timed out.")
        raise ToolError("AT response timed out. State may be unknown; no automatic command retry.")


@dataclasses.dataclass(frozen=True)
class State:
    mode: int
    composition: tuple
    model: str
    firmware: str


def one_match(pattern, text, label):
    matches = re.findall(pattern, text, re.MULTILINE)
    if len(matches) != 1:
        raise ToolError("Missing or ambiguous " + label + "; refusing to continue.")
    return matches[0]


def read_state(dev):
    dev.command("AT")
    model = one_match(r"^(QDC507)$", dev.command("AT+CGMM"), "model")
    reply = dev.command("AT+CGMR")
    lines = [line.strip() for line in reply.splitlines()
             if line.strip() and line.strip() not in ("AT+CGMR", "OK")
             and not line.strip().startswith("+")]
    if len(lines) != 1:
        raise ToolError("Missing or ambiguous firmware version.")
    firmware = lines[0]
    raw = one_match(r'^\+QCFG: "usbcfg",([^\n]+)$',
                    dev.command('AT+QCFG="usbcfg"'), "USB composition")
    try:
        composition = tuple(int(x.strip(), 0) for x in raw.split(","))
    except ValueError:
        raise ToolError("Malformed USB composition.")
    mode = int(one_match(r'^\+QCFG: "usbnet",([0-3])$',
                         dev.command('AT+QCFG="usbnet"'), "network mode"))
    return State(mode, composition, model, firmware)


def change_mode(dev, target, confirm):
    state = read_state(dev)
    if state.mode not in (0, 1) or target not in (0, 1):
        raise ToolError("Only mode 0 <-> 1 switching is supported.")
    if state.mode == target:
        print("Already in mode %d; no configuration write or restart needed." % target)
        return False
    if not confirm("Change USB network mode %d -> %d and restart the module?" % (state.mode, target)):
        print("Cancelled; module unchanged.")
        return False
    if read_state(dev) != state:
        raise ToolError("Device state changed before configuration; no write issued.")
    # Never retry a write or automatically reverse an uncertain outcome.
    dev.command('AT+QCFG="usbnet",%d' % target)
    if read_state(dev) != dataclasses.replace(state, mode=target):
        raise ToolError("Configuration readback mismatch. Stop and inspect before retrying.")
    dev.command("AT+CFUN=1,1", reset=True)
    print("Mode %d read back; restart requested. Reconnection and networking are not checked." % target)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libusb", help="Explicit path to an existing libusb dylib")
    commands = parser.add_subparsers(dest="action")
    commands.add_parser("status", help="Default: read-only model and configuration query")
    for name, help_text in [
        ("enable-ecm", "Switch to mode 1 (CDC ECM)"),
        ("disable-ecm", "Switch to mode 0 (QMI); does not turn off cellular service"),
    ]:
        p = commands.add_parser(name, help=help_text)
        p.add_argument("--yes", action="store_true",
                       help="Confirm the configuration write and module restart")
    args = parser.parse_args(argv)
    action = args.action or "status"

    def confirm(message):
        print(message, flush=True)
        if args.yes:
            return True
        try:
            return input("Type YES to proceed: ").strip() == "YES"
        except EOFError:
            return False

    try:
        with USB(args.libusb) as dev:
            if action == "status":
                print(json.dumps(dataclasses.asdict(read_state(dev))))
                print("ECM USB interface present:", dev.has_ecm)
            else:
                change_mode(dev, 1 if action == "enable-ecm" else 0, confirm)
        return 0
    except (ToolError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. If a write was issued, inspect state before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
