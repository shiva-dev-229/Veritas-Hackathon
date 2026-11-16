"""Participant metadata and keystroke ingestion, sessionization and window sampling."""
from pathlib import Path
from datetime import timedelta
import csv
import re
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

FEATURE_NAMES = [
    "hold_ms", "latency_ms", "flight_ms",
    "hand_left", "hand_right",
    "direction_LL", "direction_LR", "direction_RL", "direction_RR", "direction_space",
]

PARTICIPANT_FILENAME = re.compile(r"^User_([A-Za-z0-9]{10})\.txt$", re.IGNORECASE)
KEYSTROKE_FILENAME = re.compile(r"^([A-Za-z0-9]{10})_(\d{4})\.txt$", re.IGNORECASE)


def _parse_bool(value, field_name):
    value = str(value).strip().lower()
    if value in {"true", "yes", "1", "y"}:
        return True
    if value in {"false", "no", "0", "n"}:
        return False
    raise ValueError(f"Invalid boolean value for {field_name}: {value!r}")


def read_participant_file(path: Path):
    """Read key: value participant metadata from User_<10-char-id>.txt."""
    match = PARTICIPANT_FILENAME.match(path.name)
    if not match:
        return None, None
    user_key = match.group(1).upper()
    fields = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    if "parkinsons" not in fields:
        raise ValueError(f"{path}: missing required 'Parkinsons:' field")

    label = int(_parse_bool(fields["parkinsons"], "Parkinsons"))
    metadata = {
        "user_key": user_key,
        "label": label,
        "birth_year": _optional_int(fields.get("birthyear")),
        "gender": fields.get("gender"),
        "tremors": _optional_bool(fields.get("tremors")),
        "diagnosis_year": _optional_int(fields.get("diagnosisyear")),
        "sided": fields.get("sided"),
        "updrs": _parse_updrs(fields.get("updrs")),
        "impact": fields.get("impact"),
        "levadopa": _optional_bool(fields.get("levadopa")),
        "da": _optional_bool(fields.get("da")),
        "maob": _optional_bool(fields.get("maob")),
        "other": _optional_bool(fields.get("other")),
    }
    return user_key, metadata


