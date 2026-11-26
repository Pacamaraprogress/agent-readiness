#!/usr/bin/env python3
"""Agent-readiness check for one website. Python 3.8+, standard library only.

It runs the checks of Cloudflare's Agent Readiness scanner (isitagentready.com,
24 checks, levels 0-5, as documented on 26 Nov 2026) from your own machine and
adds three things the scanner does not report:

  * which named AI crawlers robots.txt allows or blocks, per URL;
  * per-page facts for your priority URLs (status, noindex, canonical, JSON-LD,
    text present in the raw HTML, Markdown negotiation);
  * whether /llms.txt exists (the scanner dropped that check in 2026).

The official scanner stays the reference. Use this script when the scanner is
not reachable, for sites it cannot see (staging, localhost), for many pages at
once, and for the per-bot view.

It only sends GET requests. It never posts to an MCP endpoint or a form. The
DNS-AID check asks Cloudflare's public DNS-over-HTTPS resolver about the
site's host name; pass --no-dns to skip it.

Usage:
  python3 check_site.py https://example.com
  python3 check_site.py https://example.com --page /pricing --page /contact
  python3 check_site.py https://example.com --json --out report.json
  python3 check_site.py https://example.com --fail-under 2      # for CI
"""

import argparse
import datetime
import gzip
import hashlib
import http.client
import io
import json
import re
import socket
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

VERSION = "2026.11.26"
DEFAULT_UA = ("agent-readiness-check/%s (+https://github.com/Pacamaraprogress/agent-readiness)"
              % VERSION)
MAX_BYTES = 5 * 1024 * 1024

# Named AI user agents, from each operator's own crawler page (checked 26 Nov 2026).
# purpose: training, search (indexing for answers), user (fetches when a user asks),
# control (a robots.txt token only, not a crawler). The operators of the bots in
# MAY_IGNORE_ROBOTS say robots.txt may not apply to user-requested fetches.
AI_BOTS = [
    ("GPTBot", "OpenAI", "training"),
    ("OAI-SearchBot", "OpenAI", "search"),
    ("ChatGPT-User", "OpenAI", "user"),
    ("ClaudeBot", "Anthropic", "training"),
    ("Claude-SearchBot", "Anthropic", "search"),
    ("Claude-User", "Anthropic", "user"),
    ("PerplexityBot", "Perplexity", "search"),
    ("Perplexity-User", "Perplexity", "user"),
    ("Googlebot", "Google", "search"),
    ("Google-Extended", "Google", "control"),
    ("Bingbot", "Microsoft", "search"),
    ("Applebot", "Apple", "search"),
    ("Applebot-Extended", "Apple", "control"),
    ("Meta-ExternalAgent", "Meta", "training"),
    ("Meta-WebIndexer", "Meta", "search"),
    ("Meta-ExternalFetcher", "Meta", "user"),
    ("Amazonbot", "Amazon", "training"),
    ("Amzn-SearchBot", "Amazon", "search"),
    ("Amzn-User", "Amazon", "user"),
    ("MistralAI-Training", "Mistral", "training"),
    ("MistralAI-Index", "Mistral", "search"),
    ("MistralAI-User", "Mistral", "user"),
    ("DuckAssistBot", "DuckDuckGo", "search"),
    ("CCBot", "Common Crawl", "training"),
    ("Bytespider", "ByteDance", "training"),
]
MAY_IGNORE_ROBOTS = {"ChatGPT-User", "Perplexity-User", "Meta-ExternalFetcher"}

CATEGORIES = [
    ("discoverability", "Discoverability",
     ["robotsTxt", "sitemap", "linkHeaders", "dnsAid"]),
    ("contentAccessibility", "Content Accessibility",
     ["markdownNegotiation", "searchForAgents"]),
    ("botAccessControl", "Bot Access Control",
     ["robotsTxtAiRules", "contentSignals", "webBotAuth"]),
    ("discovery", "API, Auth, MCP & Skill Discovery",
     ["apiCatalog", "oauthDiscovery", "oauthProtectedResource", "authMd",
      "mcpServerCard", "a2aAgentCard", "agentSkills", "webMcp", "ard",
      "personalAgentProtocol"]),
    ("commerce", "Commerce (optional, never scored)",
     ["x402", "mpp", "ucp", "acp", "ap2"]),
]

LABELS = {
    "robotsTxt": "robots.txt", "sitemap": "Sitemap", "linkHeaders": "Link headers",
    "dnsAid": "DNS for AI discovery", "markdownNegotiation": "Markdown negotiation",
    "searchForAgents": "Search for Agents", "robotsTxtAiRules": "AI bot rules",
    "contentSignals": "Content Signals", "webBotAuth": "Web Bot Auth",
    "apiCatalog": "API Catalog", "oauthDiscovery": "OAuth discovery",
    "oauthProtectedResource": "OAuth Protected Resource", "authMd": "auth.md",
    "mcpServerCard": "MCP Server Card", "a2aAgentCard": "A2A Agent Card",
    "agentSkills": "Agent Skills", "webMcp": "WebMCP", "ard": "ARD / AI Catalog",
    "personalAgentProtocol": "Personal Agent Protocol", "x402": "x402",
    "mpp": "MPP", "ucp": "UCP", "acp": "ACP", "ap2": "AP2",
}

# Checks that the scanner reports but leaves out of the percentage.
INFORMATIONAL = {"searchForAgents", "webBotAuth", "oauthDiscovery",
                 "oauthProtectedResource", "authMd", "personalAgentProtocol"}
COMMERCE = {"x402", "mpp", "ucp", "acp", "ap2"}

PROFILES = {
    "all": None,
    "content": {"robotsTxt", "sitemap", "linkHeaders", "dnsAid", "markdownNegotiation",
                "searchForAgents", "robotsTxtAiRules", "contentSignals"},
}

LEVEL_NAMES = ["Not Ready", "Basic Web Presence", "Bot-Aware", "Agent-Readable",
               "Agent-Integrated", "Agent-Native"]

# The relation types the scanner accepts (its fix skill lists exactly these four).
AGENT_LINK_RELS = {"service-desc", "service-doc", "describedby", "api-catalog"}


# --------------------------------------------------------------------------- HTTP

