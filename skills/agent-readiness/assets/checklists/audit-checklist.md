# Agent readiness audit checklist

A working list for one site. Run the official scanner and `scripts/check_site.py` first; most boxes can be ticked from their output. Mark each item **pass**, **fail**, **not applicable** (with the reason) or **not checked**.

Site: ______________________  Date: __________  Scanner level: ___  Script estimate: ___

## 0. Before you start

- [ ] Site type agreed (local service, shop, SaaS, docs, publisher, API product)
- [ ] Owner's policy on AI search, AI answers and training written down
- [ ] Priority pages listed (the URLs that should answer the most important prompts)
- [ ] Permission to scan the site; CDN in front of it known (Cloudflare or other, plan)

## 1. Access (fix these first)

- [ ] `/robots.txt` returns 200 as plain text (not an HTML error page)
- [ ] No leftover `Disallow: /` under `User-agent: *`
- [ ] Each AI bot's verdict matches the owner's policy (script's bot table); no search bot blocked by accident
- [ ] Named bot groups repeat the private-path `Disallow` lines
- [ ] CDN, WAF or bot-protection settings do not block bots that robots.txt allows (check CDN reports or server logs, not a faked User-Agent)
- [ ] Priority pages return 200, are not `noindex`, and carry no `nosnippet` or `max-snippet:0` unless intended
- [ ] Canonicals on priority pages point to themselves or the intended URL

## 2. Level 1: basic web presence

- [ ] `Sitemap:` line in robots.txt, or a valid `/sitemap.xml`
- [ ] Sitemap lists the priority pages and no redirected or dead URLs
- [ ] `Link` header on the homepage with an agent-useful relation (`api-catalog`, `service-desc`, `service-doc` or `describedby`), where one makes sense

## 3. Level 2: bot-aware

- [ ] AI bot rules pass the scanner (`robotsTxtAiRules`)
- [ ] `Content-Signal` line states `search`, `ai-input` and `ai-train` as the owner decided
- [ ] On Cloudflare: the live robots.txt checked for the managed block in front of the site's own rules, and the two agree

## 4. Level 3: agent-readable

- [ ] `Accept: text/markdown` on a priority page returns `Content-Type: text/markdown`
- [ ] Browsers still get HTML; both responses send `Vary: Accept`
- [ ] The Markdown says what the HTML says (spot-check two pages; no menus or cookie text dumped in)
- [ ] Markdown responses carry the same `Content-Signal` policy as robots.txt
- [ ] Key facts of each priority page (prices, specs, areas, hours, steps) are in the raw HTML, not only after JavaScript runs or inside images, PDFs or widgets
- [ ] One `<h1>` per priority page; headings say what each section answers

## 5. Level 4 and 5: only for things that exist

Mark **not applicable** when the site has no such thing. Do not publish a file to pass a check.

- [ ] Public API: `/.well-known/api-catalog` (RFC 9727 linkset) points to a working OpenAPI and docs
- [ ] Remote MCP server: card at `<server address>/server-card` and at `/.well-known/mcp/server-card.json`, identical; server answers `initialize`, `tools/list` and a `tools/call` from outside
- [ ] Catalog: `/.well-known/ai-catalog.json` (same file at `/.well-known/ard.json`) lists the real cards, with `displayName` on each entry
- [ ] Agent skills: `/.well-known/agent-skills/index.json` (v0.2.0) with digests that match the files
- [ ] A2A agent: `/.well-known/agent-card.json` with name, version, description, interfaces, capabilities and skills
- [ ] Auth for agents: OAuth metadata (`/.well-known/oauth-authorization-server`), protected resource metadata, and `WWW-Authenticate` with `resource_metadata` on 401s
- [ ] Web Bot Auth key directory: only if the client runs its own bot or agent

## 6. Informational and commerce (no effect on the level)

- [ ] Search for Agents: considered for large docs or knowledge sites only
- [ ] DNS-AID records: only with DNSSEC and a real agent endpoint
- [ ] Commerce (x402, MPP, UCP, ACP, AP2): through the shop platform or payment provider, and only where an agent can complete the purchase
- [ ] llms.txt: published only where it will be maintained (docs sites mainly); not presented as a ranking factor

## 7. Hygiene

- [ ] Nothing private under `/.well-known/` (no `.env`, keys, internal hosts, per-user data)
- [ ] Every discovery file served with the right media type and reachable without cookies
- [ ] AGENTS.md in the site's code repository, if the client's developers use coding agents

## 8. Report

- [ ] Scanner JSON and script JSON saved with the date
- [ ] Fix list ordered: access problems, then the next level's gate, then the rest
- [ ] "Does not apply" section explains each skipped item
- [ ] Report says what it does not measure: AI citations, AI referrals, content quality
- [ ] Re-test date set for after the fixes go live
