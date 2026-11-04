"""
Self-serve onboarding (WS9): page reading, the crawler (robots, sitemap, depth,
scope), PDF/DOCX extraction, derived personas, design tokens, and the
paste-URL → live flow through the API. No network: the crawler's fetch is faked.
"""
from __future__ import annotations

import asyncio
import io
import uuid
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from app.onboarding import crawler as crawler_mod
from app.onboarding.crawler import crawl, normalize
from app.onboarding.design import extract_design, hex_color
from app.onboarding.documents import DocumentError, docx_text, extract_text, pdf_text
from app.onboarding.html import parse_page
from app.onboarding.personas import from_urls, parse_model_personas
from app.tenancy.url_fetch import Fetched, UnsafeURLError


# ---- fixtures ---------------------------------------------------------------

def make_pdf(text: str) -> bytes:
    """A minimal one-page PDF with a real text layer."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def make_docx(paragraphs: list[tuple[str, str]]) -> bytes:
    """A minimal .docx: (style, text) paragraphs."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(
        f'<w:p>{f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""}'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
        for style, text in paragraphs
    )
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


HOME = """<!doctype html><html><head>
<title>Acme Robotics | Warehouse automation</title>
<meta name="description" content="Robots that pick, pack and ship.">
<meta property="og:site_name" content="Acme Robotics">
<meta name="theme-color" content="#1f6feb">
<link rel="stylesheet" href="/static/site.css">
<link rel="stylesheet" href="https://cdn.other.net/lib.css">
<link rel="icon" href="/favicon.ico">
<style>:root { --brand-primary: #e4572e; --radius: 10px; }</style>
</head><body>
<nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav>
<header><img class="site-logo" src="/img/logo.svg" alt="Acme"></header>
<main>
<h1>Warehouse robots that never sleep</h1>
<p>Acme robots pick, pack and ship orders around the clock for retailers.</p>
<a href="/for/retailers">Retailers</a> <a href="/for/3pl-providers">3PLs</a>
<a href="/pricing?utm=x#plans">See pricing</a>
<a href="/private/admin">Admin</a>
<a href="https://elsewhere.example/page">Partner</a>
<a href="/brochure.pdf">Brochure</a>
<a href="/logo.png">Logo</a>
<script>var tracking = "not copy";</script>
</main></body></html>"""

PAGES = {
    "https://acme.example/": ("text/html", HOME),
    "https://acme.example/pricing": ("text/html",
        "<title>Pricing</title><h1>Pricing</h1><p>Plans start at $2,000 per robot per month, "
        "including maintenance.</p><a href='/pricing/enterprise'>Enterprise</a>"),
    "https://acme.example/pricing/enterprise": ("text/html",
        "<h1>Enterprise</h1><p>Fleet pricing for more than fifty robots, with an SLA.</p>"),
    "https://acme.example/for/retailers": ("text/html",
        "<title>For retailers</title><meta name='description' content='Ship same-day without "
        "hiring for peak season.'><h1>Retailers</h1><p>Retail teams use Acme to ship same day "
        "during every seasonal peak.</p>"),
    "https://acme.example/for/3pl-providers": ("text/html",
        "<h1>3PL providers</h1><p>Run more client warehouses with the same floor team and "
        "fewer errors.</p>"),
    "https://acme.example/hidden": ("text/html",
        "<meta name='robots' content='noindex'><h1>Hidden</h1><p>Should never be read at all.</p>"),
    "https://acme.example/brochure.pdf": ("application/pdf", make_pdf("Acme brochure robot specs: payload 40 kg, eight hour battery")),
    "https://acme.example/private/admin": ("text/html", "<h1>Admin</h1><p>secret admin page text</p>"),
    "https://acme.example/robots.txt": ("text/plain",
        "User-agent: *\nDisallow: /private/\nSitemap: https://acme.example/sitemap.xml\n"),
    "https://acme.example/sitemap.xml": ("application/xml",
        "<urlset><url><loc>https://acme.example/hidden</loc></url>"
        "<url><loc>https://acme.example/pricing</loc></url></urlset>"),
    "https://acme.example/static/site.css": ("text/css",
        "body { background-color: #ffffff; color: #1a1a1a; font-family: 'Inter', sans-serif; }"
        "h1 { font-family: 'Space Grotesk', serif; } .card { border-radius: 10px }"
        ".btn { border-radius: 10px } .x { border-radius: 4px }"),
}