class Response(object):
    def __init__(self, url, status=None, final_url=None, headers=None, body=b"",
                 truncated=False, error=None):
        self.url = url
        self.status = status
        self.final_url = final_url or url
        self.headers = headers
        self.body = body
        self.truncated = truncated
        self.error = error

    @property
    def ok(self):
        return self.status is not None and 200 <= self.status < 300

    def header(self, name, default=""):
        if self.headers is None:
            return default
        value = self.headers.get(name)
        return default if value is None else value

    def header_all(self, name):
        if self.headers is None:
            return []
        return self.headers.get_all(name) or []

    @property
    def content_type(self):
        return self.header("Content-Type").split(";")[0].strip().lower()

    def text(self):
        charset = "utf-8"
        match = re.search(r"charset=([\w-]+)", self.header("Content-Type"), re.I)
        if match:
            charset = match.group(1)
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self):
        try:
            return json.loads(self.text())
        except ValueError:
            return None

    def describe(self):
        if self.error:
            return "request failed (%s)" % self.error
        return "HTTP %s %s" % (self.status, self.content_type or "(no content type)")


class Fetcher(object):
    """GET-only HTTP client with a small cache."""

    def __init__(self, timeout=10.0, user_agent=DEFAULT_UA, max_bytes=MAX_BYTES):
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.cache = {}
        self.count = 0
        self.lock = threading.Lock()
        self.context = ssl.create_default_context()

    def prefetch(self, requests, workers=8):
        """Warm the cache in parallel. `requests` holds (url, accept) pairs."""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda item: self.get(item[0], accept=item[1]), requests))

    def get(self, url, accept=None, extra_headers=None):
        key = (url, accept, tuple(sorted((extra_headers or {}).items())))
        if key in self.cache:
            return self.cache[key]
        headers = {"User-Agent": self.user_agent}
        if accept:
            headers["Accept"] = accept
        headers.update(extra_headers or {})
        resp = self._request(url, headers)
        if resp.error is not None:  # one retry for resets and timeouts
            resp = self._request(url, headers)
        if resp.headers is not None and resp.header("Content-Encoding").lower() == "gzip":
            try:
                resp.body = _gunzip(resp.body, self.max_bytes)
            except (OSError, EOFError):
                pass
        self.cache[key] = resp
        return resp

    def _request(self, url, headers):
        request = urllib.request.Request(url, headers=headers, method="GET")
        with self.lock:
            self.count += 1
        try:
            handle = urllib.request.urlopen(request, timeout=self.timeout, context=self.context)
            with handle:
                raw = handle.read(self.max_bytes + 1)
                resp = Response(url, handle.status, handle.geturl(), handle.headers,
                                raw[:self.max_bytes], len(raw) > self.max_bytes)
        except urllib.error.HTTPError as err:
            try:
                raw = err.read(self.max_bytes) if err.fp else b""
            except Exception:  # body of an error page is optional
                raw = b""
            resp = Response(url, err.code, err.geturl() or url, err.headers, raw)
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError,
                http.client.HTTPException, ValueError, OSError) as err:
            reason = getattr(err, "reason", err)
            resp = Response(url, error=str(reason) or err.__class__.__name__)
        return resp


def _gunzip(data, limit):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as handle:
        return handle.read(limit)


# --------------------------------------------------------------------------- robots.txt

class RobotsGroup(object):
    def __init__(self):
        self.agents = []
        self.rules = []     # (allow: bool, pattern: str)
        self.signals = []   # parsed Content-Signal lines


