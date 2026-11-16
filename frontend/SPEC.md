# peas SPEC (contract between files)

Plain classic scripts, no modules. Every JS file starts with `window.PT = window.PT || {};`.
Load order in index.html: features.js, capture.js, api.js, results.js, test.js. test.js boots on `DOMContentLoaded`.
Colors: bg #323437, accent #e2b714, sub #646669, text #d1d0c5, error #ca4754. Font: "Roboto Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace.

## Raw log entry (js/capture.js)
`{ code: string, down: number, up: number }` — `event.code`, `performance.now()` ms with decimals.
- `PT.capture.start()`: clears log, attaches `keydown`/`keyup` on `window` (capture phase) and `blur`.
- `PT.capture.stop()`: detaches listeners, discards pending (no keyup yet) keys.
- `PT.capture.getRawLog()`: returns a COPY of completed entries sorted by `down` ascending.
- Ignore `e.repeat === true`. Pending keydowns are stored in a map keyed by `code`; keyup completes the entry with the same code (NOT by order). Keyup with no pending keydown is ignored. A second keydown of a code that is already pending replaces it.
- On window `blur`: discard all pending keys.
- ALL keys are logged (Backspace, Shift, etc.); filtering happens in features.

## Features (js/features.js) — pure, no DOM. Must also work in node:
end of file: `if (typeof module !== 'undefined') module.exports = PT.features;`
- `PT.features.HAND` : object code -> "L" | "R" (Space not included).
  - L: Backquote, Digit1-5, KeyQ KeyW KeyE KeyR KeyT, KeyA KeyS KeyD KeyF KeyG, KeyZ KeyX KeyC KeyV KeyB
  - R: Digit6-9, Digit0, Minus, Equal, KeyY KeyU KeyI KeyO KeyP, BracketLeft, BracketRight, Backslash, KeyH KeyJ KeyK KeyL, Semicolon, Quote, KeyN KeyM, Comma, Period, Slash
- `PT.features.isTypingKey(code)`: true if code in HAND or code === "Space".
- `PT.features.toRows(raw, t0?)` -> Row[]. Skips entries that are not typing keys, have `repeat === true`, or `up == null`. Sorts by `down`. `t0` defaults to the smallest `down` in `raw` (any key). "previous" = previous exported row.
- Row: `{ timestamp, hand, hold_time, latency, flight, direction }` (numbers rounded to 2 decimals)
  - `timestamp` = down - t0
  - `hand` = HAND[code], or `null` for Space
  - `hold_time` = up - down
  - `latency` = down - prev.down (null for first row)
  - `flight` = down - prev.up (null for first row; negatives kept)
  - `direction`: null for first row; "S" if current is Space; otherwise (prev hand, or "S" if prev was Space) + current hand, e.g. "LR", "SL". `// TODO: verify direction codes against a real Tappy sample`
- `PT.features.summary(rows)` -> `{ count, meanHold, meanLatency, meanFlight, medianHold }` (nulls ignored; null if no values; 2 decimals).
- `PT.features.toCSV(rows)` -> string. Header `timestamp,hand,hold_time,latency,flight,direction`, null -> empty cell, `\n` line endings.
- `PT.features.toJSON(session)` -> `JSON.stringify(session, null, 2)`.
- Privacy: rows never contain key codes or text.

## Session JSON (built by test.js, sent to API and exported)
```
{ meta: { age: number|null, gender: string|null, startedAt: ISO string, userAgent: string },
  rows: Row[], summary: Summary }
```

## API (js/api.js)
- First line after namespace: `PT.config = { API_URL: "http://localhost:8000/predict" };`
- `PT.api.predict(session)` -> Promise<{score, label, details?}>. POST JSON, header Content-Type application/json, 15 s timeout via AbortController. Rejects with Error on network error, timeout, non-2xx, or response without numeric `score`.
- Response: `{ "score": 0..1, "label": string, "details": optional object }`.

## Results (js/results.js)
- `PT.results.show({ session, wpm, accuracy })`: hide `#test`, show `#results`, fill stats, draw histogram of `hold_time` on `#histogram` canvas (plain canvas, accent bars), wire buttons, call predict.
- `PT.results.hide()`: hide `#results`.
- Score panel `#scoreBody`: loading text "Analyzing…" → on success show score (as %), label; on failure "Model not reachable, you can still download your data". `#scoreNote` always reads "screening aid, not a diagnosis".
- Downloads: `peas-session-YYYYMMDD-HHMMSS.csv` / `.json` via Blob + temporary `<a download>`. Copy JSON via `navigator.clipboard.writeText` (fallback textarea+execCommand); button text briefly "copied!".
- Restart button calls `PT.test.restart()`.

## Test (js/test.js)
- `PT.test.restart()`: new 60 random common words, reset display/timer/stats, hide results, show `#test`, call `PT.capture.start()`.
- Pretest `#pretest` shown on first load; `#startBtn` reads `#age`/`#gender`, `#skipBtn` skips (meta null). Then restart(). Meta remembered for later restarts.
- Own `keydown` listener on `document` for display (ignore `e.repeat`, ignore when `#test` hidden or pretest visible, ignore ctrl/meta/alt combos). Printable single-char keys type, Space moves to next word (only if current word has ≥1 typed char), Backspace deletes within current word only. preventDefault on Space/Tab/Backspace.
- Timer + live WPM start on first typed char; update `#timer` (seconds) and `#liveWpm` every 250 ms. WPM = (correct chars incl. spaces / 5) / minutes. Accuracy = correct keypresses / total char keypresses.
- Count typing keydowns (`PT.features.isTypingKey(e.code)`). End when last word is completed (all chars typed on last word, or space after it) AND count ≥ 300. If words finished but count < 300, append 10 more words and continue.
- On end: `PT.capture.stop()`, build session (`toRows(getRawLog())`, `summary`), call `PT.results.show(...)`.
- Tab then Enter → restart. Esc → restart.
- Caret: absolutely positioned `#caret` inside `#words`, moved with CSS transition (left/top) to the active letter; blinks when idle. Scroll so the active line stays in the visible 3 lines.

## DOM ids/classes (index.html, owned by orchestrator)
Header: `#timer`, `#liveWpm`. Main: `#pretest` (`#age` number input, `#gender` select, `#startBtn`, `#skipBtn`), `#test` (`#wordsWrap` > `#words` > `.word` > `.letter`; `#caret`; `.hint`), `#results` (`#resWpm`, `#resAcc`, `#resKeys`, `#resHold`, `#resLatency`, `#resFlight`, `#scoreBody`, `#scoreNote`, canvas `#histogram`, buttons `#btnCsv`, `#btnJson`, `#btnCopy`, `#btnRestart`). Footer: `footer`.
Classes: `.hidden` (display:none), `.word.active`, `.letter.correct`, `.letter.incorrect`, `.letter.extra`, `.word.error` (underline), `#caret.idle` (blink).
