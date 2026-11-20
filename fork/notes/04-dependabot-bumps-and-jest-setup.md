# 04 — Upstream Dependabot bumps, and the Jest setup they needed

Date: 2026-11-20. PR: aursu/console#9. Plan step 1.4 (aursu/minio
`fork/reports/04-plan-final-build.md`); rows 8 and 9 of note 03.

## What this takes

Two upstream Dependabot commits, cherry-picked with `-x`. Each touches only
`web-app/yarn.lock`:

| Commit | Change | Advisories fixed (OSV, 2026-11-19) |
|---|---|---|
| `ff2b72f` | `http-proxy-middleware` 2.0.7 → 2.0.9 | GHSA-4www-5p9h-95mh (CVE-2025-32996), GHSA-9gqv-wp59-fq42 (CVE-2025-32997), both moderate |
| `6df2db8` | `formidable` 3.5.2 → 3.5.4 (`hexoid` replaced by `@paralleldrive/cuid2`) | GHSA-75v8-2h7p-7m2m (CVE-2025-46653), low |

Neither package reaches a browser:

- `http-proxy-middleware` comes in through `webpack-dev-server`, so it runs
  only in `yarn start`, the local development server.
- `formidable` comes in through `superagent`, but only through its **Node**
  entry. The bundle uses superagent's browser build, which has no formidable.

The rebuilt bundle is byte-identical to the committed one. The value of the
bumps is a lockfile without known advisories in these two packages, which is
what scanners and step 1.5 measure.

## Why our own commit sits between them

With `formidable` 3.5.4, `yarn test` failed:

```
FAIL src/common/SecureComponent/__tests__/accessControl.test.ts
  ReferenceError: TextEncoder is not defined
    at utf8ToBytes (node_modules/@noble/hashes/src/utils.ts)
    ...
    at node_modules/formidable/dist/index.cjs
    at node_modules/superagent/src/node/index.js
    at src/common/api/index.ts
```

The test imports `accessControl.ts`, which imports the store and the API
client (`src/common/api/index.ts`), which imports `superagent`. Under Jest,
superagent loads its Node entry, and so formidable, `cuid2` and
`@noble/hashes`. `@noble/hashes` calls `TextEncoder` when the module is
imported. Node defines it, but Jest's `jsdom` environment (Jest 27 in
`react-scripts` 5) does not.

**Upstream never saw this.** `63c6d89`, the simplified console, deleted all UI
tests, and upstream took this bump after that. This fork keeps the tests, so
the fix is ours:

- `web-app/src/setupTests.ts`. `react-scripts` loads it before every test
  file, by its name. It copies `TextEncoder` and `TextDecoder` from Node's
  `util` onto `globalThis`.
- `web-app/knip.config.ts` lists it as an entry. Nothing imports it, so the
  dead-code check reported it as an unused file.

The commit comes **before** the formidable cherry-pick, so every commit of the
PR passes the tests.

## Why not the obvious alternatives

- **Hold `formidable` at 3.5.2.** That keeps an advisory in the lockfile in
  order to keep a test environment unchanged. The test environment is what is
  missing something, not formidable.
- **Map `superagent` to its browser build in Jest (`moduleNameMapper`).** That
  is closer to what runs in production. But it puts a path inside
  `node_modules/superagent` into the Jest config, which breaks silently when
  superagent changes its layout. It also changes what every test loads, to
  fix a single missing global.
- **Switch Jest to `testEnvironment: node`.** The tests use the DOM through
  React, so they need jsdom.
- **Mock `superagent` in the test.** It would hide the import chain in this
  test only. The next test that imports the API client would fail the same
  way.

## Still open, for step 1.5

`http-proxy-middleware` 2.0.9 still has GHSA-64mm-vxmg-q3vj (CVE-2026-55602,
moderate: `router` matching by Host header). It is fixed in 2.0.10, which no
upstream commit reaches. It affects the local development server only. Step
1.5 updates it with the other dependencies.

## Verification

Run in `node:18.20.8` with yarn 4.4.0 (corepack), the toolchain the bundle is
built with. Each line is a run at a commit of this PR.

| Check | after `ff2b72f` + setup | after `6df2db8` (PR head) |
|---|---|---|
| `yarn install --immutable` | ok | ok |
| `./check-warnings.sh` (production build, no warnings) | ok | ok |
| `./check-prettier.sh` | ok | ok |
| `./check-deadcode.sh` (knip) | ok | ok |
| `yarn test` | 13/13, 2/2 suites | 13/13, 2/2 suites |
| `web-app/build` after the rebuild | unchanged | unchanged |

Before the setup file existed, formidable 3.5.4 gave 1 failed suite (the
failure above). `yarn why` confirms both dependency chains:
`webpack-dev-server` → `http-proxy-middleware` 2.0.9, and `superagent` →
`formidable` 3.5.4 → `@paralleldrive/cuid2` 2.2.2.

## Closed: http-proxy-middleware 2.0.12 (#22, 2026-11-20)

The item above was planned for step 1.5 but left out of its PRs; noticed
when marking the step done. `webpack-dev-server`'s range (`^2.0.3`)
allows the fix, so `yarn up -R http-proxy-middleware` moves 2.0.9 to
2.0.12, the last 2.x. It is used only by the development server: the bundle
does not change, and the full (not only production) audit no longer lists
it.

Seen on the way, not acted on: without `--no-deprecations`, the audit also
reports two **deprecation** notices. They are not vulnerabilities. Both are
major upgrades for later:

- recharts 2.x, superseded by v3;
- superagent 9, superseded by v10.2.2+.

CI's audit runs with `--no-deprecations` and stays clean.

Tests: `yarn install --immutable`; `yarn test` 41/41; prettier and
dead-code checks ok; build ok with the bundle unchanged.
