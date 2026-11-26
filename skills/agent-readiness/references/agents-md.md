# AGENTS.md

**Status:** an open format maintained at [agents.md](https://agents.md/) and, since December 2025, a project of the Agentic AI Foundation under the Linux Foundation (alongside MCP). Many coding agents read it, including OpenAI Codex, Cursor, Amp and Google's Jules. Not a website check: Cloudflare's scanner does not look for it.

**Where it applies:** code repositories, including the repository behind a docs site or a theme. It does nothing for a live website's visitors or crawlers.

## What it is

A Markdown file at the root of a repository that tells coding agents how to work in it: how to install, build and test, the conventions, and what not to touch. A README is written for people arriving on the repository; AGENTS.md is the briefing for an agent about to change code. Nested AGENTS.md files in sub-folders can add rules for that part of the tree; the closest one applies.

## What to put in it

- One paragraph on what the project is, its language and framework.
- The exact commands to install, run, test, lint and type-check.
- Where the entry points are, and which folders are generated or vendored.
- Conventions a new contributor would miss: naming, commit format, branch rules.
- What not to do, with the reason.
- What "done" means before a change is proposed.

Keep it short. Every line is loaded into the agent's context on every task. Template: `assets/templates/AGENTS.md`.

## Tool-specific files

Some agents have their own file as well: `CLAUDE.md` for Claude Code, rules files for Cursor. To keep one source of truth, write the shared guidance in AGENTS.md and make the tool-specific file a short pointer to it (Claude Code's `CLAUDE.md` can import it with a line reading `@AGENTS.md`), with only the tool-specific extras below.

## Sources

- [AGENTS.md](https://agents.md/)
- [Linux Foundation announces the Agentic AI Foundation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)
- [Claude Code memory and imports](https://code.claude.com/docs/en/memory)
