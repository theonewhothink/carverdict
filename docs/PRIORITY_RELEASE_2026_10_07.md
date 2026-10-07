# MotorJury priority execution — 7 October 2026

## Completed implementation

1. Account mutations now require the documented method, same-origin browser requests and bounded, valid JSON objects. Provider callbacks retain separate state / Google double-submit protection. Logout through GET is rejected. Malformed cookies are handled safely. Private responses use no-store and do not expose worker exception details.
2. Owner responses require all three explicit ratings, whole years owned and a boolean buy-again answer. Missing fields no longer become one-star votes. The first form has no preselected five-star answers. Ownership must be explicitly confirmed; buy-again is an explicit Yes/No choice. Inherited unconfirmed answers remain available to their account but are excluded from public averages until reconfirmed. A quick star prepares the overall field in the full form; it does not invent reliability, cost or purchase-intent answers.
3. Saved-car and recent-view labels are escaped, and account/garage/leaderboard links cannot execute scripts or navigate to another origin. Preference payloads reject nested prototype keys. Login has an additional IP attempt bound and password size limit.
4. An empty love leaderboard displays an honest invitation rather than an unsupported numeric ranking.
5. Three original practical guides add independent inspection-report questions, an everyday EV charging plan and tire-evidence questions. Official FTC, DOE and NHTSA guidance was checked on 7 October. No vehicle testing, specialist review or electrical assessment is claimed. Each adds a responsive diagram and copyable questions.
6. A reproducible production audit checks every indexable candidate's HTTP delivery, canonical, title, indexing directives and response headers, plus sitemap coverage and eleven public API/error-route checks. It does not infer search indexing, real crawler identity, field performance or approval.

## Acceptance evidence

The full publication build retains 15,888 catalogue entries, 1,096 marques, 13,034 photo references and 133 A–Z directory pages. The raw catalogue is unchanged. Generated checks pass for all 14,800 HTML pages (14,799 normal-page QA checks plus the intentional 404). The sitemap has 72 eligible URLs and the technical inventory has no findings. All 2,979 baseline sitemap routes remain available. All 6,500 standalone model pages retain saving and community controls. Article paragraph repetition is 8.1%.

21 Python tests and 105 Node tests passed. The nine new tests exercise actual account-store operations with isolated SQLite data, including session revocation, preference sync, one response per account/car, invalid-answer rejection, account isolation, actual IP rate limits, legacy answer exclusion and love toggle; they do not create public users or votes. Production HTTP and browser proof must be recorded after deployment, not inferred from the build.

## Remaining gates, in order

- Confirm the deployed source and public-route audit; update the protected dashboard with precise scope and remaining work.
- Finish the accessibility audit across all templates, authenticated UI and physical assistive technology. The present changes improve form labels, rating semantics and status announcements; they are not a whole-site certification.
- Continue original guide expansion: six of the twelve new-guide target are now implemented. Obtain real reader and qualified specialist feedback before claiming usefulness or expertise.
- Check the remaining tools for currency/unit assumptions and retire unsupported outputs. Keep unknown values visibly unknown.
- Replace the two unavailable image references and source the 2,854 missing photos with verified identity and rights. An exact-name Commons lookup for the unavailable Citroën Osée file returned no replacement; no substitute image was guessed.
- Verify Search Console / Bing ownership, real crawler access and measured reader demand. Sitemap inclusion is not proof of indexing; do not manufacture daily indexing requests or traffic metrics.
- Finish recovery, monitoring and billing prerequisites before enabling paid access. Social account registration, terms acceptance and licensed publishing assets remain prerequisites for actual channel operation.

The private dashboard's owner-added tasks, history and reports remain in the existing Durable Object. Deploying this release must not overwrite them with a baseline file or mark dependent tasks complete.
