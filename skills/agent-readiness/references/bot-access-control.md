# Bot Access Control

How a site states what AI systems may do with its content, and how bots prove who they are. Cloudflare's scanner checks three things here: AI bot rules in robots.txt (see `discoverability.md`), Content Signals, and Web Bot Auth. AI bot rules and Content Signals together are the gate to level 2.

## Content Signals

**What it is:** a `Content-Signal` line in robots.txt that says how content may be used after it is fetched. Cloudflare proposed it in 2025; it is published at [contentsignals.org](https://contentsignals.org/) and as the IETF Internet-Draft draft-romm-aipref-contentsignals. It is a draft, not a standard, and following it is voluntary. It is still the cheapest way to put a usage policy on record, and it is half of the level 2 gate.

**The three signals** (definitions from contentsignals.org, in short):

| Signal | Covers |
|---|---|
| `search` | Building a search index and showing results: links and short excerpts. It does **not** cover AI-generated search summaries. |
| `ai-input` | Putting the content into an AI model at answer time: retrieval-augmented generation, grounding, generative search answers. |
| `ai-train` | Training or fine-tuning AI models. |

Values are `yes` or `no`, separated by commas. A signal left out means no preference is stated.

**Placement:** inside a `User-agent` group, so it applies to the bots in that group. A path in front scopes it to part of the site:

```
User-agent: *
Content-Signal: search=yes, ai-input=yes, ai-train=no
Content-Signal: /research/ search=yes, ai-input=no, ai-train=no
Allow: /
```

The scanner passes `contentSignals` when any `Content-Signal` line sets `ai-train`, `search` or `ai-input`.

### The `use` extension (Cloudflare, July 2026)

Cloudflare added an optional `use` signal on 1 July 2026. It describes how much of the content an AI product may reuse:

| Value | Meaning in Cloudflare's docs |
|---|---|
| `use=immediate` | Interact, but store and reuse nothing |
| `use=reference` | Index, excerpt and link back |
| `use=full` | Summarize and reproduce |

Cloudflare's managed robots.txt now writes `Content-signal: search=yes, ai-train=no, use=reference` and puts its managed block **in front of** the site's own robots.txt, so the response a crawler sees is both combined. On a Cloudflare site, check the live `/robots.txt`, not the file in the CMS. Bot Preference Sync (August 2026) keeps that block in line with the zone's AI crawler settings.

`use` is an extension, not part of the published draft. Add it when a client wants to state the "link back" expectation; skip it otherwise.

### Which policy to recommend

Ask the client. When they have no view, propose the policy that matches how they make money:

| Business | Usual choice |
|---|---|
| Local service, shop, SaaS marketing site | `search=yes, ai-input=yes`; `ai-train` is their call (often `yes`) |
| Publisher whose content is the product | `search=yes`; `ai-input` and `ai-train` decided with their licensing plans |
| Docs for a developer product | everything `yes`: agents reading the docs is the point |

Content Signals state a preference. They do not block anything. Blocking is done with `Disallow` rules for named bots and, for bots that ignore robots.txt, at the CDN or firewall.

### Markdown responses carry a signal too

Cloudflare's Markdown for Agents keeps a `Content-Signal` response header from the origin. If the origin sends none, Cloudflare adds `ai-train=yes, search=yes, ai-input=yes`. A site whose robots.txt says `ai-train=no` should send its own header on Markdown responses, or the two will disagree.

## Web Bot Auth

**What it is:** a way for a bot to prove who it is by signing each request with HTTP Message Signatures (RFC 9421). The bot operator publishes its public keys at `/.well-known/http-message-signatures-directory` on its own domain. Status: IETF drafts from the webbotauth working group. Cloudflare's verified-bots programme uses it for bot identity (October 2026), and Cloudflare calls it the preferred way to identify agents acting for users (November 2026).

**In the scanner:** informational. A site without a key directory gets `neutral`, which does not count against it. A valid directory counts as one of the level 5 options.

**What it means for a normal website:** nothing to publish. The key directory belongs to whoever **runs a bot or an agent**. A site that only receives bots benefits through its CDN, which checks signatures and can tell a real crawler from one that copies its User-Agent string. Recommend it only when the client operates a crawler, an agent or an agentic product.

## Bot purposes and what blocking costs

| Purpose | Examples | Blocking it |
|---|---|---|
| Search | OAI-SearchBot, Claude-SearchBot, PerplexityBot, Googlebot, Bingbot | can remove the site from that assistant's or engine's answers |
| User request | ChatGPT-User, Claude-User, Perplexity-User | breaks answers about the site for people who asked about it; some of these say robots.txt may not apply |
| Training | GPTBot, ClaudeBot, CCBot, Bytespider, Meta-ExternalAgent | a policy choice; does not remove the site from the search bots' answers |

`Google-Extended` and `Applebot-Extended` are robots.txt tokens, not crawlers. Google-Extended also covers grounding in Google's generative AI products outside Search, so blocking it has an effect beyond training.

## Blocking versus throttling

A training crawler can cost real bandwidth on a large site. Options, from lightest to strongest:

1. Allow, with a Content Signal stating the policy.
2. Rate-limit specific bots at the CDN.
3. `Crawl-delay` in robots.txt. Some crawlers honour it; Google does not.
4. `Disallow` for named bots. Works for crawlers that follow robots.txt.
5. Block at the CDN or firewall. The only option for bots that ignore robots.txt. Cloudflare's AI Crawl Control also offers pay-per-crawl (moving to "Pay Per Use", in beta since September 2026).

## Sources

- [Content Signals](https://contentsignals.org/) and [draft-romm-aipref-contentsignals](https://datatracker.ietf.org/doc/draft-romm-aipref-contentsignals/)
- [Cloudflare, Content Independence Day: more AI options, 1 Jul 2026](https://blog.cloudflare.com/content-independence-day-ai-options/)
- [Cloudflare docs, managed robots.txt](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/)
- [Cloudflare, Bot Preference Sync, 21 Aug 2026](https://blog.cloudflare.com/bot-preference-sync/)
- [Cloudflare docs, Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
- [RFC 9421, HTTP Message Signatures](https://www.rfc-editor.org/rfc/rfc9421)
- [IETF webbotauth working group](https://datatracker.ietf.org/wg/webbotauth/about/)
- [Cloudflare, verified bots and accountability, 16 Oct 2026](https://blog.cloudflare.com/verified-bots-accountability/)
- [Cloudflare, Web Bot Auth](https://blog.cloudflare.com/web-bot-auth/)
- [Cloudflare, trusted agent delegation, 5 Nov 2026](https://blog.cloudflare.com/trusted-agent-delegation/)
