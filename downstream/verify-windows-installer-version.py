#!/usr/bin/env python3
"""Verify an Inno Setup installer's textual ProductVersion against its release."""
import re
import sys


RELEASE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-fork\.[0-9]+)?", re.ASCII)


def matches(expected, actual):
    # Inno Setup's SetupLdr.version.rc reserves space-filled version fields.
    # Only the installer may have this padding; do not accept metadata or other whitespace.
    return (RELEASE_VERSION.fullmatch(expected) is not None
            and actual.startswith(expected)
            and all(char == " " for char in actual[len(expected):]))


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify-windows-installer-version.py EXPECTED ACTUAL")
    expected, actual = sys.argv[1:]
    if not matches(expected, actual):
        raise SystemExit(f"Windows installer version {actual!r} != {expected!r}")


if __name__ == "__main__":
    main()
