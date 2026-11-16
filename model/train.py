"""Train/evaluate participant-level Parkinson's classifier."""
import argparse, json, random, signal
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score
from data import load_participants, build_windows, WindowDataset, collate_windows
from model import KeystrokeLSTM, ModelConfig


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def participant_split(windows, test_fraction, seed):
    users = sorted({w[2] for w in windows})
    label_map = {w[2]: w[1] for w in windows}
    y = [label_map[u] for u in users]
    try:
        train_users, test_users = train_test_split(
            users, test_size=test_fraction, random_state=seed, stratify=y
        )
    except ValueError:
        train_users, test_users = train_test_split(
            users, test_size=test_fraction, random_state=seed
        )
    train_ids, test_ids = set(train_users), set(test_users)
    return ([w for w in windows if w[2] in train_ids],
            [w for w in windows if w[2] in test_ids], train_users, test_users)


def evaluate(model, loader, device):
    model.eval()
    ys, probs = [], []
    with torch.no_grad():
        for x, y, lengths, _, _ in loader:
            p = torch.sigmoid(model(x.to(device), lengths.to(device))).cpu().numpy()
            ys.extend(y.numpy().tolist()); probs.extend(p.tolist())
    if not ys:
        return {}
    ys, probs = np.asarray(ys), np.asarray(probs)
    pred = (probs >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(ys, pred)),
        "precision": float(precision_score(ys, pred, zero_division=0)),
        "sensitivity": float(recall_score(ys, pred, zero_division=0)),
        "specificity": float(recall_score(1 - ys, 1 - pred, zero_division=0)),
        "f1": float(f1_score(ys, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(ys, probs)) if len(set(ys.tolist())) == 2 else None,
    }


def save_checkpoint(path, model, optimizer, epoch, best_score, config, args):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save({
        "epoch": epoch, "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "best_metric": best_score, "model_config": config.__dict__,
        "arguments": vars(args),
    }, tmp)
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, help="Folder containing <ID>_YYMM.txt keystroke files")
    p.add_argument("--participants-dir", required=True, help="Folder containing User_<ID>.txt participant files")
    p.add_argument("--output-dir", default="runs/default")
    p.add_argument("--window-minutes", type=int, default=5)
    p.add_argument("--stride-seconds", type=int, default=60)
    p.add_argument("--session-gap-hours", type=float, default=3.0)
    p.add_argument("--min-events", type=int, default=8)
    p.add_argument("--test-fraction", type=float, default=0.20)
    p.add_argument("--hidden-sizes", default="64,64,32")
    p.add_argument("--attention-heads", type=int, default=4)
    p.add_argument("--attention-hidden-size", type=int, default=32)
    p.add_argument("--dropout", type=float, default=0.30)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--learning-rate", type=float, default=0.0005)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--checkpoint-every-steps", type=int, default=100)
    p.add_argument("--patience", type=int, default=12)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-workers", type=int, default=0)
    args = p.parse_args()

    seed_everything(args.seed)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stop = {"requested": False}

    def request_stop(signum, frame):
        stop["requested"] = True
        print("\nStop requested; will save after the current batch.")

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    labels, metadata = load_participants(args.participants_dir)
    (output / "participant_metadata.json").write_text(json.dumps(metadata, indent=2))
    windows = build_windows(args.data_dir, labels, args.window_minutes,
                            args.session_gap_hours, args.stride_seconds, args.min_events)
    if not windows:
        raise RuntimeError("No windows created. Check filenames, participant IDs, file format and session lengths.")

    train_w, test_w, train_users, test_users = participant_split(
        windows, args.test_fraction, args.seed
    )
    if not train_w or not test_w:
        raise RuntimeError("Train/test split is empty; more participants are needed.")
    (output / "split.json").write_text(json.dumps({
        "train_users": train_users, "test_users": test_users,
        "train_windows": len(train_w), "test_windows": len(test_w)
    }, indent=2))

    train_loader = DataLoader(WindowDataset(train_w), batch_size=args.batch_size,
                              shuffle=True, num_workers=args.num_workers,
                              collate_fn=collate_windows)
    test_loader = DataLoader(WindowDataset(test_w), batch_size=args.batch_size,
                             shuffle=False, num_workers=args.num_workers,
                             collate_fn=collate_windows)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    hidden = tuple(int(v.strip()) for v in args.hidden_sizes.split(",") if v.strip())
    config = ModelConfig(input_size=10, lstm_hidden_sizes=hidden,
                         attention_heads=args.attention_heads,
                         attention_hidden_size=args.attention_hidden_size,
                         dropout=args.dropout)
    model = KeystrokeLSTM(config).to(device)
    y_train = np.asarray([w[1] for w in train_w])
    positives, negatives = int(y_train.sum()), int((y_train == 0).sum())
    pos_weight = torch.tensor([negatives / max(positives, 1)], device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate,
                                 weight_decay=args.weight_decay)

    latest, best = output / "latest.pt", output / "best.pt"
    start_epoch, best_score, stale = 1, -1.0, 0
    if latest.exists():
        ckpt = torch.load(latest, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt["epoch"] + 1
        best_score = ckpt.get("best_metric", -1.0)
        print(f"Resuming at epoch {start_epoch}")

    step = 0
    for epoch in range(start_epoch, args.epochs + 1):
        model.train(); loss_sum = 0.0
        for x, y, lengths, _, _ in train_loader:
            x, y, lengths = x.to(device), y.to(device), lengths.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x, lengths), y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            loss_sum += loss.item(); step += 1

            if step % args.checkpoint_every_steps == 0:
                save_checkpoint(latest, model, optimizer, epoch, best_score, config, args)
            if stop["requested"]:
                save_checkpoint(latest, model, optimizer, epoch, best_score, config, args)
                print("Checkpoint saved; exiting cleanly.")
                return

        mean_loss = loss_sum / max(1, len(train_loader))
        metrics = evaluate(model, test_loader, device)
        print(f"Epoch {epoch}/{args.epochs} | loss={mean_loss:.5f} | {json.dumps(metrics)}")
        score = metrics.get("roc_auc")
        if score is None:
            score = metrics.get("f1", 0.0)
        if score > best_score:
            best_score, stale = score, 0
            save_checkpoint(best, model, optimizer, epoch, best_score, config, args)
        else:
            stale += 1
        with (output / "metrics.jsonl").open("a") as f:
            f.write(json.dumps({"epoch": epoch, "train_loss": mean_loss, **metrics}) + "\n")
        save_checkpoint(latest, model, optimizer, epoch, best_score, config, args)
        # if stale >= args.patience:
        #     print("Early stopping.")
        #     break

    print(f"Training complete. Best monitored score: {best_score:.4f}")


if __name__ == "__main__":
    main()
