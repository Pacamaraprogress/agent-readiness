# Changelog

Each entry matches a [GitHub release](https://github.com/Pacamaraprogress/agent-readiness/releases), whose `agent-readiness.zip` is the file to upload to claude.ai or Claude Desktop.

## 2026.11.26

First release. The general agent-readiness material that used to sit beside the WebMCP build guide in [agent-ready](https://github.com/Pacamaraprogress/agent-ready) now has its own repository, rewritten and checked against the live scanner and the primary sources on 26 November 2026.

- `SKILL.md` with three modes: audit (official scanner first, then the script), fix (staged drafts, never overwriting site files) and reference. "Publish only what is real" is the first rule.
- `scripts/check_site.py`: Cloudflare's 24 checks, level estimate, verdicts for 25 AI bots with RFC 9309 matching, priority-page checks. Python 3.8+, standard library only. Offline tests in `tests/`.
- New references: `cloudflare-checks.md` (checks, levels, %, profiles, MCP and REST calls, changes since April 2026, known gaps), `aleyda-checklist-map.md` (where the checks fit in Aleyda Solis's checklist), `commerce-protocols.md`.
- Rewritten references: robots.txt and the AI bot list from each operator's own documentation; Content Signals with Cloudflare's `use` extension and managed robots.txt; Markdown for Agents as it works since October and November 2026; MCP Server Card location (spec vs scanner); AI Catalog vs ARD; Agent Skills v0.2.0; adoption figures from Cloudflare Radar for 23 November 2026, with caveats.
- Templates: robots.txt with a training opt-out group that keeps search and user fetches; Agent Skills index in the v0.2.0 format; MCP Server Card with the `$schema` the schema requires; AI Catalog with `host` and `displayName`.
- Audit checklist rebuilt around the levels and priority pages.
