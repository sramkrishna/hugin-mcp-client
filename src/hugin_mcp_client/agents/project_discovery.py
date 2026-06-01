"""
Project Discovery Agent — scalable, multi-source FOSS project identification.

Purpose:
    Given a strategic domain (e.g. "CUDA-adjacent ML tooling", "GPU compute
    frameworks", "open source model serving"), this agent searches widely
    across GitHub, GitLab, web sources, and foundation project lists in
    parallel, then uses an LLM to rank candidates and produce a structured
    funding brief ready for human review.

Design principles (mirroring the NVIDIA role's agentic OS vision):
    - Parallel by default  — no linear search chains; fan out, then synthesize
    - Token-aware           — LLM used for synthesis only; search is programmatic
    - Human review loop     — output is structured for quick PM triage
    - Extensible            — add new sources by writing one function and
                              registering it in SEARCHERS

Usage:
    DISCOVERY_QUERY="CUDA ML tooling" python -m hugin_mcp_client.agents.project_discovery
    DISCOVERY_QUERY="open source model serving" python -m hugin_mcp_client.agents.project_discovery

    Env vars (optional):
        GITHUB_TOKEN      — Personal Access Token (higher rate limit)
        DISCOVERY_LIMIT   — Max candidates per source (default: 10)
        DISCOVERY_OUTPUT  — Output file path (default: discovery_report.md)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 3rd-party — these are lightweight and typically already present in a Hugin
# environment.  Install with:  pip install aiohttp
# ---------------------------------------------------------------------------
try:
    import aiohttp
except ImportError:
    aiohttp = None  # graceful fallback to dry-run mode

logger = logging.getLogger("project_discovery")

# ---------------------------------------------------------------------------
# Known NVIDIA FOSS Fund recipients  —  seed data for profile learning
# Sources: https://opensource.nvidia.com/en-my/
# These ground the agent in what the fund *actually funds* so it can
# discover similar projects rather than matching keywords.
# ---------------------------------------------------------------------------

KNOWN_RECIPIENTS: list[dict[str, str]] = [
    {
        "name": "Compiler Explorer",
        "url": "https://godbolt.org/",
        "description": "Online compiler exploration tool. Lets developers interactively compile and explore assembly output across languages and architectures. Community infrastructure, not GPU-specific.",
    },
    {
        "name": "HDF5",
        "url": "https://www.hdfgroup.org/solutions/hdf5/",
        "description": "Hierarchical Data Format v5. Core scientific data storage format used broadly across HPC, ML, and scientific computing. Foundation-backed (HDF Group).",
    },
    {
        "name": "Scientific Python",
        "url": "https://scientific-python.org/",
        "description": "Umbrella project coordinating the scientific Python ecosystem (NumPy, SciPy, Matplotlib, etc.). Foundation-backed, community-governed, essential infrastructure.",
    },
    {
        "name": "Breathe",
        "url": "https://github.com/breathe-doc",
        "description": "Bridges Doxygen XML output to Sphinx documentation. Developer tooling for documentation generation, especially for C/C++ projects.",
    },
]

logger = logging.getLogger("project_discovery")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ProjectCandidate:
    """A single open-source project found during discovery."""
    name: str
    url: str
    source: str                    # e.g. "github_search", "web_mention"
    description: str = ""
    stars: int = 0
    language: str = ""
    topics: list[str] = field(default_factory=list)
    recent_activity: str = ""       # last commit / release
    maintainers: str = ""           # if discoverable
    relevance_score: int = 0        # 0-100, set by LLM analysis
    strategic_notes: str = ""       # why NVIDIA / the fund should care

    def to_brief(self) -> str:
        lines = [
            f"## {self.name}",
            f"**URL**: {self.url}",
            f"**Source**: {self.source}",
            f"**Stars**: {self.stars:,}" if self.stars else "",
            f"**Language**: {self.language}" if self.language else "",
            f"**Topics**: {', '.join(self.topics)}" if self.topics else "",
            f"**Relevance**: {self.relevance_score}/100" if self.relevance_score else "",
            f"",
            self.description,
            "",
            self.strategic_notes,
        ]
        return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Parallel searchers — add a new one by writing a function that matches the
# signature and registering it in SEARCHERS below.
# ---------------------------------------------------------------------------

SEARCHERS: list[Callable] = []  # populated by the @searcher decorator


def searcher(fn: Callable) -> Callable:
    """Decorator: register a function as a parallel search source."""
    SEARCHERS.append(fn)
    return fn


@searcher
async def search_github(
    query: str,
    session: aiohttp.ClientSession | None = None,
) -> list[ProjectCandidate]:
    """
    GitHub code / repository search.
    Uses the public search API; provide GITHUB_TOKEN for higher rate limits.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    limit = int(os.environ.get("DISCOVERY_LIMIT", "10"))
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Build a targeted GitHub search query from the domain
    # We try repo search first for structured results
    search_queries = _build_github_queries(query)

    seen_urls: set[str] = set()
    results: list[ProjectCandidate] = []

    should_close = session is None
    if session is None:
        if aiohttp is None:
            logger.warning("aiohttp not installed — skipping GitHub search")
            return []
        session = aiohttp.ClientSession(headers=headers)

    try:
        for sq in search_queries:
            if len(results) >= limit:
                break
            url = "https://api.github.com/search/repositories"
            params = {"q": sq, "sort": "stars", "per_page": min(limit - len(results), 10)}
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"GitHub search returned {resp.status}: {(await resp.text())[:200]}")
                        continue
                    body = await resp.json()
            except Exception as e:
                logger.error(f"GitHub search failed: {e}")
                continue

            for item in body.get("items", []):
                repo_url = item.get("html_url", "")
                if repo_url in seen_urls:
                    continue
                seen_urls.add(repo_url)
                topics = item.get("topics", []) or []

                # Relative recency from pushed_at
                pushed = item.get("pushed_at", "")
                activity = f"Last push: {pushed}" if pushed else ""

                results.append(ProjectCandidate(
                    name=item.get("full_name", repo_url.split("/")[-1]),
                    url=repo_url,
                    source="github_search",
                    description=item.get("description") or "",
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language") or "",
                    topics=topics,
                    recent_activity=activity,
                ))
    finally:
        if should_close:
            await session.close()

    return results