def fake_fetch(pages: dict, log: list | None = None):
    async def fetch(url, *, allowed_types=(), max_bytes=0, transport=None):
        if log is not None:
            log.append(url)
        if url not in pages:
            req = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("404", request=req, response=httpx.Response(404, request=req))
        ctype, body = pages[url]
        if allowed_types and ctype not in allowed_types:
            raise UnsafeURLError(f"unsupported content type: {ctype}")
        raw = body if isinstance(body, bytes) else body.encode()
        return Fetched(url=url, content_type=ctype, body=raw, encoding="utf-8")
    return fetch


# ---- page reading -------------------------------------------------------------

def test_parse_page_reads_copy_links_and_brand_hooks():
    info = parse_page(HOME, "https://acme.example/")
    assert info.title == "Acme Robotics | Warehouse automation"
    assert info.h1 == "Warehouse robots that never sleep"
    assert info.description == "Robots that pick, pack and ship."
    assert info.site_name == "Acme Robotics" and info.theme_color == "#1f6feb"
    assert "pick, pack and ship orders" in info.text
    assert "tracking" not in info.text                 # scripts aren't copy
    assert "Home" not in info.text.split("\n")[0]       # nav chrome left out
    assert "https://acme.example/for/retailers" in info.links
    assert info.stylesheets[0] == "https://acme.example/static/site.css"
    assert info.logo_candidates == ["https://acme.example/img/logo.svg"]
    assert "--brand-primary" in info.inline_css
    # A page without </head> still has its body copy.
    assert "Body copy" in parse_page("<html><head><title>T</title><body><p>Body copy</p>",
                                     "https://x.example/").text


def test_normalize_drops_query_fragment_and_trailing_slash():
    assert normalize("HTTPS://Acme.Example/pricing/?utm=1#plans") == "https://acme.example/pricing"
    assert normalize("https://acme.example") == "https://acme.example/"


# ---- crawler ----------------------------------------------------------------

def test_crawl_obeys_robots_sitemap_scope_and_depth():
    log: list[str] = []
    result = asyncio.run(crawl("https://acme.example", max_pages=20, max_depth=1,
                               fetch=fake_fetch(PAGES, log)))
    urls = {p.url for p in result.pages}
    assert "https://acme.example/" in urls
    assert {"https://acme.example/pricing", "https://acme.example/for/retailers",
            "https://acme.example/for/3pl-providers", "https://acme.example/brochure.pdf"} <= urls
    assert result.used_sitemap
    assert "https://acme.example/private/admin" not in log      # robots.txt
    assert result.blocked_by_robots == 1
    assert "https://acme.example/hidden" not in urls            # noindex
    assert not any("elsewhere" in u or u.endswith(".png") for u in log)  # off-site, assets
    assert "https://acme.example/pricing/enterprise" not in urls  # depth 2 > max 1
    assert log.count("https://acme.example/pricing") == 1        # ?utm and #plans deduped
    pdf = next(p for p in result.pages if p.kind == "pdf")
    assert "Acme brochure robot specs" in pdf.text


def test_crawl_page_limit_and_depth_two():
    r = asyncio.run(crawl("https://acme.example/", max_pages=3, max_depth=2,
                          fetch=fake_fetch(PAGES)))
    assert len(r.pages) == 3
    r2 = asyncio.run(crawl("https://acme.example/", max_pages=20, max_depth=2,
                           fetch=fake_fetch(PAGES)))
    assert "https://acme.example/pricing/enterprise" in {p.url for p in r2.pages}


