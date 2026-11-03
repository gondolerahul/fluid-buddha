"""
Valid site routes per target site (Req 3.5 navigation grounding).

Each site's routes live in its agent profile (app/orchestrator/profile.py):
HireBuddha's built-in profile uses the static list below; tenant sites get
routes from ingested URL sources or the console (docs/defects.md D-9).

The Heavy Thinker chooses ``navigate(path=...)`` targets. Without a constraint it
guesses paths that 404 (e.g. ``/tools`` instead of ``/product/tools``). We give
the model the real sitemap in its prompt AND validate/snap its choice
server-side so a bad guess never reaches the browser.
"""
from __future__ import annotations

from difflib import get_close_matches
from urllib.parse import urlsplit

# Authoritative static routes, mirrored from hirebuddha-website/src/app.
HIREBUDDHA_ROUTES: list[str] = [
    "/",
    "/about",
    "/contact",
    "/pricing",
    "/security",
    "/solutions",
    "/blog",
    "/use-cases",
    "/stories",
    "/terms",
    "/privacy",
    "/product/ai-employees",
    "/product/intelligence",
    "/product/tools",
    "/product/security",
    "/for/growing-companies",
    "/for/growing-companies/control",
    "/for/growing-companies/ops-playbook",
    "/for/growing-companies/roi",
    "/for/enterprise",
    "/for/enterprise/integrations",
    "/for/enterprise/deployment",
    "/for/enterprise/architecture",
    "/for/enterprise/business-case",
    "/for/solopreneurs",
    "/for/solopreneurs/team",
    "/for/solopreneurs/start",
    "/for/solopreneurs/your-day",
    "/for/startups",
    "/for/startups/day-in-the-life",
    "/for/startups/launchpad",
    "/for/startups/vs",
]

# Dynamic segments: any path under these prefixes is allowed (e.g. /solutions/growth).
HIREBUDDHA_DYNAMIC_PREFIXES = ("/solutions/", "/use-cases/", "/blog/", "/stories/")


def _site_routes(site_key: str) -> tuple[list[str], list[str]]:
    """(routes, dynamic prefixes) from the site's profile."""
    from app.orchestrator.profile import profile_for  # avoid an import cycle

    profile = profile_for(site_key)
    return profile.routes, profile.dynamic_prefixes


def normalize_route(path: str) -> str:
    if not path:
        return ""
    path = path.strip().split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def is_valid_route(site_key: str, path: str) -> bool:
    path = normalize_route(path)
    routes, prefixes = _site_routes(site_key)
    if path in routes:
        return True
    return any(
        path.startswith(p) and len(path) > len(p)
        for p in prefixes
    )


def resolve_route(site_key: str, path: str) -> str | None:
    """Return a valid route for ``path``, snapping a close guess to the real one.

    Returns ``None`` when the guess is too far from anything real, so the caller
    can drop the navigation instead of sending the visitor to a 404.
    """
    path = normalize_route(path)
    if not path:
        return None
    if is_valid_route(site_key, path):
        return path
    candidates, _ = _site_routes(site_key)
    # 1) Fuzzy match on the whole path (handles typos / case / trailing-slash;
    #    cutoff kept high so unrelated garbage drops to None instead of snapping).
    match = get_close_matches(path, candidates, n=1, cutoff=0.82)
    if match:
        return match[0]
    # 2) Last-segment match: a guess like /tools or /product/capabilities snaps
    #    to the route whose final segment is the same (/product/tools).
    leaf = path.rsplit("/", 1)[-1]
    if leaf:
        leaf_matches = [c for c in candidates if c.rsplit("/", 1)[-1] == leaf]
        if len(leaf_matches) == 1:
            return leaf_matches[0]
    return None


def sitemap_prompt(site_key: str) -> str:
    """Compact, model-friendly list of valid routes for the system prompt."""
    routes, dyn = _site_routes(site_key)
    if not routes:
        return ""
    listed = ", ".join(routes)
    dyn_note = (
        f" Dynamic sections also exist under {', '.join(dyn)} (any sub-path there is valid)."
        if dyn
        else ""
    )
    return (
        "VALID ROUTES (use `navigate` ONLY with one of these exact paths; never "
        f"invent a path): {listed}.{dyn_note}"
    )


def route_from_url(url: str) -> str:
    """The site route a crawled URL represents (``https://x.com/pricing/?a=1`` → ``/pricing``)."""
    try:
        path = urlsplit(url or "").path
    except ValueError:
        return ""
    return normalize_route(path or "/")
