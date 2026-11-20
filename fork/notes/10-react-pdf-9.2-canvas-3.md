# 10 — react-pdf 9.2.1: canvas 3, so the console can leave Node 18

Date: 2026-11-20. PR: aursu/console#17. Plan step 1.5, first half of the
toolchain work. The approach was recommended and accepted after the probe
below.

## Why this comes before the Node upgrade

The UI is built on Node 18 (`.nvmrc`), which has been end-of-life since April
2025. Moving to a supported LTS failed on one package:

- `react-pdf` 9.1 → `pdfjs-dist` 4.4.168 → optional `canvas` 2.11.2, a
  native module pdfjs uses to render PDFs **in Node**. The browser never
  runs it.
- canvas 2.11.2 has no prebuilt binary for Node 24 or 26. Compiling it from
  source needs cairo, which is not installed, so the build fails. Yarn
  carries on, because canvas is optional.
- Jest's jsdom then finds a canvas package without its binary and throws.
  **All 4 test suites failed** on Node 24 and 26, with 0 tests run. The
  production build itself was fine.

`react-pdf` 9.2.1, still within major 9, moves to `pdfjs-dist` 4.8.69, which
asks for `canvas` ^3. canvas 3 is built on **N-API**, a binary interface
that is stable across Node versions: its prebuilt binaries load on any
supported Node, with no compiler. Probed on copies of the tree:

| Node | canvas | Jest | production build |
|---|---|---|---|
| 18.20.8 | 3.2.3 loads | 41/41 | ok |
| 24.22.3 | 3.2.3 loads | 41/41 | ok |
| 26.13.1 | 3.2.3 loads | 41/41 | ok |

With canvas 2.11.2 the same probe gave 0 tests on Node 24 and 26.

## What changed

- `package.json`: `react-pdf` `^9.1.0` → `^9.2.1`. The resolution
  `@mapbox/node-pre-gyp ^2.0.3` (note 09) is removed: canvas 3 installs
  with `prebuild-install`, and node-pre-gyp is no longer in the tree. The
  `node-gyp ^11.5.0` resolution stays, because canvas 3's install falls back
  to `node-gyp rebuild`.
- `yarn.lock`: `react-pdf` 9.2.1, `pdfjs-dist` 4.8.69, `canvas` 3.2.3,
  `prebuild-install` 7.1.3 (with `tar-fs` 2.1.5, no advisories);
  node-pre-gyp and canvas 2's dependencies leave.
- **`public/scripts/pdf.worker.min.mjs` regenerated for 4.8.69.**
  `PreviewPDF.tsx` sets
  `pdfjs.GlobalWorkerOptions.workerSrc = "./scripts/pdf.worker.min.mjs"`: a
  committed static copy, not the one in `node_modules`. pdfjs refuses to
  run when library and worker versions differ, so they change together, in
  one commit.
  - How upstream produced the file was verified first: the committed 4.4.168
    copy is **byte-identical** to
    `prettier --parser babel < node_modules/pdfjs-dist/build/pdf.worker.min.mjs`.
  - The 4.8.69 copy is made the same way.
- The bundle is rebuilt. It contains only pdfjs 4.8.69, and
  `build/scripts/pdf.worker.min.mjs` equals the public copy.

The Node version itself does not change here; that is the next PR. This one
is proven on Node 18, so it can be reviewed on its own.

## The PDF preview, checked in a browser

The stand (a one-off, outside the repository): Chromium (Playwright 1.49.0)
renders a generated one-page PDF with `react-pdf` 9.2.1, as
`PreviewPDF.tsx` does (`<Document>`/`<Page>`, worker from a static
`./scripts…/pdf.worker.min.mjs`), served over HTTP.

| Worker | Result |
|---|---|
| regenerated 4.8.69 | loads (1 page), canvas rendered, text layer reads "Hello from the console PDF check" |
| old 4.4.168, as a negative control | `The API version "4.8.69" does not match the Worker version "4.4.168".` |

The control shows the stand would catch a worker left behind. Not covered:
the console's own preview page with a real object from MinIO. The stand uses
the same library, version, components and worker loading.

## Why not the obvious alternatives

- **Stay on Node 18.** It gets no security fixes.
- **Install cairo on every CI runner and developer machine** so canvas 2 can
  compile. That would be a system dependency for a module the console never
  runs.
- **Remove canvas.** It is pdfjs's optional dependency, and yarn has no clean
  way to drop one (note 09).
- **`pdfjs-dist` 4.10, which uses `@napi-rs/canvas`.** react-pdf 9.2.1 pins
  `pdfjs-dist` 4.8.69 exactly. Forcing another version under it is a
  resolution against its declared dependency, and canvas 3 already solves
  the problem.

## Tests

| Check | Result |
|---|---|
| `yarn install --immutable` | ok |
| `yarn why` | react-pdf 9.2.1, pdfjs-dist 4.8.69, canvas 3.2.3, node-gyp 11.5.0, tar 7.5.23; node-pre-gyp absent |
| canvas in Node | loads, renders a PNG |
| `./check-warnings.sh`, `./check-prettier.sh` (covers the regenerated worker), `./check-deadcode.sh` | ok |
| `yarn test` | 41/41 |
| production audit | 4 moderate, unchanged; nothing new |
| PDF rendering in Chromium | see above |
