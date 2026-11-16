# Install and run peas

peas has two parts that run side by side on your computer:

- `api/`: a Python (FastAPI) server that loads the model and scores a typing session.
- `frontend/`: a plain HTML/CSS/JS typing test that you serve as static files and open in a browser.

## Prerequisites

- Python 3.9 or newer, with `pip` and `venv` (tested on Python 3.9.6)
- Git
- A modern browser (Chrome, Firefox, Safari or Edge)
- Node.js is optional. You only need it to run the front-end unit tests.

## 1. Clone the repo

```
git clone https://github.com/shiva-dev-229/Veritas-Hackathon.git
cd Veritas-Hackathon
```

## 2. Backend (model API)

The model weights are already in the repo at `model/runs/run2/best.pt`, and the API loads that file by default. You don't need to download anything.

### macOS / Linux

```
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8000
```

### Windows (PowerShell)

```
cd api
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8000
```

The first install downloads PyTorch, which takes a few minutes. When the server is ready, the log shows `Loaded model: KeystrokeLSTM run2/best.pt (epoch 86)` followed by `Uvicorn running on http://127.0.0.1:8000`. Leave this terminal open.

Optional: run the API tests from `api/`, with the virtualenv active:

```
python -m pytest tests -q
```

## 3. Front end

Open a second terminal at the repo root.

macOS / Linux:

```
cd frontend
python3 -m http.server 5500
```

Windows:

```
cd frontend
py -m http.server 5500
```

Then open http://localhost:5500 in your browser.

Optional, if Node.js is installed: run `node frontend/tests/features.test.js` from the repo root.

## How the two connect

The front end sends each finished test to the URL in `PT.config.API_URL`, which is set on line 2 of `frontend/js/api.js`:

```
PT.config = { API_URL: "http://localhost:8000/predict" };
```

If you run the API on a different host or port, change this line to match.

## Quick check

1. Confirm the API is up: open http://localhost:8000/health or run `curl http://localhost:8000/health`. You should see:
   ```
   {"status":"ok","model_loaded":true}
   ```
2. Do a full test at http://localhost:5500:
   - Fill in age and gender, or click "skip".
   - Type the words until the test ends. It needs at least 300 keystrokes.
   - The results page should show a model score as a percentage with a label, and the note "screening aid, not a diagnosis".

## Troubleshooting

- **"Model not reachable, you can still download your data"** means the browser could not reach the API. Check that:
  - the API terminal is still running;
  - http://localhost:8000/health responds;
  - `API_URL` in `frontend/js/api.js` matches the API's port.
- **CORS error in the browser console:**
  - The API already allows all origins, so a CORS error usually means the request reached a different server on port 8000. Stop that server and start the API again.
  - Open the front end through `http://localhost:5500`, not by double-clicking `index.html`.
- **Port already in use** (`address already in use` or `Errno 48`/`98`/`10048`): something else is using the port. Either stop it, or pick another port.
  - Find what's using it on macOS/Linux: `lsof -i :8000`
  - Find what's using it on Windows: `netstat -ano | findstr :8000`
  - To use another port, run for example `uvicorn main:app --port 8001`, and set `API_URL` to `http://localhost:8001/predict`.
  - For the front end, run for example `python3 -m http.server 5501`.
- **Missing weights:** `/health` shows `"model_loaded": false`, and the API log shows `Failed to load model`.
  - Make sure `model/runs/run2/best.pt` exists. If it's missing, restore it from the repo with `git checkout -- model/runs`.
  - Always start the API from inside `api/`.
  - To load a different checkpoint, set the `PEAS_CHECKPOINT` environment variable to its path before starting the API.
- **Wrong Python version:** check it with `python3 --version` (macOS/Linux) or `py --version` (Windows).
  - Python older than 3.9 is not supported.
  - If `pip install` can't find a `torch` version, your Python may be too new for PyTorch. Install Python 3.11 or 3.12 and recreate the virtualenv. For example, on macOS/Linux run `python3.11 -m venv .venv`, and on Windows run `py -3.11 -m venv .venv`.
- **`uvicorn: command not found`:** the virtualenv isn't active. Activate it again, or run `python -m uvicorn main:app --port 8000`.
