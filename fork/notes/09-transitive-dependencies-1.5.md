# 09 — Transitive dependencies; tar 7 through two build tools (step 1.5)

Date: 2026-11-20. PR: aursu/console#16. Plan step 1.5, third dependency
PR.

## Result

`yarn npm audit --recursive --environment production`, the command CI's
"React Code Has No Known Vulnerable Deps" job runs:

| | total | critical | high | moderate | low |
|---|---|---|---|---|---|
| before step 1.5 | 99 | 4 | 39 | 45 | 11 |
| after #13 (PNG export) | 63 | 2 | 30 | 27 | 4 |
| after #14 (direct deps) | 50 | 1 | 27 | 19 | 3 |
| **after this PR** | **4** | **0** | **0** | **4** | **0** |

The plan's target for step 1.5, no high or critical, now holds for the
whole production dependency closure, not only for the shipped bundle.

## Within the declared ranges

`yarn up -R`, which moves a package to the newest version its dependents
allow:

| Package | Before → after | Pulled by |
|---|---|---|
| `brace-expansion` | 1.1.11 / 2.0.1 → 1.1.22 / 2.1.8 | minimatch |
| `minimatch` | 3.1.2 / 9.0.5 → 3.1.5 / 9.0.9 | glob |
| `glob` | 10.4.5 → 10.5.0 | node-gyp |
| `picomatch` | 2.3.1 → 2.3.2 | babel-plugin-styled-components |
| `diff` | 5.2.0 → 5.2.2 | uvu |
| `mdast-util-to-hast` | 13.2.0 → 13.2.2 | hast-util-to-html |
| `@babel/runtime` | 7.26.0 → 7.29.14 | react-redux |
| `socks` | 2.8.3 → 2.8.11 | socks-proxy-agent; brings `ip-address` 9.0.5 → 10.7.6 |

## tar: two resolutions

`tar` 6.x has no fix; every advisory needs 7.5.x. It came from
`react-pdf` → `pdfjs-dist` 4.4.168 → **`canvas` 2.11.2**, through two
native-build tools:

- `canvas` is pdfjs's optional native module for rendering PDFs in Node.
  It never runs in the browser: the bundle uses pdfjs's browser build.
  It is in the production closure only because `react-pdf` is a dependency.
- `@mapbox/node-pre-gyp` 1.0.11 downloads canvas's prebuilt binary. Its
  `tar` ^6 is outside what canvas allows to change (`^1.0.0`).
- `node-gyp` 10.2.0, its `cacache` 18 and their `tar` ^6. Yarn injects
  `node-gyp@latest` for packages with native code (canvas, fsevents), and
  that was locked at 10.2.0.

So two entries in `resolutions`:

| Resolution | Declared by dependents | Why it is safe |
|---|---|---|
| `@mapbox/node-pre-gyp` `^2.0.3` | canvas: `^1.0.0` | 2.0 needs Node 18+ and upgrades its own dependencies, including tar 7.4; the CLI that canvas's install script uses (`node-pre-gyp install --fallback-to-build --update-binary`) is unchanged |
| `node-gyp` `^11.5.0` | `latest` (locked 10.2.0) | 11.x supports Node ^18.17 (we build on 18.20.8); tar ^7.4.3; `make-fetch-happen` 14 → `cacache` 19 on tar 7. 12.x would need Node 20 and waits for the toolchain PR |

Result: one `tar`, 7.5.23.

**Verified:** with both overrides, `canvas` installs, loads and renders a
PNG in Node.

## What reaches the browser

Only `main` changes in the bundle. The readable diff shows two Babel
helpers from `@babel/runtime` 7.29: `objectWithoutProperties` uses
`indexOf` instead of `includes`, and `toPrimitive` checks that `Symbol`
exists. Same behaviour, broader compatibility. Nothing else in the shipped
code changed. Everything else in this PR is build-time or Node-side.

## What remains (4, all moderate)

- **react-router** ×2, fixed only in 7.18:
  - the backslash open redirect, which is reachable but guarded by our
    validation since #15 (note 08);
  - the SSR `deserializeErrors()` advisory, which does not apply because
    the console renders on the client only.
- **`glob` 10.5.0** and **`minimatch` 9.0.9**, under node-gyp 11's
  `cacache` 19, one moderate each. The fix needs glob 15, a major upgrade
  in build tooling that never reaches the browser. node-gyp 12 (with the
  Node LTS toolchain PR) may remove them.

## Why not the obvious alternatives

- **Remove `canvas`.** It is an optional dependency of `pdfjs-dist`.
  Yarn has no clean way to drop an optional dependency from the lockfile,
  and stubbing it out with a fake package is a hack. The resolutions keep
  it working and fix the tooling under it.
- **`resolutions: { "tar": "^7.5" }` directly.** It would force tar 7 into
  node-pre-gyp 1.x and node-gyp 10, which were written for tar 6's API.
  Moving the tools to their own versions that already use tar 7 keeps each
  package with a dependency it was written for.
- **canvas 3.** pdfjs-dist 4.4 asks for canvas ^2.11.2. Forcing a major of
  a native module is a larger risk than updating its install tooling.

## Tests

| Check | Result |
|---|---|
| `yarn install --immutable` | ok |
| `yarn why` | one `tar` (7.5.23), node-pre-gyp 2.0.3, node-gyp 11.5.0, cacache 19.0.1, the versions above |
| `canvas` in Node: require, draw, encode PNG | ok (105-byte PNG) |
| `./check-warnings.sh`, `./check-prettier.sh`, `./check-deadcode.sh` | ok |
| `yarn test` | 41/41, 4/4 suites |
| bundle | only `main`: two `@babel/runtime` helpers |
| production audit | 50 → 4, nothing new |
