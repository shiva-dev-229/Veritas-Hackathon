import torch
from torch import nn
from torch.utils.data import DataLoader
import random
import os

device = torch.accelerator.current_accelerator().type if torch.accelerator.is_available() else "cpu"
savepath = "models\\typing_model.pth"

class NeuralNetwork(nn.Module):
    def __init__(self):
        self.lstm1 = nn.LSTM()
        super().__init__()

    def forward(self, x):
        self.lstm1.
        return out

def train(dataloader, model, loss_fn, optimizer):
    size = len(dataloader.dataset)
    model.train()
    for batch, (X,y) in enumerate(dataloader):
        X, y = X.to(device), y.to(device)
        hot = nn.functional.one_hot(y, 10)

        X = rand_transform_batch(X)
        # X = X + ((torch.rand(X.size()) - 0.5) * 10).to(device)

        pred = model(X)
        loss = loss_fn(pred, hot)

        loss.backward()
        optimizer.step()
        optimizer.zero_grad()

        if batch % 100 == 0:
            print(f"Batch: {batch}, loss: {loss.item()}")

def rand_transform_batch(data):
    new_data = torch.roll(
        data,
        random.randint(-1, 1),
        1
    )
    new_data = new_data.roll(
        random.randint(-1, 1),
        2
    )
    new_data = F.rotate(new_data, random.randint(-10, 10))
    return new_data

def rand_transform(data):
    new_data = torch.roll(
        data,
        random.randint(-1, 1),
        0
    )
    new_data = new_data.roll(
        random.randint(-1, 1),
        1
    )
    new_data = new_data.unsqueeze(0)
    new_data = F.rotate(new_data, random.randint(-10, 10))
    new_data = new_data.squeeze(0)
    return new_data

def test(dataloader, model, loss_fn):
    size = len(dataloader.dataset)
    num_batches = len(dataloader)
    model.eval()
    test_loss, correct = 0, 0
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)
            pred = model(X)
            hot = nn.functional.one_hot(y, 10)
            test_loss += loss_fn(pred, hot).item()
            number_predicted = pred.argmax(1)
            for i in range(len(y)):
                if y[i] == number_predicted[i]:
                    correct += 1
    test_loss /= num_batches
    correct /= size
    print(f"Percent correct: {100*correct:>0.1f}%")
    print(f"Avg Loss: {test_loss:>8f}")

def run(model, grid):
    tensor = torch.tensor([grid], dtype=torch.float).to(device)
    model.eval()
    with torch.no_grad():
        pred = model(tensor)
        return pred.squeeze(0)

def load(model):
    if os.path.exists(savepath):
        model.load_state_dict(torch.load(savepath, weights_only=True))

def save(model):
    torch.save(model.state_dict(), savepath)
