# Guided buying experience and AI activation

The homepage and brief now start with a question, useful prompts and a visible path to a saved buying brief. Recognised questions produce reviewed, source-linked guidance without a provider or account. Unknown years, multiple candidates, other markets and the RAV4 Prime do not silently become supported versions. Applying an interpreted version to the checklist requires the reader to select the visible action.

The interface labels the active mode. Guided responses are curated rules, not generated AI answers. If the same-site `/api/genius/status` reports enabled, follow-up questions can use the real streaming AI service. Answers link back to reviewed material. Errors and incomplete streams are replaced by the reviewed guide rather than left as authoritative partial advice.

## Privacy and safety

Year and powertrain are allow-listed. Budget fields and checklist items are excluded from the AI request. VIN, email, phone and currency patterns are blocked in questions in both the browser and buying-mode Worker. Pattern checks are not a perfect detector: readers are told to keep private details out. Conversation history is session memory and can be cleared; it is not automatically saved with the brief.

AI content renders through text nodes; only same-site and listed official source links become clickable. The assistant cannot clear a VIN, diagnose a car, infer failure rates, promise a free repair or extend the RAV4 research to an unsupported version. Mechanical checks remain desk research pending actual qualified review.

## Activation

The live service reported `enabled:false` on 6 October. The exact account configuration was not inspected, and real provider answers remain unverified. Do not paste a provider key into chat, source files or browser code. The publisher must configure `ANTHROPIC_API_KEY` securely in the existing Cloudflare Worker before live model answers can be verified. `GENIUS_MODEL` selects a provider-supported model; the new default is `claude-sonnet-5`. Existing provider integration is retained.

Requests use the standard streaming Messages API, a maximum of four model rounds and 2,048 output tokens per round, with bounded page context and tool results. Defaults allow three questions/hour and ten/day per visitor, 100/day for the site. `GENIUS_DAILY_CAP` can reduce that ceiling. Provider/account spending controls and real observed token charges should be set before activation. These are request caps, not a dollar budget or a claim of profitability.

Usage logging records model, mode and token counts, without question text, private form values or VINs. Measure AI cost alongside hosting and research cost when calculating actual operating contribution. Leave the useful guided mode available if model cost or answer quality does not justify AI calls.

Implementation reference: [official Claude API primer](https://platform.claude.com/docs/en/claude_api_primer), inspected 6 October 2026. A local SDK transport fixture tests streaming, grounding, private-input rejection and disabled/quota paths; it is not a real provider answer or customer test.
