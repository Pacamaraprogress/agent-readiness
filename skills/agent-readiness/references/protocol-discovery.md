# Protocol Discovery

How a site tells agents what they can **call or install**: APIs, MCP servers, A2A agents, agent skills, and how to authenticate. Cloudflare's scanner groups these as "API, Auth, MCP & Skill Discovery". One of the four integration checks (API Catalog, MCP Server Card, A2A Agent Card, Agent Skills) is the gate to level 4.

**Publish only what is real.** Every file here describes something that must exist and work: an API, a server, an agent, a skill. An empty catalog or a card for a server that is not running sends agents to a dead end and misleads the client about what they have. A content site with no API or agent should stop at level 3 and say so.

Contents: API Catalog · MCP Server Card · AI Catalog and ARD · Agent Skills · A2A Agent Card · OAuth discovery and protected resource metadata · auth.md · Personal Agent Protocol · WebMCP · promoting an MCP server · common mistakes · sources.

## API Catalog (RFC 9727)

**Status:** published RFC (2025). The most solid file in this section.

**Path:** `/.well-known/api-catalog`, served as `application/linkset+json` (RFC 9264 linkset). The scanner sends `Accept: application/linkset+json` and needs a `linkset` array.

```json
{
  "linkset": [
    {
      "anchor": "https://example.com/api/v1",
      "service-desc": [{ "href": "https://example.com/api/v1/openapi.json", "type": "application/openapi+json" }],
      "service-doc":  [{ "href": "https://example.com/docs/api", "type": "text/html" }],
      "status":       [{ "href": "https://example.com/api/v1/health" }]
    }
  ]
}
```

- `anchor` is the API's base URL. One entry per API or version.
- `service-desc` points to the raw machine-readable description (OpenAPI), not to Swagger UI.
- Add a homepage `Link: </.well-known/api-catalog>; rel="api-catalog"` header; it also passes the Link header check.

**When:** any public REST or GraphQL API. With an OpenAPI file, this is a short job. Template: `assets/templates/api-catalog.json`.

## MCP Server Card

**Status:** SEP-2127 is **Final** in the MCP specification (Extensions Track). The schema repository (`modelcontextprotocol/ext-server-card`) still calls the v1 shape pre-release.

**What it is:** a small public JSON document that describes one remote MCP server before anyone connects. Required fields: `$schema`, `name`, `version`, `description`.

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json",
  "name": "com.example/catalog",
  "version": "1.0.0",
  "title": "Example Catalog",
  "description": "Search the Example catalog, check stock and book a consultation.",
  "websiteUrl": "https://example.com/mcp/",
  "remotes": [
    { "type": "streamable-http", "url": "https://example.com/mcp" }
  ]
}
```

- `$schema` must be exactly the address above; the schema in `modelcontextprotocol/ext-server-card` enforces it with a pattern. On 26 Nov 2026 that address returned 404. It works as an identifier anyway, so keep it, and validate against `schema.json` in that repository.
- `name` is `owner/server`, usually reverse DNS.
- The card does not list tools, resources or prompts; clients read those from the live server.
- No credentials, private addresses or anything per user. Serve it with `Access-Control-Allow-Origin: *`, media type `application/mcp-server-card+json`.

### Where it lives: the spec and the scanner disagree

| | Location |
|---|---|
| MCP spec (SEP-2127, discovery text) | Any URL. Reserved spot: `<server address>/server-card`, e.g. `https://example.com/mcp/server-card`. Clients find it through the AI Catalog, which gives its URL. The discovery text says a `.well-known` path adds nothing, because the card is per server, not per site. |
| Cloudflare's scanner | Only `/.well-known/mcp/server-card.json`, `/.well-known/mcp/server-cards.json` or `/.well-known/mcp.json` |

A site that follows the spec fails `mcpServerCard`. Recommendation: serve the card at `<server address>/server-card`, list it in the catalog, **and** serve the same file at `/.well-known/mcp/server-card.json` while the scanner works this way. Keep the two copies identical (build one from the other). `scripts/check_site.py` detects a card listed in the catalog and explains the mismatch.

**When:** only if a remote MCP server is running and meant for outside use. Template: `assets/templates/mcp-server-card.json`.

## AI Catalog and ARD: the site-wide list

A server card describes one server. A catalog lists everything a domain offers agents: server cards, A2A agent cards, skills, nested catalogs. Two specs describe the same list and disagree on names and on one required field:

