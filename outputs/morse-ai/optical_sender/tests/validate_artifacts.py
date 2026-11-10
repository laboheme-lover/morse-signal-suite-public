"""Optional schema validation using already installed jsonschema; no installation."""
import json
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / 'schema/transmission.schema.json').read_text(encoding='utf-8'))
jsonschema.Draft202012Validator.check_schema(schema)
paths = [ROOT / 'artifacts' / n for n in ('plan_i.json', 'plan_ii.json', 'run_virtual_i.json')]
paths += sorted((ROOT / 'artifacts/browser').glob('*.json'))
documents = {}
for path in paths:
    data = json.loads(path.read_text(encoding='utf-8'))
    jsonschema.validate(data, schema)
    documents[path.name] = data
plans = {d['plan_id']: d for d in documents.values() if 'intervals' in d}
for plan in plans.values():
    cursor = 0
    for interval in plan['intervals']:
        assert interval['start_ms'] == cursor
        assert interval['end_ms'] > cursor
        cursor = interval['end_ms']
    assert cursor == plan['total_duration_ms']
result = []
for name, data in documents.items():
    if 'run_id' not in data:
        continue
    assert data['plan_id'] in plans
    assert data['transitions'][-1]['state'] == 'off'
    assert data['ended_at'] is not None
    if data['status'] == 'completed':
        planned = plans[data['plan_id']]
        executed = [t for t in data['transitions'] if t['cause'] == 'scheduled']
        assert len(executed) == len(planned['intervals'])
        for transition, interval in zip(executed, planned['intervals']):
            assert transition['planned_time_ms'] == interval['start_ms']
            assert transition['state'] == interval['state']
        assert all(0 <= t['lateness_ms'] <= 50 for t in data['transitions'] if t['lateness_ms'] is not None)
    result.append({'file': name, 'status': data['status'], 'reason': data['abort_reason'],
                   'max_processing_lateness_ms': max([t['lateness_ms'] for t in data['transitions'] if t['lateness_ms'] is not None], default=None)})
summary = {'schema_documents_passed': len(documents), 'runs': result}
(ROOT / 'artifacts/validation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
