"""Retain existing record URLs without predictive ratings or unverified zero claims.

Only records with a service-specific source check display counts. Existing pages
remain useful lookup routes during migration; they are ad-free and unindexed if
their evidence needs verification. This does not create every year/pairing URL.
"""
import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from build_buying_brief import write, esc, ROOT, SITE
from nhtsa_records import identity, record_check
from catalogue_experience import record_photo


def ownership_card(r):
    fuel = int(r["annual_fuel_cost"] or 0)
    try:
        curve = json.loads(r["cost_curve"] or "[]")
        age = max(0, date.today().year - int(r["year"]))
        point = min(curve, key=lambda p: abs(int(p["age"]) - age)) if curve else None
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        point = None
    maint_low = int(point["total_low"]) if point else 0
    maint_high = int(point["total_high"]) if point else 0
    running_low, running_high = fuel + maint_low, fuel + maint_high
    fuel_type = r["fuel_type"] or ""
    if not fuel:
        fuel_note = "No usable fuel/energy figure is available; it is excluded rather than shown as $0."
        fuel_text = "Not available"
    elif fuel_type.startswith("est-adjacent:"):
        fuel_note = "Estimated from the nearest EPA-covered model year (" + esc(fuel_type.split(":", 1)[1]) + ")."
        fuel_text = f"${fuel:,}/year"
    elif fuel_type == "est-segment":
        fuel_note = "Estimated from the EPA-backed segment mean because this exact version is not matched."
        fuel_text = f"${fuel:,}/year"
    else:
        fuel_note = "EPA annual fuel/energy planning figure for the matched record."
        fuel_text = f"${fuel:,}/year"
    known = (f'<div class="ownership-known"><div><span>Fuel / energy</span><b>{fuel_text}</b><small>{fuel_note}</small></div>'
             f'<div><span>Maintenance planning band</span><b>${maint_low:,}–${maint_high:,}/year</b><small>Generic age-based planning range, not a repair quote.</small></div>'
             f'<div><span>Fuel + maintenance</span><b>${running_low:,}–${running_high:,}/year</b><small>Insurance, repairs and depreciation are added below from your numbers.</small></div></div>')
    return f'''<section class="card ownership" data-ownership-planner data-running-low="{running_low}" data-running-high="{running_high}">
<p class="eyebrow">Ownership budget · transparent inputs</p><h2>What could this car cost you?</h2>{known}
<p>MotorJury does not guess a purchase price, insurance premium, repair bill or resale value. Enter the actual listing and quotes you are considering.</p>
<form><div class="ownership-fields">
<label>Actual purchase price ($)<input name="purchase" type="number" min="0" step="100" inputmode="decimal" required placeholder="Seller's price"></label>
<label>Expected resale after holding period ($)<input name="resale" type="number" min="0" step="100" inputmode="decimal" required placeholder="Your assumption"></label>
<label>Actual insurance quote / year ($)<input name="insurance" type="number" min="0" step="10" inputmode="decimal" required placeholder="Your quote"></label>
<label>Repair reserve / year ($)<input name="repairs" type="number" min="0" step="50" inputmode="decimal" required placeholder="Your reserve"></label>
<label>Years you will keep it<input name="years" type="number" min="1" max="15" step="1" value="5" required></label>
</div><button type="submit">Calculate my ownership range</button></form>
<div class="ownership-result" data-ownership-result role="status" aria-live="polite">Enter the four actual money inputs to calculate a total.</div>
<details><summary>What the total includes</summary><p>Purchase price minus your expected resale value (depreciation), plus fuel/energy, the generic maintenance band, your insurance quote and your repair reserve for the selected years. Financing, tax, registration and parking are excluded.</p></details></section>'''


