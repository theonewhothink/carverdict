/** Real reader journeys in an isolated Chromium instance, never a signed-in browser. */
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,stat,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
const root=resolve('site'),out=resolve('verification/brand-portal');await mkdir(out,{recursive:true});
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png'};
const server=createServer(async(req,res)=>{try{let file=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(file!==root&&!file.startsWith(root+sep)){res.writeHead(403).end();return;}if((await stat(file)).isDirectory())file=join(file,'index.html');res.setHeader('Content-Type',types[extname(file)]||'application/octet-stream');res.end(await readFile(file));}catch{res.writeHead(404).end('Not found');}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch();const report={checks:[],images:[],errors:[]};
const check=(name,value)=>{assert(value,name);report.checks.push(name);};
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();const requests=[];
 page.on('pageerror',e=>report.errors.push(e.message));page.on('request',r=>requests.push(r.url()));
 await page.goto(origin+'/library/porsche/',{waitUntil:'domcontentloaded'});await page.locator('.bp-generation-tabs').waitFor({state:'visible'});
 check('24 photographs are available in the gallery',await page.locator('.bp-gallery-item').count()===24);
 check('No YouTube request before a playback choice',!requests.some(url=>/youtube|ytimg/.test(url)));
 for(const image of await page.locator('.bp-gallery img').all())await image.scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>[...document.querySelectorAll('.bp-gallery img')].every(img=>img.complete),{},{timeout:20000}).catch(()=>{});
 report.images=await page.locator('.bp-gallery img').evaluateAll(images=>images.map(img=>({alt:img.alt,loaded:img.naturalWidth>0,url:img.currentSrc})));
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:join(out,'porsche-desktop.png')});
 check('Desktop has no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.getByRole('tab',{name:'992'}).click();check('The 992 selector changes the visible generation',await page.getByRole('heading',{name:'The idea, sharpened again.'}).isVisible());
 await page.getByRole('tab',{name:'992'}).press('Home');check('Generation tabs support keyboard navigation',await page.getByRole('heading',{name:'The outline arrives.'}).isVisible());
 await page.getByRole('button',{name:'Flagships',exact:true}).click();check('Gallery filters show the three flagships',await page.locator('.bp-gallery-item:visible').count()===3);
 await page.getByRole('button',{name:'Enlarge 959 · road car',exact:true}).click();await page.getByRole('dialog').waitFor({state:'visible'});await page.getByRole('button',{name:'Next photograph',exact:true}).click();check('Gallery lightbox moves between photographs',await page.getByRole('dialog').innerText().then(text=>text.includes('Carrera GT')));await page.keyboard.press('Escape');check('Escape closes the photograph viewer',await page.getByRole('dialog').count()===0||!(await page.getByRole('dialog').isVisible()));
 await page.getByRole('button',{name:'All 24',exact:true}).click();
 await page.getByLabel('Find a Porsche in the directory').fill('959');check('The model directory filters actual entries',await page.locator('[data-portal-roster] li:visible').count()===3);
 await page.getByRole('combobox',{name:'Search cars and brands',exact:true}).fill('Porsche');await page.locator('[data-search-brand]').filter({hasText:'Porsche'}).waitFor({state:'visible'});
 await page.getByRole('combobox',{name:'Search cars and brands',exact:true}).press('ArrowDown');await page.getByRole('combobox',{name:'Search cars and brands',exact:true}).press('Enter');await page.waitForURL(origin+'/library/porsche/');await page.locator('.bp-generation-tabs').waitFor({state:'visible'});check('Header keyboard search opens the brand portal',page.url()===origin+'/library/porsche/');
 await page.goto(origin+'/library/porsche/#m-porsche-3512');await page.locator('#m-porsche-3512').waitFor({state:'visible'});check('Existing fragment destinations reveal their directory entry',await page.locator('#m-porsche-3512').isVisible());
 for(const width of [360,390,768,1440]){await page.setViewportSize({width,height:900});await page.goto(origin+'/library/porsche/');await page.locator('.bp-generation-tabs').waitFor({state:'visible'});check('No horizontal overflow at '+width+'px',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));if(width===390){await page.screenshot({path:join(out,'porsche-mobile.png')});}}
 await page.setViewportSize({width:390,height:900});for(const url of ['/','/library/','/library/ferrari/','/guides/','/ask/','/library/ferrari/ferrari-f40/']){await page.goto(origin+url);check('Exactly one header search on '+url,await page.locator('#header-car-search').count()===1);check('Header fits the phone viewport on '+url,await page.locator('[data-header-search]').evaluate(el=>el.getBoundingClientRect().right<=innerWidth+1));}
 await page.goto(origin+'/library/porsche/');await page.getByRole('button',{name:'Play The Porsche 356 SL (1952)',exact:true}).click();check('Playback loads the selected privacy-enhanced embed',await page.locator('iframe[src*="youtube-nocookie.com/embed/8-KmqfOY5C8"]').count()===1);
 check('No uncaught browser errors',report.errors.length===0);await context.close();
 const plain=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:900}}),nojs=await plain.newPage();await nojs.goto(origin+'/library/porsche/');check('All 140 directory entries work without JavaScript',await nojs.locator('[data-model-name]').count()===140);check('All eight generation stories remain readable without JavaScript',await nojs.locator('.bp-generation:visible').count()===8);check('Official video links remain available without JavaScript',await nojs.locator('.bp-film>a[href*="youtube.com/watch"]').count()===3);await plain.close();
 console.log('PORTAL_BROWSER_QA:'+JSON.stringify(report));
}finally{await writeFile(join(out,'browser-qa.json'),JSON.stringify(report,null,2));await browser.close();await new Promise(resolve=>server.close(resolve));}
