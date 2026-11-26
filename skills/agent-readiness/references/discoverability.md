# Discoverability

How agents find a site's content and machine-readable files. Cloudflare's scanner checks four things here: robots.txt, a sitemap, Link headers on the homepage, and DNS records for agent discovery (DNS-AID). The first three decide level 1.

## robots.txt

The scanner passes `robotsTxt` when `/robots.txt` returns 200 as `text/plain` with at least one `User-agent` line. It passes `robotsTxtAiRules` (needed for level 2) when the file has groups for known AI bots **or** wildcard rules that apply to every crawler. A plain, sensible `User-agent: *` file passes both.

The real work is deciding what each kind of AI bot may fetch.

### How a crawler picks its rules (RFC 9309)

- A crawler obeys **only the most specific group that names it**. If `GPTBot` has its own group, it ignores the `User-agent: *` group entirely, so repeat every `Disallow` line that should still apply.
- Groups that name the same crawler are combined.
- Inside a group, the longest matching path wins. When an `Allow` and a `Disallow` are equally long, `Allow` wins.
- `*` matches any characters and `$` anchors the end of the path.
- If robots.txt returns 4xx, crawlers treat the site as having no rules. If it returns 5xx or cannot be reached, they must assume everything is disallowed. A robots.txt that times out is a silent full block.

### Named AI user agents (checked against each operator's page, 26 Nov 2026)

| Token | Operator | Purpose | Notes |
|---|---|---|---|
| `GPTBot` | OpenAI | Training | Disallowing it says the content should not be used to train OpenAI's foundation models |
| `OAI-SearchBot` | OpenAI | Search | Sites that block it are not shown in ChatGPT search answers (they can still appear as navigational links) |
| `ChatGPT-User` | OpenAI | User request | OpenAI says robots.txt rules may not apply, because a user started the fetch |
| `ClaudeBot` | Anthropic | Training | |
| `Claude-SearchBot` | Anthropic | Search | |
| `Claude-User` | Anthropic | User request | |
| `PerplexityBot` | Perplexity | Search | Not used for training foundation models |
| `Perplexity-User` | Perplexity | User request | Perplexity says it generally ignores robots.txt |
| `Googlebot` | Google | Search | Also the crawler behind AI Overviews and AI Mode |
| `Google-Extended` | Google | Control token | Not a crawler. Covers training and grounding for Google's generative AI products other than Search. Does not affect Search inclusion or ranking. |
| `Bingbot` | Microsoft | Search | Bing's index feeds Copilot answers |
| `Applebot` | Apple | Search | |
| `Applebot-Extended` | Apple | Control token | Not a crawler. Covers use for training Apple's models |
| `Meta-ExternalAgent` | Meta | Training and indexing | |
| `Meta-WebIndexer` | Meta | Search | Meta AI search |
| `Meta-ExternalFetcher` | Meta | User request | Meta says it may bypass robots.txt |
| `Amazonbot` | Amazon | Products, may train | |
| `Amzn-SearchBot` | Amazon | Search | Not used for training |
| `Amzn-User` | Amazon | User request | Not used for training |
| `MistralAI-Training` | Mistral | Training | |
| `MistralAI-Index` | Mistral | Search | Not used for training |
| `MistralAI-User` | Mistral | User request | |
| `DuckAssistBot` | DuckDuckGo | AI answers | Respects robots.txt; not used for training |
| `CCBot` | Common Crawl | Open web corpus | Many model builders train on Common Crawl |
| `Bytespider` | ByteDance | Training | |

Older names you may still see, `Claude-Web` and `anthropic-ai`, are no longer on Anthropic's page. Existing rules for them do no harm, but do not build a policy around them.

`scripts/check_site.py` prints each of these bots' verdict for each URL you check, and marks bots that have their own group (so they skip the `*` rules) and fetchers whose operators say robots.txt may not apply.

### Three decisions, not one

1. **Search bots** (OAI-SearchBot, Claude-SearchBot, PerplexityBot, Meta-WebIndexer, Amzn-SearchBot, MistralAI-Index, Googlebot, Bingbot). Blocking one can keep the site out of that assistant's answers. Most businesses want these allowed.
2. **User-triggered fetchers** (ChatGPT-User, Claude-User, Perplexity-User, Meta-ExternalFetcher, Amzn-User, MistralAI-User). They fetch a page because a person asked about it. Several say robots.txt may not apply. Blocking them mostly breaks answers about the site for its own customers.
3. **Training** (GPTBot, ClaudeBot, Meta-ExternalAgent, Amazonbot, MistralAI-Training, CCBot, Bytespider, and the Google-Extended and Applebot-Extended tokens). A business decision about model training. Blocking these does not remove a site from the search bots above, except that Google-Extended also covers grounding in Gemini apps.

Express the training decision with Content Signals too (`bot-access-control.md`), because a signal also reaches crawlers you did not name.

### Template: allow search and user fetches, decide training separately

`assets/templates/robots.txt` holds a commented version. The short form:

