# Cloudflare's Agent Readiness checks

Cloudflare's scanner at [isitagentready.com](https://isitagentready.com/) gives a site a level from 0 to 5 and a percentage. It is the most widely used public yardstick for this field, so audits in this skill use its check IDs and level rules. Everything below was checked against the live scanner, its `llms-full.txt` and its API on 26 Nov 2026. The scanner changes often; re-check before quoting a detail to a client.

Contents: where it runs · how to call it · the 24 checks · levels · the percentage · profiles · what changed since April 2026 · known gaps and conflicts · how `scripts/check_site.py` compares · sources.

## Where the same checks run

- **isitagentready.com**, the public page. It also offers the scan as an MCP server and as a WebMCP tool on its own page.
- **URL Scanner**, "Agent Readiness" tab, in the dashboard and through the URL Scanner API (since 12 May 2026).
- **Cloudflare dashboard → Agent Readiness** (since 6 Aug 2026). "Diagnostics" groups the same checks as Quick wins, Technical groundwork, Advanced integration and Commerce, shows the evidence for each, and has "Set up in Cloudflare" buttons for some fixes. The same area has an AEO tab that measures citations and mentions in Claude and GPT answers.
- **AI Crawl Control → "Check Agent Readiness"** card.

The dashboard features need the site to be on Cloudflare. The public scanner works for any site.

## How to call it

**MCP (preferred when the client supports remote MCP).** Streamable HTTP at `https://isitagentready.com/mcp`, one tool:

```
scan_site
  url            required, the page or site to scan
  profile        optional: all | content | apiApp
  enabledChecks  optional: list of check IDs; overrides profile
```

**REST.** `POST https://isitagentready.com/api/scan` with a JSON body:

```json
{"url": "https://example.com", "format": "json"}
```

- `format: "agent"` returns Markdown: a `Score: N/5 (Level name)` line, then one short fix per failing scored check, each with a link to a fix SKILL.md.
- `enabledChecks` takes check IDs. An unknown ID returns HTTP 400 (for example `llmsTxt`).
- Without `enabledChecks` the API runs all 24 checks, including the two the web page leaves off by default (A2A and AP2).

**JSON response (camelCase, as the live API returns it):** `url`, `targetUrl`, `scannedAt`, `level`, `levelName`, `checks`, `nextLevel`, `isCommerce`, `commerceSignals`.

- `checks` is `{category: {checkId: result}}`. The categories are `discoverability`, `contentAccessibility`, `botAccessControl`, `discovery` and `commerce`.
- Each result has `status` (`pass`, `fail`, `neutral` or `unableToCheck`), `message`, optional `details`, an `evidence` trail of the requests made, and `durationMs`.
- `nextLevel` lists what the next level needs, with a fix prompt and a `skillUrl` for each item.
- The scanner's `llms-full.txt` still documents snake_case keys (`level_name`, `next_level`). The live API does not return them.

Send the scan only for sites you are allowed to assess. The scanner fetches the site from Cloudflare's network.

## The 24 checks

Page checks use the URL you give. Site-wide checks use its origin.

