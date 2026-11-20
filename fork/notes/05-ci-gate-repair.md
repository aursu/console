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
