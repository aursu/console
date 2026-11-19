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
| `.github/workflows/bundle.yaml` ("UI bundle") | on every PR touching `web-app/`: rebuild the bundle and **fail if it differs** from the committed one; put the readable diff in the Job Summary |

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
- **Post the readable diff as a PR comment.** That needs a token with write
  access in CI. The Job Summary needs none and appears on the run's page.
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
