# 12 — react-router 7.18.6 (step 1.5)

Date: 2026-11-20. PR: aursu/console#21. Plan step 1.5. The project owner
chose this over a documented audit exception, after a trial upgrade (below).

## Why

After #20, the production audit had two advisories left, both react-router
6.30.6, both fixed only in 7.18:

- **GHSA-wrjc-x8rr-h8h6** (CVE-2026-53669), the backslash open redirect.
  Reachable in the console through the post-login `redirect-path`; guarded
  by our own validation since #15 (note 08).
- Constructor injection via `deserializeErrors()` in react-router **SSR**.
  This does not apply: the console renders on the client only.

Two ways to turn "React Code Has No Known Vulnerable Deps" green:

- **ignore the two advisory IDs** in the job, with reasons;
- **upgrade to react-router 7**, which removes both at the source.

The upgrade sounded like a major migration. A trial on a copy of the tree
showed it is mostly mechanical, so it was chosen.

## Which v7

- `latest` on npm is react-router **8.5.2**, which requires React 19. The
  console runs React 18.3.1, so 8 is a different, much larger change.
- The v7 line ends at **7.18.6** (dist-tag `version-7`). Every v7 release,
  7.18.6 included, declares `react >= 18`, and 7.18.6 needs Node >= 20; the
  console builds on Node 26 (note 11).

## What changed

- **Dependency:** `react-router-dom` 6.30.6 → `react-router` 7.18.6. In v7
  the DOM APIs live in `react-router`; `react-router-dom` remains only as a
  re-exporting compatibility package.
