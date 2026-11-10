from adaptive_pipeline import evaluate as original_evaluate,LABELS as OLD_LABELS
from wabun_runtime_policy import render_body
METHODS=['baseline','timing','tracking','tempo','combined']
LABELS={k:v for k,v in OLD_LABELS.items() if k in METHODS}
def evaluate(audio,models,cfg,labels,methods=None):
    methods=list(methods or METHODS)
    if any(m not in METHODS for m in methods):raise ValueError('Unsupported Wabun method')
    outputs,detectors=original_evaluate(audio,models,cfg,labels,methods)
    result={}
    for key,(text,rows,warnings,error) in outputs.items():
        if not error:
            text,rows,new_warnings=render_body(rows)
            warnings=[w for w in warnings if 'parenthes' not in w.lower() and 'mode repair' not in w.lower()]+new_warnings
        result[key]=(text,rows,warnings,error)
    return result,detectors
