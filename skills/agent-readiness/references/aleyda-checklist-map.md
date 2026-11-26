# Where the technical checks fit in Aleyda Solis's AI Search Optimization Checklist

Aleyda Solis's [AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/) (Orainti and SEOFOMO, September 2026 edition) is a 12-step process for AI search work: measure presence first, diagnose the gap, fix readiness, then report and validate. This file says where the technical checks in this skill help and where they do not. It summarises the checklist in our own words. Read her page and the linked guides for the full steps, the traps and the KPIs; credit her when you use the process with a client.

## The main point

Cloudflare's scanner measures **protocol readiness**: can an agent find, read and call what a site publishes. Aleyda's checklist starts from **observed presence**: does the brand appear, get recommended, get linked and get described correctly for the prompts that matter. A site can reach level 5 and still be missing from AI answers. A level 1 site can be cited every day.

So:

- Run the technical audit as part of a presence diagnosis, not instead of it.
- Tie each technical fix to a measured gap where you can, and say which gap.
- Report the level as a readiness fact. Never present it as an AI visibility score.

## The checklist in three layers

| Layer | Steps (our wording) | Role of this skill |
|---|---|---|
| Presence | 1. Choose the prompts and journeys to influence. 2. Measure presence before changing anything. | None. Use a prompt-sampling method. |
| Readiness | 3. Diagnose the gap. 4. Make priority pages retrievable and extractable. 5. Align entity and naming signals. 6. Build decision-support content. 7. Grow third-party sources. 8. Make commercial information machine-readable. 9. Localize by market. 10. Measure citations and clicks separately. | Main support for 3, 4 and 8; partial for 5, 9 and 10. |
| Impact | 11. Report without overclaiming. 12. Re-test and keep, change or stop each action. | Re-run the script after each change; keep the JSON reports for comparison. |

## Step by step: what the checks cover

### Step 3, diagnose the gap

The checklist asks you to tie each presence pattern to one main readiness condition and to rank fixes by severity, importance and effort. The technical checks give evidence for three of those conditions:

| Readiness condition | Evidence from this skill |
|---|---|
| Accessible | robots.txt verdict per AI bot and per URL; HTTP status; robots.txt reachable; CDN or firewall blocks (from logs, not from the script) |
| Extractable | text present in the raw HTML; noindex and nosnippet; Markdown negotiation; heading structure |
| Transactable | commerce protocols, product structured data, feeds (step 8) |

The other conditions (fresh, useful, differentiated, corroborated, credible, recognizable, consistent) are content, entity and reputation questions. The scanner does not see them.

### Step 4, priority pages retrievable and extractable

This is where the script helps most. Its rules match the checklist:

- **Audit the priority URLs first, not the whole site.** Pass them with `--page` or `--pages-file`. The pages that answer the target prompts come from steps 1 to 3.
- **Record access per AI bot.** The "AI crawler access" table shows each named bot's robots.txt verdict for each priority URL. Search bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot), user-triggered fetchers (ChatGPT-User, Claude-User, Perplexity-User) and training bots (GPTBot, ClaudeBot) are separate decisions. Blocking a search bot can keep the page out of that assistant's answers. Google-Extended is a control token, not a crawler; see `bot-access-control.md` for what it covers.
- **robots.txt is only the stated rule.** A CDN, WAF or bot-management setting can block a bot that robots.txt allows. Confirm real access from server or CDN logs, or the CDN's AI crawler report.
- **Indexable is not the same as extractable.** The script flags pages with very little text in the raw HTML and many scripts (likely client-rendered), plus noindex and nosnippet. Facts the target prompts need (prices, specs, service areas, hours, steps) belong in the HTML, not only in images, tabs that load later, PDFs or widgets.
- **Validate after the change.** Re-run the script with the same pages and compare the JSON.

### Step 5, entity and naming signals

The script counts JSON-LD blocks per page. It does not judge them. For this step, compare the page's visible copy, its structured data and the main third-party profiles against one approved fact sheet. Structured data must never say something the visible page does not.

### Step 8, commercial information machine-readable

Two separate things:

1. **Facts an answer engine reads.** Product names, prices with currency, stock, variants, plans, limits, locations, policies. They must agree across the visible page, structured data, merchant feeds and marketplace listings, with a date on anything that changes. This is the bigger lever for most shops.
2. **Protocols an agent uses to buy.** UCP, ACP, x402, MPP and AP2 (`commerce-protocols.md`). They matter once an agent can complete a purchase, and Cloudflare never scores them. Do not lead with them for a site whose product facts still disagree across surfaces.

### Step 9, localize by market

Not covered by the checks. Hreflang, local currency and local availability need their own audit. For a local-service business a "market" is a metro or service area.

### Step 10, citations and clicks

The script cannot see citations or traffic. Agent requests do leave traces: user-triggered fetchers (ChatGPT-User, Claude-User, Perplexity-User) in server logs, and AI referrals in analytics. Report citations, referrals and conversions side by side, as the checklist says.

### Step 12, the loop

Keep each run's JSON (`--json --out <date>.json`). After a fix, re-run under the same conditions and note what changed. A level going up is a completed task, not a result; the result is the presence or business signal the fix was meant to move.

## A short order of work for a technical audit inside the checklist

1. Take the priority URLs and the prompt groups they serve from the presence work (steps 1 to 3).
2. Run the official scanner on the homepage and the script on the priority URLs.
3. Fix access first: robots.txt verdicts per bot, firewall blocks, noindex, status errors.
4. Then extractability: facts in raw HTML, headings, Markdown negotiation.
5. Then the cheap protocol wins that apply to the site type: sitemap line, Content Signals, Link header.
6. Then commercial consistency (shops and SaaS), and only after that the commerce protocols.
7. Publish discovery files (API Catalog, MCP card, skills index, catalog) only for things that exist.
8. Re-run, compare, and hand the presence re-test back to the prompt-sampling work.

## Sources

- [Aleyda Solis, The AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/)
- [Aleyda Solis, A 3-layer framework to measure AI presence, readiness and business impact](https://www.aleydasolis.com/en/ai-search/a-3-layer-framework-to-measure-ai-presence-readiness-and-business-impact-redefining-metrics-for-the-ai-search-era/)
- [Aleyda Solis, E-commerce AI search citations optimization](https://www.aleydasolis.com/en/ai-search/ecommerce-ai-search-citations-optimization/)
- [Aleyda Solis, AI traffic and citations research](https://www.aleydasolis.com/en/ai-search/ai-traffic-citations-research/)