- **Imports:** all 62 imports change from `"react-router-dom"` to
  `"react-router"`, v7's own migration step.
  - The first trial kept `react-router-dom` 7. That package imports
    `react-router/dom`, an `exports` subpath that Jest 27 (CRA's) cannot
    resolve: one test suite failed.
  - Importing from `react-router` avoids that subpath.
- **No call changes.** The console uses only declarative routing:
  `useNavigate` (44 files), `useParams` (14), `Routes`/`Route`,
  `useLocation`, `Navigate`, `Link`, and one `<BrowserRouter>`. The
  production build's TypeScript check passes unchanged.
- **The `cookie` resolution is scoped.**
  - Upstream's `resolutions: { "cookie": "^0.7.2" }` (CVE-2024-47764)
    forced *every* `cookie` to 0.7, including react-router 7's, which asks
    for `^1.0.1`.
  - It now applies only to the package it was for:
    `"local-storage-fallback/cookie": "^0.7.2"` (that package declares
    `^0.3.1`).

  | Dependent | Asks for | Gets |
  |---|---|---|
  | express (dev server) | `~0.7.1` | 0.7.1 |
  | local-storage-fallback | `^0.3.1`, raised by the resolution | 0.7.2 |
  | react-router 7 | `^1.0.1` | 1.1.1 |

  All three versions are past the CVE; cookie 1.x has no known advisories.
  Yarn re-resolved `local-storage-fallback` 4.1.2 → 4.1.3 within its range.

## What changes at runtime

v7 makes two former v6 "future flags" the default. For a declarative app
like this one:

- **`v7_relativeSplatPath`:** inside splat routes (`/*`), relative paths
  resolve differently: from the matched URL, not from the route's parent.
  The console has several splat routes. **Four relative targets were
  affected and are now absolute**, see "First CI run" below.
  - **Correction:** the first version of this note said the console's
    navigation targets were all absolute. The survey behind that claim
    searched only string forms (`to="…"`, `navigate("…")`). It missed a
    relative path written as an object with a template literal, and
    relative values inside `IAM_PAGES` constants.
- **`v7_startTransition`:** router state updates are wrapped in
  `React.startTransition`. When a lazy page loads, the previous page may
  stay visible a moment longer instead of the loading fallback.

The end-to-end suites in CI (Permissions 1–6/A/B, playwright, Subpath)
navigate the whole UI and are the check for both.

## The bundle

The readable diff shows 37 files with changes and none added or removed:

- `main`, about 4,700 lines: the router itself.
- `182`, about 1,600 lines: the object browser, the heaviest router user.
  Mostly renumbered module references and renamed minified variables.
- `3298`, about 300 lines.
- 34 other chunks, 2–4 lines each: only the reference to the router module.

152 files change in all, counting renamed hashes and source maps.

## Why not the obvious alternatives

- **Ignore the two advisories.** Cheaper still, but it keeps a router with
  a known open redirect, guarded only by our own check. The upgrade removes
  it at the source, and v7 still receives fixes.
- **react-router 8.** It needs React 19: a separate, much larger change.
- **Keep `react-router-dom` 7 and map `react-router/dom` for Jest.** That
  puts a path into `node_modules` in the Jest config (note 04 rejected the
  same for superagent). Importing from `react-router` is v7's recommended
  form anyway.

## Tests

On Node 26.13.1, yarn 4.18.1:

| Check | Result |
|---|---|
| `yarn install --immutable` | ok |
| `yarn why` | react-router 7.18.6; no react-router-dom; cookie as in the table above |
| `./check-prettier.sh` | ok, with no reformatting needed |
| `./check-warnings.sh` (production build with type check) | ok, no warnings |
| `./check-deadcode.sh` | ok |
| `yarn test` | 41/41 |
| `yarn npm audit --recursive --environment production` | **2 → 0**, "No audit suggestions" |

CI's end-to-end suites are the check for the two runtime defaults above.

## First CI run: a relative-path regression, and its fix

On the first CI run of this PR, "React Code Has No Known Vulnerable Deps"
was green and every job passed except `playwright`. Its login setup opens
`/buckets` and never saw the "Username" field.

**Reproduced locally** on a real console binary with MinIO: opening any
protected page without a session looped
`/buckets/login/login/login/…`.

- `ProtectedRoutes.tsx` (the element of MainRouter's `/*` route) redirects
  with `<Navigate to={{ pathname: \`login\` }} />`.
  - In v6, inside a splat route, `login` resolved against the route's
    parent and went to `/login`.
  - In v7 it resolves against the matched URL, giving `/buckets/login`,
    and then again from there.
- The normal bundle loops too, not only playwright's Istanbul-instrumented
  build.
- The permissions suites passed only because TestCafe opens the login page
  directly.

**Every navigation target was traced to its value**, this time including
objects, template literals and variables. Four were relative. Each now uses
the absolute path v6 went to, so behaviour is unchanged:

| Call site | Runs at | v6 went to | Now |
|---|---|---|---|
| `ProtectedRoutes.tsx` login redirect | any URL (`/*`) | `/login` | `"/login"` |
| `kbar-actions.tsx` "create bucket" | any page (Console's `/*`) | `/add-bucket` | `` `/${IAM_PAGES.ADD_BUCKETS}` `` |
| `ListBuckets.tsx` (×2) | `/buckets` | `/buckets/add-bucket` | `` `${IAM_PAGES.BUCKETS}/${IAM_PAGES.ADD_BUCKETS}` `` |
| `OBBucketList.tsx` | `/browser` | `/browser/add-bucket` | `` `${IAM_PAGES.OBJECT_BROWSER_VIEW}/${IAM_PAGES.ADD_BUCKETS}` `` |

- `IAM_PAGES.ADD_BUCKETS` stays `"add-bucket"`. It is also a nested route
  pattern (in `Buckets.tsx`, `ObjectBrowser.tsx`, `Console.tsx`), where
  relative is correct.
- The other variable targets (`tab`, `backLink`, `newPath`, `goTo`,
  `path`) all trace to absolute paths.

**Verified locally:** the real Playwright suite, run against a console
built from the fixed tree with MinIO, **6 passed**. Jest 41/41; upstream's
checks ok; prettier re-wrapped two lengthened lines.

**Also fixed:** the playwright job uploaded `playwright-report/` and
`coverage/` from the repository root, but the tests run in `web-app/`.
That is why this failure left no report behind. The paths now point at
`web-app/playwright-report/`, `web-app/test-results/` (per-test traces) and
`web-app/coverage/`.
