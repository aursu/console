# 11 — Node 26 and yarn 4.18 (step 1.5, toolchain)

Date: 2026-11-20. PR: aursu/console#18. Plan step 1.5, second half of the
toolchain work; made possible by #17 (canvas 3, note 10). The project owner
chose Node 26 over Node 24.

## What changed

| | Before | After |
|---|---|---|
| Node (`.nvmrc`) | `18`, end-of-life since April 2025 | **`26.13.1`**, the active LTS (supported to April 2029), pinned exactly |
| yarn (`packageManager`) | `yarn@4.4.0` | **`yarn@4.18.1+sha512…`**, set with `corepack use`, so corepack checks the hash |
| `resolutions.node-gyp` | `^11.5.0` | **`^12.4.0`**, which needs Node 20+ |
| corepack in CI | `corepack enable` from the runner's Node, before `setup-node` | `setup-node` from `.nvmrc`, then `npm install -g corepack@0.36.0`, then `corepack enable` |

Production audit: **4 → 2** moderate. node-gyp 12 no longer uses
`make-fetch-happen`/`cacache`, and with them go `glob` 10.5.0 and
`minimatch` 9.0.9. The 2 left are react-router's, fixed only in v7: one is
guarded by #15, the other does not apply (note 07).

## CI: corepack after setup-node, in every job

Node 25+ no longer ships corepack, which every UI job uses to get yarn.
Upstream's jobs ran `corepack enable` **before** `setup-node`, so it worked
through the runner's own Node; with Node 26 there would be no corepack.

All 15 Node setups (13 in `jobs.yaml`, `bundle.yaml`, `vulncheck.yaml`) now
follow the same order:

1. `setup-node` with the version from `.nvmrc`;
2. `npm install -g "corepack@$COREPACK_VERSION"`, defined once per
   workflow;
3. `corepack enable`.

Two side changes:

- `playwright` hard-coded Node 18; it now reads `.nvmrc` like the rest.
- `ui-assets` and `ui-assets-istanbul-coverage` lose `setup-node`'s
  `cache: "yarn"`. That cache needs `yarn` while `setup-node` itself runs,
  which is before corepack can exist for Node 26. Their `yarn install`
  still runs, only without the pre-warmed download cache.

## yarn 4.18: keeping its supply-chain defaults

yarn 4.18 has safer defaults than 4.4. Its migration wrote three settings
into `.yarnrc.yml` that switched all of them off, to keep 4.4's behaviour.
They were replaced with narrow ones:

| Setting | 4.18 default | Written by the migration | Here |
|---|---|---|---|
| `approvedGitRepositories` | none | `"**"` (any git URL) | `https://github.com/aursu/mds.git` only, the one git dependency |
| `enableScripts` | `false` | `true` (every package's install scripts) | `false`; only `canvas` is allowed, via `dependenciesMeta` in `package.json` |
| `npmMinimalAgeGate` | `1d` | `0` (versions published seconds ago are accepted) | the default, `1d` |

- **canvas** needs its install script: it fetches the prebuilt N-API binary
  that Jest's jsdom loads.
- **The other two packages with install scripts** are `core-js` and
  `core-js-pure`. Their `postinstall` only prints a funding banner, so
  skipping it changes nothing.
- **The minimal age gate** means a package version published less than a
  day ago is not resolved. That is a guard against a freshly hijacked
  release. Installs from the lockfile are unaffected.

## What the new toolchain changed in the bundle

Same sources, different Node: the readable bundle diff shows one changed
expression, in chunk `5067`:

```diff
-          const l = 10 ** -4;
+          const l = 1e-4;
```

- **The source** is `pdfjs-dist/build/pdf.mjs:16936`,
  `const EPSILON = 10 ** -NUMBER_OF_DIGITS` (4), a rounding tolerance in
  pdfjs's geometry code.
- **Why it changed:** Terser folds a constant expression into a literal
  only when the result is exact, and V8 changed:
  - Node 18: `10 ** -4` is `0.00009999999999999999`, so Terser left it as
    is;
  - Node 26: `10 ** -4` is exactly `0.0001` (`=== 1e-4`), so Terser folds
    it.
- **Effect:** none in practice. Current browsers compute exactly `0.0001`
  as well.
- **It confirms why `.nvmrc` is pinned to an exact version** and not a
  major: the build output depends on the V8 that runs Terser.

Everything else in the bundle diff is file names and `main`'s chunk-hash
table.

## Why not the obvious alternatives

- **Node 24**, which still ships corepack, would mean less CI churn now. But
  it is already in maintenance, and we would have to move again a year
  sooner. Pinning corepack is the right practice anyway once Node stops
  shipping it.
- **`.nvmrc` with a bare major (`26`).** Each machine could then build with
  a different 26.x, and as shown above, the V8 version can change the
  bundle.
- **Accept the migration's `.yarnrc.yml`.** Blanket opt-outs (`**`,
  scripts for every package, no age gate) would discard 4.18's protections
  for no reason. Each one this project needs is listed explicitly instead.
- **Keep `setup-node`'s yarn cache by enabling corepack on the runner's
  Node first.** That would reproduce the old, confusing arrangement, where
  yarn ran through a corepack from a Node other than the build's Node.

## Not in this PR

- `testcafe` in `package.json` (3.6.2) vs CI's 3.7.7, and the CI's
  unpinned `yarn add minio` in the permissions jobs (note 05). These are a
  separate CI PR.

## Tests

Node 26.13.1, corepack 0.36.0, yarn 4.18.1:

| Check | Result |
|---|---|
| fresh copy without `node_modules`: `yarn install`, then `--immutable` | ok; only canvas built; mds fetched from its approved repository |
| canvas | loads, renders a PNG |
| `./check-warnings.sh`, `./check-prettier.sh`, `./check-deadcode.sh` | ok |
| `yarn test` | 41/41 |
| `yarn build` | ok; bundle differs from Node 18's only by `10 ** -4` → `1e-4` |
| production audit | 4 → 2 (react-router only), nothing new |

CI runs every job on Node 26 through the new corepack steps; this PR is
their first run.
