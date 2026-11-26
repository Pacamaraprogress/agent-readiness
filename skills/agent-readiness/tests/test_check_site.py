"""Tests for scripts/check_site.py. Standard library only, no network.

Run from the skill folder:
    python3 -m unittest discover -s tests -v
"""

import hashlib
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "check_site.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import check_site as cs  # noqa: E402


# --------------------------------------------------------------------------- unit tests

class RobotsTests(unittest.TestCase):
    TEXT = """
# comment
User-agent: *
Disallow: /admin/
Allow: /admin/public
Disallow: /*.pdf$
Content-Signal: search=yes, ai-train=no, ai-input=yes

User-agent: GPTBot
User-agent: CCBot
Disallow: /

User-agent: ClaudeBot
Disallow: /private
Allow: /private/ok

Sitemap: https://example.com/sitemap.xml
Agentmap: /.well-known/ai-catalog.json
"""

    def setUp(self):
        self.robots = cs.Robots(self.TEXT)

    def test_groups_and_directives(self):
        self.assertEqual(len(self.robots.groups), 3)
        self.assertEqual(self.robots.groups[1].agents, ["gptbot", "ccbot"])
        self.assertEqual(self.robots.sitemaps, ["https://example.com/sitemap.xml"])
        self.assertEqual(self.robots.agentmaps, ["/.well-known/ai-catalog.json"])

    def test_wildcard_group_applies_to_unnamed_bots(self):
        self.assertTrue(self.robots.is_allowed("PerplexityBot", "/blog/post"))
        self.assertFalse(self.robots.is_allowed("PerplexityBot", "/admin/settings"))

    def test_longest_match_wins(self):
        self.assertTrue(self.robots.is_allowed("PerplexityBot", "/admin/public/page"))

    def test_end_anchor_and_wildcard(self):
        self.assertFalse(self.robots.is_allowed("Googlebot", "/files/report.pdf"))
        self.assertTrue(self.robots.is_allowed("Googlebot", "/files/report.pdf?x=1"))

    def test_named_group_replaces_wildcard_group(self):
        self.assertFalse(self.robots.is_allowed("GPTBot", "/blog/post"))
        self.assertFalse(self.robots.is_allowed("ccbot", "/"))
        # ClaudeBot has its own group, so /admin/ (from the * group) is not blocked for it.
        self.assertTrue(self.robots.is_allowed("ClaudeBot", "/admin/settings"))
        self.assertFalse(self.robots.is_allowed("ClaudeBot", "/private/x"))
        self.assertTrue(self.robots.is_allowed("ClaudeBot", "/private/ok/x"))

    def test_allow_wins_a_tie(self):
        robots = cs.Robots("User-agent: *\nDisallow: /page\nAllow: /page\n")
        self.assertTrue(robots.is_allowed("GPTBot", "/page"))

    def test_groups_with_the_same_agent_are_combined(self):
        robots = cs.Robots("User-agent: GPTBot\nDisallow: /a\n\nUser-agent: GPTBot\nDisallow: /b\n")
        self.assertFalse(robots.is_allowed("GPTBot", "/a"))
        self.assertFalse(robots.is_allowed("GPTBot", "/b"))
        self.assertTrue(robots.is_allowed("GPTBot", "/c"))

    def test_empty_disallow_counts_as_a_wildcard_rule(self):
        robots = cs.Robots("User-agent: *\nDisallow:\n")
        self.assertTrue(robots.has_wildcard_rules())
        self.assertTrue(robots.is_allowed("GPTBot", "/anything"))

    def test_no_robots_means_everything_allowed(self):
        self.assertTrue(cs.Robots("").is_allowed("GPTBot", "/"))

    def test_content_signals(self):
        self.assertEqual(self.robots.all_signals(),
                         [{"search": "yes", "ai-train": "no", "ai-input": "yes"}])
        self.assertEqual(cs.parse_content_signal("/docs/ ai-train=no,search=yes,use=reference"),
                         {"path": "/docs/", "ai-train": "no", "search": "yes", "use": "reference"})


