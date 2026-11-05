"""Create a release-version patch against the prepared downstream tree.

The checkout must have clean queue metadata. Existing release notes are never
replaced. The return value contains paths relative to the checkout root.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-fork\.(0|[1-9][0-9]*))?\Z")


def _git(tree, *args):
    return subprocess.run(["git", *args], cwd=tree, check=True,
                          stdout=subprocess.PIPE, text=True).stdout


def _version_test(path, old, new):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^    def test_fork_default_and_numeric_bundle_versions\(self\):\n.*?(?=^    def |^if __name__|\Z)", text)
    if not match:
        raise ValueError("cannot locate the release-version assertion method")
    old_numeric = old.split("-", 1)[0]
    new_numeric = new.split("-", 1)[0]
    body = match.group()
    expected = [f'"{old}|{old_numeric}|{old_numeric}"',
                f'"__VERSION__", "{old}"',
                f'info["AgentSpeedVersion"], "{old}"',
                f'"__NUMERIC_VERSION__", "{old_numeric}"',
                f'"__BUILD__", "{old_numeric}"',
                f'info["CFBundleShortVersionString"], "{old_numeric}"',
                f'info["CFBundleVersion"], "{old_numeric}"']
    if any(body.count(item) != 1 for item in expected):
        raise ValueError("release-version assertions do not match the prepared VERSION")
    replacements = [f'"{new}|{new_numeric}|{new_numeric}"',
                    f'"__VERSION__", "{new}"',
                    f'info["AgentSpeedVersion"], "{new}"',
                    f'"__NUMERIC_VERSION__", "{new_numeric}"',
                    f'"__BUILD__", "{new_numeric}"',
                    f'info["CFBundleShortVersionString"], "{new_numeric}"',
                    f'info["CFBundleVersion"], "{new_numeric}"']
    for before, after in zip(expected, replacements):
        body = body.replace(before, after, 1)
    return text[:match.start()] + body + text[match.end():]

def _notes(tree, tag, previous, start, end):
    subjects = _git(tree, "log", "--reverse", "--format=%s", f"{start}..{end}").splitlines()
    lines = [f"## {tag}", "", f"Changes since `{previous}` from the downstream patch history:", ""]
    if subjects:
        lines.extend(f"- {subject}" for subject in subjects)
    else:
        lines.append("- No downstream changes recorded since the previous version stamp.")
    return ("\n".join(lines) + "\n").encode("utf-8")


def stamp(root: Path, target_tag: str) -> list[Path]:
    """Replay the queue, append a real version patch, and create release notes.

    Requires Git, Python and access to the configured upstream. Failures leave
    pre-existing checkout files intact, including dirty queue metadata.
    """
    if not isinstance(target_tag, str) or not _TAG.fullmatch(target_tag):
        raise ValueError("release tag must be vX.Y.Z or vX.Y.Z-fork.N")
    root = Path(root).resolve()
    patches = root / "downstream" / "patches"
    series = patches / "series"
    registry = patches / "tests.json"
    note = root / "docs" / "releases" / f"{target_tag}.md"
    version = target_tag[1:]

    with tempfile.TemporaryDirectory(prefix="agent-speed-stamp-") as temp:
        tree = Path(temp) / "source"
        # manage.py requires a non-existent output outside the checkout.
        if tree == root or root in tree.parents:
            raise ValueError("temporary directory must be outside the checkout")
        subprocess.run([sys.executable, str(root / "downstream" / "manage.py"),
                        "prepare", str(tree)], cwd=root, check=True)
        version_file = tree / "VERSION"
        old = version_file.read_text(encoding="utf-8").strip()
        test_file = tree / "tests" / "test_release_version.py"
        updated_test = _version_test(test_file, old, version)
        last_stamp = _git(tree, "log", "-1", "--format=%H", "--", "VERSION").strip()
        if not last_stamp:
            raise ValueError("no VERSION history in the prepared tree")
        changes = {}
        if old != version:
            if note.exists():
                raise FileExistsError(f"release notes already exist: {note}")
            series_bytes = series.read_bytes()
            registry_bytes = registry.read_bytes()
            names = [line.strip() for line in series_bytes.decode("utf-8").splitlines()
                     if line.strip() and not line.strip().startswith("#")]
            number = max((int(name[:4]) for name in names), default=0) + 1
            if number > 9999:
                raise ValueError("patch queue has exhausted four-digit numbering")
            name = f"{number:04d}-Stamp-{target_tag}-release-version.patch"
            patch = patches / name
            if patch.exists():
                raise FileExistsError(f"patch already exists: {patch}")
            entries = json.loads(registry_bytes)
            if name in entries:
                raise ValueError(f"patch already registered: {name}")
            version_file.write_text(version + "\n", encoding="utf-8")
            test_file.write_text(updated_test, encoding="utf-8")
            _git(tree, "add", "--", "VERSION", "tests/test_release_version.py")
            _git(tree, "-c", "user.name=Downstream Patch Queue", "-c",
                 "user.email=downstream@localhost", "commit", "-m", f"Stamp {target_tag} release version")
            patch_bytes = subprocess.run(["git", "format-patch", "-1", "--stdout"], cwd=tree,
                                         check=True, stdout=subprocess.PIPE).stdout
            entries[name] = {"regression": [{"platform": "linux", "run": "python3 tests/test_release_version.py"}],
                             "related": [], "reason": ""}
            changes[patch] = (None, patch_bytes)
            changes[series] = (series_bytes, series_bytes + (b"" if not series_bytes or series_bytes.endswith(b"\n") else b"\n") + name.encode() + b"\n")
            changes[registry] = (registry_bytes, (json.dumps(entries, indent=2, ensure_ascii=False) + "\n").encode())
            changes[note] = (None, _notes(tree, target_tag, old, last_stamp, "HEAD^"))
        elif updated_test != test_file.read_text(encoding="utf-8"):
            raise ValueError("prepared version assertions are inconsistent")
        elif not note.exists():
            previous = _git(tree, "show", f"{last_stamp}^:VERSION").strip()
            previous_stamp = _git(tree, "log", "-1", "--format=%H", f"{last_stamp}^", "--", "VERSION").strip()
            if not previous_stamp:
                raise ValueError("cannot determine the previous version history")
            changes[note] = (None, _notes(tree, target_tag, previous, previous_stamp, f"{last_stamp}^"))

        if not changes:
            return []
        existing = [p for p, (before, _) in changes.items() if before is not None]
        if existing and _git(root, "status", "--porcelain", "--", *(str(p.relative_to(root)) for p in existing)).strip():
            raise ValueError("queue metadata has uncommitted changes; refusing to overwrite it")
        # Stage bytes beside each destination, then restore only our own writes
        # if a later operation fails. Never replace an existing new-file target.
        installed = []
        staged = []
        try:
            for path, (before, after) in changes.items():
                if before is not None and path.read_bytes() != before:
                    raise RuntimeError(f"file changed during stamping: {path}")
                if before is None and path.exists():
                    raise FileExistsError(path)
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".release-stamp-", delete=False) as output:
                    staged.append(Path(output.name))
                    output.write(after)
                os.chmod(staged[-1], (path.stat().st_mode & 0o777) if before is not None else 0o644)
            for (path, (before, after)), temporary in zip(changes.items(), staged):
                if before is None:
                    os.link(temporary, path)
                else:
                    if path.read_bytes() != before:
                        raise RuntimeError(f"file changed during stamping: {path}")
                    os.replace(temporary, path)
                installed.append((path, before, after))
        except BaseException:
            for path, before, after in reversed(installed):
                if path.exists() and path.read_bytes() == after:
                    if before is None:
                        path.unlink()
                    else:
                        path.write_bytes(before)
            raise
        finally:
            for temporary in staged:
                temporary.unlink(missing_ok=True)
        return [path.relative_to(root) for path in changes]
