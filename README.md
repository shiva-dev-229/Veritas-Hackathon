# PEAS: Parkinson's Early At-Home Screener

> **This project is a prototype and is not medical advice.**

**Track:** AI + Health  
**Team:** Gearheads (Shivansh Upadhyay, Dirk Winberg)  
**Event:** Veritas AI International High School Hackathon 2026

---

## The Problem

Parkinson's disease is often diagnosed late, and by the time of diagnosis, stiffness and tremors may already be affecting daily life.

PEAS is for adults who worry they might be showing early signs of Parkinson's. It lets them take a free screening test at home and decide whether to bring it up with a doctor. Changes in typing rhythm can show up in everyday computer use, so a short typing test gives them something concrete to act on without needing a clinic visit.

## What We Built

PEAS is a web app with a typing test and a machine learning model behind it.

| | |
|---|---|
| **Input** | Typing test data (key hold time, latency time, flight time). Age and gender are collected but not used in the analysis yet. |
| **Output** | A binary yes/no prediction, with a clear statement of the model's accuracy as a percentage. |
| **How it's used** | The user opens the web app, takes a short typing test, and gets a results page showing what the model found. |

## What We Added

PEAS is our own idea. We did not start from a suggested project.

## How It Works

### Data

We trained on the public [Tappy Keystroke Data](https://physionet.org/content/tappy/1.0.0/) from PhysioNet. Each person is labeled as having Parkinson's or not (a binary label).

- The model uses **10 parameters** built from hold time, latency time, and flight time.
- Birth year and gender are in the dataset but are **not used** by the model. They could be used in future experiments.
- The dataset's recordings span multiple days or even months. We wanted to analyze **2-minute recordings**, so we randomly sampled **2 to 5 minute windows** from each person's data. This also gave us more samples to train on.
- **Split:** 80% training, 20% testing.

### Model

The model is a sequence model built in PyTorch:

1. A **Long Short-Term Memory (LSTM)** with three layers reads the sequence of keystrokes.
2. **Attention pooling** lets the different data points in the sequence interact with each other.
3. A **linear feedforward layer** with a ReLU activation follows.
4. A **sigmoid** produces the final output, read as the percent chance of having the disease. We use a 50% threshold for the yes/no prediction.

### Training

- **Optimizer:** Adam, to speed up training.
- **Learning rate:** We started at 0.001, but it plateaued quickly, so we moved to 0.0005.
- **Reported results** are from epoch 57.

### Stack

| Part | Tools |
|---|---|
| Front end | TypeScript (typing test interface inspired by Monkeytype's design) |
| API | Django (Python) |
| Model | PyTorch |

## Results

All numbers are on the 20% held-out test data.

| Metric | Score |
|---|---|
| Accuracy | **74.81%** |
| Detection rate (sensitivity / recall) for Parkinson's | **79.44%** |
| False negatives (missed Parkinson's cases) | **20.56%** of people with Parkinson's |
| False positives (healthy people flagged) | **84.86%** of people without Parkinson's |
| Specificity (healthy people correctly cleared) | 15.14% |
| Precision | 92.36% |
| F1 | 85.41% |
| ROC AUC | 0.571 |
| Simple baseline ("always guess the most common answer") | about 92.8% accuracy* |

\*Not measured directly. We worked it out from the accuracy, sensitivity, and specificity above, which imply that roughly 93% of the test samples are Parkinson's cases. Always guessing "Parkinson's" would therefore score about 92.8%.

**What we saw:** The model caught about 79% of the people who have Parkinson's, but it also flagged about 85% of the healthy people. Our test data is heavily weighted toward Parkinson's samples, so the high precision and F1 are misleading: they mostly reflect how many Parkinson's samples there are, not how well the model separates the two groups. An ROC AUC of 0.57 is only slightly better than random guessing.

**Where it fails:** The model fails on healthy people. It clears only about 15% of them, so most people without Parkinson's would be told they might have it. Our overall accuracy (74.81%) is actually below the always-guess-Parkinson's baseline, so the model has not yet shown it can tell the two groups apart. We think this comes from the imbalanced data and from only having 2 to 5 minute windows to work with, but we have not tested that yet.

### Comparison with Keysense

We compared our results to Keysense from [Parkinson's Research](https://www.parkinsons-research.org/index.htm), which reports a 90% detection rate. They use around 10 minutes of typing, while ours uses around 2 minutes. Our detection rate was 79.44%, which is lower. If we tested over longer periods, we might have reached similar results.

## What We'd Do Next

- Fix the class imbalance (for example by balancing the training and test sets) so we can measure real performance instead of a number driven by the majority class.
- Make PEAS a fully available app with authentication and progress tracking, so each person can compare new tests against their own past tests.
- Add other at-home screening tests, such as a spiral drawing test (datasets for this are available).
- Train on more datasets, and collect fresh data that matches the short time window we care about.
- Train for longer and spend more time tuning hyperparameters like hidden layer size. The LSTM may also not be the right architecture for this problem, and other architectures could perform better.

## Sources

**Data and research**
- Tappy Keystroke Data (v1.0.0), PhysioNet, Open Data Commons Attribution License v1.0. https://physionet.org/content/tappy/1.0.0/ (DOI: 10.13026/C2K08D)
- Adams, W. R. (2017). High-accuracy detection of early Parkinson's Disease using multiple characteristics of finger movement while typing. *PLOS ONE* 12(11): e0188226.
- Pollard, T., et al. (2026). PhysioNet as a global platform for biomedical research. *Nature Health*. https://doi.org/10.1038/s44360-026-00096-z
- Parkinson's Research, https://www.parkinsons-research.org/index.htm. Used as a comparison for our results.

**Tools and libraries**
- PyTorch, https://pytorch.org
- TypeScript, https://www.typescriptlang.org
- Django, https://www.djangoproject.com
- Monkeytype, https://github.com/monkeytypegame/monkeytype (GPL-3.0). Design inspiration only.

**AI tools used**
- Claude Code (Anthropic), https://www.anthropic.com/claude-code. Used to help write the website front end.
- ChatGPT (OpenAI), https://chatgpt.com. Used to help write the model code.