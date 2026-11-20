// SPDX-License-Identifier: AGPL-3.0-or-later
//
// The page to open after login.
//
// When an unauthenticated user opens a console page, its path is stored in
// localStorage["redirect-path"] (ProtectedRoutes.tsx, common/api/index.ts),
// and after login the console navigates there. Because that path comes from a
// URL anyone can send, it is validated here: only a path on the console's own
// origin is used. Otherwise a crafted link would turn the login into an open
// redirect. react-router 6 does not fully guard against this (GHSA-wrjc-x8rr-
// h8h6 is fixed only in 7.18), so the check does not rely on the router.

const REDIRECT_PATH_KEY = "redirect-path";

// Control characters and spaces (code points 0-32 and 127): the URL parser
// drops tabs and newlines, so "/\t/evil.example" would become
// "//evil.example".
const hasControlOrSpace = (path: string): boolean =>
  Array.from(path).some((ch) => {
    const code = ch.charCodeAt(0);
    return code <= 0x20 || code === 0x7f;
  });

const looksExternal = (path: string): boolean =>
  !path.startsWith("/") ||
  path.startsWith("//") ||
  path.includes("\\") ||
  hasControlOrSpace(path);

export const isSafeRedirectPath = (
  path: string,
  origin: string = window.location.origin,
): boolean => {
  if (path === "" || looksExternal(path)) {
    return false;
  }
  let decoded: string;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    return false;
  }
  if (looksExternal(decoded)) {
    return false;
  }
  try {
    return new URL(path, origin).origin === origin;
  } catch {
    return false;
  }
};

// Reads and clears the stored path. Returns it if it is safe, otherwise the
// fallback.
export const takeRedirectPath = (fallback: string): string => {
  const stored = localStorage.getItem(REDIRECT_PATH_KEY) || "";
  if (stored !== "") {
    localStorage.setItem(REDIRECT_PATH_KEY, "");
  }
  return isSafeRedirectPath(stored) ? stored : fallback;
};