class HeaderAndHtmlTests(unittest.TestCase):
    def test_link_header(self):
        links = cs.parse_link_header([
            '</.well-known/api-catalog>; rel="api-catalog", </index.md>; rel="alternate"; type="text/markdown"',
            '<https://example.com/wp-json/>; rel="https://api.w.org/"'])
        self.assertEqual([l["href"] for l in links],
                         ["/.well-known/api-catalog", "/index.md", "https://example.com/wp-json/"])
        self.assertEqual(links[0]["rel"], ["api-catalog"])
        self.assertEqual(links[1]["type"], "text/markdown")

    def test_page_parser(self):
        page = cs.parse_page("""<html><head><title>Hi</title>
            <meta name="robots" content="noindex"><link rel="canonical" href="/x">
            <script type="application/ld+json">{"@type":"Organization"}</script>
            <script>document.modelContext.registerTool({})</script></head>
            <body><h1>One</h1><p>four words of text</p>
            <form toolname="find_store" tooldescription="Find a store"></form></body></html>""")
        self.assertEqual(page.title, "Hi")
        self.assertEqual(page.meta["robots"], "noindex")
        self.assertEqual(page.link_hrefs("canonical"), ["/x"])
        self.assertEqual(page.jsonld, 1)
        self.assertEqual(page.h1, 1)
        self.assertEqual(page.words, 5)  # "One" + four words; script text is not counted
        self.assertEqual(page.forms[0]["toolname"], "find_store")

    def test_svcb_priority(self):
        self.assertEqual(cs.svcb_priority("1 mcp.example.com. alpn=h2"), 1)
        self.assertEqual(cs.svcb_priority("0 other.example.com."), 0)
        self.assertEqual(cs.svcb_priority("\\# 10 0001 00"), 1)

    def test_mcp_card_name(self):
        self.assertEqual(cs.mcp_card_name({"serverInfo": {"name": "a"}}), "a")
        self.assertEqual(cs.mcp_card_name({"name": "com.example/x"}), "com.example/x")
        self.assertEqual(cs.mcp_card_name({"servers": [{"server": {"name": "b"}}]}), "b")
        self.assertIsNone(cs.mcp_card_name({"title": "no name"}))


class LevelTests(unittest.TestCase):
    @staticmethod
    def make(*passing):
        ids = [cid for _k, _l, group in cs.CATEGORIES for cid in group]
        return {cid: {"status": "pass" if cid in passing else "fail"} for cid in ids}

    def test_levels(self):
        self.assertEqual(cs.estimate_level(self.make("robotsTxt"))[0], 0)
        self.assertEqual(cs.estimate_level(self.make("robotsTxt", "sitemap"))[0], 1)
        base = ("robotsTxt", "sitemap", "robotsTxtAiRules", "contentSignals")
        self.assertEqual(cs.estimate_level(self.make(*base))[0], 2)
        self.assertEqual(cs.estimate_level(self.make(*base + ("markdownNegotiation",)))[0], 3)
        lvl4 = base + ("markdownNegotiation", "agentSkills")
        self.assertEqual(cs.estimate_level(self.make(*lvl4))[0], 4)
        # One advanced option is not enough for level 5; two are.
        self.assertEqual(cs.estimate_level(self.make(*lvl4 + ("webBotAuth",)))[0], 4)
        self.assertEqual(cs.estimate_level(self.make(*lvl4 + ("webBotAuth", "authMd")))[0], 5)
        all_four = lvl4 + ("mcpServerCard", "a2aAgentCard", "apiCatalog", "oauthDiscovery")
        self.assertEqual(cs.estimate_level(self.make(*all_four))[0], 5)

    def test_score_leaves_out_informational_and_commerce(self):
        results = {"robotsTxt": {"status": "pass"}, "sitemap": {"status": "fail"},
                   "authMd": {"status": "pass"}, "ucp": {"status": "pass"},
                   "webMcp": {"status": "unableToCheck"}, "webBotAuth": {"status": "neutral"}}
        self.assertEqual(cs.score(results)["counted"], 2)
        self.assertEqual(cs.score(results)["percent"], 50)


