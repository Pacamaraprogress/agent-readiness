# Adoption numbers

Use these to set expectations, not to scare a client. Always give the date and the population with a number; this field moves every month.

## Cloudflare Radar, 23 November 2026

**Source:** Radar AI Insights, "Adoption of AI agent standards" ([radar.cloudflare.com/ai-insights](https://radar.cloudflare.com/ai-insights)). The widget updates weekly on Mondays.

**Population:** Radar starts from the top 200,000 domains and removes categories it treats as not meaningful for agent readiness (such as search engines and unreachable infrastructure). 159,998 domains were attempted and **114,182 scanned successfully**; the percentages use 114,182 as the denominator. The counts come from Radar's chart data; the percentages are those counts divided by 114,182, which match the rounded values Radar shows.

| Check | Share | Domains |
|---|---|---|
| robots.txt present and valid | 86.75% | 99,053 |
| AI rules in robots.txt (wildcard-only files count, see caveat 1) | 84.42% | 96,396 |
| Sitemap | 73.04% | 83,402 |
| Link headers | 9.56% | 10,912 |
| Content Signals | 9.08% | 10,366 |
| OAuth discovery | 8.11% | 9,257 |
| UCP | 5.00% | 5,709 |
| Markdown negotiation | 4.79% | 5,475 |
| OAuth Protected Resource | 4.60% | 5,252 |
| WebMCP | 1.59% | 1,810 |
| API Catalog | 0.94% | 1,077 |
| MCP Server Card | 0.77% | 878 |
| Agent Skills index | 0.73% | 836 |
| DNS-AID | 0.48% | 543 |
| ARD / AI Catalog | 0.43% | 491 |
| auth.md | 0.13% | 143 |
| Web Bot Auth | 0.11% | 129 |
| A2A Agent Card | 0.10% | 117 |
| Personal Agent Protocol | 0.06% | 66 |
| ACP | 0.03% | 37 |
| MPP | 0.01% | 17 |
| x402 | 0.01% | 8 |
| AP2 | under 0.01% | 5 |

Radar has no llms.txt figure (the scanner stopped checking it) and no Search for Agents figure yet (launched 25 Nov 2026).

### Caveats

1. **"AI rules in robots.txt" is not the share of sites with AI-specific rules.** The scanner passes a robots.txt whose wildcard rules apply to every bot, which is why the figure sits just below the robots.txt figure.
2. **Do not present April to November as a growth rate.** The scanner changed in between (more accepted paths for MCP cards, new checks, new filters), and the April post gave no denominator. Part of each jump may be method change.
3. **No public weekly history.** The chart returns the latest week; the Radar API has a time series but needs a token.

## April 2026 baseline

From Cloudflare's launch post ([Introducing the Agent Readiness Score](https://blog.cloudflare.com/agent-readiness/), 17 Apr 2026), top 200,000 domains with some categories removed:

| Check | April 2026 |
|---|---|
| robots.txt | 78% |
| Content Signals | 4% |
| Markdown negotiation | 3.9% |
| MCP Server Card and API Catalog together | fewer than 15 sites |

## Other Radar figures, same week

- **AI user agents disallowed in robots.txt, top 10,000 domains.** Radar found 4,471 robots.txt files. Most often disallowed: GPTBot (950 domains: 533 fully, 417 partly), then ClaudeBot (883), CCBot (842), Google-Extended (806) and Bytespider (800).
- **Markdown savings.** The median Markdown response is 7.7% of the size of the HTML it replaces (shown for the last 7 days, no exact date on the gauge).

## How to use these numbers with a client

- **Say what the number measures.** "Under 5% of the top sites Cloudflare scanned answer with Markdown" is a fact; "95% of your competitors are invisible to AI" is not.
- **Low adoption is not a reason by itself.** A file that almost nobody publishes is cheap to be early with only if it describes something real (see "Publish only what is real" in SKILL.md).
- **Readiness is not visibility.** None of these numbers says anything about who gets cited in AI answers.
- **Re-check before quoting.** Look at Radar for a newer week and update the date.

## Status of each standard

| Standard | Status (checked 26 Nov 2026) |
|---|---|
| robots.txt | RFC 9309 |
| Sitemaps | sitemaps.org protocol, universally supported |
| Link headers | RFC 8288 |
| API Catalog | RFC 9727 |
| OAuth metadata | RFC 8414, RFC 9728 |
| HTTP Message Signatures (used by Web Bot Auth) | RFC 9421; Web Bot Auth itself is in IETF drafts |
| Markdown negotiation | ordinary HTTP content negotiation; no separate spec |
| Content Signals | IETF Internet-Draft (draft-romm-aipref-contentsignals) |
| DNS-AID | IETF Internet-Draft (draft-mozleywilliams-dnsop-dnsaid) |
| MCP Server Card | SEP-2127, Final in the MCP spec; schema v1 pre-release |
| AI Catalog | v0.9, release candidate for 1.0 |
| ARD | v0.91 proposal |
| Agent Skills Discovery | v0.2.0 draft |
| A2A Agent Card | A2A protocol (Linux Foundation project) |
| auth.md, Personal Agent Protocol | proposals |
| llms.txt | proposal (September 2024); no longer scanned by Cloudflare |
| AGENTS.md | open format under the Agentic AI Foundation (for code repositories) |

## Sources

- [Cloudflare Radar, AI Insights](https://radar.cloudflare.com/ai-insights)
- [Radar AI Insights updates, changelog, 17 Apr 2026](https://developers.cloudflare.com/changelog/post/2026-04-17-radar-ai-insights-updates/)
- [Introducing the Agent Readiness Score, Cloudflare blog, 17 Apr 2026](https://blog.cloudflare.com/agent-readiness/)
- [Radar Agent Readiness API](https://developers.cloudflare.com/api/resources/radar/subresources/agent_readiness/)
