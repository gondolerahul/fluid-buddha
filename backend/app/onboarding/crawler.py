"""
Website crawler for self-serve onboarding (WS9).

Paste a URL, get the site's pages: the crawler reads ``robots.txt`` (and obeys
it for our user agent, including a modest ``Crawl-delay``), seeds itself from
the sitemap when there is one, then follows same-site links breadth-first up to
a depth and page limit. Every request goes through the SSRF-guarded fetch
(``app.tenancy.url_fetch``), so a tenant can't point it at internal addresses,
and every redirect hop is re-checked.

Pages are HTML (text, links, headings and styling hooks are read) or a linked
PDF (its text). Query strings and fragments are dropped, so one path is one
page. ``noindex`` pages are skipped.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.onboarding.html import PageInfo, parse_page
from app.tenancy.url_fetch import Fetched, UnsafeURLError, fetch_public

logger = logging.getLogger(__name__)

USER_AGENT = "FluidBuddhaIngest"
HTML_TYPES = ("text/html", "application/xhtml+xml")
PDF_TYPE = "application/pdf"
_TEXT_TYPES = ("text/plain",)
_XML_TYPES = ("application/xml", "text/xml", "text/plain", "application/x-xml")
_MAX_PDF_BYTES = 10_000_000
_MAX_CRAWL_DELAY_S = 2.0
_MAX_SITEMAPS = 5
# Links to these are never pages worth reading.
_SKIP_EXT = re.compile(
    r"\.(png|jpe?g|gif|webp|svg|ico|bmp|tiff?|css|js|mjs|json|xml|rss|atom|zip|gz|tgz|"
    r"rar|7z|dmg|exe|msi|apk|mp3|wav|ogg|mp4|mov|avi|webm|woff2?|ttf|otf|eot|csv|xlsx?|"
    r"pptx?|docx?)$",
    re.I,
)

Fetcher = Callable[..., Awaitable[Fetched]]


@dataclass
class CrawledPage:
    url: str
    depth: int
    kind: str              # "html" | "pdf" | "text"
    info: Optional[PageInfo] = None
    text: str = ""          # readable text (for the knowledge base)

    @property
    def ingestible(self) -> bool:
        """Enough copy to be worth adding to the knowledge base."""
        body = self.info.text if self.info else self.text
        return len(body.strip()) >= 40

    @property
    def title(self) -> str:
        if self.info and self.info.name:
            return self.info.name
        path = urlsplit(self.url).path.rstrip("/")
        return path.rsplit("/", 1)[-1] or urlsplit(self.url).hostname or self.url


@dataclass
class CrawlResult:
    start_url: str
    pages: list[CrawledPage] = field(default_factory=list)
    skipped: int = 0                 # errors, non-pages, noindex
    blocked_by_robots: int = 0
    used_sitemap: bool = False

    @property
    def home(self) -> Optional[CrawledPage]:
        return next((p for p in self.pages if p.kind == "html"), None)


def normalize(url: str) -> str:
    """One canonical form per page: no query, no fragment, no trailing slash."""
    parts = urlsplit(url)
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), (parts.netloc or "").lower(), path, "", ""))


def _site_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class _Robots:
    def __init__(self, parser: Optional[RobotFileParser], disallow_all: bool = False) -> None:
        self.parser = parser
        self.disallow_all = disallow_all

    def allowed(self, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.parser is None:
            return True
        # Pages are kept without a trailing slash, but rules are often written
        # with one ("Disallow: /private/"): the page must pass both forms.
        forms = {url}
        parts = urlsplit(url)
        if not parts.path.endswith("/"):
            forms.add(urlunsplit(parts._replace(path=parts.path + "/")))
        return all(self.parser.can_fetch(USER_AGENT, f) for f in forms)

    @property
    def delay(self) -> float:
        d = self.parser.crawl_delay(USER_AGENT) if self.parser else None
        return min(float(d or 0), _MAX_CRAWL_DELAY_S)

    @property
    def sitemaps(self) -> list[str]:
        return list(self.parser.site_maps() or []) if self.parser else []


async def _robots(origin: str, fetch: Fetcher) -> _Robots:
    try:
        got = await fetch(urljoin(origin, "/robots.txt"), allowed_types=_TEXT_TYPES,
                          max_bytes=500_000)
    except httpx.HTTPStatusError as exc:
        # As the robots standard says: 401/403 means "keep out"; 404 means none.
        code = exc.response.status_code
        return _Robots(None, disallow_all=code in (401, 403))
    except (UnsafeURLError, httpx.HTTPError):
        return _Robots(None)
    parser = RobotFileParser()
    parser.parse(got.text.splitlines())
    return _Robots(parser)


_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


async def _sitemap_urls(origin: str, robots: _Robots, fetch: Fetcher, limit: int) -> list[str]:
    """Page URLs from the sitemap(s), following one level of sitemap index."""
    queue = robots.sitemaps or [urljoin(origin, "/sitemap.xml")]
    seen: set[str] = set()
    pages: list[str] = []
    fetched = 0
    while queue and fetched < _MAX_SITEMAPS and len(pages) < limit * 4:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        fetched += 1
        try:
            got = await fetch(sm, allowed_types=_XML_TYPES, max_bytes=5_000_000)
        except (UnsafeURLError, httpx.HTTPError):
            continue
        body = got.text
        locs = [loc.replace("&amp;", "&") for loc in _LOC_RE.findall(body)]
        if "<sitemapindex" in body[:2000].lower():
            queue.extend(locs)
        else:
            pages.extend(locs)
    return pages


async def crawl(
    start_url: str,
    *,
    max_pages: int = 25,
    max_depth: int = 2,
    concurrency: int = 4,
    fetch: Fetcher = fetch_public,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> CrawlResult:
    start = normalize(start_url)
    parts = urlsplit(start)
    origin = f"{parts.scheme}://{parts.netloc}"
    host = _site_host(start)
    result = CrawlResult(start_url=start)

    robots = await _robots(origin, fetch)
    if robots.delay:
        concurrency = 1  # a site that asks for a delay gets one request at a time

    def in_scope(url: str) -> bool:
        p = urlsplit(url)
        return (p.scheme in ("http", "https") and _site_host(url) == host
                and not _SKIP_EXT.search(p.path))

    queue: list[tuple[str, int]] = [(start, 0)]
    seen: set[str] = {start}
    for loc in await _sitemap_urls(origin, robots, fetch, max_pages):
        u = normalize(loc)
        if in_scope(u) and u not in seen:
            seen.add(u)
            queue.append((u, 1))
            result.used_sitemap = True

    lock = asyncio.Lock()

    async def visit(url: str, depth: int) -> None:
        if not robots.allowed(url):
            result.blocked_by_robots += 1
            return
        try:
            got = await fetch(url, allowed_types=HTML_TYPES + _TEXT_TYPES + (PDF_TYPE,),
                              max_bytes=_MAX_PDF_BYTES)
        except Exception as exc:  # one bad page must not stop the crawl
            logger.info("crawl skip %s: %s", url, exc)
            result.skipped += 1
            return
        final = normalize(got.url)
        if _site_host(final) != host:  # redirected off the site
            result.skipped += 1
            return
        if not robots.allowed(got.url) or not robots.allowed(final):
            result.blocked_by_robots += 1  # redirected into a disallowed path
            return
        page = _read(got, final, depth)
        if page is None:
            result.skipped += 1
            return
        async with lock:
            if len(result.pages) >= max_pages or any(p.url == final for p in result.pages):
                return
            seen.add(final)
            result.pages.append(page)
            if on_progress:
                await on_progress(len(result.pages))
            if page.info and depth < max_depth:
                for link in page.info.links:
                    u = normalize(link)
                    if u not in seen and in_scope(u):
                        seen.add(u)
                        queue.append((u, depth + 1))

    while queue and len(result.pages) < max_pages:
        batch = [queue.pop(0) for _ in range(min(concurrency, len(queue),
                                                 max_pages - len(result.pages)))]
        await asyncio.gather(*(visit(u, d) for u, d in batch))
        if robots.delay:
            await asyncio.sleep(robots.delay)
    return result


def _read(got: Fetched, url: str, depth: int) -> Optional[CrawledPage]:
    if got.content_type == PDF_TYPE:
        from app.onboarding.documents import DocumentError, pdf_text
        try:
            text = pdf_text(got.body).strip()
        except DocumentError:
            return None
        return CrawledPage(url=url, depth=depth, kind="pdf", text=text) if text else None
    if got.content_type in _TEXT_TYPES:
        text = got.text.strip()
        return CrawledPage(url=url, depth=depth, kind="text", text=text) if text else None
    info = parse_page(got.text, got.url)
    if info.noindex:
        return None
    text = info.text
    if info.title and not text.startswith(info.title):
        text = f"{info.title}\n\n{text}"
    if len(info.text) < 40 and not info.links:
        return None  # an empty shell (e.g. a client-rendered app with no SSR)
    return CrawledPage(url=url, depth=depth, kind="html", info=info, text=text)
