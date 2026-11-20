// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Jest setup, loaded by react-scripts before every test file.
//
// Under Jest, superagent loads its Node entry (the browser bundle uses its
// browser build instead). From formidable 3.5.4 on, that entry pulls in
// @paralleldrive/cuid2 and @noble/hashes, which call TextEncoder when
// imported. Jest's jsdom environment does not define it; Node does.
import { TextDecoder, TextEncoder } from "util";

Object.assign(globalThis, { TextDecoder, TextEncoder });
