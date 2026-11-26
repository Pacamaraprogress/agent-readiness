---
name: agent-readiness
description: Audit and fix how ready a website is for AI agents and AI crawlers, using Cloudflare's Agent Readiness checks (isitagentready.com, levels 0 to 5) inside Aleyda Solis's AI Search Optimization Checklist. Covers robots.txt rules per AI bot (GPTBot, ClaudeBot, OAI-SearchBot, PerplexityBot, Google-Extended and more), Content Signals, sitemaps, Link headers, Markdown for agents, llms.txt, API Catalog, MCP Server Cards, AI Catalog / ARD, Agent Skills, OAuth discovery, Web Bot Auth and the commerce protocols. Includes a dependency-free Python checker for the same 24 checks plus per-bot verdicts and priority pages. Use whenever someone asks "is my site agent ready", "run isitagentready", "can AI bots crawl my site", "robots.txt for AI", "should I block GPTBot", "content signals", "markdown for agents", "MCP server card", or wants the technical part of an AI search / GEO / AEO audit. Not for building WebMCP tools (use agent-ready) or measuring AI citations.
license: MIT
---

# agent-readiness

Helps an SEO, a developer or a site owner answer two questions about a website:

1. **Can AI agents and crawlers reach and read it?** (access, extractability)
2. **Does it describe what agents can do there?** (discovery files, auth, commerce)

The yardstick is Cloudflare's Agent Readiness scanner, because it is public, documented and widely used. The scanner is not a ranking factor and says nothing about whether AI answers cite the site. Keep that line clear in every report.

## Publish only what is real

The rule that overrides everything else in this skill. A discovery file is a promise to agents:

- An API Catalog lists APIs that exist and answer.
- An MCP Server Card describes a server that runs.
- An Agent Skills index points to skills that work.
- A commerce document describes a checkout an agent can complete.

A brochure site at level 3 is fine. A fake MCP card to reach level 4 misleads agents, breaks when they call it, and is the kind of thing that gets a site distrusted. When a check does not apply, say so in the report and move on.

## Modes

Pick the mode from the request. If unclear, ask one question.

### 1. AUDIT: "check this site"

1. **Ask for the priority pages** if the user has them: the URLs that should answer the client's most important prompts (pricing, service, location, product pages). If they don't, use the homepage plus 3 to 5 pages from the main navigation.
2. **Run the official scanner first** (it is the reference result):
   - MCP: the `scan_site` tool at `https://isitagentready.com/mcp` (`url`, optional `profile`: `all`, `content` or `apiApp`).
   - REST: `POST https://isitagentready.com/api/scan` with `{"url": "...", "format": "json"}`.
   - Use `profile: content` for a marketing site, blog or local business. Details in `references/cloudflare-checks.md`.
   - Only scan sites the user is allowed to assess; the scanner fetches the site from Cloudflare's network.
3. **Run the script** for what the scanner does not show, or when the scanner is unreachable:

   ```bash
   python3 <skill-folder>/scripts/check_site.py https://example.com \
     --page /pricing --page /locations --json --out audit-2026-11-26.json
   ```

   It needs Python 3.8+ and nothing else. It adds a verdict per AI bot (allowed, blocked, partly blocked, with RFC 9309 matching), and per priority page: status, noindex/nosnippet, canonical, H1 count, JSON-LD blocks, words in the raw HTML, a client-rendering warning, and Markdown negotiation. Its level is an estimate; when it and the scanner disagree, the scanner's result is the one to report, and the difference goes in the notes. `references/cloudflare-checks.md` lists where the two differ (WebMCP needs a browser, for example).
4. **Read the results with the site type in mind.** A local business does not need an API Catalog; a docs site should have Markdown negotiation; a shop should check its commerce answers.
5. **Write the report** in the format below.

### 2. FIX: "make this site ready" / "write the files"

Ask first, unless the answers are already in the conversation:

