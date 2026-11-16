# Parkinson's keystroke sequence classifier

PyTorch research prototype for classifying **2-minute typing windows** using stacked LSTMs and multi-head temporal attention pooling.

## Folder layout

```text
dataset/
├── participants/
│   ├── User_YNVRRFC8S4.txt
│   ├── User_ZY9CCHSPF2.txt
│   └── ...
└── keystrokes/
    ├── ZY9CCHSPF2_1609.txt
    ├── YNVRRFC8S4_1607.txt
    └── ...
```

Participant filenames must match `User_<10-character-code>.txt`.
Keystroke filenames must match `<10-character-code>_YYMM.txt`.

## Participant file format

The participant files are plain text, one `Field: Value` per line. For example:

```text
BirthYear: 1927
Gender: Male
Parkinsons: True
Tremors: False
DiagnosisYear: 2010
Sided: None
UPDRS: Don't know
Impact: Medium
Levadopa: True
DA: False
MAOB: False
Other: False
```

`Parkinsons` is the binary training label (`True` = 1, `False` = 0). All other fields are retained in `participant_metadata.json` for later subgroup analysis. Unknown UPDRS values are stored as null.

## Keystroke file format

Each row has eight fields, in order:

`UserKey, Date, Timestamp, Hand, Hold time, Direction, Latency time, Flight time`

The parser accepts tab-separated, comma-separated, or whitespace-separated rows and tolerates a trailing backslash. Dates are parsed as `YYMMDD`, timestamps as `HH:MM:SS.SSS`.

Example filename: `ZY9CCHSPF2_1609.txt`.

## Sessionization and window sampling

- All monthly files for a participant are read and combined through their shared ID.
- A new session begins when the calendar date changes or the gap between adjacent keystrokes exceeds `--session-gap-hours` (default 3).
- Each session is sampled into windows of `--window-minutes` (default 2).
- Windows overlap according to `--stride-seconds` (default 60).
- Windows with fewer than `--min-events` keystrokes are skipped.
- Windows are individual model samples; the model does not use a participant/month hierarchy.

## Install

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python train.py --data-dir ./dataset/keystrokes --participants-dir ./dataset/participants --output-dir ./runs/experiment1
```

Windows PowerShell:

```powershell
python train.py --data-dir .\dataset\keystrokes --participants-dir .\dataset\participants --output-dir .\runs\experiment1
```

## Main hyperparameters

```text
--window-minutes 2
--stride-seconds 60
--session-gap-hours 3
--hidden-sizes 64,64,32
--attention-heads 4
--attention-hidden-size 32
--dropout 0.30
--batch-size 32
--learning-rate 0.001
--weight-decay 0.00001
--epochs 100
--checkpoint-every-steps 100
--patience 12
```

`--hidden-sizes 128,64` creates two stacked LSTM layers; `64,64,32,16` creates four.

## Checkpointing and safe exit

- `latest.pt` is saved periodically with an atomic file replacement.
- `best.pt` stores the best selected checkpoint.
- Training resumes from `latest.pt` if present.
- Ctrl+C or SIGTERM requests a graceful exit after the current batch and saves a checkpoint.
- Model and Adam optimizer states are saved.

## Important research notes

- The split is by participant ID, so no participant contributes windows to both train and test.
- Overlapping windows from one participant are correlated. Report participant-level metrics as well as window-level metrics, and bootstrap confidence intervals by participant rather than window.
- The model intentionally uses keystroke data only. Participant metadata is retained for analysis, not fed into the classifier, to reduce label leakage.
- Age, gender, medication, device, typing experience and other motor conditions may confound results. Evaluate subgroup performance and validate on an independent cohort.
- This is a research screening prototype, not a clinically validated diagnostic tool.