| Category | Check ID | Passes when | Counts toward |
|---|---|---|---|
| Discoverability | `robotsTxt` | `/robots.txt` returns 200, `text/plain`, with at least one `User-agent` line | % and levels |
| Discoverability | `sitemap` | `/sitemap.xml` is valid XML, or robots.txt has a `Sitemap:` line | % and levels |
| Discoverability | `linkHeaders` | The homepage sends an RFC 8288 `Link` header with an agent-useful relation: `service-desc`, `service-doc`, `describedby`, `api-catalog`, or `alternate` to a Markdown version | % and levels |
| Discoverability | `dnsAid` | DNSSEC-validated ServiceMode SVCB or HTTPS records at `_index._agents.<host>`, `_a2a._agents.<host>` or `_mcp._agents.<host>` (looked up over DNS-over-HTTPS) | % |
| Content Accessibility | `markdownNegotiation` | A GET with `Accept: text/markdown` returns `Content-Type: text/markdown` | % and level 3 |
| Content Accessibility | `searchForAgents` | `GET /.well-known/search?q=...` returns 2xx `text/markdown` search results (an `Accept-Query` header or a `# Search results for:` heading) | informational |
| Bot Access Control | `robotsTxtAiRules` | robots.txt has groups for known AI bots **or wildcard rules that apply to every crawler**. A file with only `User-agent: *` rules passes. | % and level 2 |
| Bot Access Control | `contentSignals` | robots.txt has a `Content-Signal:` line with `ai-train`, `search` or `ai-input` | % and level 2 |
| Bot Access Control | `webBotAuth` | `/.well-known/http-message-signatures-directory` holds a valid JWKS. Missing gives `neutral`. | informational; a level 5 option |
| Discovery | `apiCatalog` | `/.well-known/api-catalog` returns `application/linkset+json` with a `linkset` array (RFC 9727) | % and a level 4 option |
| Discovery | `oauthDiscovery` | `/.well-known/openid-configuration` or `/.well-known/oauth-authorization-server` has valid metadata | informational; a level 5 option |
| Discovery | `oauthProtectedResource` | `/.well-known/oauth-protected-resource` has `resource` and `authorization_servers` (RFC 9728) | informational; a level 5 option |
| Discovery | `authMd` | `/auth.md` exists, protected resource metadata can be found, and the authorization server metadata has an `agent_auth` block | informational; a level 5 option |
| Discovery | `mcpServerCard` | A card at `/.well-known/mcp/server-card.json`, `/.well-known/mcp/server-cards.json` or `/.well-known/mcp.json` with `serverInfo.name` or a flat `name` | % and a level 4 option |
| Discovery | `a2aAgentCard` | `/.well-known/agent-card.json` with `name`, `version` and `supportedInterfaces`. Off by default on the web page. | a level 4 option |
| Discovery | `agentSkills` | `/.well-known/agent-skills/index.json` with a valid `skills` array (discovery v0.2.0); the legacy `/.well-known/skills/index.json` also passes | % and a level 4 option |
| Discovery | `webMcp` | The page, loaded in a browser, registers tools through `document.modelContext.registerTool()` or declares a `<form toolname tooldescription>` | % |
| Discovery | `ard` | A catalog found through a robots.txt `Agentmap:` line, `<link rel="ai-catalog">`, `/.well-known/ai-catalog.json` or DNS, with `specVersion` and at least one valid entry | % |
| Discovery | `personalAgentProtocol` | `/.well-known/poppy.json` with organization and domain (the scanner says draft 0.1; the spec is now 1.0) | informational |
| Commerce | `x402` | `/`, `/api` or `/api/v1` answers HTTP 402 with x402 payment details | never in % |
| Commerce | `mpp` | `/openapi.json` marks payable operations with `x-payment-info` | never in % |
| Commerce | `ucp` | `/.well-known/ucp` has a protocol version and services | never in % |
| Commerce | `acp` | `/.well-known/acp.json` has `protocol.name` "acp", a version, `api_base_url`, transports and `capabilities.services` | never in % |
| Commerce | `ap2` | The A2A agent card declares an AP2 extension with a role. No toggle on the web page. | never in % |

Commerce checks come back `neutral` ("not a commerce site") when the scanner sees no commerce signals. See `commerce-protocols.md`.

## Levels

| Level | Name | Needs |
|---|---|---|
| 0 | Not Ready | fewer than 2 of: `robotsTxt`, `sitemap`, `linkHeaders` |
| 1 | Basic Web Presence | 2 of those 3 |
| 2 | Bot-Aware | level 1 + `robotsTxtAiRules` + `contentSignals` |
| 3 | Agent-Readable | level 2 + `markdownNegotiation` |
| 4 | Agent-Integrated | level 3 + 1 of: `mcpServerCard`, `a2aAgentCard`, `agentSkills`, `apiCatalog` |
| 5 | Agent-Native | level 4 + 2 of these 3: `webBotAuth`; all four level 4 checks; auth metadata (`oauthDiscovery`, `oauthProtectedResource` or `authMd`) |

What this means in practice:

- **Most content sites can reach level 3** with three edits: a sitemap line in robots.txt, a Content Signals line, and Markdown negotiation.
- **Level 4 needs something an agent can call or install**: an API with a catalog, an MCP server, an A2A agent, or published agent skills. A brochure site has none of these, and a fake one to reach level 4 is worse than staying at 3 (see "Publish only what is real" in SKILL.md).
- **Level 5 is for API and agent products** that also run auth for agents.
- **The level says nothing about whether AI answers cite or recommend the site.** That is measured with prompts, not with this scanner. See `aleyda-checklist-map.md`.

## The percentage

The scanner's page works this out in the browser:

- Category % = passed ÷ counted checks in that category. Overall % = passed ÷ counted across the four non-commerce categories. Every check weighs the same.
- Not counted: the informational checks (`searchForAgents`, `personalAgentProtocol`, `oauthDiscovery`, `oauthProtectedResource`, `authMd`, and `webBotAuth` when neutral), any `neutral` result, the commerce category, and checks you turned off.
- Gauge colours: 90 and above good, 50 and above average, below 50 poor.

The level is the better number to report. The percentage moves when checks are added or reclassified, which happened several times in 2026.

