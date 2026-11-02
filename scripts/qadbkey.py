"""Legacy eight-digit QADBKEY compatibility, with no I/O or device access.

Independently implements Unix MD5-crypt, cross-checked against LibreSSL and
published vectors. Protocol reference: DJOneHubNative 7194ae8, qadbkey.go.
Format compatibility is not proof that a particular firmware accepts a key.
"""
import hashlib
import re


def parse_challenge(reply):
    lines = reply.replace("\r", "\n").splitlines()
    if "OK" not in lines or any(
            x == "ERROR" or x.startswith(("+CME ERROR:", "+CMS ERROR:")) for x in lines):
        raise ValueError("ADB challenge query was not accepted")
    records = [x for x in lines if x.startswith("+QADBKEY:")]
    if len(records) != 1:
        raise ValueError("Missing or ambiguous ADB challenge")
    match = re.fullmatch(r"\+QADBKEY:\s*([0-9]{8})\s*", records[0])
    if match is None:
        raise ValueError("Unsupported ADB challenge format")
    return match[1]


def derive(challenge):
    if not isinstance(challenge, str) or not re.fullmatch(r"[0-9]{8}", challenge):
        raise ValueError("Unsupported ADB challenge format")
    password, salt = b"SH_adb_quectel", challenge.encode("ascii")
    alternate = hashlib.md5(password + salt + password).digest()
    initial = password + b"$1$" + salt
    remaining = len(password)
    while remaining:
        size = min(16, remaining)
        initial += alternate[:size]
        remaining -= size
    count = len(password)
    while count:
        initial += b"\0" if count & 1 else password[:1]
        count >>= 1
    digest = hashlib.md5(initial).digest()
    for iteration in range(1000):
        value = password if iteration & 1 else digest
        if iteration % 3:
            value += salt
        if iteration % 7:
            value += password
        value += digest if iteration & 1 else password
        digest = hashlib.md5(value).digest()
    alphabet = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    encoded = ""
    for high, middle, low, length in ((0, 6, 12, 4), (1, 7, 13, 4),
                                    (2, 8, 14, 4), (3, 9, 15, 4),
                                    (4, 10, 5, 4), (None, None, 11, 2)):
        value = (((digest[high] << 16) if high is not None else 0)
                 | ((digest[middle] << 8) if middle is not None else 0)
                 | digest[low])
        for _ in range(length):
            encoded += alphabet[value & 63]
            value >>= 6
    return encoded[:15]
