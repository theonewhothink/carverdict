"""The first complete buying journey, from primary sources and user assumptions.

No external harvest, borrowed prose, pretend road test, price estimate or account
requirement. Source dates describe the stored checks, never the build date.
"""
import html
import hashlib
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")
ENGINE = "https://static.nhtsa.gov/odi/rcl/2020/RCMN-20V064-6563.pdf"
TANK = "https://static.nhtsa.gov/odi/tsbs/2021/MC-10190478-9999.pdf"
TOYOTA = "https://pressroom.toyota.com/2020-toyota-rav4-offers-a-new-trd-off-road-model-and-multimedia-enhancements/"
esc = html.escape

@lru_cache(maxsize=1)
def shell_assets():
    styles=[]
    (SITE/'assets').mkdir(parents=True,exist_ok=True)
    for name in ('buying-brief.css','catalogue.css','genius.css'):
        text=(ROOT/'assets'/name).read_text()
        filename=name.replace('.css','.'+hashlib.sha256(text.encode()).hexdigest()[:10]+'.css')
        (SITE/'assets'/filename).write_text(text)
        styles.append('<link rel="stylesheet" href="/assets/'+filename+'">')
    version=hashlib.sha256((ROOT/'assets/genius.js').read_bytes()).hexdigest()[:10]
    return ''.join(styles),'/assets/genius.js?v='+version


