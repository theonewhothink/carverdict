"""Read-only publication probes. GitHub records failures; no uptime percentage is invented."""
import datetime,json,os,re,sys,urllib.request
from pathlib import Path
ORIGIN='https://motorjury.com'
PATHS=('/','/library/','/guides/','/buying-brief/','/sitemap.xml')
def evaluate(manifest,probes,expected):
 findings=[p['path']+': expected HTTP 200' for p in probes if p['status']!=200]
 if not isinstance(manifest,dict) or manifest.get('checks')!='passed' or not re.fullmatch('[a-f0-9]{40}',str(manifest.get('sha',''))) or manifest.get('preview') is not False:
  findings.append('Publication manifest is missing or invalid.')
 elif expected and manifest['sha']!=expected:
  findings.append('Serving source differs from this checkout; verify deployment before reporting success.')
 return findings
def read(path):
 request=urllib.request.Request(ORIGIN+path,headers={'User-Agent':'MotorJury-release-monitor/1.0'})
 with urllib.request.urlopen(request,timeout=20) as response:
  return response.status,response.read()
def main():
 probes=[]
 for path in PATHS:
  try:status,_=read(path)
  except Exception:status=0
  probes.append({'path':path,'status':status})
 try:_,body=read('/release.json');manifest=json.loads(body)
 except Exception:manifest=None
 findings=evaluate(manifest,probes,os.environ.get('GITHUB_SHA',''))
 report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Read-only sampled public delivery and published build gate, not continuous uptime, traffic or Google indexing.','release':manifest,'probes':probes,'findings':findings}
 out=Path('verification/monitor-release.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report));return bool(findings)
if __name__=='__main__':sys.exit(main())