| | AI Catalog | ARD (Agentic Resource Discovery) |
|---|---|---|
| Version | v0.9, release candidate for 1.0, dated 19 Nov 2026 (checked 26 Nov 2026) | v0.91, "Proposal", dated 26 Aug 2026; the page was edited on 11 Nov 2026 without a new version number (checked 27 Nov 2026) |
| Well-known path | `/.well-known/ai-catalog.json` | `/.well-known/ard.json` (calls `ai-catalog.json` its predecessor) |
| Link relation | `ai-catalog` (HTML `<link>` or HTTP `Link`) | `ard` |
| Other routes | none in the spec | robots.txt `Agentmap:` line; DNS service-binding records (`_entries._agents` for entries, `_search._agents` for a registry); entry JSON-LD inside an ordinary web page, which registries must crawl |
| Top level | `specVersion` (required; `"0.9"` for this release candidate) and `entries` | `entries`; other top-level members are ignored |
| Required per entry | `identifier`, `type`, exactly one of `url` or `data` | the same, plus `displayName` |
| Media type | `application/ai-catalog+json` | the same type for nested catalogs |

Cloudflare's `ard` check reads the AI Catalog names: an `Agentmap:` line, `<link rel="ai-catalog">`, `/.well-known/ai-catalog.json`, or DNS (`_catalog._agents` TXT). It needs a non-empty `specVersion` string and a non-empty `entries` array, and reports problems in single entries without failing.

**The entry.** `identifier` is `urn:air:<your domain>:[<namespace>:]<name>`, `type` is a media type, and exactly one of `url` (a link to the artifact) or `data` (the artifact inline). ARD adds two discovery terms:

- `representativeQueries` (SHOULD, 2 to 5): questions a user might ask that this resource answers. An ARD registry builds its search index from them, so an entry without them still validates but will not be found. ARD's conformance tool reports it as a warning, not a failure.
- `capabilities` (MAY): short tool names such as `"ProductSearch"`, for filtering without fetching the artifact.

Optional in both: `description`, `tags`, `version`, `updatedAt`, `metadata`. ARD's `trustManifest` carries identity, attestations and signatures; its identity must belong to the domain in the `identifier`, which stops one site from listing entries under another's name.

**ARD entries are JSON-LD (since the 11 Nov 2026 edit).** Consumers read every entry against a base context, `https://agenticresourcediscovery.org/context/v1`, so a plain entry without `@context` stays valid. Add `"@context": "https://agenticresourcediscovery.org/context/v1"` when the entry sits inside a web page, where general JSON-LD tools may read it. An entry may also add terms from its own namespace (for example `"acme:region"` with `"acme"` bound in `@context`), and ARD registries can filter on them. AI Catalog allows members it does not define, so these extra terms do not break the AI Catalog file.

**Entry types.** `type` is an open media type: ARD accepts any valid one. The recognized types are MCP server cards (`application/mcp-server-card+json`), A2A agent cards (`application/a2a-agent-card+json`), generic agent cards (`application/agent-card+json`), agent skills (`application/agent-skills+json`, `+md`, `+zip`, `+gzip`), agent plugins (`application/agent-plugins+zip`, `+gzip`), ARD registries (`application/ai-registry+json`) and nested catalogs (`application/ai-catalog+json`). None of them is for WebMCP tools or ordinary pages. A made-up type would pass validation, but no client or registry would know what to do with it.

**The `displayName` conflict.** AI Catalog says to leave `displayName` out when the artifact carries its own name (the `title` of an MCP server card, the `name` of an A2A agent card), and when it is there it wins over the card. ARD requires it. One file can satisfy both: include `displayName`, set it to exactly the card's title, and change both together.

**What to publish:** one file, served at both well-known paths, that satisfies both specs:

```json
{
  "specVersion": "0.9",
  "host": { "displayName": "Example", "identifier": "did:web:example.com" },
  "entries": [
    {
      "identifier": "urn:air:example.com:mcp:catalog",
      "displayName": "Example Catalog MCP server",
      "type": "application/mcp-server-card+json",
      "url": "https://example.com/mcp/server-card",
      "description": "Search the Example product catalog and check stock.",
      "representativeQueries": [
        "is this product in stock",
        "find a product by name and show its price"
      ]
    }
  ]
}
```

