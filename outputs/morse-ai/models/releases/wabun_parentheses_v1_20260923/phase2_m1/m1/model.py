import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


class M1(nn.Module):
    def __init__(self, config):
        super().__init__()
        c = config['model']
        first, second = c['channels']
        kernel = c['kernel_size']
        if kernel % 2 != 1:
            raise ValueError('Odd kernel size required')
        self.conv1 = nn.Conv1d(1, first, kernel, padding=kernel // 2)
        self.conv2 = nn.Conv1d(first, second, kernel, stride=2, padding=kernel // 2)
        self.rnn = nn.LSTM(second, c['hidden_size'], batch_first=True, bidirectional=True)
        self.head = nn.Sequential(nn.Dropout(c['dropout']), nn.Linear(c['hidden_size'] * 2, c['classes']))

    @staticmethod
    def mask(x, lengths):
        valid = torch.arange(x.shape[-1], device=x.device)[None, :] < lengths.to(x.device)[:, None]
        return x * valid[:, None, :]

    def forward(self, x, lengths):
        if x.ndim != 3 or x.shape[1] != 1 or len(lengths) != len(x):
            raise ValueError('Expected [batch,1,time] and one length per item')
        if torch.any(lengths <= 0) or torch.any(lengths > x.shape[-1]):
            raise ValueError('Invalid sequence lengths')
        x = self.mask(x, lengths)
        x = self.mask(torch.relu(self.conv1(x)), lengths)
        x = torch.relu(self.conv2(x))
        lengths = (lengths + 1) // 2
        x = self.mask(x, lengths).transpose(1, 2)
        packed = pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, (hidden, _) = self.rnn(packed)
        return self.head(torch.cat((hidden[-2], hidden[-1]), dim=1))
