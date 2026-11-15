import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision.transforms import v2
from model import NeuralNetwork, train, test, load, save

batch_size = 64

training_data = datasets.MNIST(
    root="data",
    train=True,
    download=True,
    transform=v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)]),
)
training_dataloader = DataLoader(training_data, batch_size=batch_size)

testing_data = datasets.MNIST(
    root="data",
    train=False,
    download=True,
    transform=v2.Compose([v2.ToImage(), v2.ToDtype(torch.float32, scale=True)]),
)
testing_dataloader = DataLoader(testing_data, batch_size=batch_size)

device = torch.accelerator.current_accelerator().type if torch.accelerator.is_available() else "cpu"
print(f"Using {device} device")

model = NeuralNetwork(28, 28).to(device)
load(model)

loss_fn = nn.MSELoss()
# optimizer = torch.optim.SGD(model.parameters(), lr=3e-4)
# optimizer = torch.optim.Adam(model.parameters(), lr=1e-5)
# optimizer = torch.optim.Adagrad(model.parameters(), lr=1e-3)
# optimizer = torch.optim.Adadelta(model.parameters())
# optimizer = torch.optim.RMSprop(model.parameters(), lr=1e-3)
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, betas=(0.9,0.95), eps=1e-8)

epochs = 100
for t in range(epochs):
    print(f"Epoch {t+1}\n---------------")
    train(training_dataloader, model, loss_fn, optimizer)
    test(testing_dataloader, model, loss_fn)
    # if t % 10 == 0:
        # save(model)
    save(model)

save(model)
print("done")
