"""The first complete buying journey, from primary sources and user assumptions.

No external harvest, borrowed prose, pretend road test, price estimate or account
requirement. Source dates describe the stored checks, never the build date.
"""
import html
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
ENGINE = "https://static.nhtsa.gov/odi/rcl/2020/RCMN-20V064-6563.pdf"
TANK = "https://static.nhtsa.gov/odi/tsbs/2021/MC-10190478-9999.pdf"
TOYOTA = "https://pressroom.toyota.com/2020-toyota-rav4-offers-a-new-trd-off-road-model-and-multimedia-enhancements/"
esc = html.escape


def shell(title, path, body, script=""):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#12685e">
<title>{esc(title)} | MotorJury</title><meta name="description" content="Prepare for a used-car viewing with documented checks, seller questions and a transparent ownership budget.">
<link rel="canonical" href="{ORIGIN}{path}"><link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/buying-brief.css"></head><body>
<a class="skip" href="#content">Skip to content</a><header><div class="wrap"><a class="logo" href="/">Motor<span>Jury</span></a>
<nav aria-label="Main"><a href="/buying-brief/">Buying brief</a><a href="/guides/toyota-rav4-years-to-avoid/">RAV4 checks</a><a href="/vin-check/">VIN check</a></nav></div></header>
<main id="content" data-buying-product><div class="wrap">{body}</div></main>
<footer><div class="wrap"><p>Independent desk research from linked public records. US market. No road test or specialist endorsement is claimed.</p>
<p><a href="/methodology/">How the evidence works</a> · <a href="/editorial-policy/">Editorial policy</a> · <a href="/contact/">Send a correction</a> · <a href="/privacy/">Privacy</a> · <a href="/disclosure/">Advertising</a></p></div></footer>{script}</body></html>'''


def write(path, title, body, script=""):
    p = SITE / path.strip("/") / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(shell(title, path, body, script))


def sources():
    return f'''<section class="card"><h2>Sources you can check</h2><ul>
<li><a href="{ENGINE}">Toyota remedy notice: campaign 20V-064 / 20TA04</a> — engine-block recall scope and remedy.</li>
<li><a href="{TANK}">Toyota customer support program 20TE04</a> — Hybrid refuelling condition and program terms.</li>
<li><a href="{TOYOTA}">Toyota's 2020 RAV4 product information</a> — gasoline and Hybrid powertrain distinctions.</li>
<li><a href="https://www.fueleconomy.gov/feg/findacar.shtml">EPA vehicle finder</a> — match the exact version before entering fuel economy.</li>
</ul><p class="note">Documents reviewed 6 October 2026. They establish documented issues and scope; they do not establish the condition of a car for sale or current eligibility under a support program.</p></section>'''


def main():
    records = json.loads((ROOT / "data" / "pilot_records.json").read_text())["records"]
    for name in ("buying-brief.css", "buying-brief.mjs", "buying-budget.mjs"):
        (SITE / "assets").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "assets" / name, SITE / "assets" / name)
    budget = (ROOT / 'assets' / 'buying-budget.mjs').read_text()
    budget_name = 'buying-budget.' + hashlib.sha256(budget.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / budget_name).write_text(budget)
    script = (ROOT / 'assets' / 'buying-brief.mjs').read_text().replace('./buying-budget.mjs','./'+budget_name)
    script_name = 'buying-brief.' + hashlib.sha256(script.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / script_name).write_text(script)
    evidence = []
    for r in records:
        if r["make"] != "TOYOTA" or r["model"] != "RAV4":
            continue
        c, rc = r["checks"]["complaints"], r["checks"]["recalls"]
        if any(x["status"] not in ("matched", "empty") for x in (c, rc)):
            raise ValueError("Unverified pilot evidence")
        evidence.append(f'''<div data-record-year="{r['year']}"><p><b>{r['year']} RAV4:</b> {c['count']:,} complaint reports and {rc['count']} distinct recall campaigns in the matched model-level response.</p>
