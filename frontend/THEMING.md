# peas theming

## Variables (the only place colors live)
| var | used for |
|---|---|
| `--bg` | page background |
| `--main` | accent: wordmark, caret, live stats, big result numbers, histogram bars, focus borders |
| `--sub` | untyped letters, labels, hints, footer, histogram axis |
| `--sub-alt` | panels/cards: buttons, inputs, score panel, picker rows |
| `--text` | correct letters, body text, button text |
| `--error` | incorrect letters, error underline, "model not reachable" message |
| `--error-extra` | extra (over-typed) letters, dimmer than `--error` |

## Files
- `css/themes.css` — the ONLY file with literal colors. `:root, [data-theme="default"]` holds the default palette; every other theme is `[data-theme="<id>"] { ...7 vars... }`. Selectors are attribute-only (not `html[...]`) so any element with `data-theme` (e.g. picker swatches) gets that palette.
- `css/style.css` — uses `var(--…)` only.
- `css/picker.css` — picker UI, `var(--…)` only.
- `js/results.js` — histogram reads `--main`, `--sub` via `getComputedStyle(document.documentElement)` at draw time; error text uses class `.error-text` (no inline colors).
- `js/theme.js` — `PT.theme.apply(name)`, `PT.theme.list()`, `PT.theme.current()`, `PT.theme.isOpen()`. localStorage key `peas-theme` (try/catch). Inline script in `index.html <head>` sets `data-theme` on `<html>` before paint.

## Theme ids (themes.css and theme.js must match exactly)
`default`, `light`, `dracula`, `nord`, `solarized-dark`, `solarized-light`, `gruvbox-dark`, `catppuccin-mocha`, `rose-pine`, `monokai`, `forest`, `high-contrast`
