"""Mock peas scoring server. Returns random scores; no model involved.

Run from mock-server/:   uvicorn server:app --port 8000
Or directly:             python3 mock-server/server.py
"""
import random

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="peas mock server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok", "mock": True}


@app.post("/predict")
async def predict(request: Request):
    # Plain dict body on purpose: no strict schema, so any session JSON is accepted.
    try:
        body = await request.json()
    except ValueError:
        body = {}
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        rows = []

    score = round(random.random(), 3)
    return {
        "score": score,
        "label": "higher risk" if score >= 0.5 else "lower risk",
        "details": {"rows_received": len(rows), "mock": True},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
