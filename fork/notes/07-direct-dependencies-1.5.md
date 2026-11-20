# 07 — Direct dependencies within their majors (step 1.5)

Date: 2026-11-20. PR: aursu/console#14. Plan step 1.5 (aursu/minio
`fork/reports/04-plan-final-build.md`), second PR of the step.

## What changed

| Package | Before | After | Why |
|---|---|---|---|
| `react-router-dom` / `react-router` | 6.25.1 | **6.30.6**, the last 6.x | open-redirect fixes (6.30.2, 6.30.3), double-slash normalisation |
| `@remix-run/router` (via react-router) | 1.18.0 | 1.23.4 | same |
| `lodash` | 4.17.21 | **4.18.1**, the last 4.x | `_.template` code injection, `_.unset`/`_.omit` prototype pollution |
| `form-data` (via `superagent`) | 4.0.1 | **4.0.6** | **critical**: unsafe random for multipart boundaries; high: CRLF injection |
| `qs` (via `superagent`) | 6.13.1 | **6.17.1** | five DoS advisories |

`superagent` stays at 9.0.2, the last 9.x. Its ranges (`form-data ^4.0.0`,
`qs ^6.11.0`) already allow the fixed versions, so `yarn up -R form-data qs`
refreshes them in the lockfile; superagent 10 is not needed.

`lodash` needed `yarn up -R lodash` as well. With only the new range in
`package.json`, yarn added a second lodash 4.18.1 and left every other range
on 4.17.21, so the advisories stayed and the bundle had two lodash copies.
After the refresh there is one lodash, 4.18.1.

The lockfile gains 25 small packages: the helpers `form-data` 4.0.6 and
`qs` 6.17.1 depend on (`get-intrinsic`, `side-channel`, `hasown` and
relatives). Like `form-data` and `qs`, they are on superagent's Node side.

## What it changes for the console

- **react-router 6.26–6.30.** The console uses a plain `<BrowserRouter>`
  (`src/MainRouter.tsx`) and none of the `unstable_*` APIs that 6.27
  renamed. For it, the range is fixes only.
  - Since 6.28, react-router prints v7 deprecation warnings for future flags
    not opted into. Since 6.29, only in development builds, so this shows
    up in the browser console of `yarn start`, never in the shipped bundle.
- **lodash 4.18.** The behaviour changes are in `_.template`, `_.unset` and
  `_.omit`. The console imports only `lodash/get` (64 places),
  `lodash/debounce` and `lodash/groupBy`.
- **form-data, qs.** These are superagent's Node entry. The bundle uses
  superagent's browser build and contains neither.
- **The bundle:** only `main` changes. That is where react-router and
  `lodash/get` live.

## Still open: react-router's backslash open redirect

Two moderate react-router advisories remain. Both are fixed only in 7.18, a
major upgrade:

- **GHSA-wrjc-x8rr-h8h6** (CVE-2026-53669): open redirect via backslash in
  `<Link>`/`useNavigate`. It is a bypass of CVE-2025-68470, which 6.30.2
  fixed. Per the advisory, it is an issue only when "developers pass
  untrusted content into navigation paths". **The console does.**
  - `ProtectedRoutes.tsx` and `common/api/index.ts` store the path of the
    page an unauthenticated user opened in `localStorage["redirect-path"]`.
  - After login, `Login.tsx` (`getTargetPath`) and `LoginCallback.tsx`
    (SSO) pass it to `navigate()`.
  - A crafted console link is therefore a navigation path the attacker
    chooses. This is the classic post-login open redirect.
- **Constructor injection via `deserializeErrors()`** in react-router SSR.
  The console renders on the client only, so this code path does not run.

The fix for the first is ours, in the next PR: validate `redirect-path`
before navigating. Only a path on the console's own origin is accepted;
anything else falls back to the default page. This works whatever the
router does, and both login paths will share one function.

## Why not the obvious alternatives

- **react-router 7.** It clears both advisories, but it is a major upgrade
  of the router the whole UI is built on. That is outside step 1.5 ("within
  majors"), and our own validation closes the reachable one anyway.
- **superagent 10.** Not needed: the fixed `form-data` and `qs` are within
  superagent 9's ranges.

## Tests

| Check | Result |
|---|---|
| `yarn install --immutable` | ok |
| `yarn why`: react-router-dom, react-router, @remix-run/router, lodash, form-data 4.x, qs 6.x | 6.30.6, 6.30.6, 1.23.4, 4.18.1 (one copy), 4.0.6, 6.17.1 |
| `./check-warnings.sh`, `./check-prettier.sh`, `./check-deadcode.sh` | ok |
| `yarn test` | 16/16 |
| bundle | only `main` changes |
| `yarn npm audit --recursive --environment production` | **63 → 50**; critical 2 → 1 (`tar` remains, next PRs), high 30 → 27; removed: qs 5, react-router 2, @remix-run/router 2, form-data 2, lodash 2; nothing new |

The routing change is exercised in CI by the end-to-end suites (Permissions
1–6/A/B, playwright, Subpath), which navigate the whole UI.