def shell(title, path, body, script=""):
    from collection_stories import asset_script
    script=script+asset_script()
    styles,chat_script=shell_assets()
    description="Prepare for a used-car viewing with documented checks, seller questions and a transparent ownership budget."
    if path=='/':description="Explore MotorJury's car photography and complete current catalogue. Find a marque or model, then prepare a source-backed buying brief."
    elif path.startswith('/library/'):description=title+". Browse reference photographs, search models and open the complete marque roster."
    elif path.startswith('/all-cars/'):description="Browse every distinct entry in the current MotorJury catalogue, including cars without photographs or recorded dates."
    elif path=='/discover/':description='Follow six original car design stories from manufacturer archives. Explore engine packaging, roadster simplicity and the reason behind gullwing doors.'
    elif path=='/shortlist/':description='Save cars in your browser and compare explicitly scoped design briefs, with links to the source-backed stories.'
    elif path=='/catalogue-notes/':description="What the MotorJury car collection covers, how duplicates are handled, and the sources and credits for featured photographs."
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#12685e">
<title>{esc(title)} | MotorJury</title><meta name="description" content="{esc(description,quote=True)}">
<link rel="canonical" href="{ORIGIN}{path}"><meta property="og:title" content="{esc(title,quote=True)} | MotorJury"><meta property="og:description" content="{esc(description,quote=True)}"><meta property="og:url" content="{ORIGIN}{path}"><meta property="og:type" content="website"><meta property="og:image" content="{ORIGIN}/assets/og/default.png"><link rel="icon" href="/favicon.svg" type="image/svg+xml">
{styles}</head><body>
<a class="skip" href="#content">Skip to content</a><header><div class="wrap"><a class="logo" href="/">Motor<span>Jury</span></a>
<nav aria-label="Main"><a href="/library/">Car collection</a><a href="/discover/">Discover</a><a href="/ask/">Ask AI</a><a href="/guides/">Guides</a><a href="/buying-brief/">Buying brief</a><a href="/shortlist/">Saved cars<span data-saved-count></span></a></nav></div></header>
<main id="content" data-buying-product><div class="wrap">{body}</div></main>
<footer><div class="wrap"><p>Design stories from manufacturer archives. Buying brief: 2019–2020 US RAV4. No road test or specialist endorsement is claimed.</p>
<p><a href="/methodology/">How the evidence works</a> · <a href="/editorial-policy/">Editorial policy</a> · <a href="/contact/">Send a correction</a> · <a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a> · <a href="/disclosure/">Advertising</a> · <a href="/catalogue-notes/">Catalogue &amp; photo credits</a></p></div></footer>{script}<script src="{chat_script}" defer></script></body></html>'''


def guide_widget():
    return """<section class="guide-workspace" data-buying-guide aria-label="Guided buying conversation"><div class="guide-main"><div class="guide-head"><h2>What would you like to check?</h2><span class="guide-mode" data-guide-mode>Guided mode · reviewed material</span></div><p class="note">2019–2020 US RAV4. Start with a question or choose a task.</p><form><label for="guide-question">Your car question</label><textarea class="guide-input" id="guide-question" maxlength="600" placeholder="What should I check on a 2020 RAV4 Hybrid?" required></textarea><div class="guide-controls"><button type="submit" data-guide-send>Help me prepare →</button><button type="button" class="guide-clear" data-guide-clear>Clear conversation</button></div></form><div class="guide-prompts"><button type="button" data-guide-prompt="viewing">Viewing checks</button><button type="button" data-guide-prompt="recall">Recall evidence</button><button type="button" data-guide-prompt="budget">Compare costs</button></div><div data-guide-thread role="log" aria-label="Buying conversation" aria-live="polite" aria-relevant="additions"></div><details><summary>How answers work · keep private details out</summary><p class="note">Guided answers use reviewed material. When AI is available, your question and selected year/powertrain go to our AI provider. Budget inputs and saved checklist items are excluded. Do not enter a VIN, contact details or private documents.</p></details></div><aside class="guide-side"><span class="guide-source-label">Your brief</span><h3>For the actual viewing</h3><p data-guide-context>Year not confirmed · Powertrain not confirmed · US RAV4</p><ol class="guide-progress"><li>Match the exact version</li><li>Inspect the documented concern</li><li>Request the right evidence</li><li>Take a checklist and a budget</li></ol><p class="note">Answers show their sources and leave room for what is still unknown.</p><a href="/methodology/">Inspect the method</a></aside></section>"""


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
    for name in ("buying-brief.css", "buying-brief.mjs", "buying-budget.mjs", "buying-guide-core.mjs", "buying-guide.mjs", "catalogue.css"):
        (SITE / "assets").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "assets" / name, SITE / "assets" / name)
    budget = (ROOT / 'assets' / 'buying-budget.mjs').read_text()
    budget_name = 'buying-budget.' + hashlib.sha256(budget.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / budget_name).write_text(budget)
    script = (ROOT / 'assets' / 'buying-brief.mjs').read_text().replace('./buying-budget.mjs','./'+budget_name)
    script_name = 'buying-brief.' + hashlib.sha256(script.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / script_name).write_text(script)
    core = (ROOT / 'assets' / 'buying-guide-core.mjs').read_text()
    core_name = 'buying-guide-core.' + hashlib.sha256(core.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / core_name).write_text(core)
    guide = (ROOT / 'assets' / 'buying-guide.mjs').read_text().replace('./buying-guide-core.mjs', './'+core_name)
    guide_name = 'buying-guide.' + hashlib.sha256(guide.encode()).hexdigest()[:10] + '.mjs'
    (SITE / 'assets' / guide_name).write_text(guide)
    guide_script = f'<script type="module" src="/assets/{guide_name}"></script>'
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
'''
    fields = [("price", "Out-the-door purchase price — USD", "Includes taxes and purchase fees"),
              ("mpg", "Combined fuel economy — US MPG", "Match the exact EPA version"),
              ("insurance", "Annual insurance quote — USD", "Your own quote"),
              ("maintenance", "Annual maintenance allowance — USD", "Your planning assumption"),
              ("reserve", "Annual repair reserve — USD", "A reserve, not a predicted repair bill"),
              ("resale", "Resale after your holding period — USD", "Your assumption, not our valuation")]
    advanced = []
    for prefix,label in (("a","Gasoline candidate"),("b","Hybrid candidate")):
        advanced.append('<fieldset><legend>'+label+'</legend>'+''.join(f'<label>{label2}<input type="number" name="{prefix}_{key}" min="0" max="2000000" step="any" placeholder="{placeholder}"></label>' for key,label2,placeholder in fields if key!='mpg')+'</fieldset>')
    fuel_inputs=''.join(f'<fieldset><legend>{label}</legend><label>Combined fuel economy — US MPG<input type="number" name="{prefix}_mpg" min="1" max="200" step="any" placeholder="Exact EPA version or your assumption"></label></fieldset>' for prefix,label in (("a","Gasoline candidate"),("b","Hybrid candidate")))
    body = f'''<div class="buying-flow"><section class="brief-hero"><p class="eyebrow">2019–2020 US RAV4 · free · no account</p>
<h1>Go to the viewing prepared.</h1><p class="lede">Ask better questions. Keep your checklist. Compare your own costs.</p></section>
{guide_widget()}<nav class="brief-nav" aria-label="Buying brief steps"><a href="#identify">1 · Version</a><a href="#checks">2 · Evidence</a><a href="#checklist">3 · Checklist</a><a href="#budget">4 · Budget</a></nav><form id="brief-form"><details class="card brief-step" id="identify" open><summary><span class="step">01</span> Choose your RAV4</summary>
<div class="grid"><label>Model year<select name="year"><option value="">Not confirmed</option><option>2019</option><option>2020</option></select></label>
<label>Powertrain<select name="powertrain"><option value="unknown">Not confirmed yet</option><option value="gasoline">Gasoline</option><option value="hybrid">Hybrid</option></select></label></div>
<p id="version-note" class="callout">Confirm the powertrain before using version-specific checks.</p>
<p>This brief covers these model years and the US market. It does not cover the plug-in RAV4 Prime. More reviewed briefs will follow after reader testing. <a href="/library/">Browse the wider car collection</a>.</p></details>
<details class="card brief-step" id="checks"><summary><span class="step">02</span> Inspect the evidence</summary><h2>A recall check and a repair history answer different questions.</h2>
<p>Campaign 20V-064 concerns an engine-block defect in certain 2019–2020 RAV4 gasoline and Hybrid vehicles. It can cause coolant leakage and serious engine damage, with stall or fire risks described in Toyota's notice. Ask a dealer to confirm applicability and the recorded remedy for this VIN.</p>
<p><a href="{ENGINE}">Read the manufacturer remedy notice</a>. A campaign list alone does not prove that the car is affected or repaired.</p>
<div id="hybrid-check"><h3>For a Hybrid: ask about refuelling</h3><p>Toyota program 20TE04 addresses a fuel-gauge or refuelling condition on certain RAV4 Hybrid vehicles. It is a customer support program, not the same thing as a safety recall. Ask the dealer to check the VIN, symptoms, previous work and current eligibility; do not assume a free repair from the model year.</p><p><a href="{TANK}">Read the program document</a>.</p></div>
<details><summary>What the matched public record can establish</summary>{''.join(evidence)}</details>
<p><a href="https://www.nhtsa.gov/recalls" target="_blank" rel="noopener">Check the actual VIN on NHTSA</a> · <a href="https://www.toyota.com/recall" target="_blank" rel="noopener">Check with Toyota</a></p></details>
<details class="card brief-step" id="checklist"><summary><span class="step">03</span> Your viewing checklist</summary>{checklist}
<p class="note">Checking a box records your progress. It does not certify that a car is safe. Mechanical diagnosis and high-voltage checks belong with a qualified professional.</p></details>
<details class="card brief-step" id="budget"><summary><span class="step">04</span> Compare your costs</summary><h2>Start with fuel. Add ownership costs when ready.</h2>
<p>Begin with mileage, fuel price and each car's exact fuel economy for a fuel comparison. Add the remaining figures for a cash-ownership scenario. Blank costs stay unknown; an explicit zero is your assumption.</p>
{common}<div class="grid">{fuel_inputs}</div><details class="budget-more"><summary>Add purchase, insurance and other ownership costs</summary><label>Years you expect to keep the car<input name="years" type="number" min="1" max="20" placeholder="Your holding period"></label><div class="grid">{''.join(advanced)}</div></details><button type="submit">Calculate my scenarios</button>
<p class="note">Cash purchase in USD. Ownership scenario = purchase minus assumed resale, plus your stated years of fuel, insurance, maintenance and repair reserves. Financing interest, parking and other personal costs are outside this scenario. A reserve is money set aside, not a claim that repairs will occur. No market price or failure probability is estimated.</p>
<div id="budget-result" aria-live="polite" hidden></div></details>
<section class="card keep-brief"><h2>Keep your brief.</h2><p>Your saved inputs stay on this browser. A shared link contains only year and powertrain. No VIN or seller documents are requested here.</p>
<div class="actions"><button type="button" id="save-brief">Save on this browser</button><button type="button" class="secondary" id="export-brief">Download checklist</button>
</div><details><summary>Print, share or clear your brief</summary><div class="actions"><button type="button" class="secondary" id="print-brief">Print / save PDF</button><button type="button" class="secondary" id="share-brief">Copy share link</button><button type="button" class="secondary" id="clear-brief">Clear saved work</button></div></details>
<p id="brief-status" role="status"></p></section></form><details class="card"><summary>Sources and reference photographs</summary>{sources()}PHOTO_STRIP</details><noscript><p>The checklist and sources work without JavaScript. Calculation and browser saving require JavaScript.</p></noscript></div>'''
    from catalogue_experience import main as build_collection,record_photo,image
    front=record_photo('Toyota','RAV4')
    rear_name='2019 Toyota RAV4 LE 2.5L rear 4.14.19.jpg'
    rear=f'<figure class="record-photo">{image(rear_name,"2019 Toyota RAV4 LE, rear")}<figcaption>2019 RAV4 LE, a reference example. Photo: <a href="https://commons.wikimedia.org/wiki/File:{rear_name.replace(" ","_")}">Kevauto</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Displayed in a cropped frame.</figcaption></figure>'
    body=body.replace('PHOTO_STRIP','<div class="viewing-photos">'+front+rear+'</div>')
    write("/buying-brief/", "2019–2020 RAV4 buying brief", body, f'<script type="module" src="/assets/{script_name}"></script>'+guide_script)
    write('/about/', 'About MotorJury', '''<section class="hero"><h1>Useful questions before a used-car viewing.</h1><p class="lede">Explore how cars were designed, and prepare better questions before a used-car viewing.</p></section><article class="card"><h2>What we currently offer</h2><p>The first complete buying brief covers 2019–2020 US RAV4 gasoline and Hybrid vehicles. It combines linked primary documents, a version-specific checklist and a budget using the reader's own assumptions. It does not establish an individual vehicle's condition.</p><p>The collection also includes six original design stories researched from manufacturer archives. Photographs are labelled when they show a different generation. Save cars privately in your browser and compare the historical briefs.</p><h2>Who is accountable</h2><p>Adir Trabelsi is the publisher. This release contains AI-assisted desk research and generated public-record tables. No road test, owner interview, qualified-mechanic review or user research is claimed unless it actually took place and is described on the relevant page.</p><h2>What is being repaired</h2><p>Automatic reliability scores and buying verdicts are suspended. Imported biographies and unreviewed guides are withheld. Some older reference routes remain accessible while their facts, image permissions and usefulness are reviewed. They should not be read as reviewed buying recommendations.</p><p><a href="/methodology/">Inspect the evidence method</a> · <a href="/editorial-policy/">Read the editorial policy</a> · <a href="/contact/">Send a correction</a></p></article>''')
    write('/about/adir-trabelsi/', 'Publisher accountability', '''<section class="hero"><h1>Publisher accountability</h1></section><article class="card"><p>Adir Trabelsi is the publisher of MotorJury. Publication responsibility does not imply personal authorship, vehicle inspection or professional mechanical review of every page.</p><p>The current brief is described as assisted desk research. Named expert reviews and firsthand experience require actual work and a visible record.</p><a href="/about/">About the site</a> · <a href="/contact/">Contact the publisher</a></article>''')
    write("/guides/rav4-gasoline-vs-hybrid/", "Used RAV4 gasoline or Hybrid: compare the actual candidates", f'''<section class="hero"><p class="eyebrow">2019–2020 US RAV4 · decision guide</p><h1>The Hybrid premium needs your numbers.</h1><p class="lede">A badge cannot decide between two used cars with different prices, histories and condition.</p></section><article class="card">
<h2>Start with the version and condition</h2><p>Toyota describes the gasoline car with an eight-speed automatic and the Hybrid with its hybrid drivetrain. Match each seller's description to the actual vehicle before applying a check or fuel figure. A concern about one powertrain should not silently become a claim about the other.</p>
<h2>Compare fuel before making an ownership claim</h2><p>Use each car's exact EPA version or a clearly stated personal assumption. Annual fuel cost is annual miles divided by US MPG, multiplied by dollars per US gallon. Buying a more efficient car may reduce fuel spending; the purchase premium, insurance, maintenance and resale assumptions still matter.</p>
<h2>Check the right documents</h2><p>The engine-block campaign includes certain gasoline and Hybrid vehicles. The refuelling support program is Hybrid-specific. Confirm both scope and current VIN status rather than treating either as a reason to reject every car of that year.</p>
<h2>Make the comparison fair</h2><p>Keep mileage, fuel price and holding period the same. Enter each actual out-the-door price and insurance quote. Keep an unknown repair reserve or resale value blank rather than treating it as free. The tool should withhold a total-cost winner until the inputs are complete.</p>
<div class="actions"><a class="button" href="/buying-brief/">Compare my candidates</a></div><p class="note">This is desk research and a transparent scenario, not a road test, appraisal or repair prediction.</p></article>{sources()}''')
    write("/methodology/", "How MotorJury uses evidence", '''<section class="hero"><h1>Records support checks.<br>They do not certify cars.</h1></section><article class="card"><h2>Match each service separately</h2><p>NHTSA complaint and recall services can use different model spellings. We resolve the service's own model list, use explicitly verified aliases where necessary, deduplicate record IDs, and distinguish a matched empty response from an unmatched, failed or incomplete lookup. Unavailable data does not become a zero.</p><h2>No predictive reliability score</h2><p>Complaint totals do not have comparable sales or usage denominators. Recall counts are not probabilities of failure. Our earlier automatic scores and BUY/AVOID labels have been suspended. Old claims based on them are being rechecked.</p><h2>Source dates</h2><p>A source check has its own recorded date and response URLs. A page rebuild is not an editorial review. Legacy records without matching evidence are labelled as needing verification.</p><h2>Budget assumptions</h2><p>The buying brief calculates a cash-purchase scenario using your inputs. It does not estimate a market price, insurance quote, repair frequency or resale value. Unknown inputs prevent a complete ownership total.</p><h2>Historical profiles</h2><p>Design stories use manufacturer archives with linked sources and explicit version scope. Manufacturer accounts describe their own projects; they do not independently establish ownership quality. Our comparisons are editorial interpretations, not road-test findings. A later-generation photograph does not inherit an earlier car’s specifications.</p><h2>Imported material</h2><p>Imported biographies and unverified specification readers have been stopped. Existing catalogue identifiers remain during the URL migration; they are reference metadata, not independently verified buying evidence. New briefs use the linked primary documents.</p></article>''')
    write("/editorial-policy/", "MotorJury editorial policy", '''<section class="hero"><h1>Publish what the evidence can support.</h1></section><article class="card"><p>MotorJury is the accountable publisher. The new buying brief is assisted desk research. We do not claim vehicle testing, owner interviews or specialist review that has not happened.</p><p>Consequential claims need linked sources with the correct market, model year and version. A safety recall, service bulletin and customer support program are different records. We show scope and ask the reader to verify the actual VIN and remedy.</p><p>Publication, indexing and advertising eligibility are separate decisions. Advertising is currently paused while the rebuild is reviewed. A page excluded from search is not automatically eligible for ads.</p><p>Legacy content with unsupported score-based recommendations is held out of promotion and advertising during review. Further buying briefs require actual buyer testing of the pilot. Historical design stories have separate, explicit version and source labels. No completed customer test is claimed yet.</p><p><a href="/contact/">Send a correction</a> with the page and the source that changes the answer. Material corrections change the affected brief as well as its explanation.</p></article>''')
    write('/privacy/','Privacy and your choices','''<section class="collection-hero compact"><h1>Your work stays yours.</h1><p class="lede">Read without an account. Save a list in your browser. Choose whether to allow Google Analytics.</p></section><article class="card"><h2>Saved cars and viewing briefs</h2><p>The shortlist and saved buying brief use this browser’s storage. The saved brief can include your budget inputs and checked questions. Other people using the same browser may see them. Clear the relevant saved list or brief to remove it. Clearing browser data also removes saved work. Shared buying-brief links contain year and powertrain, not your budget or checked items.</p><h2>Optional analytics</h2><p>The Google Analytics library loads only after you choose Allow analytics. Necessary only keeps it unloaded. Privacy choices in the footer lets you change your decision. Analytics can measure pages and completed task types; our task events exclude entered budget figures, VINs, saved car names and checklist text. Google may use analytics cookies after opt-in. Advertising consent stays denied in this release.</p><h2>Questions and AI</h2><p>The collection discovery guide and the buying guide’s fallback work in your browser. When the interface reports AI available, submitting an AI question sends the question, recent conversation and relevant public references to MotorJury’s service and either Cloudflare Workers AI or Anthropic, depending on the active provider. The buying mode also sends the selected year and powertrain. Saved checklist items and budget fields are excluded. Recent chat history is saved in this tab’s session storage so it can follow you between pages. New chat clears that conversation; closing the tab or clearing browser data removes it. Keep VINs, contact details and private documents out of AI questions. The provider processes requests under its applicable terms; this page does not promise a provider retention period.</p><h2>Accounts and public feedback</h2><p>Account features use an email address, display name, credentials or supported sign-in identity, preferences and submitted feedback. Signing in and submitting an owner survey are separate from the browser-only shortlist. Hosting, security and rate limits use technical request information to deliver the service and prevent abuse.</p><h2>VIN checks and photographs</h2><p>A VIN entered in the VIN tool is submitted to the public NHTSA decoder through MotorJury’s service. This is separate from the AI guide. Reference photographs load from Wikimedia services, which receive normal connection information when serving the image. Catalogue images request no-referrer handling.</p><h2>Advertising and requests</h2><p>Ads are paused. The analytics choice is not a certified advertising consent platform. Advertising would require account approval, an appropriate advertising consent solution and updated disclosures before activation.</p><p>For questions about account data, privacy requests or the publisher’s service providers, use the <a href="/contact/">contact page</a>. <a href="/disclosure/">Read the advertising disclosure</a>.</p></article>''')
    write('/disclosure/','Advertising and editorial disclosure','''<section class="collection-hero compact"><h1>Know what supports the page.</h1></section><article class="card"><h2>Advertising is paused</h2><p>This release does not request Google ads. AdSense approval and advertising income have not been established by a successful site build. Ads may be introduced only after the account, consent system and individual page placements are ready.</p><h2>How the content is made</h2><p>The buying pilot and historical design stories are AI-assisted desk research with linked primary sources. They do not represent a road test, owner interview or mechanic review. Manufacturer archives describe their own projects and have that limitation. The publisher is Adir Trabelsi; <a href="/about/">read about MotorJury</a>.</p><h2>Future commercial relationships</h2><p>Any sponsored content or affiliate relationship must be disclosed on the affected page and near the relevant link. Advertising must be recognisable and kept distinct from navigation, source evidence, checklist questions and calculator outputs. Paying for exposure must not change research conclusions or create an unsupported buying verdict.</p><p><a href="/editorial-policy/">Editorial policy</a> · <a href="/privacy/">Privacy choices</a> · <a href="/contact/">Contact the publisher</a></p></article>''')
    build_collection(write)
    from reader_guides import main as build_reader_guides
    build_reader_guides(write)
    print("BUYING BRIEF: connected guide, comparison, budget and private saved checklist built")


if __name__ == "__main__":
    main()
