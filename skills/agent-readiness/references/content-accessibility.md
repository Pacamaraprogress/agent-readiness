# Content Accessibility

How an agent reads a page once it has found it. Cloudflare's scanner checks Markdown negotiation (needed for level 3) and, as information only, Search for Agents. Aleyda Solis's checklist adds the part no scanner sees: are the facts the target prompts need actually in the page an agent receives? Both are covered here.

## Facts in the raw HTML first

Before any protocol work, check that each priority page's key facts are in the HTML the server sends: prices and what they include, specs, service areas, hours, steps, names. Many AI fetchers do not run JavaScript, and text inside images is easy for any reader to miss.

Problems that hide facts:

- Content loaded by JavaScript after the page renders (tabs, accordions filled by an API call, client-rendered apps).
- Facts only in images, PDFs, iframes or third-party widgets (store locators, price calculators, review widgets).
- `noindex`, `nosnippet` or `max-snippet:0` on pages meant to be cited.

`scripts/check_site.py --page <url>` reports the words in the raw HTML, the JSON-LD blocks, noindex and nosnippet for each priority URL, and flags pages that look client-rendered (little text, many scripts). It does not render pages; compare with a rendered fetch when a page is flagged.

Structure that helps any reader, human or agent:

- One `<h1>`, then headings that say what the section answers. Do not skip levels.
- The direct answer near the top of its section, then the detail.
- Tables with header rows for comparisons and specs.
- Named entities (products, places, people) spelled the same way everywhere.

## Markdown content negotiation

**What passes the scanner:** a GET of the page with `Accept: text/markdown` returns `Content-Type: text/markdown`. HTML stays the default for every other request. This is the level 3 gate.

**Why it matters:** a Markdown version drops navigation, scripts and layout. Cloudflare Radar's measurement (late November 2026) puts the median Markdown response at 7.7% of the size of the HTML it replaces.

**Adoption:** 4.8% of the domains Radar scanned on 23 Nov 2026 (see `adoption-stats.md`).

### Rules for any implementation

- Same URL, two representations. Send `Vary: Accept` on both, or a cache will serve Markdown to browsers or HTML to agents. The script warns when `Vary: Accept` is missing.
- The Markdown must say what the HTML says. It is the same page, not a second, agent-only version with different claims.
- Keep links absolute or root-relative so they work outside the page.
- If robots.txt states a Content Signal, send the same policy in a `Content-Signal` response header on Markdown responses (see `bot-access-control.md`).

### Cloudflare: Markdown for Agents

Generally available since 9 Nov 2026, on Pro, Business and Enterprise plans and SSL for SaaS. Turning it on converts HTML to Markdown at the edge for requests that ask for it, with no change at the origin.

- Conversion limit 6 MiB (raised from 2 MiB on 9 Oct 2026, when conversion moved into the edge).
- Since 9 Oct 2026 responses no longer carry `x-markdown-tokens` or `x-original-tokens`. Ignore older guides, and the scanner's fix prompt, that still mention them.
- It adds `Vary: Accept`, keeps the origin's security and cache headers, and adds a default `Content-Signal` header when the origin sends none.
- Analytics, logs and a playground live under Agent Readiness → Markdown for Agents.

Check the output on a few real pages before calling it done. Edge conversion of a page builder's HTML can keep menus, cookie text and repeated blocks.

### Other servers

nginx, serving prebuilt `.md` files next to the HTML:

```nginx
map $http_accept $md_suffix {
    default         "";
    "~*text/markdown" ".md";
}
location / {
    add_header Vary Accept;
    try_files $uri$md_suffix $uri $uri/ =404;
}
```

Make sure `.md` files are served as `text/markdown` (add `text/markdown md;` to the `types` block if needed).

Express:

```js
app.use((req, res, next) => {
  res.vary('Accept');
  if (req.get('Accept')?.includes('text/markdown')) {
    const md = markdownFor(req.path);   // your lookup or converter
    if (md) return res.type('text/markdown').send(md);
  }
  next();
});
```

WordPress: there is no core feature. Options are a plugin that serves a Markdown version on `Accept: text/markdown`, an edge converter (Cloudflare above), or a small `template_redirect` handler that converts the post content. Test the result with the script or the scanner, and check that page caching varies on `Accept`.

### Without negotiation

Publishing `<url>.md` copies with an `alternate` link (`<link rel="alternate" type="text/markdown" href="...">`) helps agents that look for it, but does not pass the scanner's check.

## Search for Agents

**Status:** launched by Cloudflare on 25 Nov 2026. Informational in the scanner (no effect on the level or the %).

A site-wide search endpoint at `/.well-known/search?q=...` that returns results as Markdown, so an agent can search the site instead of crawling it. It is advertised with meta tags such as:

```html
<meta name="agent:endpoint" content="https://example.com/.well-known/search?q={query}">
<meta name="agent:instructions" content="Search this site with keywords or a question. Results are Markdown.">
<meta name="agent:method" content="GET">
```

On Cloudflare a dashboard toggle builds the index (AI Search) and serves the endpoint, free plan included with limits. Elsewhere it is a custom build. Worth it for large docs and knowledge sites; not for a small business site.

## llms.txt

**Status:** a proposal by Jeremy Howard (Answer.AI, September 2024), at [llmstxt.org](https://llmstxt.org/). Cloudflare's scanner no longer checks it (the API rejects the old check ID), and Radar does not measure it. No major AI provider has documented that its crawlers use it.

When it is still worth publishing:

- Developer docs, where people load the file into an IDE or an agent on purpose.
- Sites whose owners want a curated reading list for agents and will keep it current.

When to skip it: a small business site with a good sitemap and clean pages. Do not present it to a client as an AI ranking factor.

Format, if used: Markdown at `/llms.txt`, an `# H1` with the site name, a one-line summary in a blockquote, then sections of links with a short note each. Link to Markdown versions where they exist, keep it to the important entry points, and put nice-to-have links under `## Optional`. Template: `assets/templates/llms.txt`.

## Token budgets for docs pages

Addy Osmani's guidance for documentation (April 2026): aim for roughly 15,000 tokens for a quick-start, 20,000 for a concept guide, 25,000 for an API reference, and stay under about 30,000 for any page, because agents truncate or skip very long pages. Split long pages by topic and link between them. One token is roughly four characters of English.

## Copy for AI

A button that copies the page as Markdown, or a ready prompt with the page URL, is a common pattern on developer docs. It is a UX choice, not a standard, and no scanner checks it.

## Sources

- [Cloudflare docs, Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
- [Changelog: Markdown for Agents generally available, 9 Nov 2026](https://developers.cloudflare.com/changelog/post/2026-11-09-markdown-for-agents-observability/)
- [Changelog: in-edge conversion, 6 MiB, token headers removed, 9 Oct 2026](https://developers.cloudflare.com/changelog/post/2026-10-09-markdown-for-agents-in-process-conversion/)
- [Changelog: header preservation and default Content-Signal, 13 Jul 2026](https://developers.cloudflare.com/changelog/post/2026-07-13-markdown-for-agents-header-preservation/)
- [Cloudflare Radar, AI Insights](https://radar.cloudflare.com/ai-insights)
- [Search for Agents, Cloudflare blog, 25 Nov 2026](https://blog.cloudflare.com/search-for-agents/) and [docs](https://developers.cloudflare.com/ai-search/how-to/search-for-agents/)
- [llms.txt proposal](https://llmstxt.org/)
- [Addy Osmani, Agentic Engine Optimization](https://addyosmani.com/blog/agentic-engine-optimization/)
- [Aleyda Solis, AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/)