- `specVersion` is the AI Catalog version: `"0.9"` while v0.9 is the release candidate. The spec says v0.9 is not an alias for 1.0, and a consumer may reject a major version it does not support, so do not write `"1.0"` before v1.0 is published. ARD ignores this member. Release 2026.11.26 of this skill wrote `"1.0"`; correct files made from it.
- ARD now says a publisher needs only `ard.json` and `rel="ard"`. The scanner and MCP's server-card text read the AI Catalog names, so serve the same file at both paths anyway.
- **Check it:** ARD's conformance tool (`conformance/bin/conformance-test` in [ards-project/ard-spec](https://github.com/ards-project/ard-spec)) validates a manifest, or takes a domain, fetches `/.well-known/ard.json` (falling back to `ai-catalog.json` with a warning) and validates what it finds. To check one entry against the schema: `npx ajv-cli validate -s spec/schemas/ard-entry.schema.json -d entry.json`, run from a clone of that repository.
- An empty catalog published to turn a check green helps nobody. Lighthouse's agentic-browsing audits show "Not applicable" when the file is absent.

Template: `assets/templates/ai-catalog.json`.

## Agent Skills index

**Status:** Agent Skills Discovery RFC, v0.2.0 (`schemas.agentskills.io`), started by Cloudflare. A draft.

**What it is:** a list of skills (instructions an agent can load, usually `SKILL.md` files) that the site publishes for agents working with its product, for example "deploy to our platform" or "use our API". It is not a list of API endpoints.

**Path:** `/.well-known/agent-skills/index.json`. The scanner also accepts the legacy `/.well-known/skills/index.json`.

```json
{
  "$schema": "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
  "skills": [
    {
      "name": "check-stock",
      "type": "skill-md",
      "description": "Check product stock and lead times with the Example API. Use when a user asks whether an item is available.",
      "url": "/.well-known/agent-skills/check-stock/SKILL.md",
      "digest": "sha256:<sha256 of the SKILL.md file>"
    }
  ]
}
```

- Each skill needs `name`, `type`, `description`, `url` and `digest`. `type` is `skill-md` (one SKILL.md) or `archive`.
- Keep `$schema` as shown; the scanner's fix skill asks for it. The `schemas.agentskills.io` host did not resolve on 26 Nov 2026, so treat the address as an identifier.
- The digest must match the file byte for byte. Regenerate it on every change; `scripts/check_site.py` checks the first five.
- **When:** developer products, APIs and platforms whose users work through coding agents. Rarely right for a local business or a shop.

Template: `assets/templates/agent-skills-index.json`.

## A2A Agent Card

**Status:** part of the Agent2Agent (A2A) protocol, now under the Linux Foundation. Off by default in the scanner's web page, but a level 4 option.

**What it is:** `/.well-known/agent-card.json` describes an **agent** the site runs (one that other agents can talk to over A2A): `name`, `version`, `description`, `supportedInterfaces` (service URL and transport), `capabilities`, and `skills` (each with `id`, `name`, `description`).

**When:** only when the business runs an A2A-compatible agent, such as a support or booking agent with an A2A endpoint. A chat widget on a page is not one.

## OAuth discovery and protected resource metadata

**Status:** published RFCs, widely used. Informational in the scanner's %, but one of the level 5 options.

| File | RFC | Says |
|---|---|---|
| `/.well-known/oauth-authorization-server` (or `/.well-known/openid-configuration` for OpenID Connect) | RFC 8414 | where to authorize, get tokens and register clients |
| `/.well-known/oauth-protected-resource` | RFC 9728 | which authorization servers protect this API, and which scopes exist |

A protected API should also answer unauthenticated requests with `WWW-Authenticate: Bearer resource_metadata="https://example.com/.well-known/oauth-protected-resource"`, so an agent can find the metadata from the 401. Remote MCP servers that need sign-in use exactly this flow. Most OAuth libraries and identity providers publish these files for you; check they are reachable on the API's own domain.

## auth.md

**Status:** a proposal (WorkOS) for telling agents how to register and get credentials. Informational in the scanner, and a level 5 option.

It has three parts: a Markdown file at `/auth.md` whose H1 contains "auth.md", protected resource metadata (above), and an `agent_auth` block in the authorization server metadata with a `skill`, a `register_uri` and at least one registration method. Relevant only to services that want agents to sign up or sign in on their own. Never test registration endpoints during an audit: they can create accounts or send email.

## Personal Agent Protocol (Poppy)

**Status:** the spec at personalagentprotocol.org is version 1.0 (checked 26 Nov 2026); Cloudflare's scanner still describes it as draft 0.1. Informational only; it never affects the level or the %.

