from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[2]/'phase4_m3'))
import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from m3.model import M3


class M4(M3):
    """M3 feature extractor with masked additive temporal attention pooling."""
    def __init__(self, config):
        super().__init__(config)
        c = config['model']
        size = c['attention_size']
        if not isinstance(size, int) or size < 1:
            raise ValueError('Positive integer attention_size required')
        self.attention = nn.Sequential(nn.Linear(c['hidden_size']*2, size), nn.Tanh(), nn.Linear(size, 1, bias=False))

    def forward(self, x, lengths, return_attention=False):
        if x.ndim != 3 or x.shape[1] != 1 or len(lengths) != len(x):
            raise ValueError('Expected [batch,1,time] and one length per item')
        if torch.any(lengths <= 0) or torch.any(lengths > x.shape[-1]):
            raise ValueError('Invalid sequence lengths')
        x = self.mask(x, lengths)
        x = torch.cat([self.mask(torch.relu(branch(x)), lengths) for branch in self.branches], dim=1)
        x = torch.relu(self.conv2(x))
        lengths = (lengths + 1) // 2
        x = self.mask(x, lengths).transpose(1, 2)
        packed = pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        packed_states, _ = self.rnn(packed)
        states, _ = pad_packed_sequence(packed_states, batch_first=True)
        scores = self.attention(states).squeeze(-1)
        valid = torch.arange(states.shape[1], device=x.device)[None, :] < lengths.to(x.device)[:, None]
        weights = scores.masked_fill(~valid, float('-inf')).softmax(dim=1)
        context = (states * weights.unsqueeze(-1)).sum(dim=1)
        logits = self.head(context)
        return (logits, weights, lengths) if return_attention else logits