<p class="note">Checked {esc(rc['checked_at'][:10])}. Reports are not independent failures or failure rates. Components can overlap. These counts do not separate your exact powertrain or establish VIN applicability.</p>
<p><a href="{esc(rc['urls'][0])}">Inspect the recall response</a> · <a href="{esc(c['urls'][0])}">Inspect the complaint response</a></p></div>''')
    checks = [
        "Confirm the VIN, model year and powertrain match the seller's description.",
        "Run the VIN through NHTSA and Toyota; ask the dealer for campaign and remedy-completion records.",
        "Ask about coolant loss, overheating and engine work. Get the explanation and invoices, not a verbal assurance.",
        "Arrange an independent inspection. Ask the inspector to review the documented concerns and service history.",
        "Compare an insurance quote, the actual asking price and a budget before making a deposit.",
    ]
    checklist = "".join(f'<label class="check"><input type="checkbox" data-check> {esc(x)}</label>' for x in checks)
    checklist += '<label class="check" data-hybrid-item><input type="checkbox" data-check> For a Hybrid: ask about refuelling symptoms and invoices for program 20TE04. Have the dealer check current VIN eligibility.</label>'
    common = '''<div class="grid"><label>Annual mileage<input name="miles" type="number" min="0" max="200000" placeholder="Your expected miles per year"></label>
<label>Fuel price — USD per US gallon<input name="fuel" type="number" min="0.01" max="30" step="0.01" placeholder="Your local price"></label></div>
<label>Years you expect to keep the car<input name="years" type="number" min="1" max="20" placeholder="Your holding period"></label>'''
    fieldsets = []
    fields = [("price", "Out-the-door purchase price — USD", "Includes taxes and purchase fees"),
              ("mpg", "Combined fuel economy — US MPG", "Match the exact EPA version"),
              ("insurance", "Annual insurance quote — USD", "Your own quote"),
              ("maintenance", "Annual maintenance allowance — USD", "Your planning assumption"),
              ("reserve", "Annual repair reserve — USD", "A reserve, not a predicted repair bill"),
              ("resale", "Resale after your holding period — USD", "Your assumption, not our valuation")]
    for prefix, label in (("a", "Gasoline candidate"), ("b", "Hybrid candidate")):
        inputs = "".join(f'<label>{label2}<input type="number" name="{prefix}_{key}" min="0" max="2000000" step="any" placeholder="{placeholder}"></label>' for key, label2, placeholder in fields)
        fieldsets.append(f'<fieldset><legend>{label}</legend>{inputs}</fieldset>')
    body = f'''<section class="hero"><p class="eyebrow">The first MotorJury buying brief</p>
<h1>Go to the viewing with better questions.</h1><p class="lede">Build a brief for a 2019–2020 US Toyota RAV4. Check the right version, take a useful checklist, and compare a gasoline car with a Hybrid using your own budget.</p>
<span class="pill">Free · no account · no automatic buying verdict</span></section>
<form id="brief-form"><section class="card"><p class="step">1 · Identify the candidate</p><h2>Which RAV4 are you considering?</h2>
<div class="grid"><label>Model year<select name="year"><option>2019</option><option>2020</option></select></label>
<label>Powertrain<select name="powertrain"><option value="unknown">Not confirmed yet</option><option value="gasoline">Gasoline</option><option value="hybrid">Hybrid</option></select></label></div>
<p id="version-note" class="callout">Confirm the powertrain before using version-specific checks.</p>
<p>This brief covers these model years and the US market. It does not cover the plug-in RAV4 Prime. More models will follow after reader testing.</p></section>
<section class="card"><p class="step">2 · Know what needs checking</p><h2>A recall check and a repair history answer different questions.</h2>
<p>Campaign 20V-064 concerns an engine-block defect in certain 2019–2020 RAV4 gasoline and Hybrid vehicles. It can cause coolant leakage and serious engine damage, with stall or fire risks described in Toyota's notice. Ask a dealer to confirm applicability and the recorded remedy for this VIN.</p>
<p><a href="{ENGINE}">Read the manufacturer remedy notice</a>. A campaign list alone does not prove that the car is affected or repaired.</p>
<div id="hybrid-check"><h3>For a Hybrid: ask about refuelling</h3><p>Toyota program 20TE04 addresses a fuel-gauge or refuelling condition on certain RAV4 Hybrid vehicles. It is a customer support program, not the same thing as a safety recall. Ask the dealer to check the VIN, symptoms, previous work and current eligibility; do not assume a free repair from the model year.</p><p><a href="{TANK}">Read the program document</a>.</p></div>
<details><summary>What the matched public record can establish</summary>{''.join(evidence)}</details>
<p><a href="https://www.nhtsa.gov/recalls" target="_blank" rel="noopener">Check the actual VIN on NHTSA</a> · <a href="https://www.toyota.com/recall" target="_blank" rel="noopener">Check with Toyota</a></p></section>
<section class="card"><p class="step">3 · Take this to the seller</p><h2>Your viewing checklist</h2>{checklist}
<p class="note">Checking a box records your progress. It does not certify that a car is safe. Mechanical diagnosis and high-voltage checks belong with a qualified professional.</p></section>
<section class="card"><p class="step">4 · Work out your budget</p><h2>Does the Hybrid premium make sense for you?</h2>
<p>Begin with mileage, fuel price and each car's exact fuel economy for a fuel comparison. Add the remaining figures for a cash-ownership scenario. Blank costs stay unknown; an explicit zero is your assumption.</p>
{common}<div class="grid">{''.join(fieldsets)}</div><button type="submit">Calculate my scenarios</button>
<p class="note">Cash purchase in USD. Ownership scenario = purchase minus assumed resale, plus your stated years of fuel, insurance, maintenance and repair reserves. Financing interest, parking and other personal costs are outside this scenario. A reserve is money set aside, not a claim that repairs will occur. No market price or failure probability is estimated.</p>
<div id="budget-result" aria-live="polite" hidden></div></section>
<section class="card"><h2>Keep the work for your viewing</h2><p>Your saved inputs stay on this browser. A shared link contains only year and powertrain. No VIN or seller documents are requested here.</p>
<div class="actions"><button type="button" id="save-brief">Save on this browser</button><button type="button" class="secondary" id="export-brief">Download checklist</button>
<button type="button" class="secondary" id="print-brief">Print / save PDF</button><button type="button" class="secondary" id="share-brief">Copy share link</button><button type="button" class="secondary" id="clear-brief">Clear saved work</button></div>
<p id="brief-status" role="status"></p></section></form>{sources()}'''
    write("/buying-brief/", "2019–2020 RAV4 buying brief", body, f'<script type="module" src="/assets/{script_name}"></script>')
    home = '''<section class="hero"><p class="eyebrow">Know what to check before you buy</p><h1>A used car is a decision.<br>Bring better evidence.</h1>