`/.well-known/poppy.json` with `protocol_version`, an `organization` (`name`, `domain`), at least one of `agent`, `apis` or `web`, and the interfaces the site really offers personal agents, bound to an OAuth issuer when sign-in is declared. Mention it only to clients building for personal agents. Publish only interfaces that work.

## WebMCP (in-page tools)

WebMCP lets a page register tools that an agent in the visitor's browser can call. The scanner counts it in the % (`webMcp`), and it needs a browser to detect. In-page tools have no address, so the discovery files above do not apply to them: catalogs have no entry type for WebMCP, and nothing can be "listed" before a visit.

Building, testing and shipping WebMCP tools is a project of its own. Use the companion skill **agent-ready** ([github.com/Pacamaraprogress/agent-ready](https://github.com/Pacamaraprogress/agent-ready)), which holds field notes from real builds.

## Promoting an MCP server

A working endpoint is not found by itself. In order:

1. **Landing page** on the site that owns the server: what an assistant can do with it, two or three example requests, the server address as copyable text, whether sign-in is needed.
2. **Connect links.** Claude: `https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=<name>&connectorUrl=<URL-encoded address>` opens the add-connector dialog with the fields filled (confirmed by an Anthropic maintainer in May 2026; known gaps on iOS Safari and for signed-out visitors, so always print the manual steps too). ChatGPT has no documented prefilled link, and adding a custom server depends on the plan.
3. **Server card and catalog** (above): the only route from a bare domain to a working connection.
4. **MCP Registry** (`registry.modelcontextprotocol.io`, preview): publish with `mcp-publisher`; use a domain-verified name (`com.example/server`) for a client's server.

Test before promoting: `initialize`, `tools/list` and one real `tools/call` from outside the site's network, then add the server in the assistant itself. Hosted assistants call from their own data centres, and a firewall rule that blocks them breaks everything above.

Who it suits: SaaS products, data sources and large catalogues whose users already work inside an assistant. It rarely suits a local service business.

## Common mistakes

- Publishing a catalog, skills index or card for something that does not exist or does not work.
- Pointing `service-desc` at Swagger UI instead of the OpenAPI file.
- Only one MCP card location: the scanner and spec-following clients look in different places.
- `"specVersion": "1.0"` in the catalog. AI Catalog v0.9 is a release candidate and asks for `"0.9"`.
- A catalog entry without `displayName`. AI Catalog allows it, but ARD requires it, so the same file fails ARD validation.
- A skills index whose digests no longer match the files.
- OAuth metadata on the identity provider's domain only, with no protected resource metadata on the API's domain.
- Testing an MCP server only from your own machine.

## Sources

- [RFC 9727, api-catalog](https://www.rfc-editor.org/rfc/rfc9727) and [RFC 9264, linkset](https://www.rfc-editor.org/rfc/rfc9264)
- [SEP-2127, MCP Server Cards](https://modelcontextprotocol.io/seps/2127-mcp-server-cards), [ext-server-card repository](https://github.com/modelcontextprotocol/ext-server-card) and its [discovery text](https://github.com/modelcontextprotocol/ext-server-card/blob/main/docs/discovery.md)
- [AI Catalog specification](https://ai-catalog.io/spec/) and [repository](https://github.com/Agent-Card/ai-catalog)
- [ARD specification](https://agenticresourcediscovery.org/spec/) and [repository](https://github.com/ards-project/ard-spec) (entry schema, OpenAPI for registries, conformance tool)
- [Agent Skills Discovery RFC](https://github.com/cloudflare/agent-skills-discovery-rfc)
- [A2A protocol specification](https://a2a-protocol.org/latest/specification/) and [agent discovery](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [RFC 8414, OAuth authorization server metadata](https://www.rfc-editor.org/rfc/rfc8414) and [RFC 9728, protected resource metadata](https://www.rfc-editor.org/rfc/rfc9728)
- [Personal Agent Protocol draft](https://personalagentprotocol.org/docs/spec)
- [isitagentready.com fix skills](https://isitagentready.com/.well-known/agent-skills/index.json) (auth.md, A2A, ARD, Poppy)
- [MCP Registry](https://modelcontextprotocol.io/registry/about)
- [Claude connector link, maintainer's answer (issue 74)](https://github.com/anthropics/claude-ai-mcp/issues/74) and [open bug (issue 895)](https://github.com/anthropics/claude-ai-mcp/issues/895)
