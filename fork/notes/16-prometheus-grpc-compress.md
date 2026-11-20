# 16 — prometheus 0.311.3, grpc 1.83.1, compress 1.20.2; go-openapi stack (step 1.6)

Date: 2026-11-21. The last PR of step 1.6: after it, govulncheck reports no
reachable findings, and the "Analysis" job should be green.

## What

```
go get github.com/prometheus/prometheus@v0.311.3 google.golang.org/grpc@v1.83.1 \
       github.com/klauspost/compress@v1.20.2 github.com/go-openapi/swag@v0.29.2
go mod tidy
```

| Module | Before → after | Findings closed |
|---|---|---|
| `prometheus/prometheus` (indirect) | 0.301.0 → **0.311.3** | GO-2026-5264, -5381, -5662, -5710 |
| `google.golang.org/grpc` (indirect) | 1.70.0 → **1.83.1** | GO-2026-6061, -6348 |
| `klauspost/compress` | 1.17.11 → **1.20.2** | GO-2026-6865 |

Version selection moved these with them:

| Module | Before → after | Why |
|---|---|---|
| `go-openapi/strfmt` | 0.23.0 → 0.26.1 | required by prometheus 0.311.3 |
| `go-openapi/swag` | 0.23.0 → **0.29.2** | asked for; see below. Split into submodules (`swag/conv`, `netutils`, `cmdutils`, …) |
| `go-openapi/validate`, `spec`, `loads`, `errors`, `analysis`, `jsonreference` | 0.24.0 → 0.25.1, 0.21.0 → 0.22.3, 0.22.0 → 0.23.2, 0.22.0 → 0.22.7, 0.23.0 → 0.24.2, 0.21.0 → 0.21.4 | strfmt / prometheus |
| `go-openapi/jsonpointer` | 0.21.0 → 1.0.1 | swag 0.29 |
| `go-openapi/runtime` | 0.28.0 (unchanged) | — |
| `prometheus/common`, `client_golang` | 0.62.0 → 0.67.5, 1.20.5 → 1.23.2 | prometheus |
| `golang.org/x/oauth2` (direct, OIDC) | 0.26.0 → 0.36.0 | prometheus/common |
| `stretchr/testify` | 1.10.0 → 1.11.1 | prometheus |
| `google.golang.org/protobuf`, `genproto` | 1.36.5 → 1.36.11, 2025-02 → 2026-05 | grpc |
| dropped | `mongo-driver`, `mailru/easyjson`, `josharian/intern`, `mitchellh/mapstructure`, `oklog/ulid`, `asaskevich/govalidator` | strfmt 0.26 and swag 0.25+ no longer use them |

## Why prometheus is here at all

The console reaches prometheus only for `model/histogram`, through
`prom2json` (pulled by madmin-go and mc). The four prometheus advisories
concern the Prometheus *server* (config API, web UI, remote-read
endpoint). Their OSV entries list no affected symbols, so govulncheck counts
any call into the module as reachable. The console is not affected in
substance, but the bump is the only way to a clean "Analysis" without an
exception list, so it is done.

It cannot be avoided by bumping a direct dependency instead: prometheus is
indirect, and the modules that pull it (madmin-go, mc, minio/pkg,
prom2json) do not require 0.311.3. And go-openapi cannot stay at its old
versions: prometheus 0.311.3's own go.mod requires strfmt 0.26.1.

## Why swag 0.29.2, not 0.25.4

Version selection alone picks swag 0.25.4, and then `go mod tidy` fails:

```
github.com/go-openapi/swag/loading.test imports
  github.com/go-openapi/testify/enable/yaml/v2 imports
  github.com/go-openapi/testify/v2/assert/yaml: module github.com/go-openapi/testify/v2@latest
  found (v2.8.1), but does not contain package github.com/go-openapi/testify/v2/assert/yaml
```

strfmt 0.26.1 (and errors, jsonpointer, swag/jsonname) require
`go-openapi/testify/v2` ≥ v2.4, which no longer has `assert/yaml`. The tests
of swag/loading 0.25.4 still import it. `go mod tidy` loads the tests of
dependency packages, so it fails, although nothing in the build needs them.

Prometheus works around this in its own go.mod:
`replace github.com/go-openapi/testify/v2 => github.com/go-openapi/testify/v2 v2.0.2`.
That replace works for the console alone (tried: tidy, build and tests
pass). **Rejected**, because a `replace` applies only in the main module:

- reproduced locally: aursu/minio master + `replace github.com/minio/console => <this branch>`
  + `go mod tidy -compat=1.23` (exactly what the Integration and SSO jobs
  do) fails with the same error. Both jobs would go red;
- aursu/minio would need the same replace at plan step 2.1, and every
  other module that requires this console after that.

In swag 0.29 the yaml helper is its own module (`testify/enable/yaml/v2`
v2.7.0), so no replace is needed anywhere. With swag 0.29.2, the same
aursu/minio reproduction tidies and builds.

## Deprecated swag helpers (second commit)

swag 0.25+ deprecates the root-package helpers; staticcheck SA1019 failed on
hand-written code. Upstream console never moved past swag 0.23, so this is
our own change. It is mechanical: `gofmt -r` over the 17 hand-written files
that import swag, 96 call sites:

| Old | New |
|---|---|
| `swag.String(x)`, `swag.Int64(x)` | `conv.Pointer(x)` |
| `swag.Int32(2)`, `swag.Uint(2)` | `conv.Pointer[int32](2)`, `conv.Pointer[uint](2)` |
| `swag.SplitHostPort` | `netutils.SplitHostPort` |
| `swag.CommandLineOptionsGroup` | `cmdutils.CommandLineOptionsGroup` |

- `conv.Pointer` is generic; with an untyped constant it would infer
  `*int`, so the `Int32`/`Uint` sites carry the type argument.
- In swag 0.29.2 the old helpers are one-line wrappers over the new ones,
  and `swag.CommandLineOptionsGroup` is a type alias, so behaviour is
  unchanged and the generated `api.CommandLineOptionsGroups` field takes
  the new name.
- Generated code (`api/operations`, `models`, "DO NOT EDIT") still uses the
  swag root package. It is left as generated; golangci-lint skips it.

**Rejected:** excluding SA1019 for swag in `.golangci.yml`, or `//nolint`
on 96 lines. Either would keep calls that the next swag release may drop.

## Risk: the swagger runtime

The generated server code runs on strfmt/validate/spec/loads/swag. The
console uses strfmt only as a validation `Registry` (no `ObjectId`, no
bson), and no type implements easyjson, so the removal of mongo-driver and
easyjson does not touch it. `go-openapi/runtime` is unchanged. The API is
exercised by the unit tests and by the Integration (86 tests) and SSO suites
in CI; `x/oauth2` 0.36 is covered by SSO.

## Consequence for the server

aursu/minio master already builds with this console replaced in (Go
1.27.4). At step 2.1 the server's go.mod moves to the same go-openapi stack;
no replace is needed.

## Tests

Go 1.27.4 (`golang:1.27.4`, `GOTOOLCHAIN=auto`):

| Check | Result |
|---|---|
| `go build ./...`; `go vet ./api/... ./pkg/... ./integration/... ./sso-integration/...` | ok |
| `make verifiers` (gofmt, golangci-lint v2.15.0) | 0 issues |
| `go test ./api/... ./pkg/...` | 9/9 packages, 134 tests passed, 0 failed |
| govulncheck v1.10.0 | **7 → 0** reachable |
| aursu/minio master + this console, `go mod tidy -compat=1.23`, `go build` | ok |
| the same with swag 0.25.4 + prometheus's replace (rejected variant) | tidy fails |
