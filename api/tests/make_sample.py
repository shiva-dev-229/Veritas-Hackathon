"""Build a synthetic browser typing session shaped exactly like front-end/js/features.js output.

Run as a script to (re)write sample_session.json next to this file.
"""
import json
import random
import statistics
from pathlib import Path


def _r2(x):
    if x is None:
        return None
    return round(x, 2) + 0.0  # + 0.0 normalises -0.0


def make_session(n=300, seed=0):
    rng = random.Random(seed)
    rows = []
    prev = None  # {"down", "up", "side"} of the previous keystroke (raw ms)
    for _ in range(n):
        is_space = rng.random() < 0.2  # about every 5th key is a space
        hand = None if is_space else rng.choice(["L", "R"])
        hold = max(30.0, rng.gauss(100, 20))

        if prev is None:
            down = 0.0
            latency = None
            flight = None
            direction = None
        else:
            latency = max(40.0, rng.gauss(180, 50))
            down = prev["down"] + latency
            flight = down - prev["up"]  # may be negative (overlapping keys)
            direction = "S" if is_space else prev["side"] + hand

        up = down + hold
        rows.append({
            "timestamp": _r2(down),
            "hand": hand,
            "hold_time": _r2(hold),
            "latency": _r2(latency),
            "flight": _r2(flight),
            "direction": direction,
        })
        prev = {"down": down, "up": up, "side": "S" if is_space else hand}

    holds = [r["hold_time"] for r in rows if r["hold_time"] is not None]
    lats = [r["latency"] for r in rows if r["latency"] is not None]
    flis = [r["flight"] for r in rows if r["flight"] is not None]
    summary = {
        "count": len(rows),
        "meanHold": _r2(statistics.mean(holds)) if holds else None,
        "meanLatency": _r2(statistics.mean(lats)) if lats else None,
        "meanFlight": _r2(statistics.mean(flis)) if flis else None,
        "medianHold": _r2(statistics.median(holds)) if holds else None,
    }
    return {
        "meta": {
            "age": 45,
            "gender": "female",
            "startedAt": "2026-11-15T10:00:00.000Z",
            "userAgent": "pytest",
        },
        "rows": rows,
        "summary": summary,
    }


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "sample_session.json"
    out.write_text(json.dumps(make_session(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
