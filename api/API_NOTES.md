# API_NOTES — wrapping the Veritas keystroke model

Model code: `../model` (training code and weights). The API imports it and does not modify it.
The API imports from it by adding that folder to `sys.path` (override with env `PEAS_MODEL_DIR`).

## Weights
- Load `runs/run2/best.pt` (epoch 86, best test ROC-AUC **0.601**). run1/best.pt is worse (0.586). Override with env `PEAS_CHECKPOINT`.
- The checkpoint is a dict, not a full model: `{"model_state_dict", "model_config", "arguments", "epoch", "best_metric", ...}`.
- Load: `ckpt = torch.load(path, map_location="cpu", weights_only=False)`;
  `model = KeystrokeLSTM(ModelConfig(**ckpt["model_config"]))` (from `model.py`);
  `model.load_state_dict(ckpt["model_state_dict"]); model.eval()`. CPU is fine.
- model_config: input_size=10, lstm_hidden_sizes=(64,64,32), attention_heads=4, attention_hidden_size=32, dropout=0.3.
  (Note: `ModelConfig` defaults to input_size=8, which is WRONG; always build from the checkpoint's config.)

## Input
- A **variable-length raw per-keystroke sequence**, not summary features: tensor `x` `[batch, time, 10]` float32 plus `lengths` `[batch]` long.
- Built by the repo's `data._encode_features(frame)` from a pandas frame with columns
  `hold_ms, latency_ms, flight_ms, hand, direction`. Feature order (`data.FEATURE_NAMES`):
  `hold_ms, latency_ms, flight_ms, hand_left, hand_right, direction_LL, direction_LR, direction_RL, direction_RR, direction_space`.
- Scaling: the three timing columns are clipped to [0, 10000] ms then `log1p`. Negative flight becomes 0 (same as training). No other normalization.
- Training dropped rows with missing latency/flight (`dropna`), so the first row (null latency/flight) must be dropped.
- Training windows: **5 minutes** (checkpoint args `window_minutes=5`; the README says 2, but the checkpoint says 5), stride 60 s, `min_events=8`. No padding needed for batch size 1.

## Output
- `model(x, lengths)` returns one logit per sequence. `sigmoid(logit)` gives P(Parkinson's). **Class 1 = Parkinson's** (`Parkinsons: True` maps to 1).
- Training metrics used a threshold of 0.5.

## Conversion from the front-end rows (done in the API, not the front end)
| front end | model / Tappy |
|---|---|
| `hold_time`, `latency`, `flight` (ms) | `hold_ms`, `latency_ms`, `flight_ms` (ms, same units) |
| `hand` "L"/"R"/null(space) | "L"/"R"/"S". null and "S" both encode to hand_left=hand_right=0 |
| `direction` "LL","LR","RL","RR","SL","SR" | unchanged |
| `direction` "S" (current key is space) | `<prev side>` + "S", e.g. "LS","RS","SS" (Tappy style) |
| first row (latency/flight null) | dropped |
| `timestamp` | not a model feature; used only for the duration warning |

**Assumption (dataset not in the repo, so it can't be checked):** Tappy directions are two-letter codes (LL, LR, LS, RL, RR, RS, SL, SR, SS), so the bare "S" never appeared in training and `direction_space` was always 0. Translating "S" to "LS"/"RS"/"SS" reproduces that. Sending "S" as-is would switch on a feature the model never saw during training.

## Mismatch risks (surface as `details.warnings`)
1. Length: the browser test is about 300 keys (about 1 to 2 minutes). The model trained on 5-minute windows. Warn when the session spans under 5 minutes.
2. Device: Tappy was collected with a dedicated app on participants' own computers. Browser `performance.now()` timing and a QWERTY hand map may differ.
3. Model quality: test ROC-AUC is about 0.60 (chance is 0.5). The score is weakly informative. Always show "screening aid, not a diagnosis".

## API contract
- `POST /predict` body: `{meta:{age,gender,startedAt,userAgent}, rows:[{hand,hold_time,direction,latency,flight,timestamp}], summary:{...}}`
  - 200: `{"score": float 0..1, "label": str, "details": {"n_keystrokes": int, "model": str, "warnings": [str]}}`
    - label: score >= 0.5 → "higher likelihood (Parkinson's-like typing pattern)", else "lower likelihood".
  - 422: `{"detail": "<human readable message>"}` (too few usable keystrokes, i.e. fewer than 8 after dropping the first row, or a malformed body)
  - 503: `{"detail": "Model is not loaded"}`; 500: `{"detail": "Model inference failed"}` (never a traceback)
- `GET /health` → `{"status":"ok","model_loaded": bool}`
