import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


class M3(nn.Module):
    """Parallel temporal receptive fields, followed by the M2 BiGRU head."""
    def __init__(self, config):
        super().__init__()
        c = config['model']
        first, second = c['channels']
        kernels = c['branch_kernels']
        kernel = c['kernel_size']
        if len(kernels) < 2 or len(set(kernels)) != len(kernels):
            raise ValueError('At least two distinct branch kernels required')
        if any(not isinstance(k, int) or k < 1 or k % 2 == 0 for k in [*kernels, kernel]):
            raise ValueError('Positive odd kernel sizes required')
        if first < len(kernels) or first % len(kernels):
            raise ValueError('Total first-layer channels must divide evenly among branches')
        self.branches = nn.ModuleList(nn.Conv1d(1, first // len(kernels), k, padding=k // 2) for k in kernels)
        self.conv2 = nn.Conv1d(first, second, kernel, stride=2, padding=kernel // 2)
        self.rnn = nn.GRU(second, c['hidden_size'], batch_first=True, bidirectional=True)
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
        x = torch.cat([self.mask(torch.relu(branch(x)), lengths) for branch in self.branches], dim=1)
        x = torch.relu(self.conv2(x))
        lengths = (lengths + 1) // 2
        x = self.mask(x, lengths).transpose(1, 2)
        packed = pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, hidden = self.rnn(packed)
        return self.head(torch.cat((hidden[-2], hidden[-1]), dim=1))