```
User-agent: *
Disallow: /cart/
Disallow: /checkout/
Disallow: /my-account/
Content-Signal: search=yes, ai-input=yes, ai-train=no

# Opt out of training crawlers. Each named group replaces the * group for that
# bot, so repeat the private paths if the group allows anything.
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: CCBot
User-agent: Google-Extended
User-agent: Applebot-Extended
Disallow: /

Sitemap: https://example.com/sitemap.xml
```

For "allow everything", drop the second group and set `ai-train=yes`.

### Robots.txt is not the whole answer

robots.txt states a rule. A CDN, WAF or bot-management setting can still block a bot that robots.txt allows, and some bot-protection modes block AI crawlers by default. Before telling a client "AI bots can reach you", check the real responses in server or CDN logs, or the CDN's AI crawler report. Fetching the site yourself with a bot's User-Agent string is not proof either way: a CDN that verifies bots by IP will block the fake and allow the real one.

### Common mistakes

- A named group for one bot that drops the private-path `Disallow` lines (the bot now crawls `/cart/`).
- `Disallow: /` left in `User-agent: *` from a staging launch.
- robots.txt served as `text/html` (fails the scanner; some crawlers ignore it).
- Different robots.txt on `www` and the apex domain, or one of them returning 5xx.
- `Disallow: /*?` rules that also block the parameterised URLs the site depends on.

## Sitemap

The scanner passes `sitemap` when `/sitemap.xml` is valid XML or robots.txt has a `Sitemap:` line. The script also fetches the listed sitemap and warns when it does not parse.

- List every sitemap or the sitemap index in robots.txt with an absolute URL.
- Keep each child sitemap under 50,000 URLs and 50 MB uncompressed.
- Give each URL an accurate `<lastmod>`. Crawlers use it to decide what to re-fetch, so a `<lastmod>` that changes on every build is worse than none.
- Priority pages for AI answers (step 4 in `aleyda-checklist-map.md`) belong in the sitemap and in the internal links.

## Link headers (RFC 8288)

The scanner passes `linkHeaders` when the **homepage** response carries a `Link` header with one of the relations `api-catalog`, `service-desc`, `service-doc` or `describedby`. Only those four count. An `alternate` link to a Markdown version is useful to agents but does not pass the check on its own.

What to point at:

| Relation | Points to |
|---|---|
| `api-catalog` | `/.well-known/api-catalog` (RFC 9727) |
| `service-desc` | a machine-readable API description, such as an OpenAPI file |
| `service-doc` | human-readable API or developer documentation |
| `describedby` | a document that describes the site, such as `/llms.txt` |

A content site with no API can still use `describedby`:

```
Link: </llms.txt>; rel="describedby"; type="text/markdown"
```

Only add it if the target exists and is maintained. Ways to add the header: the web server (`add_header Link ...` in nginx, `Header add Link ...` in Apache), a WordPress `send_headers` hook, or a CDN rule (on Cloudflare, a Response Header Transform Rule).

## DNS for AI discovery (DNS-AID)

**Status:** an IETF Internet-Draft (draft-mozleywilliams-dnsop-dnsaid), not a standard. Counted in the scanner's percentage, not in any level.

Agents can look up endpoints under the `_agents` name of a domain: `_index._agents.<host>`, `_a2a._agents.<host>` or `_mcp._agents.<host>`. The scanner passes only on **ServiceMode SVCB or HTTPS records that a validating resolver returns as DNSSEC-authenticated**. The example from Cloudflare's fix skill:

```
_a2a._agents.example.com. 3600 IN SVCB 1 agent.example.com. alpn="a2a" port=443 mandatory=alpn,port
```

Publish this only when the domain runs an agent or MCP endpoint worth finding, and only if DNSSEC is already on for the zone. For a content site it adds nothing.

## Sources

- [RFC 9309, Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309)
- [RFC 8288, Web Linking](https://www.rfc-editor.org/rfc/rfc8288)
- [Sitemaps protocol](https://www.sitemaps.org/protocol.html)
- Operators' crawler pages: [OpenAI](https://developers.openai.com/api/docs/bots), [Anthropic](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler), [Perplexity](https://docs.perplexity.ai/docs/resources/perplexity-crawlers), [Google-Extended](https://developers.google.com/crawling/docs/google-extended), [Google's crawlers](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers), [Apple](https://support.apple.com/en-us/119829), [Meta](https://developers.facebook.com/documentation/sharing/webmasters/web-crawlers), [Amazon](https://developer.amazon.com/docs/amazonbot/amazonbot), [Mistral](https://docs.mistral.ai/robots), [DuckDuckGo](https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot), [Common Crawl](https://commoncrawl.org/ccbot)
- [DNS-AID Internet-Draft](https://datatracker.ietf.org/doc/draft-mozleywilliams-dnsop-dnsaid/)
- [isitagentready.com fix skills](https://isitagentready.com/.well-known/agent-skills/index.json) (Link headers, DNS-AID)