def test_robots_forbidden_keeps_the_crawler_out():
    pages = dict(PAGES)
    del pages["https://acme.example/robots.txt"]

    async def fetch(url, **kw):
        if url.endswith("/robots.txt"):
            req = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("403", request=req, response=httpx.Response(403, request=req))
        return await fake_fetch(pages)(url, **kw)
    r = asyncio.run(crawl("https://acme.example/", fetch=fetch))
    assert r.pages == [] and r.blocked_by_robots >= 1


def test_crawler_uses_the_ssrf_guard_by_default():
    with pytest.raises(UnsafeURLError):
        asyncio.run(crawler_mod.fetch_public("http://127.0.0.1/"))


# ---- documents --------------------------------------------------------------

def test_pdf_and_docx_text():
    assert "Hello onboarding" in pdf_text(make_pdf("Hello onboarding"))
    text = docx_text(make_docx([("Heading1", "Plans"), ("", "Pro costs 49 dollars."),
                                ("", "Cancel any time.")]))
    assert text.splitlines()[0] == "" or text.startswith("\nPlans") or "Plans" in text
    assert "Pro costs 49 dollars.\nCancel any time." in text
    assert extract_text(b"plain words", "notes.md") == "plain words"
    with pytest.raises(DocumentError):
        extract_text(b"not a pdf", "x.pdf")
    with pytest.raises(DocumentError):
        extract_text(b"not a zip", "x.docx")
    with pytest.raises(DocumentError, match="no text layer"):
        extract_text(make_pdf(""), "scan.pdf")


# ---- personas ---------------------------------------------------------------

def test_personas_from_audience_urls():
    r = asyncio.run(crawl("https://acme.example/", max_pages=20, max_depth=1,
                          fetch=fake_fetch(PAGES)))
    personas = from_urls(r.pages)
    by_slug = {p.slug: p for p in personas}
    assert set(by_slug) == {"retailers", "3pl-providers"}
    assert by_slug["retailers"].label == "Retailers"
    assert by_slug["retailers"].focus == "Ship same-day without hiring for peak season."
    assert by_slug["retailers"].landing == "/for/retailers"


def test_parse_model_personas_is_tolerant():
    text = 'Sure! [{"label": "clinic managers", "focus": "fewer no-shows", "tone": "calm", ' \
           '"landing": "/clinics"}, {"label": "Clinic Managers"}, {"nope": 1}, "x"] done'
    ps = parse_model_personas(text)
    assert [p.slug for p in ps] == ["clinic-managers"]
    assert ps[0].label == "Clinic managers" and ps[0].landing == "/clinics"
    assert parse_model_personas("no json here") == []


# ---- design tokens ------------------------------------------------------------

def test_design_tokens_from_css():
    info = parse_page(HOME, "https://acme.example/")
    d = extract_design(info, [PAGES["https://acme.example/static/site.css"][1]])
    assert d["name"] == "Acme Robotics"
    assert d["logo_url"] == "https://acme.example/img/logo.svg"
    assert d["colors"]["primary"] == "#e4572e"        # brand variable beats theme-color
    assert d["colors"]["background"] == "#ffffff" and d["colors"]["text"] == "#1a1a1a"
    assert d["typography"]["font_family"].startswith("'Inter'")
    assert d["typography"]["heading_family"].startswith("'Space Grotesk'")
    assert d["radius"] == "10px"


def test_design_falls_back_to_theme_color_then_frequency():
    plain = parse_page("<title>Plain</title><meta name='theme-color' content='#0a7d3c'>", "https://p.example/")
    assert extract_design(plain, [])["colors"]["primary"] == "#0a7d3c"
    bare = parse_page("<title>Bare</title>", "https://b.example/")
    css = ".a{color:#7b2ff7}.b{color:#7b2ff7}.c{color:#999999}.d{color:rgb(255,255,255)}"
    assert extract_design(bare, [css])["colors"]["primary"] == "#7b2ff7"
    assert hex_color("#ABC") == "#aabbcc" and hex_color("rgba(0,0,0,0.1)") is None


