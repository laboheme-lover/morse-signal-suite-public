"""Compare a validation-selected checkpoint; recording is a development check only."""
from pathlib import Path
import torch
from threadpoolctl import threadpool_limits
from compare_validation import compare
from evaluate_recording import evaluate_recording
from analyze_recording_body import analyze


if __name__=='__main__':
    torch.set_num_threads(1)
    checkpoints=[Path('models/improved_best.pt'),Path('models/continuous_v1/best_model.pt')]
    with threadpool_limits(limits=1):
        compare(Path('data/dataset/continuous_v1'),checkpoints,Path('evaluation/retraining_expanded_validation'))
        compare(Path('data/dataset/m4_300'),checkpoints,Path('evaluation/retraining_original_validation'))
        output=Path('evaluation/real_recording_continuous_v1')
        evaluate_recording(Path('C:/Users/DEVELOPER/Downloads/Tamanの和文モールス練習動画.mp3'),
                           Path('evaluation/taman_reference.txt'),checkpoints[1],output)
        analyze(output)
