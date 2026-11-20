// SPDX-License-Identifier: AGPL-3.0-or-later
import { isSafeRedirectPath, takeRedirectPath } from "../redirectPath";

const ORIGIN = "https://console.example";

describe("isSafeRedirectPath", () => {
  it.each([
    "/browser",
    "/browser/my-bucket",
    "/browser/my-bucket/cHJlZml4Lw==",
    "/browser/my-bucket/a%2Fb",
    "/browser/caf%C3%A9",
    "/tools/audit?type=s3#top",
    "/identity/users/john.doe",
  ])("accepts the console path %s", (path) => {
    expect(isSafeRedirectPath(path, ORIGIN)).toBe(true);
  });

  it.each([
    ["empty", ""],
    ["relative", "browser"],
    ["protocol-relative", "//evil.example"],
    ["protocol-relative with path", "//evil.example/login"],
    ["backslash after slash", "/\\evil.example"],
    ["backslashes only", "\\\\evil.example"],
    ["encoded backslash", "/%5Cevil.example"],
    ["encoded backslash, lower case", "/%5cevil.example"],
    ["encoded double slash", "/%2F%2Fevil.example"],
    ["tab between slashes", "/\t/evil.example"],
    ["newline between slashes", "/\n/evil.example"],
    ["leading space", " /browser"],
    ["absolute URL", "https://evil.example/browser"],
    ["javascript URL", "javascript:alert(1)"],
    ["malformed escape", "/browser/%E0%A4%A"],
  ])("rejects %s: %j", (_, path) => {
    expect(isSafeRedirectPath(path, ORIGIN)).toBe(false);
  });
});

describe("takeRedirectPath", () => {
  beforeEach(() => localStorage.clear());

  it("returns a safe stored path and clears it", () => {
    localStorage.setItem("redirect-path", "/browser/my-bucket");
    expect(takeRedirectPath("/fallback")).toBe("/browser/my-bucket");
    expect(localStorage.getItem("redirect-path")).toBe("");
  });

  it("returns the fallback for an unsafe stored path and clears it", () => {
    localStorage.setItem("redirect-path", "/\\evil.example");
    expect(takeRedirectPath("/fallback")).toBe("/fallback");
    expect(localStorage.getItem("redirect-path")).toBe("");
  });

  it("returns the fallback when nothing is stored", () => {
    expect(takeRedirectPath("/fallback")).toBe("/fallback");
  });
});
