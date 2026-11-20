# 13 — Go toolchain 1.27.4 (step 1.6, first PR)

Date: 2026-11-20. PR: aursu/console#23. Plan step 1.6 (aursu/minio
`fork/reports/04-plan-final-build.md`): the console's Go side.

## Baseline

`govulncheck ./...` on master (reachable vulnerabilities, i.e. called
symbols):

| | Go 1.23.6 (go.mod's toolchain) | Go 1.27.4 |
|---|---|---|
| total | **65** | **13** |
| standard library | 52 | **0** |
| modules | 13 | 13 |

The 13 module findings are in six modules. The next PRs of step 1.6 handle
them:

- `golang.org/x/net` (4), fixed in 0.60.0;
- `prometheus/prometheus` (4), fixed in 0.311.3;
- `grpc` (2), fixed in 1.83.1;
- `klauspost/compress`, `golang-jwt/jwt/v4` (upstream `6499469`) and
  `golang.org/x/text`, one each.

**The `go` line will have to rise.** The fixed `x/net` 0.60.0 declares
`go 1.26.0`, and `x/text`, prometheus, grpc and compress need 1.25. The
console's `go` line will therefore become 1.26.0 with the module PRs.
Consequence for the plan: the server (`go 1.24.0`) can take this console
only once its own `go` line is ≥ 1.26, so step 2.2 (server toolchain) has
to come before or with 2.1 (server → full console).

## What this PR changes

- **`go.mod`:** `toolchain go1.23.6` → `go1.27.4`. The `go 1.23` language
  line stays: it only rises when a dependency requires it (next PRs).
- **CI takes Go from `go.mod`.** About 20 jobs installed Go from a
  `go-version: [1.23.x]` matrix, and the govulncheck job pinned
  `1.23.3` with `check-latest`. All of them now use
  `setup-go` with `go-version-file: go.mod`, so the toolchain line is the
  single source.
  - The `go-version` matrix dimension is removed, and with it
    "(1.23.x, …)" in job names.
  - govulncheck is pinned to `v1.10.0` (it was `@latest`).
- **golangci-lint v1.64.8 → v2.15.0.**
  - golangci-lint refuses to analyse a module that targets a newer Go than
    the one it was built with. v1.64.8 is built with Go 1.24, v2.15.0
    with Go 1.27.0.
  - `.golangci.yml` was converted with golangci-lint's own
    `migrate --skip-validation`. Validation had to be skipped because the
    v1 file carried two obsolete entries (`golint` settings, a `service`
    block); the conversion drops them.
  - **Same lint scope as before.** In v2, `staticcheck` also runs
    stylecheck (ST) and quickfix (QF) checks, which reported 17 style
    suggestions in upstream code. v1 enabled only `staticcheck` (SA) and
    `gosimple` (S1), so the config keeps `checks: [SA*, S1*]`.
  - `gomodguard` → `gomodguard_v2`, as golangci-lint suggests. The config
    has no gomodguard settings, so it checks nothing either way.
- **Three deprecated-API findings (SA1019)**, newly detected by the newer
  staticcheck:
  - `tls.Config.PreferServerCipherSuites` has been **ignored** since Go
    1.18: removed, no behaviour change;
  - `net.Dialer.DualStack` has been the **default** since Go 1.12:
    removed, no behaviour change;
  - madmin's `AddServiceAccountReq.Comment` is deprecated in favour of
    `Description`, but the console API has both fields and sends both.
    Removing it would change what the server receives, so it is kept with
    `//nolint:staticcheck` and the reason.
- **`Test_shareObject` compares error messages.** Since Go 1.27,
  `time.ParseDuration` returns its own error type, and the test compared
  with `reflect.DeepEqual(err, errors.New("time: invalid duration
  \"invalid\""))`. The text is unchanged. Verified: on Go 1.23.6 the
  `DeepEqual` is true; on 1.27.4 the type is `*time.parseDurationError`
  and it is false. The product code is unaffected.

## Why not the obvious alternatives

- **Pin the matrix to `1.27.4`.** That would keep a second copy of the
  version in CI, next to `go.mod`, and the two would drift apart.
- **Raise the `go` line to 1.27 now.** Nothing requires it, and every
  module that imports the console, including the server, would then have to
  be on 1.27. The line rises only as far as a dependency needs (1.26.0,
  with `x/net`).
- **Enable all v2 staticcheck checks and fix the 17 suggestions.** That is
  style churn in upstream code, outside a toolchain change.
- **Delete the deprecated `Comment`.** It would change the request sent to
  the server.

## Tests

Go 1.27.4:

| Check | Result |
|---|---|
| `make verifiers` (gofmt check + golangci-lint v2.15.0) | ok, 0 issues |
| `go build ./cmd/console` | ok |
| `go vet ./api/... ./pkg/...` | ok |
| `go test ./api/... ./pkg/...` | ok, 9/9 packages |
| `govulncheck ./...` (v1.10.0) | 65 → 13: all 52 standard-library findings gone; the 13 module findings remain for the next PRs |
| actionlint | no new findings |

"Analysis" stays red until the module PRs land.
