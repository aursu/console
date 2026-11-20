# 06 — Widget PNG export through html2canvas; react-component-export-image removed

Date: 2026-11-20. PR: aursu/console#13. Plan step 1.5 (aursu/minio
`fork/reports/04-plan-final-build.md`), first PR of the step. Three options
were considered (below); `html2canvas` directly was the recommendation, and
the project owner accepted it.

## The problem

The dashboard widgets have a download menu with two options, CSV and PNG
(`DownloadWidgetDataButton.tsx`, used by the Prometheus line and bar chart
widgets). PNG called `exportComponentAsPNG` from
`react-component-export-image` 1.0.6. That package is a thin wrapper:

- it renders the element with `html2canvas`;
- it saves the canvas as a PNG through a download link;
- it also offers PDF export through jsPDF, which the console never used.

The package is unmaintained (last release 2021). Its prebuilt `dist` bakes in
its own copies of `html2canvas` and **jsPDF 1.5.3**, and it declares
`jspdf` as a dependency. As a result:

- **in the shipped bundle:** jsPDF 1.5.3 in chunk `8104`, unused code with 15
  known advisories (note 01);
- **in the production dependency closure** that CI audits
  (`yarn npm audit --environment production`): jsPDF 3.0.0 and what it pulls
  in, DOMPurify, canvg and fflate. That is **36 of the 99 advisories**,
  3 of them critical.

Upstream removed the package in `63c6d89` together with the whole dashboard.
The full console keeps the dashboard, so the fix is ours.

## The options, and why `html2canvas` directly was recommended

| Option | Effect |
|---|---|
| **`html2canvas` directly** (recommended, accepted) | same renderer as now, already in the bundle (1.4.1), no advisories in any version; about 25 lines of our code |
| `html-to-image` | maintained, also no advisories, but a different renderer (SVG `foreignObject`), so the PNG may look different, and a new dependency in the bundle |
| drop the PNG option | least code, but removes a feature of the full console |

Why `html2canvas` directly:

- **Nothing the user sees changes.** The PNG has always been drawn by
  `html2canvas`; the package only wrapped it. The only part removed is a
  PDF path that was never used.
  - `html-to-image` works differently. It serialises the DOM into SVG
    `<foreignObject>` and rasterises that, so web fonts, external CSS, inner
    SVG (the widgets are recharts SVG) and Safari's handling of
    `foreignObject` can all give a different image.
  - That difference would have to be checked visually on a live dashboard
    with Prometheus data, which this project cannot test.
- **No new code enters the supply chain.** `html2canvas` 1.4.1 is already in
  the bundle and the lockfile. The change only removes packages.
  `html-to-image` would be a new dependency in code shipped to browsers.
- **The full console keeps its feature.** Restoring the full console is the
  purpose of this fork, so removing a working feature to fix a dependency
  problem goes against it.
- **The attack surface is small.** `html2canvas` runs only when a user
  clicks the download button, and only on the console's own DOM. It never
  sees untrusted input.

The cost: `html2canvas` has not been released since 1.4.1 (2022). That is a
risk to watch, not a present problem; no advisories are known in any
version. If one appears, `html-to-image` is the fallback. The call sits in
one file (`exportElementAsPNG.ts`), so switching means changing that file and
its test.

## What changed

- `src/screens/Console/Dashboard/exportElementAsPNG.ts`: replaces
  `exportComponentAsPNG` and does exactly what it did, read from the
  package's `dist/index.js`:
  - `html2canvas(element, { scrollY: -window.scrollY, useCORS: true })`;
  - `canvas.toDataURL("image/png", 1)`;
  - a temporary `<a download>` that is clicked and removed.

  Two differences, neither visible to users:
  - It takes the DOM element, not a React ref, and skips `findDOMNode`. Both
    callers pass a ref to a plain `<div>`, and `findDOMNode` returns that
    `<div>` itself.
  - It drops the `window.open` fallback for browsers without the `download`
    attribute. Every browser the console supports has it.
- `DownloadWidgetDataButton.tsx` calls it with `componentRef.current`.
- `package.json`:
  - `html2canvas ^1.4.1` becomes a direct dependency;
  - `react-component-export-image` is removed;
  - the `jspdf ^3.0.0` resolution added by `9e0416f` is removed. jsPDF is no
    longer in the tree, so the resolution has nothing to resolve.
- `yarn.lock`: 133 lines fewer. Removed: `react-component-export-image`,
  `jspdf`, `dompurify`, `canvg`, `fflate`, `atob`, `btoa`, `rgbcolor`,
  `stackblur-canvas`, `svg-pathdata`, `@types/raf`, and the extra ranges of
  `@babel/runtime`, `core-js`, `regenerator-runtime` and
  `@types/trusted-types`. Nothing was added; `html2canvas` stays 1.4.1.
- The bundle is rebuilt:
  - chunk `8104` (jsPDF) is gone;
  - `html2canvas` is now bundled from `node_modules`, in chunk `2192`;
  - the JavaScript shrinks from 4,829,715 to 4,567,617 bytes (−262 KB).

## Why not the obvious alternatives

- **Keep the package and pin jsPDF higher via `resolutions`.** The bundle
  would still ship the 1.5.3 copy baked into the package's `dist`, whatever
  the lockfile says. That is how note 01 found the `9e0416f` resolution had
  no effect on the bundle.
- **Fork `react-component-export-image`.** It would mean maintaining a
  package to keep 25 lines of code.
- **Keep the PDF option for later.** It was never offered in the UI.

## Tests

| Check | Result |
|---|---|
| `exportElementAsPNG.test.ts` (new, 3 tests): `html2canvas` called with the element and the package's options; canvas saved as `image/png` at quality 1 under the given file name, link removed afterwards; nothing happens without an element | pass |
| `yarn test` | 16/16, 3/3 suites |
| `./check-warnings.sh`, `./check-prettier.sh`, `./check-deadcode.sh` | ok |
| `yarn install --immutable` after the lockfile update | ok |
| `yarn why jspdf` | nothing |
| bundle: files mentioning `jsPDF` | master 1 (`8104`), now 0 |
| `yarn npm audit --recursive --environment production` | **99 → 63**; removed: DOMPurify 22, jsPDF 12, canvg 1, fflate 1; nothing new. Critical 4 → 2 (`form-data`, `tar`), high 39 → 30 |

Not tested in a real browser: a widget's PNG needs the dashboard, which needs
Prometheus metrics, and the console's e2e suites do not cover it. The risk
is low: it is the same `html2canvas` 1.4.1, called with the same options, as
before.
