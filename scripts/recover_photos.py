"""Recover exact-identity P18 images; never borrow a neighbouring model's photo."""
import json,urllib.request,urllib.parse,time,datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/photo_additions.json'
UA='MotorJury/1.0 (https://motorjury.com/contact/)'

def batch(ids):
    query=urllib.parse.urlencode({'action':'wbgetentities','ids':'|'.join(ids),'props':'claims','format':'json'})
    try:
        req=urllib.request.Request('https://www.wikidata.org/w/api.php?'+query,headers={'User-Agent':UA})
        with urllib.request.urlopen(req,timeout=30) as response:entities=json.load(response).get('entities',{})
        result={}
        for qid,entity in entities.items():
            for claim in entity.get('claims',{}).get('P18',[]):
                name=claim.get('mainsnak',{}).get('datavalue',{}).get('value')
                if isinstance(name,str) and name.lower().endswith(('.jpg','.jpeg','.png','.webp')):
                    result[qid]={'filename':name,'checked_at':str(datetime.date.today()),'source':'https://www.wikidata.org/wiki/'+qid};break
        time.sleep(.25)
        return result
    except Exception as error:
        print('Photo batch retained without guesses:',type(error).__name__,flush=True);return {}

def main():
    rows=json.loads((ROOT/'site/assets/catalogue-data.json').read_text())
    qids=sorted({r['q'] for r in rows if not r['p']})
    additions=json.loads(OUT.read_text()) if OUT.exists() else {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for i,result in enumerate(pool.map(batch,[qids[n:n+50] for n in range(0,len(qids),50)])):
            additions.update(result)
            print('Photo batches checked:',i+1,'exact-identity additions:',len(additions),flush=True)
    OUT.write_text(json.dumps(additions,indent=2,ensure_ascii=False)+'\n')
    print('PHOTO RECOVERY:',len(qids),'missing identities checked;',len(additions),'exact references recovered')

if __name__=='__main__':main()
