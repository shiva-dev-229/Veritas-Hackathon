# peas (MVP): keystroke-timing typing test, research screening aid (not a diagnosis)

## Run it (two terminals)
Run these from the repo root. The API loads the model from `model/runs/run2/best.pt`.

Terminal 1, real model API (first time only: `cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`):
```
cd api && .venv/bin/uvicorn main:app --port 8000
```
Terminal 2, front end:
```
cd frontend && python3 -m http.server 5500
```
Open http://localhost:5500. Check the API with `curl localhost:8000/health`, which should return `{"status":"ok","model_loaded":true}`.
API tests: `cd api && .venv/bin/python -m pytest tests -q`. Front-end tests: `node frontend/tests/features.test.js`.

Change endpoint: edit `PT.config.API_URL` (line 2 of `frontend/js/api.js`).
Mock server (random scores, no model, for UI work only): `pip install -r frontend/mock-server/requirements.txt && python3 frontend/mock-server/server.py`.

## API contract
`POST /predict` request:
```json
{ "meta": {"age": 45, "gender": "female", "startedAt": "ISO", "userAgent": "..."},
  "rows": [{"timestamp": 0, "hand": "L", "hold_time": 98.1, "latency": null, "flight": null, "direction": null}, ...],
  "summary": {"count": 300, "meanHold": 101.2, "meanLatency": 180.4, "meanFlight": 79.0, "medianHold": 99.5} }
```
`200` response:
```json
{ "score": 0.4312, "label": "lower likelihood",
  "details": {"n_keystrokes": 299, "model": "KeystrokeLSTM run2/best.pt (epoch 86)", "warnings": ["..."]} }
```
`422` response `{"detail": "Too few keystrokes to score: ..."}` (fewer than 8 usable keystrokes, or a malformed body). `500`/`503` responses are `{"detail": "..."}`. `GET /health` returns `{"status":"ok","model_loaded":true}`.
Score = sigmoid output of the LSTM, P(Parkinson's-like pattern). The label uses a 0.5 threshold. See `../api/API_NOTES.md` for preprocessing and caveats.

## Data
Rows and CSV columns (Tappy-style, ms): timestamp, hand (L/R, inferred from QWERTY map; null for space), hold_time (up−down), latency (down−prev down), flight (down−prev up; may be negative), direction (LL/LR/RL/RR, S=space, SL/SR after space).
The first row has null latency/flight/direction. No key identities or typed text are ever exported or sent.
Themes live in css/themes.css (see THEMING.md). Pick one with the "theme" button in the footer. Contract: SPEC.md.
