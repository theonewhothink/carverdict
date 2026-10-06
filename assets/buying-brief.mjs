import { compare } from './buying-budget.mjs';
const form = document.querySelector('#brief-form');
if (form) {
  const output = document.querySelector('#budget-result');
  const status = document.querySelector('#brief-status');
  const tasks = new Set();
  const money = (n) => n === null ? 'Unknown' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
  function track(task) {
    if (tasks.has(task)) return;
    tasks.add(task);
    window.dispatchEvent(new CustomEvent('motorjury:buying-task', { detail: { task } }));
    // Never send prices, mileage, VINs, seller documents or checklist text.
    if (typeof window.gtag === 'function') window.gtag('event', 'buying_task_complete', { task_type: task });
  }
  function read() {
    const d = Object.fromEntries(new FormData(form));
    const car = (prefix) => Object.fromEntries(['price','mpg','insurance','maintenance','reserve','resale'].map((k) => [k,d[`${prefix}_${k}`]]));
    return { d, a: car('a'), b: car('b'), common: { miles:d.miles, fuel:d.fuel, years:d.years } };
  }
  function update() {
    const { d } = read();
    document.querySelector('#hybrid-check').hidden = d.powertrain === 'gasoline';
    document.querySelectorAll('[data-hybrid-item]').forEach((e) => { e.hidden = d.powertrain === 'gasoline'; });
    document.querySelector('#version-note').textContent = d.powertrain === 'unknown'
      ? 'Version not confirmed. Ask for the exact powertrain before using the version-specific checks.'
      : `Selected: ${d.year} RAV4 ${d.powertrain}. Confirm this matches the actual car. Model records do not clear its VIN.`;
    document.querySelectorAll('[data-record-year]').forEach((e) => { e.hidden = e.dataset.recordYear !== d.year; });
  }
  form.addEventListener('change', update);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const { a,b,common } = read();
    const result = compare(a,b,common);
    output.replaceChildren();
    for (const [label,r] of [['Gasoline candidate',result.left],['Hybrid candidate',result.right]]) {
      const box = document.createElement('section');
      const title = document.createElement('h3'); title.textContent = label;
      const fuel = document.createElement('p'); fuel.textContent = `Annual fuel scenario: ${money(r.annualFuel)}`;
      const total = document.createElement('p'); total.textContent = r.total === null
        ? `Ownership total unknown. Missing or invalid: ${r.missing.join(', ')}.`
        : `Cash ownership scenario over your stated holding period: ${money(r.total)}.`;
      box.append(title,fuel,total); output.append(box);
    }
    const note = document.createElement('p');
    note.textContent = result.difference === 0
      ? 'Under your inputs, the ownership scenarios cost the same. Condition and documented history still matter.'
      : result.difference === null
      ? 'The missing figures prevent an ownership-cost winner. A fuel saving alone does not establish the better purchase.'
      : `Under your inputs, the hybrid scenario is ${money(Math.abs(result.difference))} ${result.difference < 0 ? 'lower' : 'higher'} over the holding period. This is arithmetic, not a price appraisal or repair forecast.`;
    output.append(note); output.hidden = false;
    if (result.left.annualFuel !== null || result.right.annualFuel !== null) track('budget_calculation');
  });
  document.querySelector('#save-brief').addEventListener('click', () => {
    try {
      localStorage.setItem('mj-buying-brief-v1', JSON.stringify({ inputs:read().d, checks:[...form.querySelectorAll('[data-check]')].map((x) => x.checked) }));
      status.textContent = 'Saved on this browser only. Other people using this browser may see it. Nothing was uploaded.';
      track('brief_save');
    } catch { status.textContent = 'This browser could not save the brief. Use Print / save PDF instead.'; }
  });
  document.querySelector('#print-brief').addEventListener('click', () => { window.print(); });
  document.querySelector('#export-brief').addEventListener('click', () => {
    const { d } = read();
    const lines = [...form.querySelectorAll('[data-check]')].filter((x) => !x.closest('label').hidden).map((x) => `${x.checked ? '[x]' : '[ ]'} ${x.closest('label').textContent.trim()}`);
    const text = `MotorJury viewing checklist — ${d.year} RAV4, ${d.powertrain}\nModel-level research; not VIN clearance or a mechanical inspection.\n\n${lines.join('\n')}\n\nSources and budget: https://motorjury.com/buying-brief/\n`;
    const href = URL.createObjectURL(new Blob([text],{ type:'text/plain;charset=utf-8' }));
    const link = document.createElement('a'); link.href=href; link.download='motorjury-viewing-checklist.txt'; link.click();
    status.textContent = 'Checklist download requested. Check your browser downloads; your budget is excluded.';
    setTimeout(() => URL.revokeObjectURL(href),1000); track('checklist_export');
  });
  document.querySelector('#share-brief').addEventListener('click', async () => {
    const { d } = read();
    const url = new URL('/buying-brief/',location.origin);
    url.searchParams.set('year',d.year); url.searchParams.set('powertrain',d.powertrain);
    try { await navigator.clipboard.writeText(url.href); status.textContent='Copied a link with year and powertrain only. Your budget and checked items are excluded.'; }
    catch { status.textContent=`Copy this link: ${url.href}`; }
  });
  document.querySelector('#clear-brief').addEventListener('click', () => {
    try { localStorage.removeItem('mj-buying-brief-v1'); } catch {}
    form.reset(); output.hidden=true; update(); status.textContent='Saved inputs and checklist cleared from this browser.';
  });
  try {
    const saved=JSON.parse(localStorage.getItem('mj-buying-brief-v1') || 'null');
    if (saved && saved.inputs) {
      for (const [k,v] of Object.entries(saved.inputs)) { const e=form.elements.namedItem(k); if(e && typeof v==='string') e.value=v; }
      form.querySelectorAll('[data-check]').forEach((e,i) => { e.checked=saved.checks?.[i] === true; });
      status.textContent='Restored your brief from this browser. No budget calculation has run automatically.';
    }
  } catch {}
  const params=new URLSearchParams(location.search);
  for (const [key,allowed] of [['year',['2019','2020']],['powertrain',['unknown','gasoline','hybrid']]]) {
    if (allowed.includes(params.get(key))) form.elements.namedItem(key).value=params.get(key);
  }
  update();
}
