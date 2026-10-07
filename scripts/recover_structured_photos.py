"""Recover licensed car images only when Commons depicts the exact catalogue identity."""
import json,urllib.request,urllib.parse,time,datetime,re,html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
UA='MotorJury/1.0 (https://motorjury.com/contact/)'
DATE=str(datetime.date.today())
def api(params):
 params=dict(params,format='json')
 for attempt in range(3):
  try:
   req=urllib.request.Request('https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params),headers={'User-Agent':UA})
   with urllib.request.urlopen(req,timeout=35) as response:body=json.load(response)
   if body.get('error'):raise ValueError(body['error'].get('code'))
   time.sleep(.3);return body
  except Exception:
   time.sleep(1+attempt)
 return {}
def batch(rows):
 ids={r['q']:r for r in rows}
 result=api({'action':'query','generator':'search','gsrsearch':'haswbstatement:'+'|'.join('P180='+q for q in ids),'gsrnamespace':6,'gsrlimit':50,'prop':'imageinfo','iiprop':'url|size|extmetadata','iiurlwidth':960})
 pages=list(result.get('query',{}).get('pages',{}).values())
 if not pages:return {}
 entities=api({'action':'wbgetentities','ids':'|'.join('M'+str(p['pageid']) for p in pages),'props':'claims'}).get('entities',{})
 found={}
 clean=lambda value:html.unescape(re.sub('<[^>]+>','',value or '')).strip()
 for page in pages:
  filename=page['title'].removeprefix('File:')
  if not filename.lower().endswith(('.jpg','.jpeg','.png','.webp')) or re.search(r'\b(logo|badge|engine|dashboard|interior|brochure|manual)\b',filename,re.I):continue
  image=page.get('imageinfo',[{}])[0];meta=image.get('extmetadata',{})
  licence=clean(meta.get('LicenseShortName',{}).get('value',''))
  author=clean(meta.get('Artist',{}).get('value',''))
  licence_url=clean(meta.get('LicenseUrl',{}).get('value',''))
  if not (licence.startswith(('CC BY','CC0')) or licence.lower()=='public domain') or not author or not image.get('thumburl') or image.get('width',0)<640:continue
  statements=entities.get('M'+str(page['pageid']),{}).get('statements',{})
  depicted={c.get('mainsnak',{}).get('datavalue',{}).get('value',{}).get('id') for c in statements.get('P180',[]) if c.get('rank')!='deprecated'}
  for qid in depicted & ids.keys():
   tokens=re.findall(r'[a-z0-9]+',ids[qid]['n'].lower())
   score=sum(t in filename.lower() for t in tokens)*4+int(bool(re.search(r'\b(front|side|museum)\b',filename,re.I)))
   if qid in found and found[qid]['score']>=score:continue
   found[qid]={'score':score,'addition':{'filename':filename,'checked_at':DATE,'source':'https://commons.wikimedia.org/wiki/Special:EntityData/M'+str(page['pageid'])+'.json','identity_property':'P180','identity':qid},'credit':{'author':author,'licence':licence,'licence_url':licence_url or 'https://commons.wikimedia.org/wiki/Commons:Licensing','thumb':image['thumburl'],'checked_at':DATE}}
 return found
def main():
 rows=json.loads((ROOT/'site/assets/catalogue-data.json').read_text())
 pending={r['q']:r for r in rows if not r['p']}
 additions=json.loads((ROOT/'data/photo_additions.json').read_text())
 credits=json.loads((ROOT/'data/photo_credits.json').read_text())
 recovered={}
 # A popular model can fill a batch's first 50 results. Remove recovered identities
 # and repeat once so other identities can surface; never substitute a name match.
 for round_no in range(2):
  batches=[list(pending.values())[i:i+20] for i in range(0,len(pending),20)]
  with ThreadPoolExecutor(max_workers=2) as pool:
   for i,result in enumerate(pool.map(batch,batches),1):
    for qid,row in result.items():recovered[qid]=row;pending.pop(qid,None)
    if i%10==0:print('Structured photo round',round_no+1,'batch',i,'of',len(batches),'recovered',len(recovered),flush=True)
  if not recovered or not pending:break
 for qid,row in recovered.items():
  additions[qid]=row['addition'];credits[row['addition']['filename']]=row['credit']
 (ROOT/'data/photo_additions.json').write_text(json.dumps(additions,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'data/photo_credits.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2)+'\n')
 print('Exact depicted identities recovered:',len(recovered),'total photo additions:',len(additions),flush=True)
if __name__=='__main__':main()
