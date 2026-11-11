// Isolated SQLite backup/reopen drill; never connects to the production Hub.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {mkdtempSync,copyFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {HubDO} from './hub.js';
import {dashboardDispatch,digest} from './dashboard-store.mjs';
function open(path){
 const db=new DatabaseSync(path),sql={exec(query,...args){const statement=db.prepare(query);const rows=statement.columns().length?statement.all(...args):(statement.run(...args),[]);return {toArray:()=>rows};}};
 return {db,hub:new HubDO({storage:{sql}})};
}
test('closing, reopening and restoring an isolated SQLite snapshot preserves account and owner records',async()=>{
 const directory=mkdtempSync(join(tmpdir(),'motorjury-recovery-')),path=join(directory,'hub.sqlite'),snapshot=join(directory,'snapshot.sqlite');
 let db;
 try{
  let opened=open(path);db=opened.db;let h=opened.hub;
  const signed=await h.dispatch('signup',{email:'recovery-fixture@example.invalid',password:'fixture-only-strong-password',name:'Recovery fixture'},{});
  await h.dispatch('love',{token:signed.token,item:'fixture-f40',name:'Ferrari F40',url:'/library/ferrari/ferrari-f40/'},{});
  const setup='isolated-recovery-setup';await dashboardDispatch(h,'dashboard-setup',{token:setup,password:'fixture-dashboard-password'},await digest(setup));
  const session=await dashboardDispatch(h,'dashboard-login',{password:'fixture-dashboard-password',ip:'fixture'});
  await dashboardDispatch(h,'dashboard-task',{token:session.token,task:{id:'RESTORE-FIXTURE',title:'Preserve this owner edit',area:'Operations',owner:'Fixture',priority:1,status:'open',acceptance:'Retained after reopening'}});
  await dashboardDispatch(h,'dashboard-metric',{token:session.token,metric_ids:['organic_clicks'],metric:{id:'organic_clicks',value:0,start:'2026-10-01',end:'2026-10-31',source:'Isolated fixture, not audience evidence'}});
  const before=await dashboardDispatch(h,'dashboard-state',{token:session.token});
  const accountBefore=(await h.dispatch('me',{token:signed.token},{})).user;
  db.close();db=null;copyFileSync(path,snapshot);
  opened=open(path);db=opened.db;h=opened.hub;
  assert.deepEqual((await h.dispatch('me',{token:signed.token},{})).user,accountBefore);
  assert.equal((await h.dispatch('love-counts',{}, {items:'fixture-f40',token:signed.token})).counts['fixture-f40'],1);
  let after=await dashboardDispatch(h,'dashboard-state',{token:session.token});
  for(const key of ['tasks','metrics','history'])assert.deepEqual(after[key],before[key]);
  await dashboardDispatch(h,'dashboard-task',{token:session.token,task:{...before.tasks['RESTORE-FIXTURE'],title:'Temporary edit after the snapshot'}});
  assert.notDeepEqual((await dashboardDispatch(h,'dashboard-state',{token:session.token})).tasks,before.tasks);
  db.close();db=null;copyFileSync(snapshot,path);
  opened=open(path);db=opened.db;h=opened.hub;
  after=await dashboardDispatch(h,'dashboard-state',{token:session.token});
  for(const key of ['tasks','metrics','history'])assert.deepEqual(after[key],before[key]);
  assert.deepEqual((await h.dispatch('me',{token:signed.token},{})).user,accountBefore);
  assert.ok((await h.dispatch('login',{email:'recovery-fixture@example.invalid',password:'fixture-only-strong-password',ip:'restored-fixture'},{})).token);
 }finally{if(db)db.close();rmSync(directory,{recursive:true,force:true});}
});
