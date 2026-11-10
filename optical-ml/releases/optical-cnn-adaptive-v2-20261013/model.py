"""Optical-only classifiers. No audio checkpoint is reused."""
import torch
from torch import nn

class OpticalCNN(nn.Module):
 def __init__(self,classes=65):
  super().__init__()
  self.features=nn.Sequential(nn.Conv1d(5,32,5,padding=2),nn.ReLU(),nn.Conv1d(32,48,5,stride=2,padding=2),nn.ReLU(),nn.AdaptiveAvgPool1d(16))
  self.head=nn.Sequential(nn.Flatten(),nn.Linear(48*16,128),nn.ReLU(),nn.Dropout(.15),nn.Linear(128,classes))
 def forward(self,x):return self.head(self.features(x))

class OpticalBiGRU(nn.Module):
 def __init__(self,classes=65):
  super().__init__()
  self.branches=nn.ModuleList(nn.Conv1d(5,12,k,padding=k//2) for k in (3,5,9))
  self.conv=nn.Conv1d(36,48,5,stride=2,padding=2)
  self.gru=nn.GRU(48,32,batch_first=True,bidirectional=True)
  self.head=nn.Sequential(nn.Dropout(.15),nn.Linear(64,classes))
 def forward(self,x):
  x=torch.cat([torch.relu(b(x)) for b in self.branches],dim=1)
  x=torch.relu(self.conv(x)).transpose(1,2)
  _,h=self.gru(x)
  return self.head(torch.cat([h[-2],h[-1]],dim=1))

MODELS={'cnn':OpticalCNN,'multiscale_bigru':OpticalBiGRU}