def _build_github_queries(domain: str) -> list[str]:
    """Produce several GitHub search queries targeting the domain."""
    terms = domain.strip().lower().split()
    base = "+".join(terms) if terms else domain
    return [
        base,
        f"{base}+topic:ai",
        f"{base}+topic:machine-learning",
        f"{base}+topic:gpu",
    ]


@searcher
async def search_web(
    query: str,
    session: aiohttp.ClientSession | None = None,
) -> list[ProjectCandidate]:
    """
    Web search for open-source projects in the domain.
    Extracts project mentions, links, and descriptions.
    """
    limit = int(os.environ.get("DISCOVERY_LIMIT", "10"))

    # Try DuckDuckGo (no API key needed for basic use)
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs not installed — skipping web search")
        return []

    search_queries = [
        f"open source {query} projects 2026",
        f"best {query} github repositories",
        f"{query} machine learning framework open source",
    ]

    seen_urls: set[str] = set()
    results: list[ProjectCandidate] = []

    for sq in search_queries:
        if len(results) >= limit:
            break
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(sq, max_results=min(limit - len(results), 5)))
        except Exception as e:
            logger.warning(f"Web search failed for '{sq}': {e}")
            continue

        for item in raw:
            url = item.get("href", "") or item.get("link", "")
            if not url or url in seen_urls:
                continue
            # Skip non-project URLs
            if any(skip in url for skip in ("youtube.com", "amazon.", "reddit.com/r/")):
                continue
            seen_urls.add(url)
            title = item.get("title", "") or item.get("text", "")[:80]

            results.append(ProjectCandidate(
                name=title.split(" - ")[0].split(" | ")[0].strip() or "Untitled",
                url=url,
                source="web_mention",
                description=(item.get("body", "") or item.get("text", "") or "")[:300],
            ))

    return results


# ---------------------------------------------------------------------------
# LLM-based ranking
# ---------------------------------------------------------------------------

