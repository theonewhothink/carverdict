"""Destructive synthetic-account QA is restricted to an isolated loopback Worker."""
import json,secrets,sys,urllib.error,urllib.request
from urllib.parse import urlparse
origin=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8878').rstrip('/')
if urlparse(origin).hostname not in ('127.0.0.1','localhost','::1'):
 raise SystemExit('This synthetic-account test is permitted only on isolated loopback.')
cookie='';checks=[]
def call(path,method='GET',body=None,foreign=None,raw=None,typ='application/json'):
 headers={'Origin':foreign or origin}
 if cookie:headers['Cookie']=cookie
 if body is not None or raw is not None:headers['Content-Type']=typ
 data=(raw if raw is not None else json.dumps(body)).encode() if body is not None or raw is not None else None
 req=urllib.request.Request(origin+path,data=data,headers=headers,method=method)
 try:r=urllib.request.urlopen(req,timeout=15)
 except urllib.error.HTTPError as e:r=e
 return r.status,json.load(r),dict(r.headers)
def check(label,status,expected):
 assert status==expected,(label,status,expected)
 checks.append({'check':label,'status':'pass'})
check('GET logout cannot mutate account',call('/api/auth/logout')[0],405)
check('cross-site signup rejected',call('/api/auth/signup','POST',{},foreign='https://foreign.example')[0],403)
check('invalid JSON rejected',call('/api/prefs','POST',raw='{')[0],400)
check('non-JSON write rejected',call('/api/prefs','POST',raw='{}',typ='text/plain')[0],415)
check('oversized body rejected',call('/api/prefs','POST',raw=json.dumps({'prefs':{'x':'x'*140000}}))[0],413)
email='priority-qa-'+secrets.token_hex(6)+'@example.invalid'
s,u,h=call('/api/auth/signup','POST',{'email':email,'password':secrets.token_urlsafe(20)})
check('isolated signup',s,200)
assert 'HttpOnly' in h.get('Set-Cookie','') and 'Secure' in h.get('Set-Cookie','')
# Manually replay this synthetic cookie only to loopback: production cookies are
# intentionally Secure and a normal HTTP browser must not send them here.
cookie=h['Set-Cookie'].split(';')[0]
check('signed-in identity',call('/api/auth/me')[0],200)
assert call('/api/auth/me')[1]['user']['email']==email
check('preference sync',call('/api/prefs','POST',{'prefs':{'garage':[{'u':'/cars/toyota/rav4/2019/','t':'RAV4'}]}})[0],200)
assert call('/api/auth/me')[1]['user']['prefs']['garage'][0]['t']=='RAV4'
item='toyota/rav4/2019'
baseline=call('/api/survey?item=toyota%2Frav4%2F2019')[1]['rollup']['n']
check('incomplete rating rejected',call('/api/survey','POST',{'item':item,'overall':5})[0],400)
assert call('/api/survey?item=toyota%2Frav4%2F2019')[1]['rollup']['n']==baseline
check('explicit owner answers saved',call('/api/survey','POST',{'item':item,'overall':4,'reliability':3,'running_cost':2,'years_owned':0,'would_buy_again':False,'owned':True})[0],200)
a=call('/api/survey?item=toyota%2Frav4%2F2019')[1]
assert a['mine']['reliability']==3 and a['mine']['would_buy_again']==0 and a['rollup']['n']==baseline+1
check('love toggle on',call('/api/love','POST',{'item':item,'name':'RAV4','url':'javascript:alert(1)'})[0],200)
assert call('/api/most-loved')[1]['items'][0]['url']=='/'
check('love toggle off',call('/api/love','POST',{'item':item})[0],200)
check('logout revokes session',call('/api/auth/logout','POST',{})[0],200)
assert call('/api/auth/me')[1]['user'] is None
print(json.dumps({'scope':'Isolated local workerd and Durable Object. No production users or votes created.','checks':checks}))
