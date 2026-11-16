"""Tests for the Veritas keystroke inference API (api/main.py)."""
import copy
import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

API_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(TESTS_DIR))

import main  # noqa: E402
from make_sample import make_session  # noqa: E402


@pytest.fixture(scope="module")
def client():
    # The model is loaded in the lifespan hook, so the client must be used as a context manager.
    with TestClient(main.app) as c:
        yield c


def _repo_data():
    """Import the repo's own data.py from the model directory (not a copy)."""
    model_dir = str(Path(main.MODEL_DIR))
    if model_dir not in sys.path:
        sys.path.insert(0, model_dir)
    mod = importlib.import_module("data")
    assert Path(mod.__file__).resolve().parent == Path(model_dir).resolve()
    return mod


def _scalar(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return float(np.ravel(value)[0])


# 1. health ------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


# 2. happy path -----------------------------------------------------------------

def test_predict_sample_session(client):
    r = client.post("/predict", json=make_session(n=300))
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 1
    assert isinstance(body["label"], str) and body["label"]
    details = body["details"]
    assert details["n_keystrokes"] == 299  # first row has no latency/flight
    assert isinstance(details["warnings"], list)
    assert all(isinstance(w, str) for w in details["warnings"])
    assert isinstance(details["model"], str)


# 3. too few keystrokes -------------------------------------------------------

def test_too_few_keystrokes(client):
    r = client.post("/predict", json=make_session(n=5))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str)
    assert "Too few" in detail


# 4. malformed bodies ----------------------------------------------------------

def test_malformed_rows_not_a_list(client):
    r = client.post("/predict", json={"rows": "nope"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_malformed_hold_time_not_numeric(client):
    session = make_session(n=50)
    session["rows"][10]["hold_time"] = "abc"
    r = client.post("/predict", json=session)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_malformed_non_json_body(client):
    r = client.post("/predict", content=b"this is not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


# 5. browser rows -> model frame -----------------------------------------------

def test_rows_to_frame_conversion():
    rows = [
        {"timestamp": 0, "hand": "L", "hold_time": 100, "latency": None,
         "flight": None, "direction": None},
        {"timestamp": 150, "hand": "L", "hold_time": 90, "latency": 150,
         "flight": 50, "direction": "LL"},
        # space after an L key: browser "S" -> Tappy "LS"; hand None -> "S"
        {"timestamp": 350, "hand": None, "hold_time": 80, "latency": 200,
         "flight": 60, "direction": "S"},
        # following key keeps its two-letter direction
        {"timestamp": 560, "hand": "R", "hold_time": 95, "latency": 210,
         "flight": 40, "direction": "SR"},
    ]
    frame = main.rows_to_frame(rows)
    assert len(frame) == 3  # first row dropped
    assert list(frame.columns) == ["hand", "direction", "hold_ms", "latency_ms", "flight_ms"]
    assert list(frame["hand"]) == ["L", "S", "R"]
    assert list(frame["direction"]) == ["LL", "LS", "SR"]
    assert list(frame["hold_ms"]) == [90, 80, 95]
    assert list(frame["latency_ms"]) == [150, 200, 210]
    assert list(frame["flight_ms"]) == [50, 60, 40]


# 6. parity with the repo's own pipeline ----------------------------------------

def _write_tappy_file(rows, path):
    """Write rows[1:] in the Tappy keystroke format the repo's data.py reads."""
    base = datetime(2026, 11, 15, 10, 0, 0)  # date 261115
    lines = []
    for i in range(1, len(rows)):
        r = rows[i]
        prev = rows[i - 1]
        stamp = base + timedelta(milliseconds=round(r["timestamp"]))
        time_str = stamp.strftime("%H:%M:%S") + ".%03d" % (stamp.microsecond // 1000)
        hand = r["hand"] if r["hand"] is not None else "S"
        if r["direction"] == "S":
            prev_side = prev["hand"] if prev["hand"] is not None else "S"
            direction = prev_side + "S"  # Tappy style: LS / RS / SS
        else:
            direction = r["direction"]
        fields = [
            "ABCDEFGHIJ",
            "261115",
            time_str,
            hand,
            str(r["hold_time"]),
            direction,
            str(r["latency"]),
            str(r["flight"]),
        ]
        lines.append("\t".join(fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_parity_with_repo_pipeline(tmp_path):
    repo_data = _repo_data()
    rows = make_session(n=300)["rows"]

    keystroke_file = tmp_path / "ABCDEFGHIJ_2611.txt"
    _write_tappy_file(rows, keystroke_file)

    frame = repo_data._read_keystroke_file(keystroke_file)
    x_repo = repo_data._encode_features(frame)
    x_api = main.encode_rows(rows)

    assert x_repo.shape == x_api.shape == (299, 10)
    assert np.allclose(x_repo, x_api, atol=1e-5)

    p_repo = main.predict_proba(x_repo)
    p_api = main.predict_proba(x_api)
    assert abs(p_repo - p_api) <= 1e-6

    # and both agree with the model's own forward pass
    direct = main.MODEL.predict_proba(
        torch.tensor(x_api)[None], torch.tensor([len(x_api)])
    )
    assert abs(p_api - _scalar(direct)) <= 1e-6


# 7. negative flight is clipped to 0 before log1p --------------------------------

def test_negative_flight_clipped_to_zero():
    rows = make_session(n=3)["rows"]
    rows[1]["flight"] = -20.0  # overlapping keys
    assert main.encode_rows(rows)[0, 2] == 0.0