def apply_pilot(con):
    for record in json.loads((ROOT / "data" / "pilot_records.json").read_text())["records"]:
        rows = con.execute('''SELECT my.id,mk.name,mo.name,my.year FROM model_years my
            JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
            WHERE my.year=?''', (record["year"],)).fetchall()
        ids = [r[0] for r in rows if identity(r[1]) == identity(record["make"]) and identity(r[2]) == identity(record["model"])]
        if len(ids) != 1:
            raise ValueError("Pilot record does not match one exact database identity")
        my = ids[0]
        for kind, check in record["checks"].items():
            record_check(con, my, kind, check)
        c, r = record["checks"]["complaints"], record["checks"]["recalls"]
        if any(x["status"] not in ("matched", "empty") for x in (c, r)):
            raise ValueError("Pilot sources did not pass validation")
        con.execute("UPDATE model_years SET complaint_count=?,complaint_sample=?,recall_count=?,severe_recalls=NULL,data_gap=NULL WHERE id=?", (c["count"],c["count"],r["count"],my))
        con.execute("DELETE FROM complaints WHERE my_id=?", (my,))
        con.executemany("INSERT INTO complaints(my_id,component,count,sample) VALUES(?,?,?,NULL)", [(my,name,n) for name,n in c["components"]])
        con.execute("DELETE FROM recalls WHERE my_id=?", (my,))
        con.executemany("INSERT INTO recalls(my_id,campaign,date,component,summary,severe) VALUES(?,?,?,?,?,NULL)",
            [(my,x["NHTSACampaignNumber"],x.get("ReportReceivedDate"),x.get("Component"),x.get("Summary")) for x in r["results"]])
    con.commit()


