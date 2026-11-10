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

## Lean code rules (adopted 2026-11-10)

Adapted from Ponytail v5.3.3 by Dietrich Gebert (MIT licence). Rules text only: no plugin, no hooks.

Solve the whole task with the least new code. End every coding reply with one or two lines: what you skipped or did not check, and any risk the owner must know.

### Before you write
Read the task and the code it touches. List every place the change must reach: callers, tests, fixtures, config, exports. Check what the change could break: data it would destroy or expose, callers that stop working. That is scope. Extra features are not.

### The smallest complete change
Take the first option that fully works:
1. Does it need to exist? Skip features, options and flexibility nobody asked for, and name them in one line.
2. Already in this codebase (a helper, component, pattern)? Use it the way the surrounding code does.
3. Standard library or platform feature? Use it, unless the project has its own.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader understands at a glance? One line.
6. Otherwise: the minimum code that works.

- Be lazy about the solution, never about finishing it: complete every part the task needs, including the callers, tests and fixtures the change breaks.
- No abstraction, wrapper, option, config or "for later" code nobody asked for. Deletion beats addition. Keep the existing structure and conventions.
- Bug fix: grep every caller of the function first, then fix the root cause once in the shared code.
- Code you move or merge keeps its error handling and validation.
- Between options of equal size, take the one that is correct on edge cases.
- New non-trivial logic (a branch, loop, parser, money or security code) leaves one small test that would actually fail if the logic broke.
- A shortcut with a known limit gets a comment: `shortcut: <the limit>, <when to upgrade>`.

### Never cut
Validation at trust boundaries, authorisation, privacy, error handling that prevents data loss, security, accessibility, anything the owner asked for, and every step of this project's own release and verification procedure, even when the task does not mention it.

### Levels
- Payments, purchases, invoicing, accounting, legal outputs, login and personal data: build exactly what was asked; name a smaller option in one line instead of taking it.
- Everything else: the rules above.
- Never push back on or shrink the owner's request itself; these rules govern how to build, not whether.
