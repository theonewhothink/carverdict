# Release and commercial validation

This branch is a pilot for review. It is not an AdSense approval guarantee or evidence of demand.

## Before replacing production

- [ ] Complete the real buyer test in BUYER_TEST.md and record the decision.
- [ ] Review the independently sourced brief with a qualified mechanic; do not invent an endorsement.
- [ ] Restore access to actual Search Console and analytics. Identify valuable pages and inbound links before applying the proposed broad index exclusions or withheld guide copy.
- [ ] Approve the URL migration treatment. This build preserves all 2,979 URLs captured from the Oct 6 production sitemap, but that is not a complete inventory of every historical URL.
- [ ] Verify production mode, canonical URLs, sitemap exclusions, consent and the deployment preview through the real Cloudflare Worker. A local static preview does not verify edge routing or all production integrations.
- [ ] Complete secure AI activation and real answer evaluation as described in AI_EXPERIENCE.md. Keep guided mode available. Include observed AI token charges in the cost register.
- [ ] Verify checklist file contents and OS printing in a supported browser; in-app download completion was not exposed.
- [ ] Keep the current Cloudflare deployment ID and database snapshot for immediate rollback. After release, verify key URLs and source-check states; roll back on broken routing, false zeros, lost checklist data or invalid results.

## Advertising

`data/publication_policy.json` pauses all ad requests. Public access, indexing and advertising are separate decisions. Only exact reviewed paths may be authorised later; `noindex` is never ad approval. A deployment must not turn ads on automatically.

Before AdSense re-review, finish the reader test, review the remaining public catalogue and reference images, check image permissions and truthful authorship, confirm live privacy/consent behaviour, and examine the site as a visitor. Holding pages and noindex tags alone do not establish a valuable site. Do not resubmit merely because the build passed.

After account approval and Google-compliant consent are verified, test a small number of clearly labelled placements on reviewed pages. Keep controls, checklist questions and calculator results distinct from advertising. Check mobile usability, layout movement, task completion and actual revenue before adding placements. Never solicit clicks, buy artificial visits or reward ad interactions.

## Reader acquisition — prepared work, not sent outreach

Start with the useful output: a viewing checklist and an honest gasoline/Hybrid cost comparison. The first article should answer the exact RAV4 buyer question and link to the brief. Prepare a short demonstration showing a missing-cost result and a downloaded checklist. Share only where the publisher authorises outreach and the community permits useful contributions. Do not promise sponsorships, coverage or traffic.

Expand toward RAV4/CR-V/CX-5 only after the pilot passes, with primary records, exact versions and practical checks. Use observed queries and reader questions to choose subsequent briefs. Maintain existing useful URLs instead of generating every year and pairing. No additional model briefs are scheduled in this branch.

## Measure usefulness and profit

The new tool emits one `buying_task_complete` event per task type per page session for a calculation with usable fuel inputs, save or export. It emits no entered prices, VINs or checklist text. A preview requests neither analytics nor ads. Production measurement still requires verified consent, configured analytics and a reporting baseline; it is not proven here.

Track: people who complete a useful task, repeat use, organic entry queries, successful exports, dangerous misunderstandings, ad revenue and operating cost. Define reporting windows and consent-related measurement gaps before interpreting changes. A save is not proof that someone made a good purchase.

Maintain a real cost register: research/review hours and rates, hosting, AI token charges, tools, acquisition and maintenance. Monthly operating profit = actual ad revenue minus those costs. If page RPM is measured, revenue = monetised pageviews / 1,000 × measured page RPM. Do not mix page RPM with impression RPM or assume a rate from another site.

Current costs, revenue, acquisition rate and RPM: unknown. Start a measured trial after approval, set a spending ceiling from actual resources, and expand only when useful reader behaviour and economics support it. No revenue forecast is presented as a fact.