def main():
    # New-page thresholds must not delete an already published, exact year record
    # when complaint/recall totals change in the nightly dataset.
    legacy=json.loads((ROOT/'data'/'legacy_routes.json').read_text())['routes']
    published=set(legacy)
    con=sqlite3.connect(ROOT / "data" / "cars.sqlite")
    apply_pilot(con)
    # Small migration/test fixtures may predate the cost tables. Keep the routes useful
    # and render "Not available" rather than turning an absent join into a build failure.
    con.execute('''CREATE TABLE IF NOT EXISTS fuel(my_id INT PRIMARY KEY, fuel_type TEXT,
        mpg_city REAL, mpg_hwy REAL, mpg_comb REAL, annual_fuel_cost INT,
        ev_range REAL, kwh_100mi REAL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS computed_scores(my_id INT PRIMARY KEY,
        reliability_score INT, verdict TEXT, reasons TEXT, cost_curve TEXT,
        complaints_per_year REAL)''')
    con.row_factory=sqlite3.Row
    rows=con.execute('''SELECT my.*,mk.name make,mk.slug kslug,mo.name model,mo.slug mslug,
        f.annual_fuel_cost,f.fuel_type,cs.cost_curve
        FROM model_years my JOIN models mo ON mo.id=my.model_id JOIN makes mk ON mk.id=mo.make_id
        LEFT JOIN fuel f ON f.my_id=my.id LEFT JOIN computed_scores cs ON cs.my_id=my.id
        ORDER BY mk.name,mo.name,my.year DESC''').fetchall()
    checks={(r["my_id"],r["service"]):dict(r) for r in con.execute("SELECT * FROM source_checks")}
    by_model=defaultdict(list)
    by_make=defaultdict(list)
    def count(r,kind):
        c=checks.get((r["id"],kind))
        value=r["complaint_count" if kind=="complaints" else "recall_count"]
        return f'{value:,}' if c and c["status"] in ("matched","empty") and value is not None else "Not verified"
    made=0
    for r in rows:
        by_model[(r["kslug"],r["mslug"])].append(r)
        url=f'/cars/{r["kslug"]}/{r["mslug"]}/{r["year"]}/'
        if url not in published and not (SITE / url.strip('/') / 'index.html').exists():
            continue
        name=f'{r["year"]} {r["make"]} {r["model"]}'
        rc=checks.get((r["id"],"recalls"))
        campaign_html=''
        if rc and rc["status"] in ("matched","empty"):
            campaigns=con.execute("SELECT * FROM recalls WHERE my_id=? ORDER BY campaign",(r["id"],)).fetchall()
            campaign_html=''.join(f'<li><b>{esc(x["campaign"])}</b> — {esc(x["component"] or "")}<p>{esc(x["summary"] or "")}</p></li>' for x in campaigns)
            campaign_html=f'<section class="card"><h2>Matched campaigns</h2><ul>{campaign_html}</ul><p class="note">Checked {esc(rc["checked_at"][:10])}. Campaigns are model-level; a dealer must confirm VIN applicability and remedy completion.</p></section>'
        elif rc:
            campaign_html=f'<p class="callout">The most recent recall check is {esc(rc["status"])}. No zero-recall or safe-to-buy conclusion can be drawn.</p>'
        lookup='https://www.nhtsa.gov/vehicle/'+str(r['year'])+'/'+r['make'].upper()+'/'+r['model'].upper().replace(' ','%20')
        engage=(f'<section class="card engagement-card"><div class="love-host" data-love="my:{r["id"]}" data-love-name="{esc(name)}"></div>'
                f'<div class="survey-card" data-survey="my:{r["id"]}" data-survey-name="{esc(name)}"></div></section>')
        body=f'''<section class="hero"><p class="eyebrow">US public safety record</p><h1>{esc(name)}</h1><p class="lede">Use the record to choose what to check. It cannot establish this car's condition.</p></section>
<section class="card"><h2>What is verified here?</h2><p>Complaint reports: <b>{count(r,'complaints')}</b>. Distinct recall campaigns: <b>{count(r,'recalls')}</b>.</p><p>“Not verified” means the snapshot lacks a successful service-specific matching check. It does not mean zero. Complaint totals are reports, not failure rates.</p><p>Predictive reliability scores and automatic BUY/AVOID decisions are suspended.</p><div class="actions"><a class="button" href="https://www.nhtsa.gov/recalls">Check the actual VIN</a><a class="button secondary" href="{esc(lookup)}">See the NHTSA vehicle record</a></div></section>
{record_photo(r["make"],r["model"],r["year"])}{campaign_html}{ownership_card(r)}{engage}<section class="card"><h2>Before a deposit</h2><ul><li>Confirm the exact version and service history.</li><li>Ask for dealer evidence of applicable recall remedies.</li><li>Arrange an independent inspection of the actual vehicle.</li><li>Compare your purchase quote and insurance with a budget.</li></ul><p><a href="/cars/{r['kslug']}/{r['mslug']}/">Other years of this model</a> · <a href="/buying-brief/">See the RAV4 buying-brief example</a></p></section>'''
        write(url,name+' — documented safety checks and ownership budget',body+'<script src="/assets/ownership.js" defer></script>')
        f=SITE / url.strip('/') / 'index.html'
        if not rc or rc['status'] not in ('matched','empty'):
            f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
        made+=1
    for (ks,ms),rs in by_model.items():
        r=rs[0]; url=f'/cars/{ks}/{ms}/'
        if not (SITE / url.strip('/') / 'index.html').exists():continue
        trs=[]
        for x in rs:
            year_url=f'/cars/{ks}/{ms}/{x["year"]}/'
            y=f'<a href="{year_url}">{x["year"]}</a>' if (SITE / year_url.strip('/') / 'index.html').exists() else str(x['year'])
            trs.append(f'<tr><td>{y}</td><td>{count(x,"complaints")}</td><td>{count(x,"recalls")}</td></tr>')
        write(url,f'{r["make"]} {r["model"]} — public-record lookup',f'''<section class="hero"><h1>{esc(r['make'])} {esc(r['model'])}</h1><p class="lede">Choose a year to investigate documented issues. The table is not a reliability ranking.</p></section><section class="card"><div class="table-wrap"><table><thead><tr><th>Year</th><th>Complaint reports</th><th>Recall campaigns</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div><p class="note">Unverified source matching is shown explicitly rather than reported as zero. Counts do not establish VIN applicability or whether a remedy is complete.</p><a href="https://www.nhtsa.gov/recalls">Check the actual VIN</a></section>''')
        f=SITE/url.strip('/')/'index.html';f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
        by_make[ks].append((r['make'],r['model'],url));made+=1
    for ks,models in by_make.items():
        links=''.join(f'<li><a href="{u}">{esc(model)}</a></li>' for _,model,u in models)
        write('/cars/'+ks+'/',models[0][0]+' safety-record lookup',f'<section class="hero"><h1>{esc(models[0][0])} public records</h1><p class="lede">Choose a model. Source matching is being verified; this list is not a recommendation.</p></section><section class="card"><ul>{links}</ul></section>')
    links=''.join(f'<li><a href="/cars/{ks}/">{esc(models[0][0])}</a></li>' for ks,models in by_make.items())
    write('/cars/','Look up a car in the public record',f'<section class="hero"><h1>Look up the record.<br>Then check the actual car.</h1><p class="lede">This US-market snapshot is being verified service by service. No automated reliability verdict is published.</p></section><section class="card"><ul>{links}</ul></section>')
    # Preserve published comparison routes, even though the unsupported ranking
    # generator no longer selects pairs. Unknown versions stay unknown.
    model_keys={ks+'-'+ms:(ks,ms) for ks,ms in by_model}
    compare_links=[]
    for path in legacy:
        if not path.startswith('/compare/') or path=='/compare/':continue
        pair=path.strip('/').split('/')[-1].split('-vs-')
        if len(pair)!=2:raise ValueError('Unrecognised existing comparison path')
        keys=[model_keys.get(p) for p in pair]
        if any(k is None for k in keys):
            # Keep the exact route, without claiming a guessed identity or match.
            title='Compare the actual candidates'
            content='<p>The previous automated comparison is withheld because its source identities and scores need review. Confirm the exact years and powertrains before comparing records or costs.</p>'
        else:
            names=[by_model[k][0]['make']+' '+by_model[k][0]['model'] for k in keys]
            title=names[0]+' or '+names[1]+'?'
            content=''.join(f'<h2>{esc(name)}</h2><p><a href="/cars/{k[0]}/{k[1]}/">Choose the year and inspect matched records</a>.</p>' for name,k in zip(names,keys))
        content+='<p>Use the same mileage, holding period and budget assumptions for both cars. Get each actual purchase and insurance quote, check its VIN and arrange an independent inspection. A difference in complaint totals is not a failure-rate comparison.</p><p><a href="/buying-brief/">See a complete RAV4 comparison and budget example</a>.</p>'
        write(path,title,f'<section class="hero"><p class="eyebrow">Comparison route · source review in progress</p><h1>{esc(title)}</h1></section><article class="card">{content}</article>')
        f=SITE/path.strip('/')/'index.html';f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
        compare_links.append(f'<li><a href="{path}">{esc(title)}</a></li>')
    write('/compare/','Compare used-car candidates', '<section class="hero"><h1>Compare the cars you can actually buy.</h1></section><section class="card"><p>The first complete comparison connects a 2019–2020 RAV4 gasoline or Hybrid to a checklist and your own budget. Earlier automated comparisons are ad-free reference routes while their evidence is reviewed.</p><a class="button" href="/guides/rav4-gasoline-vs-hybrid/">Start with the complete example</a></section><details class="card"><summary>Existing reference comparisons</summary><ul>'+''.join(compare_links)+'</ul></details>')
    # Problem routes duplicate safety records, not a separate reliability ranking.
    for f in (SITE/'problems').rglob('index.html'):
        relative=f.parent.relative_to(SITE/'problems').as_posix()
        destination=SITE/'cars'/relative/'index.html'
        if destination.exists():
            f.write_text(destination.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
        else:
            path='/problems/'+('' if relative=='.' else relative+'/')
            write(path,'Documented problems need an exact match','<section class="hero"><h1>Check the actual vehicle.</h1></section><section class="card"><p>Automatic problem rankings are suspended. Choose the exact year and version, verify campaigns by VIN, and use an independent inspection to establish condition.</p><a href="/cars/">Open the public-record lookup</a></section>')
            f.write_text(f.read_text().replace('</head>','<meta name="robots" content="noindex,follow"></head>'))
    write('/years-to-avoid/','How to investigate a used-car year','<section class="hero"><h1>A model year is a starting point.<br>Check the actual car.</h1></section><article class="card"><p>Automatic best-year and worst-year rankings are suspended. Complaint totals cannot establish failure probability without comparable sales and usage denominators.</p><p>Start with the exact powertrain and year. Check applicable campaigns by VIN, ask for remedy and service records, and arrange an independent inspection. Then compare the actual price and ownership assumptions with an alternative.</p><p><a href="/buying-brief/">Work through the RAV4 example</a> · <a href="/cars/">Look up a model record</a></p></article>')
    con.close()
    print(f'RECORD PAGES: {made} existing URLs retained with evidence states; no rating or false zero')


if __name__=='__main__': main()
