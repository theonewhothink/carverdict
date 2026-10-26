/** Exercise the reusable portal, including archives with one or no photographs. */
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join,extname} from 'node:path';
const root=resolve('site'),out=resolve('verification/brand-portal');
await mkdir(out,{recursive:true});
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png'};
const server=createServer(async(req,res)=>{try{const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);let file=resolve(root,'.'+path+(path.endsWith('/')?'index.html':''));if(!file.startsWith(root+'/'))throw Error('invalid path');const body=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]||'application/octet-stream'});res.end(body);}catch{res.writeHead(404);res.end('Not found');}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const manifest=JSON.parse(await readFile(join(root,'assets/brand-portals.json'),'utf8'));
const samples=['Ferrari','BMW','Toyota','Mercedes-Benz','Audi AG','Renault','9ff'].map(brand=>manifest.find(x=>x.brand===brand));
samples.push(manifest.find(x=>x.photographs===0&&x.brand.length>20));
const checks=[],errors=[],images=[];
function check(label,condition){checks.push({label,passed:!!condition});if(!condition)throw Error(label);}
const browser=await chromium.launch({headless:true});
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
 for(const record of samples){
  await page.goto(origin+record.path);await page.locator('[data-brand-portal]').waitFor();
  await page.getByLabel('Find a '+record.brand+' in the directory',{exact:true}).waitFor();
  check(record.brand+': one main heading',await page.locator('h1').count()===1);
  check(record.brand+': complete visible directory',await page.locator('[data-model-name]:visible').count()===record.entries);
  check(record.brand+': matching gallery size',await page.locator('.bp-gallery-item').count()===record.photographs);
  check(record.brand+': open sections',await page.locator('.brand-portal details').count()===0);
  const first=await page.locator('[data-model-name]').first().getAttribute('data-model-name');
  const field=page.getByLabel('Find a '+record.brand+' in the directory',{exact:true});await field.fill(first);
  check(record.brand+': search matches the actual car',await page.locator('[data-model-name]:visible').count()>=1);
  await field.fill('NoSuchCarIdentity-ZZ1234');check(record.brand+': honest empty result',await page.locator('[data-no-models]').isVisible());await field.fill('');
  if(record.photographs){
   await page.getByRole('button',{name:'Enlarge '+await page.locator('.bp-gallery-item figcaption>b').first().innerText(),exact:true}).click();
   check(record.brand+': gallery is named for the correct marque',await page.getByRole('dialog',{name:record.brand+' photograph viewer',exact:true}).isVisible());await page.keyboard.press('Escape');
   images.push(await page.locator('.bp-masthead img').first().evaluate(img=>({brand:img.alt,url:img.currentSrc,loaded:img.complete&&img.naturalWidth>0})));
  }
  for(const width of [360,1440]){await page.setViewportSize({width,height:1000});check(record.brand+': no overflow at '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  if(['BMW','Ferrari'].includes(record.brand)){await page.screenshot({path:join(out,record.brand.toLowerCase()+'-portal-desktop.png')});}
 }
 const ferrari=manifest.find(x=>x.brand==='Ferrari');await page.goto(origin+ferrari.path);await page.getByRole('button',{name:'Play 75 years of Ferrari',exact:true}).click();
 check('Ferrari: real selected film loads on demand',await page.locator('iframe[src*="youtube-nocookie.com/embed/S3Fn5kk6_fM"]').count()===1);
 await page.goto(origin+'/library/');await page.getByRole('link',{name:'BMW portal →',exact:true}).click();check('Library marque chip opens the brand portal',page.url()===origin+'/library/bmw/');
 check('No uncaught browser errors across sparse and full portals',errors.length===0);await context.close();
 const plain=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:900}}),nojs=await plain.newPage();
 for(const record of samples.slice(0,3)){await nojs.goto(origin+record.path);check(record.brand+': complete directory without JavaScript',await nojs.locator('[data-model-name]').count()===record.entries);check(record.brand+': source notes visible without JavaScript',await nojs.locator('#sources').isVisible());}
 await plain.close();console.log('ALL_BRAND_BROWSER_QA:'+JSON.stringify({checks,errors,images}));
}finally{await writeFile(join(out,'all-brands-browser-qa.json'),JSON.stringify({checks,errors,images},null,2));await browser.close();await new Promise(resolve=>server.close(resolve));}
