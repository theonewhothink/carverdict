"""Bundle private dashboard baseline and measured build coverage; never emit a public JSON asset."""
import json,subprocess,datetime,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
seed=json.loads((root/'docs/dashboard-register.json').read_text())
seed['business_plan']=json.loads((root/'docs/business-plan.json').read_text())
seed['seo']=json.loads((root/'workers/dashboard-seo.json').read_text())
for metric in seed['metrics']:
 if metric['id']=='organic_clicks':metric['view']='seo'
extra=json.loads((root/'docs/dashboard-metrics.json').read_text())
ids={m['id'] for m in seed['metrics']}
seed['metrics'].extend(m for m in extra if m['id'] not in ids)
coverage=json.loads((root/'site/assets/catalogue-coverage.json').read_text()) if (root/'site/assets/catalogue-coverage.json').exists() else {}
rows=json.loads((root/'site/assets/catalogue-data.json').read_text()) if (root/'site/assets/catalogue-data.json').exists() else []
try:sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
except Exception:sha='unknown'
seed['build']={'sha':sha,'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'html_pages':len(list((root/'site').rglob('*.html'))),'coverage':coverage,'catalogue_entries':len(rows),'photo_references':sum(bool(r.get('p')) for r in rows),'catalogue_sha256':hashlib.sha256((root/'data/car_library.json').read_bytes()).hexdigest() if (root/'data/car_library.json').exists() else None}
(root/'workers/dashboard-data.json').write_text(json.dumps(seed,ensure_ascii=False)+'\n')
print('Private dashboard build baseline:',seed['build']['catalogue_entries'],'entries;',len(seed['tasks']),'tasks')
