# 15 — golang.org/x/net 0.60.0 and the x/ family; go line 1.26.0 (step 1.6)

Date: 2026-11-20. PR: aursu/console#27, stacked on #26 (jwt).

## What

`go get golang.org/x/net@v0.60.0`, then `go mod tidy`. Go's version
selection moved the rest of the family with it:

| Module | Before → after |
|---|---|
| `golang.org/x/net` | 0.35.0 → **0.60.0** (4 reachable findings fixed) |
| `golang.org/x/text` | 0.22.0 → **0.42.0** (1 finding fixed; x/net 0.60 requires 0.42) |
| `golang.org/x/crypto` | 0.33.0 → 0.57.0 |
| `golang.org/x/sys` | 0.30.0 → 0.48.0 |
| `golang.org/x/sync` | 0.11.0 → 0.23.0 |
| `golang.org/x/term` | 0.29.0 → 0.46.0 |
| **`go` line** | 1.23 → **1.26.0**, required by x/net 0.60.0 (note 13) |

Asking for `x/text` 0.39.0 (the first fixed version) together with x/net
failed: "x/net@v0.60.0 requires x/text@v0.42.0". So only x/net is
requested.

**Upstream `28b0801`** (x/net 0.37 → 0.38, plus the vulncheck Go pin) is
**superseded**: x/net 0.38 is still vulnerable, and #23 already replaced the
Go pin. Note 03 says so.

## A new lint finding

With `go 1.26`, staticcheck reports `runtime.GOROOT` (deprecated since Go
1.24) in `pkg/logger/logger.go`. It is one of several candidate prefixes
the logger trims from stack-trace paths, next to the caller's `goRoot` and
`build.Default.GOROOT`. Replacing it would change which prefixes are
trimmed, so it is kept, with `//nolint:staticcheck` and the reason.

## Consequence for the server

A module that requires this console now needs `go >= 1.26`. In plan 04,
step 2.2 (server Go 1.27.4) comes before or with 2.1 (server → full
console). In this repo's CI, Integration and SSO add a `replace` to MinIO's
go.mod and run `go mod tidy`, which raises MinIO's go line in the job. They
build with Go 1.27.4 from the console's go.mod (note 14), so that works.

## Tests

Go 1.27.4:

| Check | Result |
|---|---|
| `go build ./...`, `go vet ./api/... ./pkg/...` | ok |
| `go test ./api/... ./pkg/...` | 9/9 packages |
| `make verifiers` | 0 issues |
| govulncheck | **12 → 7**, from 3 modules: prometheus, grpc, compress (next PR) |
