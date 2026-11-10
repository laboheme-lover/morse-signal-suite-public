"""Small three-block CNN. Temporal pooling retains Morse symbol order."""
from dataclasses import fields
import torch
from torch import nn
from audio_preprocessing import PreprocessConfig


class MorseCNN(nn.Module):
    def __init__(self, num_classes=65, temporal_bins=16, dropout=0.3, variant='classic'):
        super().__init__()
        if type(num_classes) is not int or num_classes < 2 or type(temporal_bins) is not int or temporal_bins < 1:
            raise ValueError('Invalid model dimensions')
        if not 0 <= dropout < 1:
            raise ValueError('Invalid dropout')
        if variant not in ('classic','temporal'):
            raise ValueError('Unknown CNN variant')
        self.variant=variant
        self.model_config = dict(num_classes=num_classes, temporal_bins=temporal_bins, dropout=dropout,variant=variant)
        layers=[]
        if variant=='temporal':
            # Fixed frequency pooling gives invariance to small carrier shifts and reduces CPU work.
            layers.append(nn.MaxPool2d((4,1)))
        for input_channels,output_channels in ((1,16),(16,32),(32,64)):
            kernel,padding=((3,9),(1,4)) if variant=='temporal' else (3,1)
            layers.extend([nn.Conv2d(input_channels,output_channels,kernel,padding=padding,bias=False),
                           nn.BatchNorm2d(output_channels),nn.ReLU(),nn.MaxPool2d(2)])
        self.features=nn.Sequential(*layers)
        self.classifier=nn.Sequential(nn.AdaptiveAvgPool2d((1,temporal_bins)),nn.Flatten(),
                                      nn.Linear(64*temporal_bins,128),nn.ReLU(),nn.Dropout(dropout),
                                      nn.Linear(128,num_classes))

    def forward(self,x):
        if x.ndim!=4 or x.shape[1]!=1 or min(x.shape[2:])<8:
            raise ValueError('Expected [B,1,Mel,Time] with both spatial dimensions >= 8')
        if self.variant=='temporal':
            x=x/80.0  # fixed scaling is part of the saved model, identical in inference
        return self.classifier(self.features(x))  # logits for CrossEntropyLoss


def load_checkpoint(path, device='cpu'):
    checkpoint=torch.load(path,map_location=device,weights_only=True)
    if checkpoint.get('format_version')!='m6-v1':
        raise ValueError('Unsupported checkpoint format')
    mapping=checkpoint['label_to_index']
    if sorted(mapping.values())!=list(range(len(mapping))) or len(mapping)!=checkpoint['model_config']['num_classes']:
        raise ValueError('Checkpoint class mapping mismatch')
    spec=checkpoint['preprocessing']
    config=PreprocessConfig(**{f.name:spec[f.name] for f in fields(PreprocessConfig)})
    if config.to_dict()!=spec:
        raise ValueError('Unsupported preprocessing specification')
    model=MorseCNN(**checkpoint['model_config']).to(device)
    model.load_state_dict(checkpoint['model_state_dict'],strict=True)
    model.eval()
    return model,config,checkpoint
