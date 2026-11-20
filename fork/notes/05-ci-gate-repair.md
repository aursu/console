# 05 — Repairing the console CI gate

Date: 2026-11-20. PR: aursu/console#10. Same purpose as step 0.2 in aursu/minio
(report `fork/reports/05-ci-gate-repair.md` there): CI must work as the PR
gate before more UI changes go in.

## What was broken

On #7 and #9, 15 jobs failed. None of the failures came from the PRs
themselves. Two causes:

| Cause | Jobs |
|---|---|
| **The upstream MinIO distribution is gone.** `quay.io/minio/minio` and Docker Hub's `minio/minio` / `minio/mc` refuse pulls, and `dl.min.io` answers 410 | Permissions Tests 1–6, A, B; playwright; Subpath with Nginx (start `quay.io/minio/minio:latest`); Integration, SSO (build `FROM minio/minio:latest`) |
| **React Tests had no `setup-node` step.** It ran on the runner's default Node, not 18 from `.nvmrc`; jsdom then failed to load the native `canvas` module | React Tests |

An earlier status ("console CI mostly green, two expected reds") was wrong.
These jobs were already red, and nobody had looked at them.

State of the external dependencies on 2026-11-20:

| Dependency | State |
|---|---|
| `quay.io/minio/minio`, `minio/minio`, `minio/mc`, `quay.io/minio/mc` | gone |
| `dl.min.io` (mc download) | HTTP 410 |
| `github.com/minio/minio` | archived, still clonable |
| `quay.io/minio/openldap`, `quay.io/minio/dex`, `ghcr.io/dexidp/dex` | still served |
| `ghcr.io/aursu/minio/minio:RELEASE.2025-03-12T18-04-18Z` | the fork's copy, the only tag |

## What changed

1. **React Tests: Node from `.nvmrc`**, like every other UI job. Corepack
   is enabled after `setup-node`, so the yarn shim belongs to that Node.
2. **One test-server image.** In the `Makefile`:
   - `MINIO_VERSION` defaults to the fork's
     `RELEASE.2025-03-12T18-04-18Z` image, pinned by digest. It is the image
     aursu/minio's own Dockerfile builds on.
   - The ten hard-coded `quay.io/minio/minio:latest` now use
     `$(MINIO_VERSION)`.
   - The SSO target's `minio/mc` client container also uses the server
     image, which ships `/usr/bin/mc`.
3. **mc from the server container.** `initialize-env.sh` and
   `cleanup-env.sh` take mc with `docker cp minio:/usr/bin/mc` instead of
   downloading it. The client is then always the one shipped with the server
   under test.
4. **Server built from aursu/minio.** The "Build latest MinIO", Integration
   and SSO jobs:
   - clone `aursu/minio` instead of `minio/minio`;
   - take Go from its `go.mod` (1.24, toolchain 1.24.8), not the 1.23.x
     matrix.

   The step that picks a same-named branch of the MinIO repository is kept:
   a console branch can still be tested against a matching aursu/minio
   branch. The integration job's unused mc download is removed.
5. **Coverage is no longer uploaded to `play.min.io`.** That is MinIO's
   public demo server. It still answers, so a repaired coverage job would have
   published this fork's reports to a third party. The threshold check, which
   is the gate, stays.

## Why these choices

- **mc from the server image, not built from aursu/mc** (aursu/minio's
  `install-mc.sh`). The console tests need a client for `admin policy` and
  `admin user`. Building mc needs Go and the aursu/minio checkout in every
  permissions job, about a minute each. The pinned server image already
  carries a client of the same release (`RELEASE.2025-03-12T17-29-24Z`), and
  `docker cp` takes it from the container the test has just started. The
  only reason to build mc would be a newer client, and these tests do not
  need one.
- **A pinned release image for the permissions jobs, a source build for
  Integration and SSO.** This keeps the split upstream already had:
  - the permissions, playwright and subpath jobs ran a released image;
  - Integration and SSO built the server from source, SSO with this console
    swapped in.

  Building the server in eleven more jobs would add minutes to every PR and
  test nothing more about the console.
- **The image is pinned by digest.** A moving tag would let a test server
  change under a console PR. This also follows the aursu/minio Dockerfile.
- **Not mirroring `quay.io/minio/openldap` and `dex` now.** They still
  resolve. If they disappear, the SSO job fails at `docker run` with a clear
  message, and they get mirrored to `ghcr.io/aursu` then.

## Not changed

- `web-app/tests/scripts/operator.sh` still downloads mc from `dl.min.io`.
  It belongs to the old operator tests, and no job runs it.
- `actions/checkout@v3` (28 uses) and the shellcheck notes that actionlint
  reports. They were there before; the branch adds none (compared with
  master: the same or fewer findings in every category).

## Verification

Local:

| Check | Result |
|---|---|
| `make -n` of the permissions targets | the pinned image, quoted, digest included |
| mc taken with `docker cp` from a container of the pinned image | `RELEASE.2025-03-12T17-29-24Z` |
| that mc against that server: the 28 policies of `web-app/tests/policies`, `admin user add`, `admin policy attach` | all ok |
| aursu/minio master `56c24cddd` + `replace github.com/minio/console => <this tree>`, Go 1.24.8: `go mod tidy`, `go mod tidy -compat=1.23`, `go build` | ok, so the SSO job's server build works with the full console |
| actionlint 1.7.7 | no new findings |

