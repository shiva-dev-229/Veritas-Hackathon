"""Configurable stacked-LSTM + multi-head attention pooling classifier."""
from dataclasses import dataclass
from typing import Sequence
import torch
from torch import nn


@dataclass
class ModelConfig:
    input_size: int = 8
    lstm_hidden_sizes: Sequence[int] = (64, 64, 32)
    attention_heads: int = 4
    attention_hidden_size: int = 32
    dropout: float = 0.30


class AttentionPooling(nn.Module):
    """Learns several independent temporal attention summaries."""
    def __init__(self, input_size: int, heads: int = 4, attention_hidden_size: int = 32):
        super().__init__()
        if heads < 1:
            raise ValueError("attention_heads must be >= 1")
        self.heads = heads
        self.scorers = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_size, attention_hidden_size),
                nn.Tanh(),
                nn.Linear(attention_hidden_size, 1, bias=False),
            ) for _ in range(heads)
        ])

    def forward(self, sequence, lengths):
        # sequence: [batch, time, features], lengths: [batch]
        batch, time, _ = sequence.shape
        positions = torch.arange(time, device=sequence.device).unsqueeze(0)
        mask = positions >= lengths.unsqueeze(1)
        pooled = []
        for scorer in self.scorers:
            scores = scorer(sequence).squeeze(-1)
            scores = scores.masked_fill(mask, torch.finfo(scores.dtype).min)
            weights = torch.softmax(scores, dim=1)
            pooled.append(torch.sum(sequence * weights.unsqueeze(-1), dim=1))
        return torch.cat(pooled, dim=-1)


class KeystrokeLSTM(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        sizes = list(config.lstm_hidden_sizes)
        if not sizes or any(int(s) <= 0 for s in sizes):
            raise ValueError("lstm_hidden_sizes must be a non-empty list of positive integers")

        self.lstm_layers = nn.ModuleList()
        previous = config.input_size
        for hidden in sizes:
            self.lstm_layers.append(nn.LSTM(
                input_size=previous,
                hidden_size=int(hidden),
                num_layers=1,
                batch_first=True,
            ))
            previous = int(hidden)

        self.dropout = nn.Dropout(config.dropout)
        self.attention = AttentionPooling(
            previous, config.attention_heads, config.attention_hidden_size
        )
        pooled_size = previous * config.attention_heads
        self.classifier = nn.Sequential(
            nn.Linear(pooled_size, max(16, previous)),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(max(16, previous), 1),
        )

    def forward(self, x, lengths):
        for layer in self.lstm_layers:
            x, _ = layer(x)
            x = self.dropout(x)
        pooled = self.attention(x, lengths)
        logits = self.classifier(pooled).squeeze(-1)
        return logits  # pass through sigmoid for probabilities; use logits for BCEWithLogitsLoss

    @torch.no_grad()
    def predict_proba(self, x, lengths):
        return torch.sigmoid(self.forward(x, lengths))
