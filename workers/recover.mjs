// ---- 404 recovery -------------------------------------------------------------------
// Search Console lists three families of dead URLs the catalogue rebuilds leave behind:
// library pages whose marque slug came from a Wikidata label that has since changed
// ("audi-ag" -> "audi", "jaguar-cars" -> "jaguar"); /compare/ and /problems/ pages
// built on trim-level model slugs that canonicalisation later folded ("x5-sdrive35i" ->
// "x5"); and localised copies of pages that no longer exist. Rather than a growing list
// of hand-written rules, a 404 for an HTML path is answered by probing the obvious
// current homes, cheapest first, and 301-ing to the first that exists.
//
// What it must NOT do is climb to an ancestor. The first version ended every candidate
// list with the section index ("/cars/", "/library/", "/"), so an invented path such as
// /cars/toyota/no-such-model/ answered 200 from /cars/toyota/. That turns the site into an
// unbounded space of soft 404s: any typo, any scraped bad link, any crawler probe resolves
// to a real page. A recovery candidate now has to be a specific page that the same thing
// plausibly moved to. Everything else gets an honest 404.
const MARQUE_SUFFIX = /-(ag|se|sa|spa|srl|plc|inc|ltd|llc|gmbh|nv|bv|cars|car|auto|autos|automobile|automobiles|automotive|motor|motors|motor-company|motor-corporation|motor-co|company|corporation|corp|group|holding|holdings|industries)$/;
const LANGS = new Set(["en", "pt", "es", "fr", "de", "he"]);

export function makeRecovery(REDIRECT_MAP) {
  const REDIRECT_SLUGS = [...REDIRECT_MAP.entries()].map(([a, b]) => [
    a.replace(/^\/cars\//, "").replace(/\/$/, "").replace("/", "-"),
    b.replace(/^\/cars\//, "").replace(/\/$/, "").replace("/", "-")]);
  return function recoveryCandidates(p) {
  const out = [];
  let m;
  if ((m = /^\/library\/([^/]+)\/([^/]+)\/$/.exec(p))) {
    // Only the marque slug is allowed to have drifted; the model slug must still match.
    const [, marque, model] = m;
    const bases = new Set([marque.replace(MARQUE_SUFFIX, ""), marque.split("-")[0]]);
    bases.delete(marque);
    for (const b of bases) out.push(`/library/${b}/${model}/`);
  } else if ((m = /^\/library\/([^/]+)\/$/.exec(p))) {
    const marque = m[1];
    out.push(`/library/${marque.replace(MARQUE_SUFFIX, "")}/`, `/library/${marque.split("-")[0]}/`);
  } else if ((m = /^\/problems\/([^/]+)\/([^/]+)\/(?:(\d{4})\/)?$/.exec(p))) {
    // A /problems/ page only recovers onto the model it names, and only through a
    // recorded slug migration. No make-level or section-level fallback.
    const [, make, model, year] = m;
    const t = REDIRECT_MAP.get(`/cars/${make}/${model}/`);
    if (t) {
      const pr = t.replace("/cars/", "/problems/");
      if (year) out.push(pr + year + "/");
      out.push(pr, t + (year ? year + "/" : ""), t);
    }
    if (year) out.push(`/problems/${make}/${model}/`, `/cars/${make}/${model}/${year}/`);
    out.push(`/cars/${make}/${model}/`);
  } else if ((m = /^\/compare\/([^/]+)\/$/.exec(p))) {
    let slug = m[1];
    for (const [a, b] of REDIRECT_SLUGS) {
      if (slug === a || slug.startsWith(a + "-vs-") || slug.endsWith("-vs-" + a)) slug = slug.replace(a, b);
    }
    if (slug !== m[1]) out.push(`/compare/${slug}/`);
  } else if ((m = /^\/([a-z]{2})\/(.*)$/.exec(p)) && LANGS.has(m[1])) {
    // The localised copies are noindex; a dead one recovers onto its English original,
    // which is the page the reader wanted, and nowhere else.
    const rest = "/" + m[2];
    out.push(rest);
    for (const c of recoveryCandidates(rest)) out.push(`/${m[1]}${c}`, c);
  } else if ((m = /^\/cars\/([^/]+)\/([^/]+)\/(\d{4})\/$/.exec(p))) {
    // A dead model-year recovers onto that same nameplate's overview — the year may
    // simply have no record. An unknown nameplate recovers onto nothing.
    const t = REDIRECT_MAP.get(`/cars/${m[1]}/${m[2]}/`);
    if (t) out.push(t + m[3] + "/", t);
    out.push(`/cars/${m[1]}/${m[2]}/`);
  } else if ((m = /^\/cars\/([^/]+)\/([^/]+)\/$/.exec(p))) {
    const t = REDIRECT_MAP.get(p);
    if (t) out.push(t);
  }
  return out.filter((c, i, arr) => c !== p && arr.indexOf(c) === i);
  };
}