async def rank_candidates(
    candidates: list[ProjectCandidate],
    domain: str,
) -> list[ProjectCandidate]:
    """
    Use the configured LLM to score each candidate on strategic relevance
    to the given domain and produce actionable notes.

    Falls back to a simple heuristic sort if no LLM is available.
    """
    if not candidates:
        return candidates

    # Try loading Hugin's LLM provider
    try:
        from hugin_mcp_client.agents.provider import create_provider
        from hugin_mcp_client.llm_provider import LLMProvider
        import tomllib
    except ImportError:
        logger.warning("Hugin LLM not available — using heuristic ranking")
        return _heuristic_rank(candidates, domain)

    # Read Hugin config for LLM settings
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.toml")
    if not os.path.exists(config_path):
        logger.warning("config.toml not found — using heuristic ranking")
        return _heuristic_rank(candidates, domain)

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except Exception:
        return _heuristic_rank(candidates, domain)

    llm_config = config.get("llm", {})
    provider_name = llm_config.get("provider", "anthropic")

    # Build the ranking prompt
    projects_json = [
        {"name": c.name, "url": c.url, "description": c.description[:200],
         "stars": c.stars, "topics": c.topics}
        for c in candidates
    ]

    prompt = textwrap.dedent(f"""\
    You are an open-source investment strategist. Score each project below on
    strategic relevance to NVIDIA's FOSS Fund in the domain: "{domain}".

    For each project, assign a relevance_score (0-100) based on:
    - Direct relevance to {domain}
    - Project health and community engagement
    - Strategic value to NVIDIA's ecosystem
    - Potential for partnership or funding impact

    Also provide 1-2 sentences of strategic_notes explaining WHY this project
    matters or doesn't matter.

    Return ONLY a JSON array. No markdown, no explanation.

    Projects:
    {json.dumps(projects_json, indent=2)}
    """)

    try:
        # Use Hugin's LLM provider directly
        provider: LLMProvider = create_provider(provider_name, llm_config)

        # Add a system-style instruction via user message
        response = provider.create_message(
            user_message=prompt,
            tools=[],
        )
        raw = provider.extract_text_response(response)

        # Parse JSON from response
        scored = json.loads(raw)
        if isinstance(scored, list) and len(scored) == len(candidates):
            for i, s in enumerate(scored):
                candidates[i].relevance_score = s.get("relevance_score", 0)
                candidates[i].strategic_notes = s.get("strategic_notes", "")
    except Exception as e:
        logger.warning(f"LLM ranking failed: {e} — using heuristic sort")
        return _heuristic_rank(candidates, domain)

    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates


def _heuristic_rank(
    candidates: list[ProjectCandidate],
    domain: str,
) -> list[ProjectCandidate]:
    """Simple relevance scoring without an LLM call."""
    domain_terms = set(domain.lower().split())
    for c in candidates:
        score = 0
        text = (c.name + " " + c.description + " " + " ".join(c.topics)).lower()
        # +10 per domain term match
        for term in domain_terms:
            if term in text:
                score += 10
        # +1 per 100 stars (cap at 20)
        score += min(c.stars // 100, 20)
        c.relevance_score = min(score, 100)
        c.strategic_notes = f"Autosuggested — domain match: {score}%"
    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Profile learning  —  derive a fund profile from known recipients
# ---------------------------------------------------------------------------

@dataclass
class FundProfile:
    """Learned characteristics of what this fund tends to support."""
    description: str = ""
    typical_categories: list[str] = field(default_factory=list)
    typical_governance: list[str] = field(default_factory=list)
    ecosystem_relationship: str = ""
    # Expanded search queries derived from profile + known recipients
    search_queries: list[str] = field(default_factory=list)


async def learn_profile() -> FundProfile:
    """
    Analyze known FOSS Fund recipients and build a search profile.
    Uses an LLM if available; falls back to a heuristic description.
    """
    profile = FundProfile()

    recipients_summary = "\n".join(
        f"- {r['name']}: {r['description']}" for r in KNOWN_RECIPIENTS
    )

    # Try LLM-based analysis
    try:
        from hugin_mcp_client.agents.provider import create_provider
        from hugin_mcp_client.llm_provider import LLMProvider
        import tomllib

        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config.toml"
        )
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            llm_config = config.get("llm", {})
            provider_name = llm_config.get("provider", "anthropic")

            prompt = textwrap.dedent(f"""\
            Analyze these known FOSS Fund recipients and describe the
            profile of what this fund supports — categories, governance
            patterns, ecosystem role. Also suggest 5 search queries for
            finding *new* projects that fit a similar profile.

            Known recipients:
            {recipients_summary}

            Return a JSON object with keys:
            - description (str): 2-3 sentence fund profile
            - typical_categories (list[str]): e.g. "dev tooling", "scientific infra"
            - typical_governance (list[str]): e.g. "foundation-backed"
            - ecosystem_relationship (str): how projects relate to NVIDIA's ecosystem
            - search_queries (list[str]): 5 search queries for finding similar projects
            """)

            provider: LLMProvider = create_provider(provider_name, llm_config)
            response = provider.create_message(user_message=prompt, tools=[])
            raw = provider.extract_text_response(response)
            data = json.loads(raw)

            profile.description = data.get("description", "")
            profile.typical_categories = data.get("typical_categories", [])
            profile.typical_governance = data.get("typical_governance", [])
            profile.ecosystem_relationship = data.get("ecosystem_relationship", "")
            profile.search_queries = data.get("search_queries", [])
            logger.info(f"Learned fund profile: {profile.description[:100]}...")
            return profile
    except Exception as e:
        logger.warning(f"LLM profile learning failed: {e}")

    # Fallback heuristic profile
    profile.description = (
        "The NVIDIA FOSS Fund supports developer and scientific infrastructure "
        "projects — tooling, data formats, documentation, and ecosystem libraries. "
        "Recipients tend to be broadly adopted community infrastructure, not "
        "NVIDIA-specific, and often foundation-backed."
    )
    profile.typical_categories = [
        "developer tooling", "scientific computing", "documentation",
        "data infrastructure", "ecosystem libraries"
    ]
    profile.typical_governance = ["community-governed", "foundation-backed"]
    profile.ecosystem_relationship = (
        "Complementary infrastructure — not NVIDIA-specific but broadly "
        "used in the ecosystems NVIDIA participates in (HPC, AI/ML, developer tools)"
    )
    profile.search_queries = [
        "compiler explorer interactive development",
        "scientific data format HPC library",
        "sphinx documentation python ecosystem",
        "scientific python numpy scipy tool",
        "developer tool open source community",
    ]
    return profile


