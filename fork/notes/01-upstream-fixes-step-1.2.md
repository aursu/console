# 01 — Upstream UI fixes 9e0416f and 33a7fbb (plan step 1.2)

Date: 2026-11-19. PR: aursu/console#5. Plan: aursu/minio
`fork/reports/04-plan-final-build.md`, step 1.2.

## Context: why upstream fixes have to be carried over at all

This repository restores the **full** MinIO console. Its tree is upstream's
`v1.7.6` (aursu/console#1). Upstream kept working on the console after
v1.7.6, but on a line that was about to drop most of it:

- `63c6d89` (2025-03-11) "simplified Console" removed the admin, IAM, SSO
  and monitoring screens.
- v2.0.x was released from that simplified line. Then the repository was
  deleted.

So between v1.7.6 and the end of upstream there are **31 commits**. Some are
fixes to code we still ship: the object browser, permissions, forms and
dependencies. A plain restore of v1.7.6 rolls those fixes back. Every such fix
we do not carry over is a bug or a security issue that upstream already solved
and that we would ship again.

The rule for carrying them over:

- **Original commits only, cherry-picked with `-x`.** Authorship and a
  pointer to the upstream commit are kept, so every line can be traced to
  upstream.
- **The bundle is rebuilt in the same PR.** The console serves `web-app/build`
  embedded in its Go binary. A UI fix that exists only in `web-app/src` never
  reaches a browser.
- **Upstream's own checks are the tests**: warnings, prettier, dead code, and
  `yarn test`.

This step became possible only after step 1.3 (aursu/console#4). Before it,
`yarn install` could not fetch `mds` (`github.com/minio/mds` is 404), so
nothing on the UI side could be built or tested.

## Commit 1 — `9e0416f` "Allow console to recognize s3.Delete* (#3507)"

Author: Allan Roger Reid, 2025-02-21.

### What it changes

- `permissions.ts`: a new scope `IAM_SCOPES.S3_DELETE_ACTIONS = "s3:Delete*"`,
  also added to the `BUCKET_OWNER` role's scope list.
- The object browser accepts `s3:Delete*` wherever it checked only the
  specific action:
  - `ListObjects.tsx`: deleting selected objects (2 places);
  - `ObjectDetailPanel.tsx`: deleting an object or its versions (3 places);
  - `TagsModal.tsx`: deleting an object tag.
- `accessControl.test.ts`: the two delete-permission tests also pass the
  wildcard scope.
- `package.json` / `yarn.lock`: a `resolutions` entry `jspdf: ^3.0.0`, which
  brings `dompurify` 3.2.4 into the lockfile instead of 2.5.7.
- `Makefile`: prettier's renamed flag (`--loglevel` → `--log-level`).

### Why: the bug

The console decides which buttons to show by comparing the user's policy
**actions as strings** with the scopes a screen needs. A policy that grants
deletion with the wildcard `"Action": ["s3:Delete*"]` is valid IAM. The
server honours it for `DeleteObject`, `DeleteObjectVersion`,
`DeleteObjectTagging` and so on. But the string `s3:Delete*` never equals
`s3:DeleteObject`, so the console **hid or disabled the delete buttons** for
users who were in fact allowed to delete. They had to fall back to `mc`, or
the admin had to spell out every action.

### What it does not do

It does not grant anything. Authorisation is enforced by the server on every
request; the console only shows or hides controls. A user without delete
rights still gets `AccessDenied` from the server, whatever the UI shows. The
change brings the UI in line with what the server already allows.

### The jspdf / dompurify part: what it really changes in our build

The intent upstream was a security bump. In February 2025, DOMPurify 3.2.4
fixed CVE-2025-26791 (XSS), and jsPDF 3.0 pulls DOMPurify 3.x. **In our
build it does not change what is shipped**, which was measured on
2026-11-19:

- The console uses jsPDF only indirectly, through
  `react-component-export-image@1.0.6` and its function
  `exportComponentAsPNG` (the dashboard "download widget as PNG" button,
  `DownloadWidgetDataButton.tsx`).
- That package ships a **prebuilt `dist/index.js` with jsPDF 1.5.3 baked
  in**. Webpack bundles that `dist`, not `node_modules/jspdf`.
- So the `jspdf ^3.0.0` resolution changes `yarn.lock` and `node_modules`
  only:
  - the jsPDF chunk (`8104.*.chunk.js`) is **byte-identical** before and after
    the rebuild, and reports `version="1.5.3"`;
  - **DOMPurify is not in the bundle at all.**

The advisory picture (OSV, 2026-11-19) explains why this matters:

| Package / version | Advisories | Shipped to browsers? |
|---|---|---|
| jsPDF 1.5.3 (inside `react-component-export-image`) | 15 | **yes** |
| jsPDF 2.5.2 / 3.0.0 (lockfile before / after) | 12 / 12 | no |
| DOMPurify 2.5.7 / 3.2.4 (lockfile before / after) | 21 / 22 | no |

The shipped jsPDF 1.5.3 is old and vulnerable, but it is **not reachable**:
the console calls only the PNG export of its own dashboard widgets, and every
jsPDF advisory needs attacker input passed to jsPDF's PDF APIs. It is still
dead, vulnerable code in the bundle, and scanners will flag it. The real fix
is upstream's later commit `7e5f4f3` "Fixed UI security issues and updated
project dependencies (#3556)". It removes `react-component-export-image`
together with its jsPDF, and it is part of plan step 1.4.

We keep the resolution anyway. It is upstream's own change, it keeps the
lockfile free of the older jsPDF/DOMPurify for any future direct use, and
`7e5f4f3` builds on it.

## Commit 2 — `33a7fbb` "Fix regex pattern in webhook management (#3512)"

Author: Quentin JOLY, 2025-03-07.

### What it changes

The client-side validation of the webhook endpoint URL, in both forms
(`AddEndpointModal.tsx`, `EditWebhookEndpoint.tsx`):

```
before  ^(https?):\/\/([a-zA-Z0-9\-.]+)(:[0-9]+)?(\/[a-zA-Z0-9\-.\/]*)?$
after   ^(https?):\/\/([a-zA-Z0-9\-.]+)(:[0-9]+)?(\/[a-zA-Z0-9_\-.\/]*)?$
```

The path part now allows `_`.

### Why: the bug

Underscores are common in webhook paths (`/hooks/minio_events`,
`/api/v1/bucket_notify`). The old pattern rejected every such URL, so the
console refused to save a valid endpoint, while the server would accept it
through `mc admin config set`. The host part is unchanged, so hostnames still
admit only letters, digits, `-` and `.`.

### Risk

Only the UI validation widens, and only by one character in the path. The
server validates and uses the endpoint as before.

## Commit 3 — the rebuilt bundle

Built with the original toolchain (Node 18.20.8, yarn 4.4.0) through
upstream's own `./check-warnings.sh`. Changed files:

| File | Contains |
|---|---|
| `main.*.js` | the `s3:Delete*` scope (9e0416f) |
| `182.*.chunk.js` | object browser delete/tag dialogs (9e0416f) |
| `7052.*.chunk.js` | webhook endpoint form, the new regex (33a7fbb) |
| `asset-manifest.json`, `index.html` | the new file names |

Everything else in the bundle is byte-identical. The first version of this
commit's message attributed chunks 182 and 7052 to jspdf/dompurify. That was a
guess, and it was wrong; the message was corrected before merge.

## How it was verified

Upstream's UI CI steps, run locally on the result:

| Step | Result |
|---|---|
| `yarn install --immutable` | ok |
| `./check-warnings.sh` (build must have no warnings) | ok |
| `./check-prettier.sh` | ok |
| `./check-deadcode.sh` (knip) | ok |
| `yarn test` | 13/13 tests, 2/2 suites, incl. `accessControl.test.ts` |

Go side, with the new bundle embedded: `go build ./cmd/console` ok, and
`go test ./api/... ./pkg/...` passes all 9 packages.

Both fixes were also located in the built files: the regex with `_` in chunk
7052, and `s3:Delete*` in `main`.

## Why not the obvious alternatives

- **Skip post-v1.7.6 upstream fixes and treat v1.7.6 as final.** That
  re-ships bugs upstream had already fixed in code we still serve.
- **Write our own fixes for the same bugs.** That duplicates work upstream
  already did and reviewed. Original commits keep the fork traceable and
  cherry-pickable.
- **Cherry-pick without rebuilding the bundle.** The served UI would not
  change.
- **Bump jsPDF further to a clean version.** It would not help either: the
  shipped copy comes from `react-component-export-image`, whatever the lockfile
  says. Removing that package (`7e5f4f3`, step 1.4) is the fix.
