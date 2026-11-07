#!/usr/bin/env python3
"""Prepare, verify, and export the downstream git-am patch queue."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import release_network

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PATCHES = HERE / "patches"
CONFIG = json.loads((HERE / "config.json").read_text())
SHA = re.compile(r"[0-9a-f]{40}\Z")
NAME = re.compile(r"[0-9]{4}-[A-Za-z0-9][A-Za-z0-9._-]*\.patch\Z")


def run(args, cwd=None, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(args, cwd=cwd, check=True, **kwargs)


def base_sha(value):
    if not SHA.fullmatch(value):
        raise ValueError("baseline must be a full lowercase 40-character commit SHA")
    return value


def new_directory(value):
    path = Path(value).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError("output must be outside the main workspace")
    if os.path.lexists(value):
        raise ValueError(f"output already exists: {path}")
    return path


def queue():
    names = []
    for line in (PATCHES / "series").read_text().splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if not NAME.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate series entry: {name}")
        if not (PATCHES / name).is_file():
            raise ValueError(f"missing patch: {name}")
        names.append(name)
    extra = {p.name for p in PATCHES.glob("*.patch")} - set(names)
    if extra:
        raise ValueError(f"patches absent from series: {', '.join(sorted(extra))}")
    return names


def registry(names, require_commands=True):
    entries = json.loads((PATCHES / "tests.json").read_text())
    if not isinstance(entries, dict) or set(entries) != set(names):
        raise ValueError("tests.json keys must exactly match series entries")
    for name, entry in entries.items():
        if not isinstance(entry, dict) or set(entry) != {"regression", "related", "reason"}:
            raise ValueError(f"{name}: expected regression, related, and reason")
        for category in ("regression", "related"):
            commands = entry[category]
            if not isinstance(commands, list):
                raise ValueError(f"{name}: {category} must be a list")
            for command in commands:
                if (not isinstance(command, dict) or set(command) != {"platform", "run"}
                        or command["platform"] not in ("linux", "macos", "windows", "all")
                        or not isinstance(command["run"], str) or not command["run"].strip()):
                    raise ValueError(f"{name}: invalid {category} command")
        if not isinstance(entry["reason"], str):
            raise ValueError(f"{name}: reason must be a string")
        if require_commands and not entry["regression"] and not entry["related"] and not entry["reason"].strip():
            raise ValueError(f"{name}: register tests or explain why no tests apply")
    return entries


def prepare(output, base, names):
    output = new_directory(output)
    def clone():
        # Reserve the destination atomically; never remove a directory we did not create.
        output.mkdir()
        identity = output.stat()
        try:
            release_network.run_once(
                ["git", "clone", "--no-checkout", CONFIG["upstream_url"], str(output)],
                timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            try:
                current = output.stat()
            except FileNotFoundError:
                pass
            else:
                if not output.is_symlink() and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    shutil.rmtree(output)
            raise

    release_network.retry(clone, label="clone upstream")
    run(["git", "checkout", "--detach", base], cwd=output)
    for name in names:
        run(["git", "-c", "user.name=Downstream Patch Queue", "-c",
             "user.email=downstream@localhost", "am", "--", str(PATCHES / name)], cwd=output)
    return output


def export(source, destination, base):
    source = Path(source).resolve()
    if source == ROOT or ROOT in source.parents:
        raise ValueError("development checkout must be outside the main workspace")
    destination = new_directory(destination)
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source, text=True)
    if status:
        raise ValueError("development checkout must be clean before export")
    run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=source)
    merges = subprocess.check_output(["git", "rev-list", "--merges", f"{base}..HEAD"], cwd=source, text=True)
    if merges.strip():
        raise ValueError("patch queue must be linear; merge commits cannot be exported")
    changed = subprocess.check_output(["git", "log", "--format=", "--name-only", f"{base}..HEAD", "--", "downstream", "docs/remote-agent-monitoring-handoff.md"], cwd=source, text=True)
    if changed.strip():
        raise ValueError("maintenance files must not be included in application patches")
    old_names = queue()
    old_entries = registry(old_names, require_commands=False)
    destination.mkdir(parents=True)
    run(["git", "format-patch", "--no-signature", "--output-directory", str(destination), f"{base}..HEAD"], cwd=source)
    names = sorted(p.name for p in destination.glob("*.patch"))
    if any(not NAME.fullmatch(name) for name in names):
        raise ValueError("git format-patch produced an unsupported filename")
    (destination / "series").write_text("".join(name + "\n" for name in names))
    entries = {name: old_entries.get(name, {"regression": [], "related": [], "reason": ""}) for name in names}
    (destination / "tests.json").write_text(json.dumps(entries, indent=2) + "\n")
    print(f"Exported {len(names)} patches to {destination}; register tests before installing the queue.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=CONFIG["upstream_commit"], help="candidate full upstream SHA (default: configured pin)")
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare", help="clone the pin and apply the queue into a new directory")
    prep.add_argument("output")
    verify = sub.add_parser("verify", help="prepare a fresh tree and run registered platform tests")
    verify.add_argument("--platform", choices=("linux", "macos", "windows"), required=True)
    exp = sub.add_parser("export", help="export a clean development checkout into a new directory")
    exp.add_argument("source")
    exp.add_argument("output")
    args = parser.parse_args()
    base = base_sha(args.base)
    if args.action == "export":
        export(args.source, args.output, base)
        return
    names = queue()
    entries = registry(names)
    if args.action == "prepare":
        prepare(args.output, base, names)
        return
    actual = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else None
    if args.platform != actual:
        raise ValueError(f"requested {args.platform} verification on {actual or sys.platform}; run on the target platform")
    with tempfile.TemporaryDirectory(prefix="agent-speed-verify-") as temp:
        tree = prepare(Path(temp) / "source", base, names)
        for name in names:
            for category in ("regression", "related"):
                for command in entries[name][category]:
                    if command["platform"] in ("all", args.platform):
                        print(f"{name} [{category}, {command['platform']}]: {command['run']}", flush=True)
                        subprocess.run(command["run"], cwd=tree, shell=True, check=True)
    print(f"Queue and registered {args.platform} commands passed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