def _optional_int(value):
    if value is None or value.strip().lower() in {"", "none", "don't know", "unknown", "n/a"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _optional_bool(value):
    if value is None or value.strip().lower() in {"", "none", "don't know", "unknown", "n/a"}:
        return None
    return _parse_bool(value, "optional metadata")


def _parse_updrs(value):
    if value is None or value.strip().lower() in {"", "don't know", "unknown", "none", "n/a"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_participants(participants_dir: str):
    """Load all User_<ID>.txt files. Returns label map and metadata map."""
    labels, metadata = {}, {}
    paths = sorted(Path(participants_dir).glob("User_*.txt"))
    if not paths:
        raise RuntimeError(f"No participant files matching User_<10-char-id>.txt found in {participants_dir}")
    for path in paths:
        user_key, info = read_participant_file(path)
        if user_key is None:
            continue
        if user_key in labels:
            raise ValueError(f"Duplicate participant ID {user_key}")
        labels[user_key] = info["label"]
        metadata[user_key] = info
    if not labels:
        raise RuntimeError("No valid participant metadata files were found.")
    return labels, metadata


def _read_keystroke_file(path: Path) -> pd.DataFrame:
    # The supplied sample is tab-separated; accept comma, tab or whitespace.
    raw = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    rows = []
    for line in raw:
        line = line.strip().rstrip("\\").strip()
        if not line:
            continue
        if "," in line:
            parts = next(csv.reader([line], skipinitialspace=True))
        elif "\t" in line:
            parts = line.split("\t")
        else:
            parts = re.split(r"\s+", line)
        parts = [p.strip() for p in parts]
        if parts and parts[0].lower() in {"userkey", "user_key"}:
            continue
        if len(parts) >= 8:
            rows.append(parts[:8])

    columns = ["user_key", "date", "time", "hand", "hold_ms",
               "direction", "latency_ms", "flight_ms"]
    if not rows:
        return pd.DataFrame(columns=columns + ["datetime"])
    df = pd.DataFrame(rows, columns=columns)
    df["user_key"] = df["user_key"].astype(str).str.upper()
    df["datetime"] = pd.to_datetime(
        df["date"].astype(str).str.zfill(6) + " " + df["time"].astype(str),
        format="%y%m%d %H:%M:%S.%f", errors="coerce"
    )
    for col in ["hold_ms", "latency_ms", "flight_ms"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^0-9.+-]", "", regex=True),
            errors="coerce"
        )
    df["hand"] = df["hand"].astype(str).str.upper()
    df["direction"] = df["direction"].astype(str).str.upper()
    df = df.dropna(subset=["datetime", "hold_ms", "latency_ms", "flight_ms"])
    return df.sort_values("datetime").reset_index(drop=True)


def _encode_features(frame: pd.DataFrame) -> np.ndarray:
    hand = frame["hand"].fillna("").astype(str)
    direction = frame["direction"].fillna("").astype(str)
    x = np.column_stack([
        frame["hold_ms"].to_numpy(dtype=np.float32),
        frame["latency_ms"].to_numpy(dtype=np.float32),
        frame["flight_ms"].to_numpy(dtype=np.float32),
        (hand == "L").to_numpy(dtype=np.float32),
        (hand == "R").to_numpy(dtype=np.float32),
        (direction == "LL").to_numpy(dtype=np.float32),
        (direction == "LR").to_numpy(dtype=np.float32),
        (direction == "RL").to_numpy(dtype=np.float32),
        (direction == "RR").to_numpy(dtype=np.float32),
        (direction == "S").to_numpy(dtype=np.float32),
    ])
    x[:, :3] = np.clip(x[:, :3], 0, 10000)
    x[:, :3] = np.log1p(x[:, :3])
    return x.astype(np.float32)


def build_windows(data_dir: str, labels: dict, window_minutes: int = 2,
                  session_gap_hours: float = 3.0, stride_seconds: int = 60,
                  min_events: int = 8):
    """Return (features, label, participant_id, window_id) samples."""
    windows = []
    paths = sorted(Path(data_dir).glob("*"))
    for path in paths:
        if not path.is_file():
            continue
        match = KEYSTROKE_FILENAME.match(path.name)
        if not match:
            continue
        user_key = match.group(1).upper()
        if user_key not in labels:
            continue

        frame = _read_keystroke_file(path)
        if frame.empty:
            continue
        # Filename ID is authoritative; also verify row-level ID when present.
        frame = frame[frame["user_key"] == user_key]
        if frame.empty:
            continue

        frame = frame.sort_values("datetime").reset_index(drop=True)
        gaps = frame["datetime"].diff()
        date_changed = frame["datetime"].dt.date != frame["datetime"].shift().dt.date
        new_session = gaps.isna() | (gaps > pd.Timedelta(hours=session_gap_hours)) | date_changed
        frame["session_id"] = new_session.cumsum()

        duration = timedelta(minutes=window_minutes)
        stride = timedelta(seconds=stride_seconds)
        for session_id, session in frame.groupby("session_id", sort=True):
            session = session.reset_index(drop=True)
            start, end = session["datetime"].iloc[0], session["datetime"].iloc[-1]
            current = start
            used_starts = set()
            while current + duration <= end:
                stop = current + duration
                chunk = session[(session["datetime"] >= current) & (session["datetime"] < stop)]
                if len(chunk) >= min_events:
                    windows.append((_encode_features(chunk), labels[user_key], user_key,
                                    f"{path.name}:{session_id}:{current.isoformat()}"))
                    used_starts.add(current)
                current += stride

            # Add a final trailing window when it is not already represented.
            final_start = end - duration
            if final_start > start and final_start not in used_starts:
                chunk = session[(session["datetime"] >= final_start) & (session["datetime"] <= end)]
                if len(chunk) >= min_events:
                    windows.append((_encode_features(chunk), labels[user_key], user_key,
                                    f"{path.name}:{session_id}:final"))
    return windows


class WindowDataset(Dataset):
    def __init__(self, windows):
        self.windows = windows
    def __len__(self):
        return len(self.windows)
    def __getitem__(self, idx):
        x, y, user, session = self.windows[idx]
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32), user, session


def collate_windows(batch):
    xs, ys, users, sessions = zip(*batch)
    lengths = torch.tensor([len(x) for x in xs], dtype=torch.long)
    max_len = int(lengths.max())
    feature_count = xs[0].shape[1]
    padded = torch.zeros(len(xs), max_len, feature_count, dtype=torch.float32)
    for i, x in enumerate(xs):
        padded[i, :len(x)] = x
    return padded, torch.stack(ys), lengths, users, sessions
