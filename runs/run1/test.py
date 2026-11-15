from torch.utils.data import DataLoader

from data import load_participants, build_windows, WindowDataset, collate_windows
from train import participant_split

def main():
    labels, metadata = load_participants("data/ArchivedUsers")
    windows = build_windows("data/TappyData", labels, 2,
                            3, 60, 8)
    train_w, test_w, train_users, test_users = participant_split(
        windows, 0.2, 42
    )
    test_loader = DataLoader(WindowDataset(test_w), batch_size=32,
                             shuffle=False, num_workers=0,
                             collate_fn=collate_windows)

    latest, best = output / "latest.pt", output / "best.pt"
    start_epoch, best_score, stale = 1, -1.0, 0
    if latest.exists():
        ckpt = torch.load(latest, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])

if __name__ == "__main__":
    main()