# --------------------------------------------------------------------------- local test sites

SKILL_MD = b"---\nname: check-stock\ndescription: Check stock.\n---\nCall the API.\n"

GOOD_SITE = {
    "/robots.txt": ("text/plain", """User-agent: *
Disallow: /cart/
Content-Signal: search=yes, ai-input=yes, ai-train=no

User-agent: GPTBot
Disallow: /

Sitemap: {origin}/sitemap.xml
"""),
    "/sitemap.xml": ("application/xml", """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{origin}/</loc></url><url><loc>{origin}/pricing</loc></url></urlset>"""),
    "/": ("text/html", """<html><head><title>Example</title><link rel="canonical" href="{origin}/">
<script type="application/ld+json">{{"@type":"Organization","name":"Example"}}</script></head>
<body><h1>Example</h1><p>{words}</p></body></html>"""),
    "/pricing": ("text/html", """<html><head><title>Pricing</title><meta name="robots" content="noindex">
</head><body><h1>Pricing</h1><p>Plans start here.</p></body></html>"""),
    "/llms.txt": ("text/plain", "# Example\n\n- [Pricing]({origin}/pricing): plans\n"),
    "/.well-known/api-catalog": ("application/linkset+json",
                                 '{{"linkset":[{{"anchor":"{origin}/api","service-desc":[{{"href":"{origin}/openapi.json"}}]}}]}}'),
    "/.well-known/agent-skills/check-stock/SKILL.md": ("text/markdown", SKILL_MD.decode()),
    "/.well-known/agent-skills/index.json": ("application/json", json.dumps({
        "$schema": "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
        "skills": [{"name": "check-stock", "type": "skill-md", "description": "Check stock.",
                    "url": "/.well-known/agent-skills/check-stock/SKILL.md",
                    "digest": "sha256:" + hashlib.sha256(SKILL_MD).hexdigest()}]}).replace("{", "{{").replace("}", "}}")),
    "/.well-known/ai-catalog.json": ("application/ai-catalog+json", """{{"specVersion":"1.0","entries":[
{{"identifier":"urn:air:example.com:mcp:catalog","type":"application/mcp-server-card+json",
"url":"/mcp/server-card"}}]}}"""),
    "/mcp/server-card": ("application/mcp-server-card+json", '{{"name":"com.example/catalog","version":"1.0.0"}}'),
    "/.well-known/oauth-protected-resource": ("application/json",
                                              '{{"resource":"{origin}/api","authorization_servers":["{origin}"]}}'),
    "/.well-known/oauth-authorization-server": ("application/json",
                                                '{{"issuer":"{origin}","token_endpoint":"{origin}/token"}}'),
}


def make_handler(site):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            origin = "http://%s:%d" % self.server.server_address[:2]
            accept = self.headers.get("Accept", "")
            if path == "/" and site is GOOD_SITE:
                if "text/markdown" in accept:
                    return self.send(200, "text/markdown", "# Example\n\nShort.\n",
                                     {"Vary": "Accept"})
                extra = {"Link": '</.well-known/api-catalog>; rel="api-catalog"', "Vary": "Accept"}
            else:
                extra = {}
            if path in site:
                ctype, body = site[path]
                body = body.format(origin=origin, words="word " * 200)
                return self.send(200, ctype, body, extra)
            self.send(404, "text/html", "<html><body>Not found</body></html>")

        def send(self, status, ctype, body, extra=None):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(data)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)
    return Handler


class Server(ThreadingHTTPServer):
    request_queue_size = 64  # the checker opens up to 8 connections at once


class LocalSite(object):
    def __init__(self, site):
        self.server = Server(("127.0.0.1", 0), make_handler(site))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return "http://127.0.0.1:%d" % self.server.server_address[1]

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def statuses(report):
    return {cid: r["status"] for group in report["checks"].values() for cid, r in group.items()}


