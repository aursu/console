# 14 — actions/setup-go v6; no automatic toolchain downloads (step 1.6)

Date: 2026-11-20. PR: aursu/console#24. Follows note 13.

## Why

With setup-go v5, `go-version-file: go.mod` installed the `go` line (1.23).
Every Go job then downloaded go1.27.4 from proxy.golang.org, because of
`toolchain go1.27.4` and Go's default `GOTOOLCHAIN=auto`. One of those
downloads failed on #23 ("Test API": stream INTERNAL_ERROR). setup-go
v6.0.0 reworked toolchain handling (actions/setup-go#460).

## What changed, and what CI showed

- **`actions/setup-go@v5` → `@v6`**, in all 15 uses. CI evidence:
  - 13 jobs report `Setup go version spec 1.27.4` and take it
    `Found in cache @ /opt/hostedtoolcache/go/1.27.4`, with no download;
  - "Build latest MinIO" gets 1.24.8 from MinIO's go.mod, as intended.
  - v6 also sets **`GOTOOLCHAIN=local`** in the job environment.
- **Integration and SSO take Go from the console's go.mod** (were: MinIO's).
  - With `GOTOOLCHAIN=local` they stayed on MinIO's 1.24.8 for the
    console's test code. Under v5, the console's toolchain line had switched
    them to 1.27.4.
  - Their coverage profiles then came from another Go than api/pkg's, and
    the coverage job's `gocovmerge` failed with
    `OVERLAP BEFORE: …/api/admin_arns.go`.
  - With the console's go.mod (1.27.4, which builds MinIO fine) the coverage
    check passed again.
- **`GOTOOLCHAIN: local` in the jobs without setup-go.**
  - Ten jobs have no setup-go: Permissions ×8, Subpath, playwright. They
    still downloaded go1.27.4, in their "Start Console" step. The cause:
    the Makefile's `GOPATH := $(shell go env GOPATH)` runs the runner's
    preinstalled Go inside the module, which auto-switched to the toolchain
    line just to print a path. This predates v6.
  - With `local`, nothing is downloaded. Those jobs use no other Go.
  - **Correction: job-level, not workflow-level.** The first version set
    `GOTOOLCHAIN: local` for the whole workflow. With that set,
    **setup-go v6 ignores the `toolchain` line and installs the `go` line**.
    12 jobs then ran Go 1.23, and the tests, lint and build mostly passed,
    on the wrong Go. Only the MinIO build broke: Go 1.23 cannot parse
    MinIO's go.mod (`unknown block type: tool`, a Go 1.24 directive). The
    setting is now on the 10 jobs without setup-go only, and the setup-go
    jobs install 1.27.4 again.
- **The `PATH` step in "Analysis" is removed** (added in #23, note 13).
  With v6 the `go` on PATH already is go1.27.4.

## Seen, not caused by this PR

"Test Subpath with Nginx" failed on both runs of this PR with TestCafe's
"Cannot establish one or more browser connections" (1 of 3 Firefox
instances). The runner image (20261111.635) and the `nginx:latest` digest
were identical to the last successful run on master. It is the third
occurrence overall (also #20, Permissions Part 2), so it gets its own fix
(`--browser-init-timeout`) in a separate PR.

## Tests

CI on this PR is the test. Expected:

- no `go: downloading go1` line in any job;
- all functional jobs green, apart from the Subpath flake;
- "Analysis" reports the 13 module findings ("affected by 13
  vulnerabilities from 6 modules"), not a package-loading error.
