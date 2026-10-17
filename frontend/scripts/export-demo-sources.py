"""Export approved reference identities/advisory replays, never download or train."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml.hazard_rehearsal import verify_fixtures  # noqa: E402
from ml.worker.comprehensive_schema import ComprehensiveOutlook  # noqa: E402

verify_fixtures()
source = ROOT / 'ml/fixtures/hazard_coverage'
sites = json.loads((source / 'backend_sites.json').read_text(encoding='utf-8'))
index = {r['id']: r for r in sites['records']}
references = [index[sid] for sid in sites['batch_site_ids']]
assert len(references) == len({r['id'] for r in references}) == 50
advisories = []
for name in ('example_1_response.json', 'example_2_response.json'):
    result = ComprehensiveOutlook.model_validate_json((source / name).read_text(encoding='utf-8'))
    assert result.is_demo_or_simulated and result.not_work_clearance
    advisories.append(result.model_dump(mode='json'))
output = ROOT / 'frontend/src/demo/generated'
output.mkdir(parents=True, exist_ok=True)
for name, value in (('references.json', references), ('advisories.json', advisories)):
    (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
print('Exported 50 reconciled EIA reference plants and two validated 2.1 replay advisories; no retrieval/refit.')
