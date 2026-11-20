# 08 — Post-login redirect: only paths on the console's own origin

Date: 2026-11-20. PR: aursu/console#15. Plan step 1.5, our own fix for the
react-router advisory note 07 left open.

## The problem

When an unauthenticated user opens a console page, the console remembers it
and returns there after login:

- `ProtectedRoutes.tsx` stores `useLocation().pathname`, and
  `common/api/index.ts` stores `window.location.pathname` on a 401, in
  `localStorage["redirect-path"]`.
- After login, the stored value is passed to `navigate()`:
  - normal login: `Login.tsx` `getTargetPath()`, called from
    `loginThunks.ts`; default `/browser`;
  - SSO: an inline copy in `LoginCallback.tsx`; default `/`.

The stored value comes from a URL, and anyone can send a URL. react-router
GHSA-wrjc-x8rr-h8h6 (CVE-2026-53669, moderate) is an open redirect via
backslash in `<Link>`/`useNavigate`, a bypass of CVE-2025-68470. The
advisory says it matters only when "developers pass untrusted content into
navigation paths", and that is what the console does.

The scenario: a crafted console link → the victim logs in → the console
navigates to a destination the attacker chose. A redirect from a trusted
login page is a standard phishing step. The fix is in react-router 7.18
only; react-router 6.30.6 (note 07) is the last 6.x.

## The fix

`src/screens/LoginPage/redirectPath.ts`:

- `isSafeRedirectPath(path, origin)` accepts a path only if all of these
  hold:
  - it starts with exactly one `/`: not empty, not relative, not `//`;
  - it has no backslash;
  - it has no control character or space. The URL parser drops tabs and
    newlines, so `/\t/evil.example` would turn into `//evil.example`;
  - the same holds after percent-decoding, which closes `/%5Cevil.example`
    and `/%2F%2Fevil.example`. A malformed escape is rejected;
  - `new URL(path, origin).origin` equals the console's origin.
- `takeRedirectPath(fallback)` reads and clears the stored value. It returns
  the value if it is safe, otherwise the fallback.

Both login paths now use it: `getTargetPath()` with `/browser`, and
`LoginCallback.tsx` with `/`, the same defaults as before. The duplicated
inline copy in `LoginCallback.tsx` is gone. For every legitimate path the
behaviour is unchanged: a valid stored path is returned as it was stored,
not re-serialised, so `basename` handling is exactly as before.

## Why not the obvious alternatives

- **react-router 7.** It fixes the advisory in the router, but it is a major
  upgrade of the router the whole UI is built on. It is outside step 1.5,
  and the check here works whatever the router version.
- **Stop storing the path.** That would remove a working feature: after a
  session expires, the user is sent back where they were.
- **Store only router-internal state (`navigate(..., { state })`).** Both
  writers would need changing, and `common/api/index.ts` writes outside the
  router on a 401 and then reloads the page. A validated read covers both
  writers and any future one.

## Tests

`src/screens/LoginPage/__tests__/redirectPath.test.ts`, 25 tests:

- accepted, as real console paths look: `/browser`,
  `/browser/my-bucket`, base64 prefixes with `=`, `%2F` inside a path,
  `/browser/caf%C3%A9`, a path with query and hash, `/identity/users/john.doe`;
- rejected: empty; relative; `//evil.example` and `//evil.example/login`;
  `/\evil.example`; `\\evil.example`; `/%5Cevil.example`, `/%5cevil.example`;
  `/%2F%2Fevil.example`; tab and newline between the slashes; a leading
  space; `https://evil.example/browser`; `javascript:alert(1)`; a malformed
  escape;
- `takeRedirectPath`: a safe value is returned and cleared; an unsafe value
  gives the fallback and is cleared; nothing stored gives the fallback.

| Check | Result |
|---|---|
| `yarn test` | 41/41, 4/4 suites |
| `./check-warnings.sh` | ok. The first version used a regular expression with control characters, which ESLint's `no-control-regex` flags; replaced with an explicit character-code check. |
| `./check-prettier.sh`, `./check-deadcode.sh` | ok |
| bundle | rebuilt |

Normal login is also exercised in CI by the end-to-end suites
(playwright's login test, TestCafe logins for each permission user). They
go through `getTargetPath()` and must still land on their pages.