## Profiles

| Profile | Runs |
|---|---|
| `all` | every check except A2A and AP2 (the API runs those too when `enabledChecks` is empty) |
| `content` | `robotsTxt`, `sitemap`, `linkHeaders`, `dnsAid`, `markdownNegotiation`, `searchForAgents`, `robotsTxtAiRules`, `contentSignals` |
| `apiApp` | everything except commerce and A2A |

Use `content` for a marketing site, a blog or a local business, so the report is not padded with API checks that do not apply.

## What changed since the April 2026 launch

1. Commerce moved into its own optional category. The April "Capabilities" category is now "API, Auth, MCP & Skill Discovery" (`discovery`).
2. New checks: DNS-AID, Search for Agents, auth.md, A2A Agent Card, ARD, Personal Agent Protocol, MPP and AP2. There are 24 in all.
3. llms.txt is no longer a check. It was optional and off by default in April. The scanner's own `llms.txt` still lists it, which is out of date.
4. OAuth discovery, OAuth Protected Resource, auth.md, Search for Agents, Personal Agent Protocol and Web Bot Auth became informational: shown, but left out of the %.
5. The 0 to 5 level ladder was published with explicit gates.
6. Matching became more lenient: three MCP card paths and a flat `name`; the v0.2.0 skills index plus the legacy path; WebMCP through `document.modelContext` and declarative forms.
7. More places to run it (URL Scanner, dashboard, AI Crawl Control).

## Known gaps and conflicts

- **MCP Server Card location.** The MCP spec (SEP-2127, Final) puts the card next to the server, at `<server address>/server-card`, and finds it through the AI Catalog. Its discovery text says a `.well-known` path adds nothing. The scanner only looks under `/.well-known/`. A site that follows the spec fails the scanner. Serving the same card at both places satisfies both. Details in `protocol-discovery.md`.
- **ARD versus AI Catalog file names.** The scanner reads `/.well-known/ai-catalog.json` and `rel="ai-catalog"` (the AI Catalog spec). The ARD spec v0.91 uses `/.well-known/ard.json` and `rel="ard"`. Serve the same file at both paths.
- **Commerce scoring.** `llms-full.txt` says commerce checks count for sites with commerce signals; the page's code never adds them to the %. Treat commerce as unscored.
- **Markdown token headers.** Cloudflare's Markdown for Agents stopped sending `x-markdown-tokens` on 9 Oct 2026, but the scanner's fix prompt still mentions it as optional. Do not add it for the scanner's sake.
- **WebMCP needs a browser.** The scanner renders the page. A static fetch cannot see tools registered from JavaScript.

## How `scripts/check_site.py` compares

The script uses the same check IDs, statuses and level rules, so its output lines up with the scanner's. Its results matched the scanner on developers.cloudflare.com (level 4, the same passes and fails) on 26 Nov 2026. Differences:

| Area | Scanner | Script |
|---|---|---|
| WebMCP | renders the page | finds declarative forms only; reports `unableToCheck` otherwise |
| MCP Server Card | also sends a POST to the MCP endpoint | GET only; also looks for a card listed in the AI Catalog and warns about the path conflict |
| ARD | four routes including DNS | Agentmap, `rel="ai-catalog"`, `rel="ard"`, both well-known paths; no DNS route |
| x402 | also queries Coinbase's x402 Bazaar | probes the three paths only |
| Extras | none | AI bot access per URL from robots.txt, per-page facts for priority URLs, llms.txt presence, skill digest checks |
| Reach | public internet from Cloudflare | your own machine, so staging, VPN-only and localhost sites work |

The script's result is an estimate. When the two disagree, the scanner's result is the one a client will see, so report it and explain the difference.

## Sources

- [isitagentready.com](https://isitagentready.com/), its [llms-full.txt](https://isitagentready.com/llms-full.txt) and its [agent skills index](https://isitagentready.com/.well-known/agent-skills/index.json)
- [Introducing the Agent Readiness Score, Cloudflare blog, 17 Apr 2026](https://blog.cloudflare.com/agent-readiness/)
- [URL Scanner Agent Readiness report, changelog, 12 May 2026](https://developers.cloudflare.com/changelog/post/2026-05-12-URL-scanner-report-agent-readiness/)
- [Agent Readiness and AEO in the dashboard, Cloudflare blog, 6 Aug 2026](https://blog.cloudflare.com/aeo/)
- [AI Crawl Control, track robots.txt](https://developers.cloudflare.com/ai-crawl-control/features/track-robots-txt/)
- [Search for Agents, Cloudflare blog, 25 Nov 2026](https://blog.cloudflare.com/search-for-agents/)