<p class="lede">Find the documented issues, prepare questions for the seller, and budget with your own numbers. Leave with a brief you can take to the viewing.</p>
<div class="actions"><a class="button" href="/buying-brief/">Build a RAV4 buying brief</a><a class="button secondary" href="/guides/toyota-rav4-years-to-avoid/">See how the research works</a></div>
<p class="note">First complete example: 2019–2020 US RAV4 gasoline and Hybrid. Free, without an account.</p></section>
<div class="grid"><section class="card"><p class="step">A clear next step</p><h2>What should I ask before travelling to see it?</h2><p>Start with the exact version, VIN campaign check and documented repair history. Take a checklist rather than relying on a single reliability score.</p><a href="/buying-brief/">Prepare the viewing</a></section>
<section class="card"><p class="step">Your numbers, visible assumptions</p><h2>Will a Hybrid cost less for me?</h2><p>Compare actual purchase prices and fuel use. Keep unknown costs visible and see when your assumptions change the answer.</p><a href="/guides/rav4-gasoline-vs-hybrid/">Compare the decisions</a></section></div>
<section class="card"><h2>Evidence you can inspect</h2><p>Our first brief connects manufacturer campaign documents and matched US safety records to practical buying questions. Those records describe issues to investigate. They cannot establish an individual car's condition.</p><p><a href="/cars/">Public-record lookup</a> · <a href="/vin-check/">Decode a VIN</a> · <a href="/methodology/">Read the method</a></p></section>'''
    write("/", "Know what to check before buying a used car", home)
    write('/about/', 'About MotorJury', '''<section class="hero"><h1>Useful questions before a used-car viewing.</h1><p class="lede">MotorJury is being rebuilt around documented checks and practical buying tools.</p></section><article class="card"><h2>What we currently offer</h2><p>The first complete buying brief covers 2019–2020 US RAV4 gasoline and Hybrid vehicles. It combines linked primary documents, a version-specific checklist and a budget using the reader's own assumptions. It does not establish an individual vehicle's condition.</p><h2>Who is accountable</h2><p>Adir Trabelsi is the publisher. This release contains AI-assisted desk research and generated public-record tables. No road test, owner interview, qualified-mechanic review or user research is claimed unless it actually took place and is described on the relevant page.</p><h2>What is being repaired</h2><p>Automatic reliability scores and buying verdicts are suspended. Imported biographies and unreviewed guides are withheld. Some older reference routes remain accessible while their facts, image permissions and usefulness are reviewed. They should not be read as reviewed buying recommendations.</p><p><a href="/methodology/">Inspect the evidence method</a> · <a href="/editorial-policy/">Read the editorial policy</a> · <a href="/contact/">Send a correction</a></p></article>''')
    write('/about/adir-trabelsi/', 'Publisher accountability', '''<section class="hero"><h1>Publisher accountability</h1></section><article class="card"><p>Adir Trabelsi is the publisher of MotorJury. Publication responsibility does not imply personal authorship, vehicle inspection or professional mechanical review of every page.</p><p>The current brief is described as assisted desk research. Named expert reviews and firsthand experience require actual work and a visible record.</p><a href="/about/">About the site</a> · <a href="/contact/">Contact the publisher</a></article>''')
    write("/guides/rav4-gasoline-vs-hybrid/", "Used RAV4 gasoline or Hybrid: compare the actual candidates", f'''<section class="hero"><p class="eyebrow">2019–2020 US RAV4 · decision guide</p><h1>The Hybrid premium needs your numbers.</h1><p class="lede">A badge cannot decide between two used cars with different prices, histories and condition.</p></section><article class="card">
<h2>Start with the version and condition</h2><p>Toyota describes the gasoline car with an eight-speed automatic and the Hybrid with its hybrid drivetrain. Match each seller's description to the actual vehicle before applying a check or fuel figure. A concern about one powertrain should not silently become a claim about the other.</p>
<h2>Compare fuel before making an ownership claim</h2><p>Use each car's exact EPA version or a clearly stated personal assumption. Annual fuel cost is annual miles divided by US MPG, multiplied by dollars per US gallon. Buying a more efficient car may reduce fuel spending; the purchase premium, insurance, maintenance and resale assumptions still matter.</p>
<h2>Check the right documents</h2><p>The engine-block campaign includes certain gasoline and Hybrid vehicles. The refuelling support program is Hybrid-specific. Confirm both scope and current VIN status rather than treating either as a reason to reject every car of that year.</p>
<h2>Make the comparison fair</h2><p>Keep mileage, fuel price and holding period the same. Enter each actual out-the-door price and insurance quote. Keep an unknown repair reserve or resale value blank rather than treating it as free. The tool should withhold a total-cost winner until the inputs are complete.</p>
<div class="actions"><a class="button" href="/buying-brief/">Compare my candidates</a></div><p class="note">This is desk research and a transparent scenario, not a road test, appraisal or repair prediction.</p></article>{sources()}''')
    write("/methodology/", "How MotorJury uses evidence", '''<section class="hero"><h1>Records support checks.<br>They do not certify cars.</h1></section><article class="card"><h2>Match each service separately</h2><p>NHTSA complaint and recall services can use different model spellings. We resolve the service's own model list, use explicitly verified aliases where necessary, deduplicate record IDs, and distinguish a matched empty response from an unmatched, failed or incomplete lookup. Unavailable data does not become a zero.</p><h2>No predictive reliability score</h2><p>Complaint totals do not have comparable sales or usage denominators. Recall counts are not probabilities of failure. Our earlier automatic scores and BUY/AVOID labels have been suspended. Old claims based on them are being rechecked.</p><h2>Source dates</h2><p>A source check has its own recorded date and response URLs. A page rebuild is not an editorial review. Legacy records without matching evidence are labelled as needing verification.</p><h2>Budget assumptions</h2><p>The buying brief calculates a cash-purchase scenario using your inputs. It does not estimate a market price, insurance quote, repair frequency or resale value. Unknown inputs prevent a complete ownership total.</p><h2>Imported material</h2><p>Wikipedia harvesting, imported biographies and encyclopedia specification readers have been stopped. Existing catalogue identifiers remain during the URL migration; they are reference metadata, not independently verified buying evidence. New briefs use the linked primary documents.</p></article>''')
    write("/editorial-policy/", "MotorJury editorial policy", '''<section class="hero"><h1>Publish what the evidence can support.</h1></section><article class="card"><p>MotorJury is the accountable publisher. The new buying brief is assisted desk research. We do not claim vehicle testing, owner interviews or specialist review that has not happened.</p><p>Consequential claims need linked sources with the correct market, model year and version. A safety recall, service bulletin and customer support program are different records. We show scope and ask the reader to verify the actual VIN and remedy.</p><p>Publication, indexing and advertising eligibility are separate decisions. Advertising is currently paused while the rebuild is reviewed. A page excluded from search is not automatically eligible for ads.</p><p>Legacy content with unsupported score-based recommendations is held out of promotion and advertising during review. The first brief must be tested with actual buyers before the larger collection expands. No completed customer test is claimed yet.</p><p><a href="/contact/">Send a correction</a> with the page and the source that changes the answer. Material corrections change the affected brief as well as its explanation.</p></article>''')
    print("BUYING BRIEF: connected guide, comparison, budget and private saved checklist built")


if __name__ == "__main__":
    main()