- **Site type:** local service, shop, SaaS marketing site, docs, publisher, API product.
- **Policy on AI use:** search, answers (ai-input) and training. Never assume; `references/bot-access-control.md` has a default table to propose when the owner has no view.
- **What exists:** public APIs, an MCP server, agent skills, OAuth, a checkout agents could use.
- **Platform and access:** CMS, CDN (Cloudflare or not, which plan), who can edit robots.txt and server config.

Then:

1. Write drafts to a staging folder (`./agent-readiness-draft/`). **Never overwrite a live or existing file**; show a diff against the current one. robots.txt in particular often carries rules someone added on purpose.
2. Start from `assets/templates/` and fill in real values only. Leave out every file that would describe something the site does not have.
3. Order the work by level: robots.txt and sitemap (level 1), AI bot rules and Content Signals (level 2), Markdown negotiation (level 3), then discovery files only where real (level 4+).
4. For each change, give the exact file content or config, where it goes, how to test it, and the check it should flip.
5. After the client deploys, re-run the scanner and the script under the same conditions and compare.

| Need | Template or guide |
|---|---|
| robots.txt with AI bot groups, sitemap and Content Signals | `assets/templates/robots.txt`, `references/discoverability.md`, `references/bot-access-control.md` |
| Markdown negotiation (Cloudflare, nginx, Express, WordPress) | `references/content-accessibility.md` |
| llms.txt (docs sites mainly) | `assets/templates/llms.txt` |
| API Catalog (`/.well-known/api-catalog`) | `assets/templates/api-catalog.json` |
| MCP Server Card | `assets/templates/mcp-server-card.json` |
| AI Catalog / ARD (`/.well-known/ai-catalog.json`, `/.well-known/ard.json`) | `assets/templates/ai-catalog.json` |
| Agent Skills index | `assets/templates/agent-skills-index.json` |
| AGENTS.md for the site's code repository | `assets/templates/AGENTS.md`, `references/agents-md.md` |
| Audit checklist to hand to a developer | `assets/checklists/audit-checklist.md` |

### 3. REFERENCE: "what is X" / "should I care about Y"

Answer from `references/`. Always say:

- **Status:** RFC, IETF draft, proposal, vendor feature or informal convention.
- **Who reads it today**, when that is documented. If no AI provider has said it uses something, say that.
- **Adoption** with its date and population (`references/adoption-stats.md`).
- **The primary source**, not a blog summary.

## Report format

```markdown
# Agent readiness: <site>, <date>

**Level <n> (<name>)** from isitagentready.com, profile <profile>. <passed>/<counted> scored checks.
Script estimate: level <n> (<same / differs because ...>).
Next level needs: <the scanner's nextLevel items, in plain words>.

## Fix list
| # | Fix | Why it matters | Check it flips | Effort | Owner |
(ordered by: access problems first, then the next level's gate, then the rest)

## AI bot access
<table from the script: bot, operator, purpose, verdict; flag bots blocked by accident
and user-triggered fetchers that may ignore robots.txt>

## Priority pages
<per page: status, indexable, facts in raw HTML, client-rendered warning, Markdown>

## Does not apply to this site
<checks left out and why, e.g. "no public API, so no API Catalog">

## What this audit does not measure
Whether AI answers cite or recommend the site, AI referral traffic, and content quality.
```

Keep the fix list to what the client can act on. Put raw JSON in a separate file.

## Where this sits in Aleyda Solis's checklist

Aleyda Solis's [AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/) (12 steps, September 2026) starts from presence: which prompts matter, whether the brand shows up, and why not. This skill covers the technical part of that work (her steps on diagnosing gaps, making priority pages retrievable and extractable, and machine-readable commercial information) and nothing more. Read `references/aleyda-checklist-map.md` before an audit that is part of a wider AI search project. Credit her and link to the checklist; do not copy its text.

## Levels at a glance