# ---------------------------------------------------------------------------
# Orchestrator  —  profile → parallel search → rank → human-ready output
# ---------------------------------------------------------------------------

async def discover(domain: str = "") -> list[ProjectCandidate]:
    """
    1. Learn the fund profile from known recipients
    2. Run all registered searchers in parallel using profile-derived queries
    3. Deduplicate
    4. Rank by relevance to fund profile
    5. Return sorted candidates
    """
    # Phase 0: Learn fund profile
    profile = await learn_profile()
    logger.info(f"Fund profile: {profile.description[:80]}...")

    # Build search queries: combine user domain (if given) with profile queries
    search_queries = profile.search_queries.copy()
    if domain:
        search_queries.insert(0, domain)
        # Also generate a fused query
        for cat in profile.typical_categories[:2]:
            search_queries.append(f"{domain} {cat}")

    logger.info(f"Searching with {len(search_queries)} queries across {len(SEARCHERS)} searchers")

    # Phase 1: Parallel search across all sources × all queries
    tasks = [
        searcher(q) for q in search_queries[:5]  # limit to keep parallelism sane
        for searcher in SEARCHERS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect and log errors
    all_candidates: list[ProjectCandidate] = []
    for result in results:
        if isinstance(result, Exception):
            logger.debug(f"Search task failed: {result}")
            continue
        if isinstance(result, list):
            all_candidates.extend(result)

    logger.info(f"Raw candidates: {len(all_candidates)}")

    # Phase 2: Deduplicate by URL
    seen: dict[str, ProjectCandidate] = {}
    for c in all_candidates:
        if c.url not in seen:
            seen[c.url] = c
    unique = list(seen.values())
    logger.info(f"After dedup: {len(unique)} unique")

    # Phase 3: Rank by relevance to fund profile
    ranked = await rank_candidates(unique, domain or profile.description)
    logger.info(f"Top candidate: {ranked[0].name if ranked else 'none'}")

    return ranked, profile


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    candidates: list[ProjectCandidate],
    domain: str,
    profile: FundProfile | None = None,
    known_count: int = len(KNOWN_RECIPIENTS),
) -> str:
    """Produce a human-readable Markdown report."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Project Discovery Report",
        f"",
        f"**Generated**: {now}",
        f"**Candidates**: {len(candidates)}",
        f"**Seeded from**: {known_count} known FOSS Fund recipients",
        f"",
        f"---",
        f"",
        f"## Fund Profile",
        f"",
        f"Learned from analyzing past FOSS Fund recipients:",
        f"",
    ]

    if profile:
        if profile.description:
            lines.append(f">{profile.description}")
            lines.append("")
        if profile.typical_categories:
            cats = ", ".join(f"`{c}`" for c in profile.typical_categories)
            lines.append(f"**Categories**: {cats}")
        if profile.typical_governance:
            govs = ", ".join(f"`{g}`" for g in profile.typical_governance)
            lines.append(f"**Governance**: {govs}")
        if profile.ecosystem_relationship:
            lines.append(f"**Ecosystem role**: {profile.ecosystem_relationship}")
    else:
        lines.append("Heuristic profile (no LLM available for analysis).")

    lines.extend([
        "",
        "**Known recipients used for training:**",
    ])
    for r in KNOWN_RECIPIENTS:
        lines.append(f"- [{r['name']}]({r['url']})")

    lines.extend([
        "",
        "---",
        "",
        f"## Executive Summary",
        f"",
        f"The following {len(candidates)} projects were surfaced across "
        f"GitHub search and web search using profile-derived queries. "
        f"Ranked by similarity to the fund profile above.",
        f"",
        f"### Top 3 Recommendations",
        f"",
    ])

    for i, c in enumerate(candidates[:3]):
        lines.append(f"**{i+1}. [{c.name}]({c.url})** — {c.relevance_score}/100")
        lines.append(f"   {c.strategic_notes}")

    lines.extend([
        "",
        "---",
        "## All Candidates (ranked)",
        "",
    ])

    for i, c in enumerate(candidates):
        lines.append(f"### {i+1}. {c.name}  ({c.relevance_score}/100)")
        lines.append(f"**URL**: [{c.url}]({c.url})")
        lines.append(f"**Source**: {c.source}")
        if c.stars:
            lines.append(f"**Stars**: {c.stars:,}")
        if c.language:
            lines.append(f"**Language**: {c.language}")
        if c.topics:
            lines.append(f"**Topics**: `{'` `'.join(c.topics)}`")
        if c.description:
            lines.append(f"")
            lines.append(c.description)
        if c.strategic_notes:
            lines.append(f"")
            lines.append(f"> {c.strategic_notes}")
        lines.append("")

    lines.extend([
        "---",
        "## 🔍 Human Review Required",
        "",
        "This report is an AI-assisted first pass. Before funding decisions:",
        "",
        "- [ ] Verify project health — commits, releases, maintainer responsiveness",
        "- [ ] Check governance model — single vendor? foundation-backed?",
        "- [ ] Assess NVIDIA ecosystem fit — does this project use or integrate with "
        "CUDA / TensorRT / Triton / etc.?",
        "- [ ] Reach out to maintainers — gauge interest and capacity",
        "- [ ] Cross-reference with existing FOSS Fund recipients",
        "",
        "---",
        f"*Generated by Hugin Project Discovery Agent • {now}*",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main():
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    domain = os.environ.get("DISCOVERY_QUERY") or " ".join(sys.argv[1:])
    if not domain:
        print("Usage: DISCOVERY_QUERY='GPU ML tooling' python -m hugin_mcp_client.agents.project_discovery")
        print("   or: python -m hugin_mcp_client.agents.project_discovery CUDA ML frameworks")
        sys.exit(1)

    print(f"\n🔍 Project Discovery Agent")
    print(f"   Domain: {domain}")
    print(f"   Searching GitHub + web in parallel...\n")

    candidates, profile = await discover(domain)

    if not candidates:
        print("⚠️  No candidates found. Try a broader query.")
        sys.exit(0)

    report = generate_report(candidates, domain, profile=profile)

    output_path = os.environ.get("DISCOVERY_OUTPUT", "discovery_report.md")
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\n✅ Found {len(candidates)} candidates")
    print(f"📄 Report written to {output_path}")
    print(f"\n🏆 Top 3:")
    for i, c in enumerate(candidates[:3]):
        print(f"   {i+1}. {c.name} — relevance: {c.relevance_score}/100")
        print(f"      {c.url}")
    print()


def cli():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
