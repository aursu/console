#!/usr/bin/env python3
"""Readable diff of the committed UI bundle (web-app/build) between two refs.

The bundle is minified, so a plain diff is one changed line per file. This
pairs each JS/CSS file of <base> with the one of <head> by name with the
content hash removed (main.45669c2e.js ~ main.8f3a6a8e.js), formats both with
the repository's own prettier, and diffs the result. Webpack and terser are
deterministic, so only real changes remain; minified names stay. Lines that
change on every rebuild are dropped (sourceMappingURL, the LICENSE.txt
reference, main's chunk-hash table), and so are hunks left without changes.

Needs node and web-app/node_modules (yarn install), e.g.:
    docker run --rm -v "$PWD:/w" -w /w node:18 \\
        python3 -I fork/bin/bundle_diff.py origin/master

Usage: bundle_diff.py [--markdown] <base-ref> [<head-ref>]   (head: HEAD)
Exit status: 0 on success (changes or not), 1 on error.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from dataclasses import dataclass

BUILD_DIR = "web-app/build/static"
PRETTIER = "web-app/node_modules/prettier/bin/prettier.cjs"

_HASHED_SUFFIX = re.compile(r"\.[0-9a-f]{8}(\.chunk)?\.(js|css)$")
_NOISE = (
    re.compile(r"sourceMappingURL="),
    re.compile(r"LICENSE\.txt"),
    re.compile(r'^\s*\d+: "[0-9a-f]{8}",?$'),  # main's chunk-hash table
)


class BundleDiffError(Exception):
    """A user-facing failure: bad ref, missing prettier, git error."""


@dataclass(frozen=True)
class BundleFile:
    """One JS/CSS file of the bundle at some ref."""

    path: str

    @property
    def key(self) -> str:
        """Path below static/ with the content hash removed: js/182.chunk.js."""
        relative = self.path.removeprefix(BUILD_DIR + "/")
        return _HASHED_SUFFIX.sub(r"\1.\2", relative)

    @property
    def parser(self) -> str:
        return "css" if self.path.endswith(".css") else "babel"


@dataclass(frozen=True)
class FileChange:
    """A bundle file that differs between the two refs."""

    key: str
    old: BundleFile | None
    new: BundleFile | None


def pair_changes(old_files: list[BundleFile], new_files: list[BundleFile]) -> list[FileChange]:
    """Pair files by key; a file whose path (content hash) is equal is unchanged."""
    old_by_key = {f.key: f for f in old_files}
    new_by_key = {f.key: f for f in new_files}
    changes = []
    for key in sorted(old_by_key.keys() | new_by_key.keys()):
        old, new = old_by_key.get(key), new_by_key.get(key)
        if old is not None and new is not None and old.path == new.path:
            continue
        changes.append(FileChange(key, old, new))
    return changes


def is_noise(line: str) -> bool:
    return any(pattern.search(line) for pattern in _NOISE)


def readable_diff(old_text: str, new_text: str, old_label: str, new_label: str) -> list[str]:
    """Unified diff without noise lines, and without hunks left with no change."""
    lines = difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(), old_label, new_label, lineterm=""
    )
    header: list[str] = []
    result: list[str] = []
    hunk: list[str] = []

    def flush() -> None:
        if any(line[:1] in "+-" for line in hunk[1:]):
            result.extend(hunk)
        hunk.clear()

    for line in lines:
        if line.startswith(("---", "+++")) and not hunk:
            header.append(line)
        elif line.startswith("@@"):
            flush()
            hunk.append(line)
        elif line[:1] in "+-" and is_noise(line[1:]):
            continue
        else:
            hunk.append(line)
    flush()
    return header + result if result else []


class Git:
    def run(self, *args: str) -> str:
        completed = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise BundleDiffError(f"git {' '.join(args)}: {completed.stderr.strip()}")
        return completed.stdout

    def toplevel(self) -> str:
        return self.run("rev-parse", "--show-toplevel").strip()

    def verify(self, ref: str) -> None:
        try:
            self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except BundleDiffError:
            raise BundleDiffError(f"unknown ref: {ref}") from None

    def bundle_files(self, ref: str) -> list[BundleFile]:
        paths = self.run("ls-tree", "-r", "--name-only", ref, "--", BUILD_DIR).splitlines()
        return [BundleFile(p) for p in paths if p.endswith((".js", ".css"))]

    def show(self, ref: str, path: str) -> str:
        return self.run("show", f"{ref}:{path}")


class Prettier:
    def format(self, text: str, parser: str) -> str:
        completed = subprocess.run(
            ["node", PRETTIER, "--parser", parser], input=text, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            raise BundleDiffError(f"prettier failed: {completed.stderr.strip()}")
        return completed.stdout


def render(changes: list[FileChange], diffs: dict[str, list[str]], base: str, head: str, markdown: bool) -> str:
    out: list[str] = []
    if markdown:
        out.append(f"### Readable bundle diff: `{base}` → `{head}`\n")
    if not changes:
        out.append(f"bundle unchanged between {base} and {head}")
    for change in changes:
        if change.old is None:
            out.append(f"added: {change.new.path}")
        elif change.new is None:
            out.append(f"removed: {change.old.path}")
        elif markdown:
            out.append(f"<details><summary><code>{change.key}</code></summary>\n")
            out.append("```diff")
            out.extend(diffs[change.key])
            out.append("```\n</details>\n")
        else:
            out.extend(diffs[change.key])
    return "\n".join(out) + "\n"


def run(base: str, head: str, markdown: bool, git: Git, prettier: Prettier) -> str:
    os.chdir(git.toplevel())
    if not os.path.isfile(PRETTIER):
        raise BundleDiffError(f"missing {PRETTIER} (run yarn install in web-app)")
    git.verify(base)
    git.verify(head)

    changes = pair_changes(git.bundle_files(base), git.bundle_files(head))
    diffs = {}
    for change in changes:
        if change.old is not None and change.new is not None:
            diffs[change.key] = readable_diff(
                prettier.format(git.show(base, change.old.path), change.old.parser),
                prettier.format(git.show(head, change.new.path), change.new.parser),
                change.old.path,
                change.new.path,
            )
    return render(changes, diffs, base, head, markdown)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Readable diff of the committed UI bundle.")
    parser.add_argument("--markdown", action="store_true", help="output for a GitHub job summary")
    parser.add_argument("base", help="base ref, e.g. origin/master")
    parser.add_argument("head", nargs="?", default="HEAD", help="head ref (default: HEAD)")
    args = parser.parse_args(argv)
    try:
        sys.stdout.write(run(args.base, args.head, args.markdown, Git(), Prettier()))
    except BundleDiffError as error:
        print(f"bundle_diff: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
