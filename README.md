# agent-readiness: a Claude skill for AI agent readiness audits

A free Claude skill that checks **how ready a website is for AI agents and AI crawlers**, explains what each result means for that kind of site, and writes the fixes. It runs in claude.ai, Claude Desktop and Claude Code. MIT licensed.

**[Download the latest zip](https://github.com/Pacamaraprogress/agent-readiness/releases/latest/download/agent-readiness.zip)** · [Releases](https://github.com/Pacamaraprogress/agent-readiness/releases) · [Changelog](CHANGELOG.md) · [Türkçe](#türkçe)

## What it does

- **Audit.** Runs Cloudflare's Agent Readiness scanner ([isitagentready.com](https://isitagentready.com/)) through its MCP server or API, then adds what the scanner does not show: a verdict for each of 25 AI bots under your robots.txt, and checks on your priority pages (indexable, facts in the raw HTML, client-side rendering, Markdown version). The result is an ordered fix list, not a score.
- **Fix.** Asks for the site type and the owner's policy on AI search, AI answers and training, then writes robots.txt, Content Signals, Markdown negotiation rules and, only where something real exists behind them, discovery files: API Catalog, MCP Server Card, AI Catalog / ARD, Agent Skills index. Drafts go to a staging folder; nothing on the site is overwritten.
- **Explain.** Answers "what is X" and "should I bother with Y" with the status of each standard (RFC, IETF draft, proposal, vendor feature), who reads it, adoption numbers with dates, and the primary source.

The technical work is placed inside [Aleyda Solis's AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/): the skill covers the steps about retrievable, extractable priority pages and machine-readable commercial information, and says plainly that a readiness level is not AI visibility.

## The checker script

`skills/agent-readiness/scripts/check_site.py` runs the same 24 checks as Cloudflare's scanner, estimates the level, and adds the per-bot and per-page facts. Python 3.8 or newer, standard library only, GET requests only.

```bash
python3 skills/agent-readiness/scripts/check_site.py https://example.com --page /pricing --page /contact
python3 skills/agent-readiness/scripts/check_site.py https://example.com --profile content --json --out report.json
python3 skills/agent-readiness/scripts/check_site.py https://example.com --fail-under 3   # exit 1 below level 3, for CI
```

The official scanner stays the reference: when the two disagree, report the scanner's result. Known differences (WebMCP needs a real browser, for example) are listed in `references/cloudflare-checks.md`. Tests run offline against a local server:

```bash
cd skills/agent-readiness && python3 -m unittest discover -s tests
```

## Levels (Cloudflare's rules, November 2026)

| Level | Name | Needs |
|---|---|---|
| 0 | Not Ready | fewer than 2 of robots.txt, sitemap, Link headers |
| 1 | Basic Web Presence | 2 of those 3 |
| 2 | Bot-Aware | + AI bot rules + Content Signals |
| 3 | Agent-Readable | + Markdown content negotiation |
| 4 | Agent-Integrated | + an MCP Server Card, A2A Agent Card, Agent Skills index or API Catalog |
| 5 | Agent-Native | + 2 of 3: Web Bot Auth, all four level-4 items, auth metadata for agents |

Most content sites can reach level 3. Level 4 needs something an agent can call or install; the skill will not invent one to pass a check.

## Install

### claude.ai and Claude Desktop

1. Download **[agent-readiness.zip](https://github.com/Pacamaraprogress/agent-readiness/releases/latest/download/agent-readiness.zip)**. Leave it zipped.
2. In Claude, open **Customize → Skills**, click **+**, choose **Upload skill** and pick the zip.
3. Code execution must be turned on in Settings (the checker script needs it).

To update, download the zip again from the same link and upload it again.

### Claude Code: as a plugin

```
/plugin marketplace add Pacamaraprogress/agent-readiness
/plugin install agent-readiness@agent-readiness
```

To update:

```
/plugin marketplace update agent-readiness
/plugin update agent-readiness@agent-readiness
```

### Claude Code: copy by hand

```bash
git clone https://github.com/Pacamaraprogress/agent-readiness.git
cp -R agent-readiness/skills/agent-readiness ~/.claude/skills/
```

## Try it

- "Is example.com agent ready? It's a local plumbing business; check the homepage, /services and /areas."
- "Which AI bots does our robots.txt block, and is any of that by accident?"
- "We want to stay in ChatGPT and Perplexity answers but opt out of training. Write the robots.txt."
- "Set up Markdown for agents on our nginx docs site."
- "Do we need an MCP Server Card? We have a public REST API but no MCP server."
- "What is the difference between ai-catalog.json and ard.json?"

## Good to know

- **Readiness is not visibility.** A level 5 site can be missing from AI answers. Citations are measured with prompt sampling, not with this scanner.
- **Publish only what is real.** Discovery files are promises to agents. An empty catalog or a card for a server that does not run helps nobody.
- **A robots.txt rule is not a block.** Some user-triggered fetchers say robots.txt may not apply to them, and a CDN can block bots that robots.txt allows.
- Facts, dates and adoption numbers were checked on 26 November 2026. The scanner changed several times in 2026; re-check before quoting.
- Not affiliated with Cloudflare or with Aleyda Solis. The checklist is credited and linked, not copied.
- Building in-page WebMCP tools is a separate job: see [agent-ready](https://github.com/Pacamaraprogress/agent-ready).

## What's inside

```
skills/agent-readiness/
├── SKILL.md                          how Claude uses the skill
├── scripts/check_site.py             the checker (standard library only)
├── tests/test_check_site.py          offline tests
├── references/
│   ├── cloudflare-checks.md          the 24 checks, levels, %, MCP and API calls
│   ├── aleyda-checklist-map.md       where the checks fit in the 12-step checklist
│   ├── discoverability.md            robots.txt, 25 AI bots, sitemap, Link headers, DNS-AID
│   ├── bot-access-control.md         Content Signals, Web Bot Auth, blocking vs throttling
│   ├── content-accessibility.md      raw-HTML facts, Markdown negotiation, llms.txt
│   ├── protocol-discovery.md         API Catalog, MCP Server Card, AI Catalog / ARD, skills, OAuth
│   ├── commerce-protocols.md         x402, MPP, UCP, ACP, AP2 in short
│   ├── adoption-stats.md             Cloudflare Radar figures with dates and caveats
│   └── agents-md.md                  AGENTS.md for code repositories
└── assets/
    ├── checklists/audit-checklist.md
    └── templates/                    robots.txt, llms.txt, AGENTS.md, discovery JSON files
```

## Feedback

Ran it on a site and the result differed from the official scanner? Please [open an issue](https://github.com/Pacamaraprogress/agent-readiness/issues) with the URL (if public), both results and the date.

## Sources

- [isitagentready.com](https://isitagentready.com/) and [Introducing the Agent Readiness Score](https://blog.cloudflare.com/agent-readiness/) (Cloudflare, April 2026)
- [Cloudflare Radar, AI Insights](https://radar.cloudflare.com/ai-insights)
- [Aleyda Solis, AI Search Optimization Checklist](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/)
- [RFC 9309, Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309) · [Content Signals](https://contentsignals.org/) · [RFC 9727, API Catalog](https://www.rfc-editor.org/rfc/rfc9727)

## License

[MIT](LICENSE).

---

## Türkçe

**agent-readiness**, bir web sitesinin **yapay zeka ajanlarına ve AI tarayıcılarına ne kadar hazır olduğunu** kontrol eden ücretsiz bir Claude skill'i. claude.ai, Claude Desktop ve Claude Code'da çalışır. MIT lisanslıdır.

**Ne yapar:**

- **Denetim.** Cloudflare'in Agent Readiness tarayıcısını ([isitagentready.com](https://isitagentready.com/)) MCP sunucusu ya da API üzerinden çalıştırır. Tarayıcının göstermediklerini ekler: robots.txt'nize göre 25 AI botunun her biri için izin verildi mi, engellendi mi; öncelikli sayfalarınızda indekslenebilirlik, bilgilerin ham HTML'de olup olmadığı, JavaScript'le oluşturulan içerik ve Markdown sürümü. Sonuç bir puan değil, sıralı bir düzeltme listesidir.
- **Düzeltme.** Sitenin türünü ve sahibinin AI arama, AI cevapları ve model eğitimi konusundaki tercihini sorar. robots.txt, Content Signals ve Markdown kurallarını yazar. API Catalog, MCP Server Card, AI Catalog / ARD ve Agent Skills dosyalarını yalnızca arkasında gerçekten çalışan bir şey varsa hazırlar. Taslaklar ayrı bir klasöre yazılır, sitedeki hiçbir dosyanın üzerine yazılmaz.
- **Açıklama.** "X nedir, Y ile uğraşmaya değer mi" sorularını standardın durumu (RFC, IETF taslağı, öneri), kimin kullandığı, tarihli benimsenme oranları ve birincil kaynakla cevaplar.

Teknik iş, [Aleyda Solis'in AI Search Optimization Checklist'i](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist/) içine yerleştirilmiştir. Bir hazırlık seviyesinin AI görünürlüğü olmadığını açıkça söyler.

**Kontrol betiği:** `skills/agent-readiness/scripts/check_site.py`, Cloudflare'in 24 kontrolünü çalıştırır, seviyeyi tahmin eder ve bot ve sayfa bilgilerini ekler. Python 3.8+, ek paket gerekmez, yalnızca GET isteği gönderir. Resmi tarayıcıyla sonuç farklıysa resmi tarayıcının sonucu raporlanır.

**Kurulum:** [agent-readiness.zip](https://github.com/Pacamaraprogress/agent-readiness/releases/latest/download/agent-readiness.zip) dosyasını indirin, açmadan Claude'da **Customize → Skills → + → Upload skill** ile yükleyin. Ayarlarda kod çalıştırma açık olmalı. Claude Code için yukarıdaki `/plugin` komutlarını kullanın.

**Bilmeniz gerekenler:** Hazırlık seviyesi AI cevaplarında görünürlük demek değildir. Keşif dosyaları ajanlara verilen sözlerdir; gerçekte olmayan bir şeyi yayınlamayın. Bilgiler 26 Kasım 2026'da kontrol edildi. Cloudflare veya Aleyda Solis ile bir bağı yoktur. Sayfa içi WebMCP araçları kurmak ayrı bir iştir: [agent-ready](https://github.com/Pacamaraprogress/agent-ready).

Dosyalar İngilizcedir; Claude sizin yazdığınız dilde cevap verir.