| Level | Name | Gate |
|---|---|---|
| 0 | Not Ready | fewer than 2 of robots.txt, sitemap, Link headers |
| 1 | Basic Web Presence | 2 of those 3 |
| 2 | Bot-Aware | + AI bot rules + Content Signals |
| 3 | Agent-Readable | + Markdown negotiation |
| 4 | Agent-Integrated | + one of MCP Server Card, A2A Agent Card, Agent Skills, API Catalog |
| 5 | Agent-Native | + 2 of 3: Web Bot Auth, all four level-4 items, auth metadata |

Full rules and the percentage formula: `references/cloudflare-checks.md`.

## Reference files

Read the one that matches the question; none needs to be loaded up front.

| File | Covers |
|---|---|
| `references/cloudflare-checks.md` | the 24 checks, levels, %, profiles, MCP/REST calls, changes since April 2026, script vs scanner |
| `references/aleyda-checklist-map.md` | where these checks fit in the 12-step checklist; order of work |
| `references/discoverability.md` | robots.txt (RFC 9309 matching), 25 AI bots and what blocking each one does, sitemap, Link headers, DNS-AID |
| `references/bot-access-control.md` | Content Signals and the `use` extension, Cloudflare managed robots.txt, Web Bot Auth, blocking vs throttling |
| `references/content-accessibility.md` | facts in raw HTML, Markdown negotiation (Cloudflare, nginx, Express, WordPress), Search for Agents, llms.txt, token budgets |
| `references/protocol-discovery.md` | API Catalog, MCP Server Card (spec vs scanner location), AI Catalog vs ARD, Agent Skills, A2A, OAuth, auth.md, Poppy, promoting an MCP server |
| `references/commerce-protocols.md` | x402, MPP, UCP, ACP, AP2 in short; what to tell a client |
| `references/adoption-stats.md` | Radar figures (23 Nov 2026) with caveats; status of each standard |
| `references/agents-md.md` | AGENTS.md for code repositories |

## Good habits

- **Date every number and every "the scanner does X".** Cloudflare changed the checks several times in 2026.
- **Check the live robots.txt, not the CMS copy.** CDNs (Cloudflare's managed robots.txt in particular) can add rules in front of it.
- **A robots.txt rule is not a block.** Some user-triggered fetchers say robots.txt may not apply to them; real blocking happens at the CDN or firewall.
- **Blocking a search bot removes the site from that assistant's answers.** Blocking a training bot does not. Explain the difference before the client decides.
- **WebMCP** (in-page tools for browser agents) is one of the 24 checks but needs its own build process: use the agent-ready skill ([github.com/Pacamaraprogress/agent-ready](https://github.com/Pacamaraprogress/agent-ready)).
- **Never present readiness as visibility.** A level 5 site can be absent from AI answers; a level 1 site can be cited every day.

## Script notes

- `scripts/check_site.py --help` lists every option. Useful ones: `--profile content`, `--only robotsTxt,contentSignals`, `--pages-file urls.txt`, `--no-dns`, `--fail-under 3` (exit code 1 below level 3, for CI).
- It sends GET requests only (plus DNS-over-HTTPS lookups unless `--no-dns`), identifies itself in the User-Agent, caps each response at 5 MiB, and does not run JavaScript.
- Tests: `python3 -m unittest discover -s tests` from the skill folder. They use a local test server and need no network.

## Primary sources

- [isitagentready.com](https://isitagentready.com/) and its [check list](https://isitagentready.com/llms-full.txt)
- [Introducing the Agent Readiness Score, Cloudflare, 17 Apr 2026](https://blog.cloudflare.com/agent-readiness/)
- [Cloudflare Radar, AI Insights](https://radar.cloudflare.com/ai-insights)
- [Aleyda Solis, AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/)
- [RFC 9309, Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309)
- [Content Signals](https://contentsignals.org/)
- [RFC 9727, API Catalog](https://www.rfc-editor.org/rfc/rfc9727)
- [MCP Server Cards, SEP-2127](https://modelcontextprotocol.io/seps/2127-mcp-server-cards)
