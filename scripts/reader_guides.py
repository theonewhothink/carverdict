"""Original reader guides with explicit research provenance and useful next steps."""
import html
from pathlib import Path
from build_guides import parse, md
ROOT=Path(__file__).resolve().parent.parent
SLUGS=('before-a-used-car-viewing','what-car-photos-cannot-tell-you','recalls-history-and-inspections')
def main(write):
 cards=[]
 for slug in SLUGS:
  meta,body=parse((ROOT/'data/guides'/f'{slug}.md').read_text())
  text=md(body,lambda _: '')
  article=f'<section class="collection-hero compact"><p class="eyebrow">A practical reader guide · checked {meta["date"]}</p><h1>{html.escape(meta["title"])}</h1><p class="lede">{html.escape(meta["description"])}</p></section><article class="collection-story">{text}<p class="note">Published by MotorJury. AI-assisted desk research and original editorial suggestions. No vehicle test or specialist review is claimed.</p></article><section class="card"><h2>Keep exploring</h2><a href="/guides/">All reviewed reader guides →</a> · <a href="/ask/">Ask a question about this guide</a></section>'
  write('/guides/'+slug+'/',meta['title'],article)
  cards.append(f'<article class="card"><h2><a href="/guides/{slug}/">{html.escape(meta["title"])}</a></h2><p>{html.escape(meta["description"])}</p></article>')
 write('/guides/','Guides that help you take the next step','<section class="collection-hero compact"><p class="eyebrow">Read, ask, prepare</p><h1>Make your next car question a useful one.</h1><p class="lede">Practical guides for a viewing, a photo comparison or a closer look at the evidence.</p></section><div class="guide-cards">'+''.join(cards)+'</div><section class="card"><h2>Considering a US RAV4?</h2><p>Work through the version, manufacturer records, seller questions and your own costs.</p><a href="/buying-brief/">2019–2020 RAV4 buying brief →</a> · <a href="/guides/rav4-gasoline-vs-hybrid/">Gasoline and Hybrid: compare your costs</a></section><section class="card"><h2>Here for the cars?</h2><p>Follow six engineering ideas through our collection.</p><a href="/discover/">Explore the design stories →</a></section>')
