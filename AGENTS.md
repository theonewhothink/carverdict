# MotorJury project instructions

## SEO skills

Use the installed Corey Haines skills when their task matches:
- `seo-audit`: read `.agents/skills/seo-audit/SKILL.md` for search traffic diagnosis, technical SEO, indexing, snippets, and SEO reviews.
- `site-architecture`: read `.agents/skills/site-architecture/SKILL.md` for navigation, URL hierarchy, internal links, and migration plans.
- `schema`: read `.agents/skills/schema/SKILL.md` for JSON-LD, structured data, and supported Google rich results.
- `programmatic-seo`: read `.agents/skills/programmatic-seo/SKILL.md` for data-driven pages, templates, and publishing at scale.

Read only the matching skill and supporting references needed for the task. Other skills named by upstream cross-references are not installed; do not assume they are available.

## MotorJury SEO requirements

- Read `data/publication_policy.json`, `docs/dashboard-metrics.json`, and the dated search baseline when relevant before recommending indexing or measurement changes.
- Retain the editorial indexing gates for thin or unreviewed catalogue pages. Do not mass-remove `noindex` or add ineligible pages to the sitemap to increase page counts.
- Preserve published URLs and exact-identity redirects. Unknown vehicle identities must remain 404; never redirect them to unrelated pages.
- Use source-backed facts. Label price estimates and unknown safety counts accurately.
- Treat vendor checklists as guidance. Verify changing Google requirements against current Google Search Central documentation. Do not present title lengths, word counts, H1 counts, click depths, or subdomain rules as guaranteed ranking requirements.
- Distinguish raw HTML from rendered DOM when checking schema. Confirm current Google feature eligibility and visible-content accuracy.
- Separate sitemap submission, crawl/index status, and measured traffic recovery. Date all analytics evidence and state the consent scope of GA4 figures.
- Respect the project build workflow: `build.sh` can deploy. Use preview mode or the appropriate build-only checks for validation.