In CI: this PR runs every repaired job. The results are in the PR.

## Result of #10, and the second pass (#11)

#10 was merged before its CI finished, and the repair turned out to be
partial. The PR description had presented it as complete before any
repaired job had run. A repair is done only when the jobs it repairs are
green.

| Job | After #10 |
|---|---|
| React Tests | **green** |
| Permissions 1–6, A, B; Subpath | MinIO and mc setup green (28 policies, all users); then **TestCafe failed**: "Firefox 160 browser disconnected", 13/13 |
| Integration | builds and runs; **2 tests failed** (`TestAddRemoteBucket`, `TestDeleteRemoteBucket`) |
| SSO | **`mc alias set`: connection refused** |
| playwright | **"Playwright requires Node.js 20 or higher"** |

Each has its own cause, and #11 fixes each in its own commit:

1. **TestCafe 3.5.0 does not work with Firefox 160.** Reproduced locally on
   Ubuntu 24.04 with Mozilla's Firefox 160.0.1 and Node 18.20.8, on a
   one-line test page: 3.5.0 hangs until killed (exit 124), 3.7.7 passes in
   3 s. The jobs now install 3.7.7. `web-app/package.json` still pins 3.6.2;
   aligning it changes `yarn.lock` and is left to step 1.5.
2. **Playwright was installed unpinned.** The job ran `yarn init -y`, added
   six packages without versions, and ran `yarn install --no-immutable`, so
   it got the latest Playwright, which needs Node 20. All six are already
   locked (`@playwright/test` 1.49.0). The job now runs
   `yarn install --immutable` and installs browsers from `web-app`.
   Checked locally: 1.49.0 on Node 18 lists the 6 e2e tests.
3. **The second integration server embedded the wrong console.** The tests
   create their replication target bucket through MinIO 2's embedded
   console (`:9092`). aursu/minio's `go.mod` pins upstream's simplified
   console. Its `getMakeBucketResponse` calls `makeBucket(..., false)` and
   drops the versioning and locking the test asks for, so the target never
   had versioning. The job now uses the same `replace` as SSO, so both
   servers embed the console under test.
4. **SSO raced the server.** Pulling `minio/mc` used to take seconds and hid
   the race. Since #10 the client image is already local and asks before
   the server listens. The Makefile retries for up to 120 s and prints the
   server log on failure. Checked locally: MinIO keeps running while the
   OpenID provider is not reachable yet.

### Why not the alternatives

- **Switch TestCafe to Chrome instead of upgrading it.** That changes the
  browser the tests were written against. Upgrading TestCafe keeps the
  environment and was proven on the same Firefox the runner has.
- **Pin `playwright@1.49.0` in the job's `yarn add`.** It would keep a second
  dependency list in the workflow, apart from the lockfile, and that is how
  the job drifted in the first place.
- **For Integration, set versioning on the target bucket with mc.** It
  would work around the console instead of testing it. The servers should
  embed the console under test.

### Not changed

- The permissions jobs still `yarn add minio` at the repository root
  unpinned. That step works today; it moves to the lockfile with step 1.5.

## Test tools pinned (#20, step 1.5)

Both items left open above are closed:

- **`minio` JS (permissions jobs).**
  - The repository root has no `package.json`, so corepack runs yarn
    classic 1.22.22 there, and `yarn add minio` installed the newest
    release, 8.0.7 on 2026-11-20.
  - The tests use it in `web-app/tests/utils/functions.ts`.
  - It is now `yarn add "minio@$MINIO_JS_VERSION"`, with 8.0.7, the
    version that passes today.
- **TestCafe.**
  - CI installs `testcafe@$TESTCAFE_VERSION` (3.7.7), and
    `web-app/package.json` now lists 3.7.7 too (it was 3.6.2), so a
    local run uses the same version as CI.
  - The lockfile changes only for testcafe and what it pulls in.

Both versions are defined once, in the `env` block at the top of
`jobs.yaml`, next to `COREPACK_VERSION`.

**Why not move `minio` into `web-app`'s lockfile.** The permissions jobs do
not install `web-app`'s dependencies at all. That takes minutes per job,
across nine jobs, for a single test helper. An exact pin gives the same
reproducibility.

Checked: `yarn install --immutable` ok; `yarn test` 41/41; prettier and
dead-code checks ok; bundle unchanged; production audit unchanged;
actionlint shows no new findings.

## TestCafe browser start-up (#25)

"Cannot establish one or more browser connections" (1 of 3 browsers) hit
4 times by 2026-11-20:

- #20 Permissions Part 2;
- #24 Subpath, twice;
- #24 Permissions Part 1.

Each time the runner image and the `nginx:latest` digest were identical to
those of a passing run, so it was not drift in the environment. All four
were in jobs that start **three Firefox instances at once** (`-c 3`); the
jobs without `-c` never failed. TestCafe's default limit for a local
browser to start is 2 minutes.

- Every TestCafe call gets `--browser-init-timeout 360000` (6 minutes).
- Subpath loses `-c 3`: it has a single test, so the extra browsers only
  add start-up load.

Why not drop `-c 3` everywhere: Parts 1–3, A and B have 7–29 tests each and
gain from concurrency; the longer start-up limit addresses the actual
failure.
