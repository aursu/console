# 02 — Reviewing the UI bundle: proof it matches the sources, and a readable diff

Date: 2026-11-19. Follows aursu/console#5, where a bundle change could only be
reviewed as one huge line per file.

## The problem

`web-app/build` is committed. `web-app/assets.go` embeds it
(`//go:embed build/*`), so `go build` of the console, and of the MinIO server
that imports it as a module, works without Node.js. Every UI fix therefore
lands as two things in a PR:

- **the sources** (`web-app/src`), which are readable;
- **the rebuilt bundle**: minified JS/CSS whose content hash is in the file
  name, so each changed file shows as one deleted and one added file, each a
  single line hundreds of kilobytes long.

That raises two questions a reviewer could not answer:

1. **Is the committed bundle really built from the committed sources?**
   Nothing checked it. A PR could carry a bundle built from other code.
2. **What changed in the shipped code?** GitHub shows a minified diff as
   unreadable.

## What this adds

| Part | Effect |
|---|---|
| `.gitattributes`: `web-app/build/** linguist-generated=true` | GitHub collapses bundle files in PR diffs; the review starts from the sources |
| `fork/bin/bundle_diff.py` (+ `fork/test/test_bundle_diff.py`) | readable diff of the bundle between two refs; unit-tested |
| `.github/workflows/bundle.yaml` ("UI bundle") | on every PR touching `web-app/`: rebuild the bundle and **fail if it differs** from the committed one; put the readable diff in the Job Summary and in a PR comment (see below) |

### How the readable diff works

`bundle_diff.py <base> [<head>]` lists the JS/CSS files of `web-app/build/static`
at both refs. It pairs them by name with the content hash removed
(`main.45669c2e.js` ↔ `main.8f3a6a8e.js`, `182.6e133743.chunk.js` ↔
`182.7256c0d0.chunk.js`), formats both sides with the repository's own
prettier (the version pinned by `yarn.lock`), and makes a unified diff. Lines
that change on every rebuild are dropped (`sourceMappingURL`, the `LICENSE.txt`
reference, `main`'s chunk-hash table), and so are hunks left with no change.

This works because webpack and terser are deterministic: unchanged code
minifies to the same output, so only real changes remain. Minified names
(`r.OV`, `ze`) stay, but the logic is visible. On aursu/console#5 the whole
bundle diff came to 23 lines:

- the `s3:Delete*` scope;
- its use in five object browser checks;
- the webhook regex in two forms.

Each line maps to a line of the cherry-picked source changes.

Local use (needs `web-app/node_modules`):

```sh
docker run --rm -v "$PWD:/w" -w /w node:18 python3 -I fork/bin/bundle_diff.py origin/master
```

From a git worktree, also mount the main repository at its real path; the
worktree's `.git` file points there.

### Why the rebuild check can be exact

Building twice from the same sources with the same toolchain gives identical
files. Verified on 2026-11-19: `master` after #5 rebuilt with Node 18.20.8 and
yarn 4.4.0 gives **zero** differences in `web-app/build`, `.map` files
included. Upstream's own v1.7.6 bundle reproduced in 243 of 244 files (#4). The
one difference was a source map built before upstream ran prettier, and #5's
rebuild removed it.

The job uses Node from `.nvmrc` and `yarn install --immutable`, so a toolchain
change is itself a reviewed change.

## The diff as a PR comment (added after #7)

On #7 the readable diff existed, but only in the Job Summary, on the run's
page (Checks → UI bundle → Summary). From the PR's "Files changed" tab, where a
reviewer looks, it could not be found. GitHub always shows committed files
there as they are; `linguist-generated` only collapses them.

So the job now also keeps **one comment on the PR** with the same diff:

- `bundle_diff.py --comment PATH --run-url URL` writes the comment body next
  to the normal output, from the same run (prettier runs once).
- The body starts with a hidden marker, `<!-- bundle-diff -->`. The workflow
  looks for a comment by `github-actions[bot]` with that marker and edits it;
  if there is none, it creates one. A push updates the comment, it does not add
  another.
- GitHub rejects comments over 65,536 characters. The body is kept under
  60,000: whole file sections are kept when they fit, a file that does not fit
  is listed by name, and smaller files after it are still shown. The footer
  links to the run, whose summary always has the full diff.
- The job gets `pull-requests: write`, job-level only; the workflow default
  stays `contents: read`.
- PRs from forks are skipped: GitHub gives them a read-only token. All PRs
  here come from branches of aursu/console.

**Correction.** The first version of this note rejected a PR comment because
it "needs a token with write access in CI". That was wrong: the workflow's
built-in `GITHUB_TOKEN` can comment once the job is granted
`pull-requests: write`. No stored secret or app is involved.

Why the shell calls `gh api` instead of a marketplace "sticky comment" action:
the token can write to the PR, and a third-party action would get that
access. `gh` is preinstalled on the runner, and the lookup-and-update is five
lines.

## Why Python and not a shell script

The first version was bash. Its job is mostly pairing and filtering data,
which bash does poorly: two `awk` lookups per file to pair names, `sed`
escaping to strip hashes, `grep -v` over diff text, and `printf` for Markdown.
In Python it is a `dict`, one `re.sub`, `difflib` with a pattern list, and
plain strings, and the pure parts are unit-tested without git or node.
Python 3 is already present wherever the tool runs: the `ubuntu-24.04` runner
and the `node:18` image. Node is needed anyway, for prettier. A Node.js
script would avoid the second runtime, but would add a third language to the
repository's tooling for no gain over Python's standard library.

## Why not the obvious alternatives

- **Stop committing the bundle; build it in CI or at release.** `go build`
  of the server pulls this module and needs the files present (`go:embed`).
  Without them, the server build would need Node.js.
- **Keep source maps out of the repo.** They are part of what upstream
  shipped. Dropping them changes the artifact and is a separate decision.
- **`-diff` in `.gitattributes`.** It would hide bundle changes from local
  `git diff` too, while `linguist-generated` only collapses them on GitHub.

## Tests

- `bundle_diff.py`:
  - 11 unit tests (`python3 -I -m unittest discover -s fork/test`) cover
    pairing by key, noise filtering, dropping noise-only hunks and both output
    formats; they need neither git nor node, and the CI job runs them first;
  - ruff: clean;
  - on #5's change (`5e0dbc3df` → `f3f503e2f`): exactly the 3 changed files and 23 changed lines, with no noise;
  - `--markdown` gives collapsible sections;
  - the same ref twice gives "bundle unchanged";
  - an unknown ref exits 1 with a message.
- The rebuild check, simulated locally on `master`: `yarn build`, then
  `git status --porcelain -- web-app/build` is empty.
- The workflow runs on its own PR (its path filter includes itself).

Tests of the PR comment:

- 5 more unit tests (16 in all): the marker first and the run link last; the
  unchanged bundle; a file too large for the limit is named and the result
  stays under it; a smaller file after it is still shown; in Markdown, added
  and removed files are list items.
- ruff: clean. Two `l` variable names in the #6 tests were renamed; the note
  above called them clean, but they were not.
- On #7's real change (`64ed2db7d` → `35ec5295f`): the comment is 28 KB and
  carries both files. With the limit forced to 3,000 characters, it is 1,016
  characters long: `main.js` is shown, and `182.chunk.js` is named with a
  pointer to the run.
- actionlint 1.7.7 (with shellcheck): clean.
- The workflow posts on its own PR, so the PR itself shows the comment (in
  this case "bundle unchanged", since the PR does not touch the bundle).
