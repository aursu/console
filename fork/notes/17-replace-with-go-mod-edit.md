# 17 — the embedded-server jobs overwrite MinIO's console replace

Date: 2026-11-22. A CI change only; no console code moves.

## Why

"Integration Tests with Latest Distributed MinIO" and "SSO Integration
Test" build `aursu/minio` with this console embedded. Each added the
console to MinIO's go.mod by appending a line:

```
echo "replace github.com/minio/console => ../" >> go.mod
```

That works while MinIO's go.mod has no replace for the console. Plan 04,
step 2.1, gives it one: `aursu/minio` will point at a commit of this repo.
Two replaces of the same module with different targets are an error, so
from that merge on both jobs would fail before building anything:

```
go: conflicting replacements for example.com/a:
	../a
	../b
```

(reproduced with two throwaway modules and Go 1.27.4; the message is the
same for any module path).

## What

Both jobs use `go mod edit -replace github.com/minio/console=../` instead.
It writes the replace when there is none and overwrites the one that is
there, so the jobs build MinIO with the console under test in both cases.
The integration job's comment now says why, and no longer says that
`aursu/minio` pins upstream's simplified console.

## Not changed

- **"Check-out matching MinIO branch" in these two jobs runs in the
  console's checkout, not in `minio_repository`.** If `aursu/minio` had a
  branch with the same name as a console PR's branch, `git checkout
  alt/<branch>` would replace the console tree with MinIO's. No branch name
  has matched so far, so the step has been a no-op; it is left for a
  change of its own. Until then, console and MinIO branches must not share
  a name. In "Build latest MinIO" the same step runs in MinIO's checkout
  and is correct.

## Tests

On the build host, Go 1.27.4, this console's tree with MinIO checked out
inside it as in CI (so `../` is the console). The jobs' build step, `go mod
edit -replace`, `go mod tidy -compat=1.23`, then `go build`:

| MinIO tree | Before | Old step (`echo >>`) | New step |
|---|---|---|---|
| `aursu/minio` master `29316c0c5` | no console replace | (worked, as in CI so far) | replace `=> ../`, tidy ok, build ok |
| `aursu/minio` step 2.1 branch | `=> github.com/aursu/console v1.7.7-0.20261120232317-7832665c91d3` | **`conflicting replacements`**, tidy rc 1 | the line overwritten to `=> ../`, tidy ok, build ok |

`go list -m` after the new step resolves `github.com/minio/console` to `../`
in both trees: the server is built with the console under test.
