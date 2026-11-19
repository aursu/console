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

Usage: bundle_diff.py [--markdown] [--comment PATH --run-url URL]
                      <base-ref> [<head-ref>]   (head: HEAD)
--comment also writes a PR comment body to PATH: it starts with a hidden
marker (so CI finds and updates the same comment) and stays under GitHub's
size limit, listing by name the files that do not fit.
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
COMMENT_MARKER = "<!-- bundle-diff -->"  # finds the PR comment to update
COMMENT_LIMIT = 60000  # GitHub rejects comment bodies over 65536 characters
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


def _section(change: FileChange, diffs: dict[str, list[str]], markdown: bool) -> str:
    """The output for one changed file."""
    if change.old is None:
        return f"- added: `{change.new.path}`" if markdown else f"added: {change.new.path}"
    if change.new is None:
        return f"- removed: `{change.old.path}`" if markdown else f"removed: {change.old.path}"
    if markdown:
        body = "\n".join(diffs[change.key])
        return f"<details><summary><code>{change.key}</code></summary>\n\n```diff\n{body}\n```\n</details>\n"
    return "\n".join(diffs[change.key])


def _title(base: str, head: str) -> str:
    return f"### Readable bundle diff: `{base}` → `{head}`\n"


def render(changes: list[FileChange], diffs: dict[str, list[str]], base: str, head: str, markdown: bool) -> str:
    out: list[str] = [_title(base, head)] if markdown else []
    if not changes:
        out.append(f"bundle unchanged between {base} and {head}")
    out.extend(_section(change, diffs, markdown) for change in changes)
    return "\n".join(out) + "\n"


def render_comment(
    changes: list[FileChange], diffs: dict[str, list[str]], base: str, head: str, run_url: str, limit: int
) -> str:
    """Markdown for a PR comment of at most `limit` characters.

    Whole file sections are kept, in order, when they fit; a file that does
    not fit is skipped and listed by name, and smaller files after it are
    still shown. The footer points to the run, whose summary has the full
    diff.
    """
    title = f"{COMMENT_MARKER}\n{_title(base, head)}"
    footer = f"\nRebuild check and full diff: {run_url}\n"
    if not changes:
        return f"{title}\nbundle unchanged between {base} and {head}\n{footer}"
    # Room for the worst case: a note naming every file.
    budget = limit - len(title) - len(footer) - len(_omitted_note([c.key for c in changes]))
    kept: list[str] = []
    omitted: list[str] = []
    used = 0
    for change in changes:
        section = _section(change, diffs, markdown=True)
        if used + len(section) + 1 > budget:
            omitted.append(change.key)  # a later, smaller file may still fit
            continue
        kept.append(section)
        used += len(section) + 1
    parts = [title, *kept]
    if omitted:
        parts.append(_omitted_note(omitted))
    return "\n".join(parts) + footer


def _omitted_note(keys: list[str]) -> str:
    names = ", ".join(f"`{key}`" for key in keys)
    return f"\n**Too long for a comment, see the run summary:** {names}\n"


def collect(
    base: str, head: str, git: Git, prettier: Prettier
) -> tuple[list[FileChange], dict[str, list[str]]]:
    """The changed files between the refs and the readable diff of each."""
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
    return changes, diffs


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Readable diff of the committed UI bundle.")
    parser.add_argument("--markdown", action="store_true", help="output for a GitHub job summary")
    parser.add_argument("--comment", metavar="PATH", help="also write a PR comment body (Markdown) to PATH")
    parser.add_argument("--run-url", metavar="URL", help="link to the CI run, in the comment footer")
    parser.add_argument("base", help="base ref, e.g. origin/master")
    parser.add_argument("head", nargs="?", default="HEAD", help="head ref (default: HEAD)")
    args = parser.parse_args(argv)
    if args.comment and not args.run_url:
        parser.error("--comment needs --run-url")
    try:
        changes, diffs = collect(args.base, args.head, Git(), Prettier())
        sys.stdout.write(render(changes, diffs, args.base, args.head, args.markdown))
        if args.comment:
            body = render_comment(changes, diffs, args.base, args.head, args.run_url, COMMENT_LIMIT)
            with open(args.comment, "w", encoding="utf-8") as comment:
                comment.write(body)
    except BundleDiffError as error:
        print(f"bundle_diff: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