# ---- paste URL → live, through the API -----------------------------------------

def _tenant(client: TestClient) -> dict:
    email = f"onb_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register",
                      json={"email": email, "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_crawl_api_ingests_pages_personas_and_design(monkeypatch):
    import app.tenancy.url_fetch as url_fetch
    from app.main import app

    monkeypatch.setattr(url_fetch, "fetch_public", fake_fetch(PAGES))
    with TestClient(app) as client:
        h = _tenant(client)
        wid = client.post("/tenant/websites", json={"name": "Acme", "domain": "acme.example"},
                          headers=h).json()["id"]
        # Unsafe start URLs are refused before anything runs.
        bad = client.post(f"/tenant/websites/{wid}/crawl", json={"url": "http://10.0.0.5/"},
                          headers=h)
        assert bad.status_code == 422

        job = client.post(f"/tenant/websites/{wid}/crawl?wait=true",
                          json={"max_pages": 20, "max_depth": 1}, headers=h).json()
        assert job["status"] == "done", job
        assert job["start_url"] == "https://acme.example/"
        assert job["pages_ingested"] == job["pages_found"] >= 5
        assert job["personas_added"] == 2 and job["design_found"] is True
        assert job["duration_s"] is not None

        assert client.get(f"/tenant/websites/{wid}/crawl", headers=h).json()["id"] == job["id"]
        ing = client.get(f"/tenant/websites/{wid}/ingestion", headers=h).json()
        assert ing["counts"]["ingested"] >= 5 and ing["document_count"] >= 5
        names = {s["name"] for s in ing["sources"]}
        assert "Pricing" in names and "Retailers" in names

        prof = client.get(f"/tenant/websites/{wid}/profile", headers=h).json()
        assert {p["slug"] for p in prof["personas"]} == {"retailers", "3pl-providers"}
        assert "/pricing" in prof["routes"] and not any(r.endswith(".pdf") for r in prof["routes"])

        design = client.get(f"/tenant/websites/{wid}/design", headers=h).json()
        assert design["extracted"]["colors"]["primary"] == "#e4572e"
        assert design["design"]["tokens"]["--ds-color-primary"] == "#e4572e"

        # A re-crawl refreshes the same sources instead of duplicating them,
        # and keeps the personas the site now has.
        again = client.post(f"/tenant/websites/{wid}/crawl?wait=true",
                            json={"max_pages": 20, "max_depth": 1}, headers=h).json()
        assert again["status"] == "done" and again["personas_added"] == 0
        ing2 = client.get(f"/tenant/websites/{wid}/ingestion", headers=h).json()
        assert len(ing2["sources"]) == len(ing["sources"])

        # Another tenant can't see or start this site's crawl.
        h2 = _tenant(client)
        assert client.get(f"/tenant/websites/{wid}/crawl", headers=h2).status_code == 404
        assert client.post(f"/tenant/websites/{wid}/crawl", json={}, headers=h2).status_code == 404


def test_upload_pdf_and_docx_sources():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid = client.post("/tenant/websites", json={"name": "Docs Co"}, headers=h).json()["id"]
        up = lambda name, data, ctype: client.post(  # noqa: E731
            f"/tenant/websites/{wid}/sources/upload",
            files={"file": (name, io.BytesIO(data), ctype)}, headers=h)
        r = up("guide.pdf", make_pdf("Setup takes one afternoon"), "application/pdf")
        assert r.status_code == 201 and "Setup takes one afternoon" in r.json()["preview"]
        r = up("faq.docx", make_docx([("", "Refunds within thirty days.")]),
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert r.status_code == 201 and r.json()["preview"] == "Refunds within thirty days."
        bad = up("broken.pdf", b"%PDF-1.4 garbage", "application/pdf")
        assert bad.status_code == 422 and "PDF" in bad.json()["detail"]