class Robots(object):
    """robots.txt parsed as RFC 9309 describes, plus Content-Signal lines."""

    def __init__(self, text):
        self.groups = []
        self.sitemaps = []
        self.agentmaps = []
        self.global_signals = []
        self.parse(text or "")

    def parse(self, text):
        current = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = RobotsGroup()
                    self.groups.append(current)
                current.agents.append(value.split("/")[0].strip().lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key in ("allow", "disallow"):
                # An empty Disallow still counts as a rule (it allows everything).
                if current is not None:
                    current.rules.append((key == "allow", value))
            elif key == "sitemap":
                self.sitemaps.append(value)
            elif key == "agentmap":
                self.agentmaps.append(value)
            elif key == "content-signal":
                signal = parse_content_signal(value)
                if current is None:
                    self.global_signals.append(signal)
                else:
                    current.signals.append(signal)

    def groups_for(self, token):
        token = token.lower()
        named = [g for g in self.groups if token in g.agents]
        if named:
            return named
        return [g for g in self.groups if "*" in g.agents]

    def named_bots(self):
        names = set()
        for group in self.groups:
            names.update(a for a in group.agents if a != "*")
        return names

    def has_wildcard_rules(self):
        return any("*" in g.agents and g.rules for g in self.groups)

    def all_signals(self):
        found = list(self.global_signals)
        for group in self.groups:
            found.extend(group.signals)
        return found

    def is_allowed(self, token, path):
        """True if `token` may fetch `path`: longest match wins, allow wins a tie."""
        rules = []
        for group in self.groups_for(token):
            rules.extend(group.rules)
        best = None  # (length, allow)
        for allow, pattern in rules:
            if not pattern:
                continue
            if _robots_match(pattern, path):
                length = len(pattern)
                if best is None or length > best[0] or (length == best[0] and allow):
                    best = (length, allow)
        return True if best is None else best[1]


def _robots_match(pattern, path):
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.match(regex + ("$" if anchored else ""), path) is not None


def parse_content_signal(value):
    """`search=yes, ai-train=no` -> {'search': 'yes', 'ai-train': 'no'}.

    A leading path (`/docs/ ai-train=no`) is kept under the key 'path'."""
    result = {}
    match = re.match(r"^(/\S*)\s+(.*)$", value)
    if match:
        result["path"] = match.group(1)
        value = match.group(2)
    for key, val in re.findall(r"([A-Za-z][\w-]*)\s*=\s*([\w-]+)", value):
        result[key.lower()] = val.lower()
    return result


# --------------------------------------------------------------------------- headers and HTML

def parse_link_header(values):
    """RFC 8288 Link header values -> [{'href':..., 'rel': [...], 'type':...}]."""
    links = []
    for value in values:
        for part in re.findall(r'<[^>]*>(?:\s*;\s*[^,;=]+(?:=(?:"[^"]*"|[^,;]*))?)*', value):
            href = part[1:part.index(">")]
            params = {}
            for name, quoted, bare in re.findall(r';\s*([^=;,\s]+)\s*(?:=\s*(?:"([^"]*)"|([^;,]*)))?',
                                                 part[part.index(">") + 1:]):
                params[name.lower()] = (quoted or bare or "").strip()
            links.append({"href": href, "rel": params.get("rel", "").lower().split(),
                          "type": params.get("type", "").lower()})
    return links


class PageParser(HTMLParser):
    """Collects the page facts the checks need from raw (unrendered) HTML."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.title = ""
        self.meta = {}
        self.links = []
        self.jsonld = 0
        self.h1 = 0
        self.forms = []
        self.scripts = 0
        self.words = 0
        self._skip = 0
        self._in_title = False
        self.script_text = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name:
                self.meta.setdefault(name, a.get("content", ""))
        elif tag == "link":
            self.links.append({"rel": a.get("rel", "").lower().split(), "href": a.get("href", ""),
                               "type": a.get("type", "").lower()})
        elif tag == "script":
            self.scripts += 1
            self._skip += 1
            self._in_script = True
            if a.get("type", "").lower() == "application/ld+json":
                self.jsonld += 1
        elif tag in ("style", "noscript", "template"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "form":
            self.forms.append(a)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1
            if tag == "script":
                self._in_script = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_script:
            self.script_text.append(data)
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.words += len(data.split())

    def link_hrefs(self, rel):
        return [l["href"] for l in self.links if rel in l["rel"]]


def parse_page(text):
    parser = PageParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # malformed HTML must not stop the report
        pass
    return parser


# --------------------------------------------------------------------------- results

def result(status, message, details=None, warnings=None):
    out = {"status": status, "message": message}
    if details:
        out["details"] = details
    if warnings:
        out["warnings"] = warnings
    return out


def _json_obj(resp):
    data = resp.json() if resp.ok else None
    return data if isinstance(data, dict) else None


def _is_html(resp):
    return resp.content_type in ("text/html", "application/xhtml+xml")


# --------------------------------------------------------------------------- the checker

class Checker(object):
    def __init__(self, url, fetcher=None, dns=True, pages=(), profile="all", only=None):
        if "://" not in url:
            url = "https://" + url
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("not an http(s) URL: %s" % url)
        self.url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path or "/",
                                            parts.query, ""))
        self.origin = "%s://%s" % (parts.scheme, parts.netloc)
        self.host = parts.hostname or ""
        self.fetcher = fetcher or Fetcher()
        self.dns = dns
        self.pages = [urllib.parse.urljoin(self.origin + "/", p) for p in pages]
        wanted = PROFILES.get(profile)
        if only:
            wanted = set(only)
        self.wanted = wanted
        self.results = {}
        self._robots = None

    # shared fetches -----------------------------------------------------------
    def get(self, path_or_url, accept=None, headers=None):
        url = path_or_url if "://" in path_or_url else self.origin + path_or_url
        return self.fetcher.get(url, accept=accept, extra_headers=headers)

    @property
    def robots_resp(self):
        return self.get("/robots.txt")

    @property
    def robots(self):
        if self._robots is None:
            resp = self.robots_resp
            text = resp.text() if resp.ok and not _is_html(resp) else ""
            self._robots = Robots(text)
        return self._robots

    @property
    def home(self):
        return self.get(self.origin + "/")

    @property
    def page(self):
        return self.get(self.url)

    def page_html(self):
        resp = self.page
        return parse_page(resp.text()) if resp.ok and _is_html(resp) else parse_page("")

    # running --------------------------------------------------------------------
    WELL_KNOWN = [
        "/robots.txt", "/sitemap.xml", "/llms.txt", "/auth.md", "/openapi.json", "/api", "/api/v1",
        "/.well-known/http-message-signatures-directory", "/.well-known/openid-configuration",
        "/.well-known/oauth-authorization-server", "/.well-known/oauth-protected-resource",
        "/.well-known/mcp/server-cards.json", "/.well-known/mcp.json", "/.well-known/mcp/server-card.json",
        "/.well-known/agent-card.json", "/.well-known/agent-skills/index.json",
        "/.well-known/skills/index.json", "/.well-known/ai-catalog.json", "/.well-known/ard.json",
        "/.well-known/poppy.json", "/.well-known/ucp", "/.well-known/acp.json",
    ]

    def prefetch(self):
        items = [(self.origin + p, None) for p in self.WELL_KNOWN]
        items += [(self.origin + "/", None), (self.url, None), (self.url, "text/markdown"),
                  (self.origin + "/.well-known/api-catalog", "application/linkset+json"),
                  (self.origin + "/.well-known/search?q=contact", "text/markdown")]
        for page in self.pages:
            items += [(page, None), (page, "text/markdown")]
        wants_dns = self.wanted is None or "dnsAid" in self.wanted
        if self.dns and wants_dns and "." in self.host and not re.match(r"^[\d.]+$", self.host):
            for label in ("_index._agents", "_a2a._agents", "_mcp._agents"):
                for rtype in (64, 65):
                    items.append(("https://cloudflare-dns.com/dns-query?" + urllib.parse.urlencode(
                        {"name": "%s.%s" % (label, self.host), "type": rtype}), "application/dns-json"))
        self.fetcher.prefetch(items)

    def run(self):
        if self.wanted is None or len(self.wanted) > 3:
            self.prefetch()
        for _key, _label, ids in CATEGORIES:
            for cid in ids:
                if self.wanted is not None and cid not in self.wanted:
                    continue
                try:
                    self.results[cid] = getattr(self, "check_" + cid)()
                except Exception as err:  # one broken check must not hide the rest
                    self.results[cid] = result("unableToCheck", "check crashed: %r" % err)
        extras = {
            "aiBotAccess": self.extra_bot_access(),
            "pages": [self.extra_page(u) for u in [self.url] + self.pages],
            "llmsTxt": self.extra_llms_txt(),
        }
        level, missing = estimate_level(self.results)
        return {
            "tool": "agent-readiness check_site.py",
            "version": VERSION,
            "url": self.url,
            "origin": self.origin,
            "scannedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": level,
            "levelName": LEVEL_NAMES[level],
            "nextLevel": missing,
            "score": score(self.results),
            "checks": {key: {cid: self.results[cid] for cid in ids if cid in self.results}
                       for key, _label, ids in CATEGORIES},
            "extras": extras,
            "requests": self.fetcher.count,
            "partial": self.wanted is not None,
            "note": ("Estimate made with the published rules of Cloudflare's scanner. "
                     "Run https://isitagentready.com for the official result."),
        }

    # Discoverability ------------------------------------------------------------
    def check_robotsTxt(self):
        resp = self.robots_resp
        if not resp.ok:
            return result("fail", "/robots.txt: %s" % resp.describe())
        if resp.content_type != "text/plain":
            return result("fail", "/robots.txt is served as %s; it must be text/plain"
                          % (resp.content_type or "an unknown type"))
        if not self.robots.groups:
            return result("fail", "/robots.txt has no User-agent line")
        return result("pass", "/robots.txt found (%d groups, %d Sitemap lines)"
                      % (len(self.robots.groups), len(self.robots.sitemaps)))

    def check_sitemap(self):
        listed = self.robots.sitemaps[:3]
        candidates = listed or [self.origin + "/sitemap.xml"]
        checked = []
        for url in candidates:
            resp = self.get(url)
            kind, count, problem = inspect_sitemap(resp, url)
            checked.append({"url": url, "type": kind, "entries": count, "problem": problem})
            if kind:
                return result("pass", "%s is a valid %s with %s entries"
                              % (url, kind, count if count is not None else "an unknown number of"),
                              {"checked": checked})
        if listed:
            return result("pass", "robots.txt lists a sitemap (the scanner passes on that), "
                          "but it did not parse", {"checked": checked},
                          ["Fix the sitemap file: %s" % checked[0]["problem"]])
        return result("fail", "No Sitemap line in robots.txt and /sitemap.xml is not a sitemap "
                      "(%s)" % checked[0]["problem"], {"checked": checked})

    def check_linkHeaders(self):
        resp = self.home
        links = parse_link_header(resp.header_all("Link"))
        useful = [l for l in links if AGENT_LINK_RELS.intersection(l["rel"])]
        if useful:
            return result("pass", "Homepage Link header points to: %s"
                          % ", ".join("%s (%s)" % (l["href"], " ".join(l["rel"])) for l in useful),
                          {"links": links})
        if links:
            return result("fail", "Homepage sends Link headers, but none with relation service-desc, "
                          "service-doc, describedby or api-catalog", {"links": links})
        return result("fail", "Homepage sends no Link header")

    def check_dnsAid(self):
        if not self.dns:
            return result("skipped", "DNS lookups turned off (--no-dns)")
        if not self.host or re.match(r"^[\d.]+$|:", self.host) or self.host == "localhost":
            return result("skipped", "No public host name to look up")
        found, unsigned, tried = [], [], []
        for label in ("_index._agents", "_a2a._agents", "_mcp._agents"):
            name = "%s.%s" % (label, self.host)
            for rtype in (64, 65):  # SVCB, HTTPS
                tried.append("%s type %d" % (name, rtype))
                answer = doh_query(self.fetcher, name, rtype)
                if answer is None:
                    continue
                for record in answer.get("Answer") or []:
                    if record.get("type") in (64, 65) and svcb_priority(record.get("data", "")) > 0:
                        (found if answer.get("AD") else unsigned).append(
                            "%s %s" % (name, record.get("data", "")))
        if found:
            return result("pass", "DNSSEC-validated ServiceMode records: %s" % "; ".join(found))
        if unsigned:
            return result("fail", "Records found but not DNSSEC-validated: %s" % "; ".join(unsigned))
        return result("fail", "No SVCB/HTTPS records under _agents (draft-mozleywilliams-dnsop-dnsaid)",
                      {"queried": tried})

    # Content accessibility ------------------------------------------------------
    def check_markdownNegotiation(self):
        md = self.get(self.url, accept="text/markdown")
        if md.ok and md.content_type == "text/markdown":
            details = {"bytes": len(md.body)}
            html = self.page
            if html.ok and html.body:
                details["htmlBytes"] = len(html.body)
                details["markdownShareOfHtml"] = round(100.0 * len(md.body) / len(html.body), 1)
            warnings = []
            if "accept" not in md.header("Vary").lower():
                warnings.append("No 'Vary: Accept' header: a cache may serve Markdown to "
                                "browsers or HTML to agents")
            if md.header("Content-Signal"):
                details["contentSignalHeader"] = md.header("Content-Signal")
            return result("pass", "Accept: text/markdown returns text/markdown", details, warnings)
        return result("fail", "Accept: text/markdown returned %s" % md.describe())

    def check_searchForAgents(self):
        html = self.page_html()
        advertised = {k: v for k, v in html.meta.items() if k.startswith("agent:")}
        resp = self.get("/.well-known/search?q=contact", accept="text/markdown")
        details = {"metaTags": advertised} if advertised else None
        body = resp.text().lstrip() if resp.ok else ""
        if resp.ok and resp.content_type == "text/markdown" and (
                resp.header("Accept-Query") or body.startswith("# Search results for")):
            return result("pass", "/.well-known/search answers with Markdown results", details)
        return result("fail", "/.well-known/search?q=: %s" % resp.describe(), details)

    # Bot access control -----------------------------------------------------------
    def check_robotsTxtAiRules(self):
        if not self.robots.groups:
            return result("fail", "No usable robots.txt")
        known = {b[0].lower(): b[0] for b in AI_BOTS}
        named = sorted(known[a] for a in self.robots.named_bots() if a in known)
        if named:
            return result("pass", "Groups for AI bots: %s" % ", ".join(named))
        if self.robots.has_wildcard_rules():
            return result("pass", "No AI-specific groups; the User-agent: * rules apply to every "
                          "AI bot (the scanner accepts this)")
        return result("fail", "No AI bot groups and no wildcard rules")

    def check_contentSignals(self):
        signals = self.robots.all_signals()
        known = [s for s in signals if set(s) & {"ai-train", "search", "ai-input"}]
        if known:
            warnings = []
            for s in known:
                for k, v in s.items():
                    if k in ("ai-train", "search", "ai-input") and v not in ("yes", "no"):
                        warnings.append("%s=%s: values are yes or no" % (k, v))
            return result("pass", "Content-Signal: %s" % "; ".join(
                ", ".join("%s=%s" % kv for kv in s.items()) for s in known), None, warnings)
        return result("fail", "robots.txt has no Content-Signal line with ai-train, search or ai-input")

    def check_webBotAuth(self):
        resp = self.get("/.well-known/http-message-signatures-directory")
        if resp.status in (404, 410) or (resp.ok and _is_html(resp)):
            return result("neutral", "No key directory (only needed if this site runs a bot or agent)")
        data = _json_obj(resp)
        keys = data.get("keys") if data else None
        if isinstance(keys, list) and keys and all(isinstance(k, dict) and k.get("kty") for k in keys):
            warnings = []
            if resp.content_type != "application/http-message-signatures-directory+json":
                warnings.append("Content-Type is %s; expected "
                                "application/http-message-signatures-directory+json" % resp.content_type)
            return result("pass", "JWKS with %d key(s)" % len(keys), None, warnings)
        return result("fail", "Key directory: %s, not a valid JWKS" % resp.describe())

    # Protocol discovery -------------------------------------------------------------
    def check_apiCatalog(self):
        resp = self.get("/.well-known/api-catalog", accept="application/linkset+json")
        data = _json_obj(resp)
        linkset = data.get("linkset") if data else None
        if isinstance(linkset, list) and linkset and all(isinstance(e, dict) and e.get("anchor")
                                                         for e in linkset):
            warnings = []
            if resp.content_type != "application/linkset+json":
                warnings.append("Content-Type is %s; RFC 9727 expects application/linkset+json"
                                % resp.content_type)
            return result("pass", "linkset with %d API entr%s" % (len(linkset), "y" if len(linkset) == 1 else "ies"),
                          None, warnings)
        return result("fail", "/.well-known/api-catalog: %s" % (
            "no linkset array with anchors" if resp.ok else resp.describe()))

    def _oauth_as(self):
        for path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
            data = _json_obj(self.get(path))
            if data and data.get("issuer") and (data.get("authorization_endpoint") or data.get("token_endpoint")):
                return path, data
        return None, None

    def check_oauthDiscovery(self):
        path, data = self._oauth_as()
        if data:
            return result("pass", "%s (issuer %s)" % (path, data.get("issuer")))
        return result("fail", "No OAuth/OIDC metadata at /.well-known/openid-configuration or "
                      "/.well-known/oauth-authorization-server")

    def _prm(self):
        urls = []
        for value in self.page.header_all("WWW-Authenticate"):
            urls += re.findall(r'resource_metadata="([^"]+)"', value)
        urls.append(self.origin + "/.well-known/oauth-protected-resource")
        for url in urls:
            data = _json_obj(self.get(url))
            if data and data.get("resource") and isinstance(data.get("authorization_servers"), list):
                return url, data
        return None, None

    def check_oauthProtectedResource(self):
        url, data = self._prm()
        if data:
            return result("pass", "%s lists %d authorization server(s)"
                          % (url, len(data["authorization_servers"])))
        return result("fail", "No RFC 9728 metadata with resource and authorization_servers")

    def check_authMd(self):
        resp = self.get("/auth.md")
        have_file = resp.ok and not _is_html(resp)
        _url, prm = self._prm()
        _path, as_meta = self._oauth_as()
        have_agent_auth = bool(as_meta and as_meta.get("agent_auth"))
        if have_file and prm and have_agent_auth:
            return result("pass", "/auth.md, protected resource metadata and agent_auth all found")
        missing = [name for name, ok in (("/auth.md", have_file), ("protected resource metadata", prm),
                                         ("agent_auth in the authorization server metadata", have_agent_auth))
                   if not ok]
        return result("fail", "Missing: %s" % ", ".join(missing))

    def check_mcpServerCard(self):
        tried = []
        for path in ("/.well-known/mcp/server-cards.json", "/.well-known/mcp.json",
                     "/.well-known/mcp/server-card.json"):
            resp = self.get(path)
            tried.append("%s: %s" % (path, resp.describe()))
            name = mcp_card_name(resp.json() if resp.ok else None)
            if name:
                return result("pass", "%s describes %s" % (path, name))
        warnings = []
        catalog_cards = [e for e in self._catalog_entries() if "mcp-server-card" in str(e.get("type", ""))]
        for entry in catalog_cards[:3]:
            url = entry.get("url")
            if url and mcp_card_name(_json_obj(self.get(urllib.parse.urljoin(self.origin + "/", url)))):
                warnings.append("A server card is listed in the AI Catalog at %s (SEP-2127 placement). "
                                "The scanner only looks under /.well-known, so it still reports a fail; "
                                "serving a copy at /.well-known/mcp/server-card.json satisfies both." % url)
                break
        return result("fail", "No server card at the three /.well-known paths", {"tried": tried}, warnings)

    def _a2a_card(self):
        data = _json_obj(self.get("/.well-known/agent-card.json"))
        return data

    def check_a2aAgentCard(self):
        data = self._a2a_card()
        if data and data.get("name") and data.get("version") and data.get("supportedInterfaces"):
            return result("pass", "Agent card for %s %s" % (data.get("name"), data.get("version")))
        if data:
            return result("fail", "/.well-known/agent-card.json lacks name, version or supportedInterfaces")
        return result("fail", "No /.well-known/agent-card.json")

    def check_agentSkills(self):
        for path, legacy in (("/.well-known/agent-skills/index.json", False),
                             ("/.well-known/skills/index.json", True)):
            resp = self.get(path)
            data = _json_obj(resp)
            skills = data.get("skills") if data else None
            if not (isinstance(skills, list) and skills):
                continue
            warnings = []
            if legacy:
                warnings.append("Legacy path; move the index to /.well-known/agent-skills/index.json")
            if "$schema" not in data:
                warnings.append("No $schema (discovery v0.2.0 uses "
                                "https://schemas.agentskills.io/discovery/0.2.0/schema.json)")
            for skill in skills:
                lacking = [f for f in ("name", "type", "description", "url", "digest")
                           if not (isinstance(skill, dict) and skill.get(f))]
                if lacking:
                    warnings.append("Skill %r lacks %s" % (skill.get("name") if isinstance(skill, dict) else skill,
                                                           ", ".join(lacking)))
            warnings += self._verify_digests(path, skills[:5])
            return result("pass", "%s lists %d skill(s)" % (path, len(skills)), None, warnings)
        return result("fail", "No skills index at /.well-known/agent-skills/index.json")

    def _verify_digests(self, index_path, skills):
        warnings = []
        base = self.origin + index_path
        for skill in skills:
            if not isinstance(skill, dict):
                continue
            digest, url = str(skill.get("digest", "")), skill.get("url")
            if not (url and digest.startswith("sha256:")):
                continue
            resp = self.get(urllib.parse.urljoin(base, url))
            if not resp.ok:
                warnings.append("Skill %s: %s returned %s" % (skill.get("name"), url, resp.describe()))
            elif hashlib.sha256(resp.body).hexdigest() != digest.split(":", 1)[1].lower():
                warnings.append("Skill %s: digest does not match the file at %s" % (skill.get("name"), url))
        return warnings

    def check_webMcp(self):
        html = self.page_html()
        forms = [f for f in html.forms if f.get("toolname")]
        if forms:
            return result("pass", "Declarative WebMCP form(s): %s" % ", ".join(f["toolname"] for f in forms))
        scripts = " ".join(html.script_text)
        if re.search(r"modelContext", scripts) and re.search(r"registerTool|provideContext", scripts):
            return result("unableToCheck", "Inline script mentions modelContext.registerTool; "
                          "confirm in a browser (this script does not run JavaScript)")
        return result("unableToCheck", "Imperative WebMCP tools need a browser to detect. Run the "
                      "official scanner, or open the page in Chrome with WebMCP enabled")

    def _catalog_sources(self):
        sources = []
        for url in self.robots.agentmaps:
            sources.append(("robots.txt Agentmap", urllib.parse.urljoin(self.origin + "/", url)))
        for rel in ("ai-catalog", "ard"):
            for href in self.page_html().link_hrefs(rel):
                sources.append(('<link rel="%s">' % rel, urllib.parse.urljoin(self.url, href)))
        sources.append(("/.well-known/ai-catalog.json", self.origin + "/.well-known/ai-catalog.json"))
        sources.append(("/.well-known/ard.json", self.origin + "/.well-known/ard.json"))
        return sources

    def _catalog(self):
        for how, url in self._catalog_sources():
            resp = self.get(url)
            data = _json_obj(resp)
            if data is not None:
                return how, url, resp, data
        return None, None, None, None

    def _catalog_entries(self):
        _how, _url, _resp, data = self._catalog()
        entries = (data or {}).get("entries")
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []

    def check_ard(self):
        how, url, resp, data = self._catalog()
        if data is None:
            return result("fail", "No catalog found (robots.txt Agentmap line, <link rel=\"ai-catalog\"> or "
                          "rel=\"ard\", /.well-known/ai-catalog.json, /.well-known/ard.json; DNS is not checked)")
        entries = data.get("entries")
        if not isinstance(data.get("specVersion"), str) or not data.get("specVersion") \
                or not isinstance(entries, list) or not entries:
            return result("fail", "%s (via %s) lacks a specVersion string or a non-empty entries array"
                          % (url, how))
        # The scanner checks structure only and reports spec problems without failing,
        # so problems with single entries are warnings here too.
        valid, warnings = [], []
        for entry in entries:
            if not isinstance(entry, dict):
                warnings.append("Entry %r is not an object" % (entry,))
                continue
            ident = str(entry.get("identifier", ""))
            label = ident or entry.get("displayName") or "(no identifier)"
            problems = []
            if not ident.startswith("urn:air:"):
                problems.append("an identifier of the form urn:air:<domain>:<namespace>:<name>")
            if not entry.get("type"):
                problems.append("a type (media type)")
            if ("url" in entry) == ("data" in entry):
                problems.append("exactly one of url or data")
            if not entry.get("displayName"):
                problems.append("a displayName (ARD v0.91 requires it)")
            if problems:
                warnings.append("Entry %s needs %s" % (label, "; ".join(problems)))
            valid.append(label)
        if resp.content_type != "application/ai-catalog+json":
            warnings.append("Content-Type is %s; expected application/ai-catalog+json" % resp.content_type)
        if how == "/.well-known/ard.json":
            warnings.append("Found only at /.well-known/ard.json; the scanner reads ai-catalog.json, so serve "
                            "the same file there too")
        if valid:
            return result("pass", "%s (via %s): %d entr%s" % (url, how, len(valid),
                                                             "y" if len(valid) == 1 else "ies"),
                          {"entries": valid}, warnings)
        return result("fail", "%s has no valid entries" % url, None, warnings)

    def check_personalAgentProtocol(self):
        data = _json_obj(self.get("/.well-known/poppy.json"))
        org = data.get("organization") if data else None
        domain = org.get("domain") if isinstance(org, dict) else None
        if domain:
            warnings = []
            def bare(name):
                return re.sub(r"^www\.", "", name.lower())
            if bare(domain) != bare(self.host):
                warnings.append("organization.domain %s does not match the host %s" % (domain, self.host))
            return result("pass", "/.well-known/poppy.json for %s (issuer binding not checked)" % domain,
                          None, warnings)
        if data:
            return result("fail", "/.well-known/poppy.json lacks organization.name and organization.domain")
        return result("fail", "No /.well-known/poppy.json")

    # Commerce (never scored) ----------------------------------------------------------
    def check_x402(self):
        for path in ("/", "/api", "/api/v1"):
            resp = self.get(path)
            if resp.status != 402:
                continue
            data = resp.json() or {}
            if (isinstance(data, dict) and "x402Version" in data) or resp.header("PAYMENT-REQUIRED") \
                    or resp.header("X-PAYMENT-REQUIRED"):
                return result("pass", "%s answers 402 with an x402 payment request" % path)
            return result("fail", "%s answers 402 without x402 payment details" % path)
        return result("neutral", "No HTTP 402 on /, /api or /api/v1")

    def check_mpp(self):
        data = _json_obj(self.get("/openapi.json"))
        if not data:
            return result("neutral", "No /openapi.json")
        for path, ops in (data.get("paths") or {}).items():
            if isinstance(ops, dict) and any(isinstance(op, dict) and "x-payment-info" in op
                                             for op in ops.values()):
                return result("pass", "/openapi.json marks payable operations (first: %s)" % path)
        return result("neutral", "/openapi.json has no x-payment-info")

    def check_ucp(self):
        resp = self.get("/.well-known/ucp")
        data = _json_obj(resp)
        if data is None:
            return result("neutral", "No /.well-known/ucp")
        body = data.get("ucp") if isinstance(data.get("ucp"), dict) else data
        if (body.get("protocol_version") or body.get("version")) and body.get("services"):
            return result("pass", "UCP profile with services")
        return result("fail", "/.well-known/ucp lacks protocol_version or services")

    def check_acp(self):
        data = _json_obj(self.get("/.well-known/acp.json"))
        if data is None:
            return result("neutral", "No /.well-known/acp.json")
        proto = data.get("protocol") or {}
        caps = data.get("capabilities") or {}
        if (isinstance(proto, dict) and proto.get("name") == "acp" and proto.get("version")
                and data.get("api_base_url") and data.get("transports")
                and isinstance(caps, dict) and caps.get("services")):
            return result("pass", "ACP discovery document, version %s" % proto.get("version"))
        return result("fail", "/.well-known/acp.json lacks protocol.name 'acp', version, api_base_url, "
                      "transports or capabilities.services")

    def check_ap2(self):
        card = self._a2a_card() or {}
        caps = card.get("capabilities") if isinstance(card.get("capabilities"), dict) else {}
        for ext in caps.get("extensions") or []:
            if isinstance(ext, dict) and "ap2" in str(ext.get("uri", "")).lower():
                params = ext.get("params") or {}
                if isinstance(params, dict) and params.get("roles"):
                    return result("pass", "A2A card declares AP2 roles: %s" % params.get("roles"))
                return result("fail", "AP2 extension without roles")
        return result("neutral", "No AP2 extension in an A2A agent card")

    # Extras (not part of the scanner) ---------------------------------------------------
    def extra_bot_access(self):
        paths = []
        for url in [self.url] + self.pages:
            parts = urllib.parse.urlsplit(url)
            path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
            if path not in paths:
                paths.append(path)
        rows = []
        resp = self.robots_resp
        # RFC 9309: a 4xx robots.txt means no rules; an unreachable one (5xx, network
        # error) means crawlers must assume everything is disallowed.
        unreachable = resp.error is not None or (resp.status or 0) >= 500
        robots_ok = bool(self.robots.groups)
        for token, operator, purpose in AI_BOTS:
            named = token.lower() in self.robots.named_bots()
            if unreachable:
                verdicts = {p: False for p in paths}
            else:
                verdicts = {p: (self.robots.is_allowed(token, p) if robots_ok else True) for p in paths}
            rows.append({"bot": token, "operator": operator, "purpose": purpose,
                         "ownGroup": named, "mayIgnoreRobots": token in MAY_IGNORE_ROBOTS,
                         "paths": verdicts})
        return {"robotsFound": robots_ok, "robotsUnreachable": unreachable,
                "robotsStatus": resp.status, "paths": paths, "bots": rows,
                "note": "robots.txt rules only. A CDN or firewall can still block a bot that robots.txt "
                        "allows; check server or CDN logs for the real responses."}

    def extra_page(self, url):
        resp = self.get(url)
        info = {"url": url, "status": resp.status, "finalUrl": resp.final_url,
                "contentType": resp.content_type, "error": resp.error}
        if not resp.ok:
            return info
        html = parse_page(resp.text()) if _is_html(resp) else None
        robots_meta = ""
        if html:
            robots_meta = ",".join(v for k, v in html.meta.items() if k in ("robots", "googlebot"))
        x_robots = ", ".join(resp.header_all("X-Robots-Tag"))
        directives = (robots_meta + "," + x_robots).lower()
        info.update({
            "xRobotsTag": x_robots or None,
            "metaRobots": robots_meta or None,
            "noindex": "noindex" in directives or "none" in re.split(r"[,\s]+", directives),
            "nosnippet": "nosnippet" in directives,
        })
        if html:
            canon = html.link_hrefs("canonical")
            info.update({
                "title": html.title.strip()[:120],
                "canonical": canon[0] if canon else None,
                "h1Count": html.h1,
                "jsonLdBlocks": html.jsonld,
                "wordsInRawHtml": html.words,
                "scripts": html.scripts,
                "likelyClientRendered": html.words < 150 and html.scripts >= 5,
            })
        md = self.get(url, accept="text/markdown")
        info["markdown"] = md.ok and md.content_type == "text/markdown"
        return info

    def extra_llms_txt(self):
        resp = self.get("/llms.txt")
        if not resp.ok or _is_html(resp):
            return {"found": False, "detail": resp.describe()}
        text = resp.text()
        return {"found": True, "contentType": resp.content_type, "bytes": len(resp.body),
                "links": len(re.findall(r"\]\((https?://[^)]+|/[^)]*)\)", text)),
                "startsWithH1": text.lstrip().startswith("# "),
                "note": "Not scored by Cloudflare's scanner since 2026; no major AI provider "
                        "has said it reads llms.txt."}


# --------------------------------------------------------------------------- helpers for checks

def inspect_sitemap(resp, url):
    """Returns (kind, entry_count, problem)."""
    if not resp.ok:
        return None, None, resp.describe()
    body = resp.body
    if url.endswith(".gz") or body[:2] == b"\x1f\x8b":
        try:
            body = _gunzip(body, MAX_BYTES)
        except (OSError, EOFError):
            return None, None, "gzip file did not decompress"
    head = body[:4096].decode("utf-8", "replace")
    if "<!DOCTYPE" in head.upper() or "<!ENTITY" in head.upper():
        if re.search(r"<html", head, re.I):
            return None, None, "served HTML, not XML"
        return None, None, "has a DOCTYPE/ENTITY declaration; sitemaps should not"
    if resp.truncated or len(body) >= MAX_BYTES:
        match = re.search(r"<(?:\w+:)?(urlset|sitemapindex)\b", head)
        return (match.group(1), None, None) if match else (None, None, "too large to parse")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        return None, None, "XML did not parse (%s)" % err
    tag = root.tag.split("}")[-1]
    if tag not in ("urlset", "sitemapindex"):
        return None, None, "root element is <%s>, not <urlset> or <sitemapindex>" % tag
    return tag, len(list(root)), None


def doh_query(fetcher, name, rtype):
    url = "https://cloudflare-dns.com/dns-query?" + urllib.parse.urlencode({"name": name, "type": rtype})
    resp = fetcher.get(url, accept="application/dns-json")
    data = resp.json() if resp.ok else None
    return data if isinstance(data, dict) else None


def svcb_priority(data):
    """Priority of an SVCB/HTTPS answer; 0 means AliasMode, -1 unreadable."""
    data = data.strip()
    if data.startswith("\\#"):
        parts = data.split()
        hexdata = "".join(parts[2:])
        try:
            return int(hexdata[:4], 16)
        except ValueError:
            return -1
    try:
        return int(data.split()[0])
    except (ValueError, IndexError):
        return -1


def mcp_card_name(data):
    """Server name from a server card, a list of cards, or a registry-style document."""
    if isinstance(data, list):
        for item in data:
            name = mcp_card_name(item)
            if name:
                return name
        return None
    if not isinstance(data, dict):
        return None
    info = data.get("serverInfo")
    if isinstance(info, dict) and info.get("name"):
        return info["name"]
    if isinstance(data.get("name"), str) and data["name"]:
        return data["name"]
    for key in ("servers", "serverCards", "cards"):
        if isinstance(data.get(key), list):
            name = mcp_card_name(data[key])
            if name:
                return name
    if isinstance(data.get("server"), dict):
        return mcp_card_name(data["server"])
    return None


def estimate_level(results):
    """Level 0-5 by the scanner's published rules, and what the next level needs."""
    def ok(cid):
        return results.get(cid, {}).get("status") == "pass"

    basics = [c for c in ("robotsTxt", "sitemap", "linkHeaders") if ok(c)]
    if len(basics) < 2:
        return 0, ["2 of 3: robotsTxt, sitemap, linkHeaders (now %d)" % len(basics)]
    gate2 = [c for c in ("robotsTxtAiRules", "contentSignals") if not ok(c)]
    if gate2:
        return 1, gate2
    if not ok("markdownNegotiation"):
        return 2, ["markdownNegotiation"]
    integration = ("mcpServerCard", "a2aAgentCard", "agentSkills", "apiCatalog")
    if not any(ok(c) for c in integration):
        return 3, ["1 of: " + ", ".join(integration)]
    options = {
        "webBotAuth": ok("webBotAuth"),
        "all four of " + ", ".join(integration): all(ok(c) for c in integration),
        "auth metadata (oauthDiscovery, oauthProtectedResource or authMd)":
            ok("oauthDiscovery") or ok("oauthProtectedResource") or ok("authMd"),
    }
    if sum(options.values()) >= 2:
        return 5, []
    return 4, ["2 of 3 (now %d): %s" % (sum(options.values()), "; ".join(options))]


def score(results):
    counted = [cid for cid, r in results.items()
               if cid not in INFORMATIONAL and cid not in COMMERCE
               and r["status"] in ("pass", "fail")]
    passed = [cid for cid in counted if results[cid]["status"] == "pass"]
    pct = round(100.0 * len(passed) / len(counted)) if counted else 0
    return {"passed": len(passed), "counted": len(counted), "percent": pct,
            "note": "Counts only scored checks this script could run; WebMCP needs a browser and "
                    "is left out unless a declarative form was found."}


# --------------------------------------------------------------------------- report

def render_text(report):
    out = []
    w = out.append
    w("Agent readiness check: %s" % report["url"])
    w("Scanned %s with check_site.py %s (%d requests)" % (report["scannedAt"], report["version"],
                                                          report["requests"]))
    w("")
    w("Estimated level: %d of 5, %s%s" % (report["level"], report["levelName"],
                                          " (only some checks ran, so this is a floor)"
                                          if report.get("partial") else ""))
    s = report["score"]
    w("Scored checks passed: %d of %d (%d%%)" % (s["passed"], s["counted"], s["percent"]))
    w(report["note"])
    for key, label, ids in CATEGORIES:
        checks = report["checks"].get(key) or {}
        if not checks:
            continue
        w("")
        w(label)
        for cid in ids:
            if cid not in checks:
                continue
            r = checks[cid]
            tag = {"pass": "PASS", "fail": "FAIL", "neutral": "--", "skipped": "SKIP",
                   "unableToCheck": "??"}.get(r["status"], r["status"])
            info = " (info)" if cid in INFORMATIONAL else ""
            w("  %-5s %-26s %s" % (tag, LABELS[cid] + info, r["message"]))
            for warning in r.get("warnings") or []:
                w("        ! %s" % warning)
    if report["nextLevel"]:
        nxt = min(report["level"] + 1, 5)
        w("")
        w("To reach level %d (%s), pass: %s" % (nxt, LEVEL_NAMES[nxt], "; ".join(report["nextLevel"])))
    bots = report["extras"]["aiBotAccess"]
    w("")
    if bots["robotsUnreachable"]:
        state = " (robots.txt unreachable: crawlers must treat everything as disallowed)"
    elif not bots["robotsFound"]:
        state = " (no robots.txt rules: all allowed)"
    else:
        state = ""
    w("AI crawler access by robots.txt%s" % state)
    paths = bots["paths"]
    w("  %-21s %-12s %-9s %s" % ("bot", "operator", "purpose", "  ".join(p[:28] for p in paths)))
    for row in bots["bots"]:
        cells = "  ".join(("allowed" if row["paths"][p] else "BLOCKED").ljust(min(len(p), 28))
                          for p in paths)
        mark = ("*" if row["ownGroup"] else "") + ("~" if row["bot"] in MAY_IGNORE_ROBOTS else "")
        w("  %-21s %-12s %-9s %s" % (row["bot"] + mark, row["operator"], row["purpose"], cells))
    w("  * has its own group, so it ignores the User-agent: * rules.")
    w("  ~ its operator says robots.txt may not apply to fetches a user asked for.")
    w("  %s" % bots["note"])
    w("")
    w("Pages")
    for p in report["extras"]["pages"]:
        if p.get("error") or not p.get("status") or p["status"] >= 400:
            w("  %s: %s" % (p["url"], p.get("error") or "HTTP %s" % p["status"]))
            continue
        flags = []
        if p["finalUrl"] != p["url"]:
            flags.append("redirects to %s" % p["finalUrl"])
        if p.get("noindex"):
            flags.append("NOINDEX")
        if p.get("nosnippet"):
            flags.append("nosnippet")
        if p.get("likelyClientRendered"):
            flags.append("little text in raw HTML (client-rendered?)")
        w("  %s: HTTP %s, %s words in raw HTML, %s JSON-LD block(s), canonical %s, Markdown %s%s"
          % (p["url"], p["status"], p.get("wordsInRawHtml", "?"), p.get("jsonLdBlocks", "?"),
             "set" if p.get("canonical") else "missing", "yes" if p.get("markdown") else "no",
             "; " + "; ".join(flags) if flags else ""))
    llms = report["extras"]["llmsTxt"]
    w("")
    if llms["found"]:
        w("llms.txt: found (%d bytes, %d links). %s" % (llms["bytes"], llms["links"], llms["note"]))
    else:
        w("llms.txt: not found (%s). Optional." % llms["detail"])
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Agent-readiness check for one website "
                                                 "(Cloudflare's 24 checks plus per-bot and per-page facts).")
    parser.add_argument("url", help="site or page to check, e.g. https://example.com")
    parser.add_argument("--page", action="append", default=[], metavar="URL_OR_PATH",
                        help="extra priority page to check (repeatable)")
    parser.add_argument("--pages-file", metavar="FILE", help="file with one priority URL or path per line")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="all",
                        help="'content' runs only the 8 checks for content sites")
    parser.add_argument("--only", metavar="IDS", help="comma-separated check IDs to run")
    parser.add_argument("--no-dns", action="store_true", help="skip the DNS-AID lookup")
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per request (default 10)")
    parser.add_argument("--user-agent", default=DEFAULT_UA, help="User-Agent header to send")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--out", metavar="FILE", help="also write the report to FILE")
    parser.add_argument("--fail-under", type=int, metavar="LEVEL",
                        help="exit with status 1 if the estimated level is below LEVEL")
    args = parser.parse_args(argv)

    pages = list(args.page)
    if args.pages_file:
        with open(args.pages_file, encoding="utf-8") as handle:
            pages += [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    only = [c.strip() for c in args.only.split(",")] if args.only else None
    if only:
        unknown = [c for c in only if c not in LABELS]
        if unknown:
            parser.error("unknown check IDs: %s" % ", ".join(unknown))
    try:
        checker = Checker(args.url, Fetcher(args.timeout, args.user_agent), dns=not args.no_dns,
                          pages=pages, profile=args.profile, only=only)
    except ValueError as err:
        parser.error(str(err))
    report = checker.run()
    text = json.dumps(report, indent=2) + "\n" if args.json else render_text(report)
    sys.stdout.write(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    if args.fail_under is not None and report["level"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
