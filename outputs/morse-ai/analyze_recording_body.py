"""Secondary, explicitly rule-assisted body analysis of saved recording predictions."""
import csv
import json
from pathlib import Path
from evaluate_recording import edit_alignment


def select_body(rows):
    starts=[i for i,r in enumerate(rows) if r['pattern']=='-..---']
    ends=[i for i,r in enumerate(rows) if r['pattern']=='...-.']
    if len(starts)!=1 or len(ends)!=1 or ends[0]<=starts[0]:
        raise ValueError('Expected exactly one ordered start/end prosign pair')
    return [r for r in rows[starts[0]+1:ends[0]] if r['rule_prediction'] not in '、」']


def analyze(directory):
    directory=Path(directory)
    with (directory/'segments.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    body=select_body(rows)
    reference=(directory/'reference_normalized.txt').read_text(encoding='utf-8').replace('」','').replace('、','')
    (directory/'reference_body.txt').write_text(reference,encoding='utf-8')
    cnn=''.join(r['prediction'] for r in body)
    rule=''.join(r['rule_prediction'] for r in body)
    cnn_metrics,_=edit_alignment(reference,cnn)
    rule_metrics,_=edit_alignment(reference,rule)
    result={'scope':'Rule-assisted start/end and punctuation exclusion; not CNN-only end-to-end',
            'selected_segment_indices':[int(r['index']) for r in body],
            'excluded_segments':len(rows)-len(body),'cnn':cnn_metrics,'rule':rule_metrics,
            'model_updated':False}
    if len(body)==len(reference):
        comparisons=[dict(index=r['index'],start_seconds=r['start_seconds'],reference=c,
                          prediction=r['prediction'],correct=r['prediction']==c,
                          confidence=r['confidence'],rule_prediction=r['rule_prediction'])
                     for r,c in zip(body,reference)]
        correct=sum(r['correct'] for r in comparisons)
        result['cnn_positional_correct']=correct
        result['cnn_positional_accuracy']=correct/len(reference)
        with (directory/'body_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(comparisons[0]))
            writer.writeheader();writer.writerows(comparisons)
    for name,text in [('cnn_body.txt',cnn),('rule_body.txt',rule)]:
        (directory/name).write_text(text,encoding='utf-8')
    (directory/'body_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='selected_segment_indices'},ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    analyze(parser.parse_args().directory)
