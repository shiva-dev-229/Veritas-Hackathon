"""FastAPI inference server for the Veritas keystroke model.

Run with:  python main.py   (serves on http://127.0.0.1:8000)
"""
import logging
import math
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

MODEL_DIR = Path(os.environ.get(
    "PEAS_MODEL_DIR",
    Path(__file__).resolve().parent.parent / "model",
))
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from data import _encode_features, FEATURE_NAMES  # noqa: E402  (repo's own encoder)
from model import KeystrokeLSTM, ModelConfig  # noqa: E402

CHECKPOINT = Path(os.environ.get("PEAS_CHECKPOINT", MODEL_DIR / "runs/run2/best.pt"))
MIN_KEYSTROKES = 8
TRAIN_WINDOW_MS = 5 * 60 * 1000
THRESHOLD = 0.5

logger = logging.getLogger("veritas.api")
logging.basicConfig(level=logging.INFO)

MODEL: Optional[KeystrokeLSTM] = None
MODEL_INFO: str = "KeystrokeLSTM (not loaded)"


def load_model(path: Any) -> Tuple[KeystrokeLSTM, str]:
    """Load the checkpoint dict and rebuild the model from its stored config."""
    path = Path(path)
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    cfg = dict(ckpt["model_config"])
    if "lstm_hidden_sizes" in cfg:
        cfg["lstm_hidden_sizes"] = tuple(cfg["lstm_hidden_sizes"])
    model = KeystrokeLSTM(ModelConfig(**cfg))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    info = f"KeystrokeLSTM {path.parent.name}/{path.name} (epoch {ckpt.get('epoch')})"
    return model, info


@asynccontextmanager
async def lifespan(app: FastAPI):
    global MODEL, MODEL_INFO
    try:
        MODEL, MODEL_INFO = load_model(CHECKPOINT)
        logger.info("Loaded model: %s", MODEL_INFO)
    except Exception:
        logger.exception("Failed to load model from %s; server will run without it", CHECKPOINT)
        MODEL = None
    yield


app = FastAPI(title="Veritas inference API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Row(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hand: Optional[str] = None
    hold_time: Optional[float] = None
    direction: Optional[str] = None
    latency: Optional[float] = None
    flight: Optional[float] = None
    timestamp: Optional[float] = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    age: Optional[float] = None
    gender: Optional[str] = None
    startedAt: Optional[str] = None
    userAgent: Optional[str] = None


class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meta: Optional[Meta] = None
    rows: List[Row]
    summary: Optional[dict] = None


def _finite(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def rows_to_frame(rows: List[dict]) -> pd.DataFrame:
    """Convert front-end rows into the frame shape expected by data._encode_features.

    Rows missing a timing value (e.g. the first row) are dropped. Every row,
    skipped or not, updates the previous-hand state used for space directions.
    """
    columns = ["hand", "direction", "hold_ms", "latency_ms", "flight_ms"]
    records = []
    prev_side = "S"
    for r in rows:
        hold = _finite(r.get("hold_time"))
        latency = _finite(r.get("latency"))
        flight = _finite(r.get("flight"))
        raw_hand = r.get("hand")
        hand = "S" if raw_hand is None else str(raw_hand).upper()

        if hold is not None and latency is not None and flight is not None:
            direction_raw = r.get("direction")
            if direction_raw is None:
                direction = ""
            else:
                direction = str(direction_raw).upper()
                if direction == "S":
                    direction = prev_side + "S"
            records.append({
                "hand": hand,
                "direction": direction,
                "hold_ms": hold,
                "latency_ms": latency,
                "flight_ms": flight,
            })
        prev_side = hand

    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records, columns=columns)


def encode_rows(rows: List[dict]) -> np.ndarray:
    return _encode_features(rows_to_frame(rows))


def predict_proba(x: np.ndarray) -> float:
    """Score one session. x is [T, 10] (or [1, T, 10]); returns P(Parkinson's-like)."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[None, :, :]
    seq_len = arr.shape[1]
    tensor = torch.from_numpy(arr)
    lengths = torch.tensor([seq_len], dtype=torch.long)
    with torch.no_grad():
        return torch.sigmoid(MODEL(tensor, lengths)).reshape(-1)[0].item()


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL is not None}


@app.post("/predict")
def predict(session: Session):
    if MODEL is None:
        return JSONResponse(status_code=503, content={"detail": "Model is not loaded on the server."})

    rows = [r.model_dump() for r in session.rows]
    try:
        frame = rows_to_frame(rows)
        n = len(frame)
        if n < MIN_KEYSTROKES:
            return JSONResponse(status_code=422, content={
                "detail": (
                    f"Too few keystrokes to score: got {n}, need at least {MIN_KEYSTROKES}. "
                    "Please complete the full typing test."
                ),
            })
        x = encode_rows(rows)
        score = predict_proba(x)
    except Exception:
        logger.exception("Model inference failed")
        return JSONResponse(status_code=500, content={
            "detail": "Model inference failed. You can still download your data.",
        })

    warnings: List[str] = []
    stamps = [r["timestamp"] for r in rows if _finite(r.get("timestamp")) is not None]
    if stamps and (max(stamps) - min(stamps)) < TRAIN_WINDOW_MS:
        warnings.append(
            "Session is shorter than the 5-minute windows the model was trained on; "
            "the score is less reliable."
        )
    warnings.append("Research prototype (test ROC-AUC about 0.60); not a diagnosis.")

    label = "higher likelihood" if score >= THRESHOLD else "lower likelihood"
    return {
        "score": round(float(score), 4),
        "label": label,
        "details": {
            "n_keystrokes": n,
            "model": MODEL_INFO,
            "warnings": warnings,
        },
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        msg = str(first.get("msg", "invalid value"))
        summary = f"{loc}: {msg}" if loc else msg
    else:
        summary = "unknown error"
    return JSONResponse(status_code=422, content={"detail": f"Invalid request body: {summary}"})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %r", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