class IntegrationTests(unittest.TestCase):
    def test_good_site(self):
        with LocalSite(GOOD_SITE) as origin:
            report = cs.Checker(origin, cs.Fetcher(timeout=5), dns=False, pages=["/pricing"]).run()
        st = statuses(report)
        for cid in ("robotsTxt", "sitemap", "linkHeaders", "markdownNegotiation", "robotsTxtAiRules",
                    "contentSignals", "apiCatalog", "agentSkills", "ard", "oauthDiscovery",
                    "oauthProtectedResource"):
            self.assertEqual(st[cid], "pass", (cid, report["checks"]))
        self.assertEqual(st["dnsAid"], "skipped")
        self.assertEqual(st["webBotAuth"], "neutral")
        self.assertEqual(st["mcpServerCard"], "fail")
        self.assertIn("SEP-2127", " ".join(report["checks"]["discovery"]["mcpServerCard"]["warnings"]))
        self.assertEqual(st["webMcp"], "unableToCheck")
        self.assertEqual(st["ucp"], "neutral")
        self.assertNotIn("warnings", report["checks"]["discovery"]["agentSkills"])  # digest matched
        # Level 4 (API Catalog + Agent Skills); level 5 needs 2 of 3 advanced options, only auth metadata passes.
        self.assertEqual(report["level"], 4)
        bots = {b["bot"]: b for b in report["extras"]["aiBotAccess"]["bots"]}
        self.assertFalse(bots["GPTBot"]["paths"]["/"])
        self.assertTrue(bots["GPTBot"]["ownGroup"])
        self.assertTrue(bots["ClaudeBot"]["paths"]["/"])
        pages = {p["url"].rsplit("/", 1)[-1]: p for p in report["extras"]["pages"]}
        self.assertTrue(pages["pricing"]["noindex"])
        self.assertFalse(pages[""]["noindex"])
        self.assertEqual(pages[""]["jsonLdBlocks"], 1)
        self.assertTrue(pages[""]["markdown"])
        self.assertTrue(report["extras"]["llmsTxt"]["found"])
        text = cs.render_text(report)
        self.assertIn("Estimated level: 4 of 5, Agent-Integrated", text)
        self.assertIn("NOINDEX", text)

    def test_bare_site(self):
        with LocalSite({}) as origin:
            report = cs.Checker(origin, cs.Fetcher(timeout=5), dns=False).run()
        st = statuses(report)
        self.assertEqual(report["level"], 0)
        self.assertEqual(st["robotsTxt"], "fail")
        self.assertEqual(st["sitemap"], "fail")
        self.assertEqual(st["x402"], "neutral")
        self.assertFalse(report["extras"]["llmsTxt"]["found"])
        # A 404 robots.txt means no rules, so every bot is allowed.
        self.assertTrue(all(all(b["paths"].values()) for b in report["extras"]["aiBotAccess"]["bots"]))

    def test_robots_served_as_html_fails(self):
        site = {"/robots.txt": ("text/html", "<html>User-agent: *</html>")}
        with LocalSite(site) as origin:
            report = cs.Checker(origin, cs.Fetcher(timeout=5), dns=False, only=["robotsTxt"]).run()
        self.assertEqual(statuses(report), {"robotsTxt": "fail"})
        self.assertIn("text/plain", report["checks"]["discoverability"]["robotsTxt"]["message"])

    def test_unreachable_site(self):
        report = cs.Checker("http://127.0.0.1:9", cs.Fetcher(timeout=2), dns=False).run()
        self.assertEqual(report["level"], 0)
        self.assertTrue(report["extras"]["aiBotAccess"]["robotsUnreachable"])

    def test_cli_json_and_fail_under(self):
        with LocalSite(GOOD_SITE) as origin:
            proc = subprocess.run([sys.executable, SCRIPT, origin, "--no-dns", "--json",
                                   "--fail-under", "5"], capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["level"], 4)
            proc = subprocess.run([sys.executable, SCRIPT, origin, "--no-dns", "--profile", "content"],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("API Catalog", proc.stdout)
        proc = subprocess.run([sys.executable, SCRIPT, "https://example.com", "--only", "nope"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
