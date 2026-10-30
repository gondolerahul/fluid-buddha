"""
Design-time ingestion source loader (Req 3.7).

For the HireBuddha site the authored page copy already lives as structured
markdown in ``hirebuddha-website/docs``. We load those files, map each to its
site route (DOM anchoring for later ``navigate`` commands), and hand the text to
cortex's KnowledgeTreeService which builds DOCUMENT -> SECTION -> CHUNK nodes.

A live-DOM crawler can later replace ``load_site_documents`` without touching
the rest of the pipeline.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# Repo layout: <root>/backend/ and <root>/hirebuddha-website/
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND_DIR.parent

SITE_CONTENT_DIRS: dict[str, list[Path]] = {
    "hirebuddha": [
        _ROOT / "hirebuddha-website" / "docs" / "website-copies",
        _ROOT / "hirebuddha-website" / "docs" / "product-docs",
    ],
    "buddha-cognitive-lab": [
        _ROOT / "buddha-cognitive-lab-website" / "docs" / "website-copies",
    ],
    "fluidbuddha": [
        _ROOT / "fluidbuddha-website" / "docs" / "website-copies",
    ],
}

# Per-site env override pointing at the website's ``docs/`` base (set when that
# folder is mounted into the backend container). The subdirs under each base are
# the same ones listed in SITE_CONTENT_DIRS above.
_CONTENT_DIR_ENV: dict[str, str] = {
    "hirebuddha": "HIREBUDDHA_CONTENT_DIR",
    "buddha-cognitive-lab": "BUDDHA_COGNITIVE_LAB_CONTENT_DIR",
    "fluidbuddha": "FLUIDBUDDHA_CONTENT_DIR",
}

_CONTENT_SUBDIRS: dict[str, list[str]] = {
    "hirebuddha": ["website-copies", "product-docs"],
    "buddha-cognitive-lab": ["website-copies"],
    "fluidbuddha": ["website-copies"],
}


def _content_dirs(site_key: str) -> list[Path]:
    """Resolve content dirs, honouring the per-site ``*_CONTENT_DIR`` env var
    (set when the website's ``docs/`` folder is mounted into the container)."""
    env_var = _CONTENT_DIR_ENV.get(site_key)
    env_dir = os.environ.get(env_var) if env_var else None
    if env_dir:
        base = Path(env_dir)
        return [base / sub for sub in _CONTENT_SUBDIRS.get(site_key, [])]
    return SITE_CONTENT_DIRS.get(site_key, [])


@dataclass
class SourceDocument:
    filename: str
    route: str | None
    content: str


# filename-stem (after the leading NN-) -> route on the site.
_EXACT_ROUTES: dict[str, str] = {
    "homepage": "/",
    "product-ai-employees": "/product/ai-employees",
    "product-intelligence": "/product/intelligence",
    "product-tools": "/product/tools",
    "product-security": "/product/security",
    "solutions-overview": "/solutions",
    "pricing": "/pricing",
    "pragya": "/",
    "about": "/about",
    "contact": "/contact",
    # buddha-cognitive-lab routes
    "about-company": "/about/company",
    "research": "/research",
    "products-overview": "/products",
    "product-hirebuddha": "/products/hirebuddha",
    "product-fluidbuddha": "/products/fluidbuddha",
    "product-chantingbuddha": "/products/chantingbuddha",
    "solutions": "/solutions",
    "careers": "/careers",
}


def route_for(filename: str) -> str | None:
    """Best-effort map a copy filename to its site route (DOM anchor)."""
    stem = Path(filename).stem
    stem = re.sub(r"^\d+-", "", stem)  # strip leading "07-"
    if stem in _EXACT_ROUTES:
        return _EXACT_ROUTES[stem]
    if stem.startswith("loop-"):
        return f"/solutions/{stem[len('loop-'):]}"
    if stem.startswith("usecase-"):
        return f"/use-cases/{stem[len('usecase-'):]}"
    if stem.startswith("story-"):
        return f"/stories/{stem[len('story-'):]}"
    if stem.startswith("icp-medium-enterprise"):
        return "/for/growing-companies"
    if stem.startswith("icp-startups"):
        return "/for/startups"
    if stem.startswith("icp-solopreneurs"):
        return "/for/solopreneurs"
    if stem.startswith("icp-enterprise"):
        return "/for/enterprise"
    return None


def load_site_documents(site_key: str) -> list[SourceDocument]:
    dirs = _content_dirs(site_key)
    docs: list[SourceDocument] = []
    for d in dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            route = route_for(path.name)
            # Prepend a route anchor so retrieved snippets can drive navigation.
            header = f"[Page: {route}]\n\n" if route else ""
            docs.append(SourceDocument(
                filename=path.name, route=route, content=header + text
            ))
    return docs
