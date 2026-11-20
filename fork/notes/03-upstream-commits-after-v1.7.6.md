# 03 — Upstream commits after v1.7.6: what is taken, what is not, and why

Date: 2026-11-19. Plan step 1.4 (aursu/minio `fork/reports/04-plan-final-build.md`).
First PR of the step: aursu/console#7.

## Why every commit gets a decision

The fork's console is upstream's `v1.7.6` tree (aursu/console#1). Upstream
made **31 commits** after it (`v1.7.6..2017f33b2`) before the repository was
deleted. Most of them belong to the "simplified Console" line that removed the
features this fork exists to keep. A few fix code the full console still ships.
Taking a commit blindly could remove features. Skipping one blindly re-ships a
bug that upstream had already fixed. So each of the 31 has a decision and a
reason below.

How taken commits are applied:

- cherry-picked with `-x`, with original authorship kept;
- any conflict resolution is described in the commit message;
- the bundle is rebuilt in the same PR;
- upstream's UI checks and `yarn test` must pass;
- the "UI bundle" job proves that the bundle matches the sources.

## Decisions

| # | Commit | Subject | Decision |
|---|---|---|---|
| 1 | `9e0416f` | Allow console to recognize s3.Delete* | **taken**, #5 (step 1.2) |
| 2 | `36d0e78` | Updated Project dependencies | superseded by step 1.5 (see below) |
| 3 | `33a7fbb` | Fix regex pattern in webhook management | **taken**, #5 (step 1.2) |
| 4 | `63c6d89` | Implemented AGPL MinIO Object Browser simplified Console | **not taken**: the removal this fork reverses |
| 5 | `71b1b70` | Clean-up after PR 3509 | not taken: removes admin APIs left after #4 |
| 6 | `6499469` | Update jwt package | **taken**, #26 (step 1.6): jwt/v4 4.5.1 → 4.5.2, govulncheck 13 → 12 |
| 7 | `f5ad4de` | Updated Packages & versions | superseded by step 1.5 |
| 8 | `ff2b72f` | Bump http-proxy-middleware 2.0.7 → 2.0.9 | **taken**, #9 |
| 9 | `6df2db8` | Bump formidable 3.5.2 → 3.5.4 | **taken**, #9, with our Jest setup fix (note 04) |
| 10 | `28b0801` | Fixed vulnerabilities in go packages | superseded by #27 (step 1.6): its x/net 0.38 is still vulnerable; x/net 0.60.0 instead, and its vulncheck Go pin by #23 |
| 11 | `40c4ce7` | License Comparisson updates | not taken: commercial licence comparison page |
| 12 | `ee974a5` | Release v2.0.0 | not taken: release commit of the simplified line |
| 13 | `e2bbf91` | Vacuum Swagger | not taken: removes ~24k lines of API (admin) |
| 14 | `3dc0fdc` | Remove more unused APIs | not taken: removes further APIs and their CI jobs |
| 15 | `7871f6b` | UI Forms Cleanup | **not taken**: deletes `LoginCallback.tsx`, the **SSO login callback** |
| 16 | `0398c69` | Updated design of License page | not taken: commercial licence page |
| 17 | `a4281ed` | Updated project dependencies | superseded by step 1.5 |
| 18 | `220a555` | Release v2.0.1 | not taken: release commit |
| 19 | `5553e7e` | Update README.md screenshots | not taken: screenshots of the simplified UI |
| 20 | `ecce093` | docs: add more color to the readme | not taken: README of the simplified product |
| 21 | `e479c7b` | Decreased Browser direct download threshold to 5GiB | **taken**, #7 |
| 22 | `7e5f4f3` | Fixed UI security issues and updated project dependencies | superseded by step 1.5 (dependency bumps only) |
| 23 | `6aee1e0` | Privacy policy | not taken: text in the commercial licence consent modal |
| 24 | `40bee68` | Fixed Search bucket input interaction | not taken: fixes the simplified console's sidebar filter, which the full console does not have (see below) |
| 25 | `2595faf` | Release v2.0.2 | not taken: release commit |
| 26 | `7d96079` | License modal improvements | not taken: licence modal + dependency bumps |
| 27 | `3d6c4cb` | Release v2.0.3 | not taken: release commit |
| 28 | `a2dfcce` | Fix download option in file preview | **taken**, #7 |
| 29 | `ffaa993` | Update doc links to new docs subdomain | not taken: the new `docs.min.io` paths now redirect to AIStor documentation |
| 30 | `88cd0d4` | Add a "+" sign after version number and total size if > 20 versions | **taken**, #7 (conflict resolved, see below) |
| 31 | `2017f33` | Release v2.0.4 | not taken: release commit |

## Taken in #7

- **`e479c7b`** (Alex). Above 5 GiB instead of 50 GiB, a download goes
  straight to the browser instead of through the console's in-page object
  manager, which holds the file in memory. 5–50 GiB files no longer exhaust the
  browser tab.
- **`a2dfcce`** (SSushmitha8). The "Download" button in file preview passed
  the object's `path` where `downloadObject` expects the object name, so the
  download from preview failed or fetched the wrong key. It now passes
  `objectName`.
- **`88cd0d4`** (Nico). The versions list asks the server for at most 21
  versions (`limit: 21`). When there are more than 20, the count and total
  size show a "+" (e.g. "20+ versions"), so the console no longer presents a
  truncated list as complete.
  - Conflict: in `MenuWrapper.tsx` and `Login.tsx` upstream only re-wrapped a
    `docs.min.io` link (prettier), on lines that differ in this tree. Those
    two files were kept as they are; the change itself, in
    `ObjectDetailPanel.tsx` and `VersionsNavigator.tsx`, applied unchanged.

## Dependency commits: why they are superseded, not cherry-picked

`36d0e78`, `f5ad4de`, `a4281ed` and `7e5f4f3` are dependency snapshots
(package.json + yarn.lock). Each conflicts here in `web-app/yarn.lock`: the
lockfile already differs from upstream's at that point (`mds` from
aursu/mds, the `jspdf` resolution of #5). Resolving a lockfile conflict means
regenerating the lockfile. That is no longer upstream's lockfile but a new
resolution, and a series of four such regenerations would be four
unreviewable lockfiles leading to versions that are outdated today. Step 1.5
does the same job once, with current versions:

- Node LTS, yarn 4.x;
- direct dependencies updated within their majors, transitive ones via
  `resolutions`;
- target: no high or critical advisory in the shipped bundle.

The two Dependabot bumps (`ff2b72f`, `6df2db8`) apply cleanly with their
lockfile hunks, so they are taken as upstream made them, in #9. The formidable
bump broke `yarn test` here, because upstream had already deleted its tests.
The fix is ours, see note 04.

**Correction recorded in note 01:** `7e5f4f3` does not remove
`react-component-export-image`. Upstream removed it in `63c6d89` together with
the dashboard; the full console keeps both. Removing the shipped jsPDF 1.5.3
is our own change, in step 1.5.

## `40bee68` — not taken, nothing to reimplement

Decided 2026-11-20. "Fixed Search bucket input interaction" changes
`Menu/Listing/BucketFiltering.tsx` and `Menu/Listing/BucketsListing.tsx`, and
bumps `mds` from 1.1.3 to 1.1.4.

**What it fixes.** `63c6d89`, the simplified console, replaced the full
console's navigation with a left sidebar that lists buckets and has a
filter input on top. With the sidebar collapsed, that input was hidden and
could not be used. The fix:

- adds a search icon to the collapsed sidebar, which expands the sidebar and
  focuses the input;
- hides the "No Results" box while the sidebar is collapsed.

The bump to `mds` 1.1.4 is for the `ref` on `InputBox` that the focus needs.

**Why it does not apply here.**

- `Menu/Listing/` does not exist in this tree. Upstream created both files
  in `63c6d89`, and they were never part of v1.7.6.
- The full console filters buckets on the page, not in the sidebar: a
  `SearchBox` in the action bar of `Buckets/ListBuckets/ListBuckets.tsx` and
  of `ObjectBrowser/OBBucketList.tsx`, with local state. It is visible
  whatever the sidebar's state, so the bug cannot occur.
- Nothing else in the commit is a fix for code we ship, and nothing here
  needs `mds` 1.1.x.

With this, every one of the 31 commits has a final decision. Still to do
from this table:

- the dependency snapshots, superseded by step 1.5;
- `6499469` and `28b0801`, the Go modules, in step 1.6.

## Readable diff: a limitation seen here

For #7 the readable bundle diff (`fork/bin/bundle_diff.py`) shows 279 changed
lines for three small fixes. 277 of them are in chunk `182`. The real changes
are a few lines:

- `limit: 21` twice;
- the `"+"`;
- the `downloadFile` callback.

The rest are the **minifier renaming local variables**: when a function gains
a variable, terser reassigns short names (`we` → `Ce`), and every line using
them changes. The logic of those lines is unchanged. A possible improvement to
the tool is to mark lines that differ only in short identifiers. Not done
yet.

## Verification of #7

| Step | Result |
|---|---|
| `yarn install --immutable` | ok |
| `./check-warnings.sh` | ok |
| `./check-prettier.sh` | ok |
| `./check-deadcode.sh` | ok |
| `yarn test` | 13/13 tests, 2/2 suites |
| `go build ./cmd/console` + `go test ./api/... ./pkg/...` | ok, 9/9 packages |
| all three fixes located in the built bundle | `main` (5 GiB threshold), `182` (`limit: 21`, `"+"`, preview `downloadFile`) |
