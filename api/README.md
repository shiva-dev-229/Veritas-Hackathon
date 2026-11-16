# peas model API

This API wraps the model code in `../model` (imported, not modified). Preprocessing details are in `API_NOTES.md`.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time only
.venv/bin/uvicorn main:app --port 8000                               # run
.venv/bin/python -m pytest tests -q                                  # tests (9)
```
Environment overrides: `PEAS_MODEL_DIR` (model repo path), `PEAS_CHECKPOINT` (default `runs/run2/best.pt`).
The request and response shapes are in `../frontend/README.md`, which also shows how to run both pieces in two terminals.
