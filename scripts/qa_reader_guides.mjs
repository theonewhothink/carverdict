/** Generated guide journeys in CI's isolated Chromium, never a reader account. */
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,stat,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
const root=resolve('site'),out=resolve('verification/reader-guides');
const slugs=['used-car-ownership-budget','hybrid-fuel-break-even','match-car-version-before-you-buy','recall-check-to-dealer-record','car-design-timeline','compare-car-design-briefs'];
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png'};
const server=createServer(async(req,res)=>{try{let file=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(file!==root&&!file.startsWith(root+sep)){res.writeHead(403).end();return;}if((await stat(file)).isDirectory())file=join(file,'index.html');res.setHeader('Content-Type',types[extname(file)]||'application/octet-stream');res.end(await readFile(file));}catch{res.writeHead(404).end('Not found');}});
await mkdir(out,{recursive:true});
const report={checks:[],errors:[]};let browser;
const check=(name,condition)=>{assert(condition,name);report.checks.push(name);};
try{
 await new Promise((done,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',done);});
 const origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch();const page=await browser.newPage();
 page.on('pageerror',error=>report.errors.push(error.message));
 for(const width of [320,390,1440]){
  await page.setViewportSize({width,height:950});
  for(const slug of slugs){
   const response=await page.goto(origin+'/guides/'+slug+'/',{waitUntil:'networkidle'});
   check(slug+' responds at '+width,response.status()===200);
   check(slug+' has one main heading at '+width,await page.locator('h1').count()===1);
   check(slug+' fits viewport '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  }
 }
 await page.setViewportSize({width:390,height:950});
 await page.goto(origin+'/guides/used-car-ownership-budget/');
 for(const [name,value]of Object.entries({price:25000,resale:10000,years:5,insurance:1000,maintenance:700,reserve:500,mpg:30,miles:12000,fuel:3.5}))await page.locator('input[name="'+name+'"]').fill(String(value));
 await page.getByRole('button',{name:'Calculate my scenario',exact:true}).click();
 check('Ownership form calculates the fictional five-year scenario',(await page.locator('[data-guide-result]').innerText()).includes('$33,000.00'));
 check('Ownership breakdown contains all five components',await page.locator('[data-guide-result] tbody tr').count()===5);
 check('Currency amounts stay on one line',await page.locator('[data-guide-result] tbody td:nth-child(2)').evaluateAll(cells=>cells.every(cell=>{const range=document.createRange();range.selectNodeContents(cell);return range.getClientRects().length===1;})));
 check('Ownership result fits a narrow viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.locator('[data-guide-result]').screenshot({path:join(out,'ownership-result-390.png')});
 await page.goto(origin+'/guides/hybrid-fuel-break-even/');
 for(const [name,value]of Object.entries({a:30,b:40,premium:2000,miles:12000,fuel:3.5}))await page.locator('input[name="'+name+'"]').fill(String(value));
 await page.getByRole('button',{name:'Calculate my scenario',exact:true}).click();
 check('Fuel-only example gives 5.71 years',(await page.locator('[data-guide-result]').innerText()).includes('5.71 years'));
 await page.locator('input[name="b"]').fill('30');await page.getByRole('button',{name:'Calculate my scenario',exact:true}).click();
 check('Equal MPG cannot promise a positive-premium payback',(await page.locator('[data-guide-result]').innerText()).includes('no fuel-only payback'));
 await page.locator('[data-guide-result]').screenshot({path:join(out,'fuel-result-390.png')});
 check('Guide journeys raise no browser script errors',report.errors.length===0);
}finally{
 await writeFile(join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');
 if(browser)await browser.close();await new Promise(done=>server.close(done));
}
console.log('Reader guide browser checks:',report.checks.length,'passed');
