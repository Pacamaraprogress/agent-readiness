# Commerce protocols (short reference)

Cloudflare's scanner has a Commerce category with five checks. They never count toward the level or the %, and a site with no commerce signals gets `neutral` on all five. This file says what each one is so you can answer a client's question. It is not a build guide: payment and checkout work belongs to the client's payment provider and developers.

| Check | Protocol | Who is behind it | What the scanner looks for |
|---|---|---|---|
| `x402` | x402 | Created by Coinbase; since 2026 governed by the x402 Foundation at the Linux Foundation | HTTP 402 with x402 payment headers on `/`, `/api` or `/api/v1`, or a listing in Coinbase's x402 Bazaar |
| `mpp` | Machine Payments Protocol | Tempo and Stripe | `/openapi.json` with `x-payment-info` on operations that cost money |
| `ucp` | Universal Commerce Protocol | Google with Shopify and a long list of retailers and platforms | `/.well-known/ucp` with `protocol_version` and `services` |
| `acp` | Agentic Commerce Protocol | OpenAI and Stripe (Apache 2.0) | `/.well-known/acp.json` with `protocol.name` "acp", version, `api_base_url`, transports and `capabilities.services` |
| `ap2` | Agent Payments Protocol | Google (v0.2) | An AP2 extension, with a role, inside the A2A Agent Card. Opt-in in the scanner. |

## In one line each

- **x402**: a server answers an unpaid request with HTTP 402; the client pays and retries. Built for paying per request: an API call, a page, an MCP tool call. Cloudflare's Monetization Gateway (beta since 30 Sep 2026) charges agents this way.
- **MPP**: also HTTP 402, for charging per API request, tool call or piece of content, with the price advertised in the OpenAPI document.
- **UCP**: the shopping journey for agents: catalog search, cart, identity linking, checkout, orders. Discovery at `/.well-known/ucp`.
- **ACP**: checkout between a buyer's agent and a merchant, including passing payment credentials safely. Behind checkout inside ChatGPT.
- **AP2**: proof of what the user authorised (mandates as verifiable credentials) when an agent pays on their behalf. Rides on A2A.

## What to tell a client

- **A local service or lead-generation site:** none of these apply. The scanner shows `neutral`, which costs nothing.
- **An online shop:** the realistic route is through the shop platform or payment provider (Shopify, Stripe and others are building these in). Do not hand-write a `/.well-known/ucp` or `acp.json` for a store that cannot take an agent's order; "Publish only what is real" applies here more than anywhere.
- **An API or content business that wants to charge agents per request:** x402 or MPP, usually through a gateway rather than custom code.

Adoption on 23 Nov 2026 (Radar, 114,182 domains): UCP 5.00%, ACP 0.03%, MPP 0.01%, x402 0.01%, AP2 under 0.01%. See `adoption-stats.md`.

## Sources

- [x402](https://x402.org/) and [Linux Foundation: x402 Foundation launch, 2 Apr 2026](https://www.linuxfoundation.org/press/linux-foundation-is-launching-the-x402-foundation-and-welcoming-the-contribution-of-the-x402-protocol)
- [Machine Payments Protocol](https://mpp.dev/)
- [Universal Commerce Protocol](https://ucp.dev/)
- [Agentic Commerce Protocol](https://www.agenticcommerce.dev/)
- [Agent Payments Protocol](https://ap2-protocol.org/)
- [Cloudflare, Monetization Gateway beta, 30 Sep 2026](https://blog.cloudflare.com/monetization-gateway-beta/)
- [isitagentready.com check list](https://isitagentready.com/llms-full.txt)
