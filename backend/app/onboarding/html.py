"""
Read one HTML page for onboarding: its readable text (for the knowledge base),
the links on it (for the crawler), its title/headings/description (for page
names and personas), and its styling hooks (for design-token extraction).

Standard-library ``html.parser`` only; forgiving of broken markup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

# Content that is never visible copy.
# (Not <head>: its closing tag is optional, and its text is only the title.)
_SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "canvas"}
# Navigation chrome repeats on every page and adds nothing to the knowledge base.
_CHROME = {"nav"}
_BLOCK = {"p", "div", "section", "article", "main", "header", "footer", "li", "ul", "ol",
          "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "table", "blockquote", "dd", "dt",
          "figcaption", "aside", "form", "label"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "source", "track", "wbr"}


@dataclass
class PageInfo:
    url: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    theme_color: str = ""
    h1: str = ""
    headings: list[str] = field(default_factory=list)
    text: str = ""
    links: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)
    inline_css: str = ""
    logo_candidates: list[str] = field(default_factory=list)
    icons: list[str] = field(default_factory=list)
    og_image: str = ""
    noindex: bool = False

    @property
    def name(self) -> str:
        """A short page name: the h1, else the title."""
        return (self.h1 or self.title or "").strip()[:200]


class _Reader(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.info = PageInfo(url=base_url)
        self._skip = 0
        self._chrome = 0
        self._in_title = False
        self._heading: str | None = None
        self._heading_buf: list[str] = []
        self._in_style = False
        self._parts: list[str] = []
        self._css: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _abs(self, href: str | None) -> str:
        href = (href or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            return ""
        return urljoin(self.base, href)

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "base" and a.get("href"):
            self.base = urljoin(self.base, a["href"])
        if tag == "title":
            self._in_title = True
        elif tag == "style":
            self._in_style = True
        elif tag == "meta":
            self._meta(a)
        elif tag == "link":
            self._link(a)
        elif tag == "a":
            href = self._abs(a.get("href"))
            if href and "nofollow" not in a.get("rel", "").lower():
                self.info.links.append(href)
        elif tag == "img":
            hint = " ".join((a.get("class", ""), a.get("id", ""), a.get("alt", ""),
                             a.get("src", ""))).lower()
            src = self._abs(a.get("src"))
            if src and "logo" in hint:
                self.info.logo_candidates.append(src)
        if tag in ("h1", "h2", "h3") and not self._skip:
            self._heading, self._heading_buf = tag, []
        if tag in _SKIP and tag not in _VOID:
            self._skip += 1
        if tag in _CHROME:
            self._chrome += 1
        if tag in _BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "style":
            self._in_style = False
        if tag in _SKIP and self._skip:
            self._skip -= 1
        if tag in _CHROME and self._chrome:
            self._chrome -= 1
        if self._heading == tag:
            text = _squash(" ".join(self._heading_buf))
            if text:
                if tag == "h1" and not self.info.h1:
                    self.info.h1 = text
                self.info.headings.append(text)
            self._heading = None
        if tag in _BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.info.title += data
            return
        if self._in_style:
            self._css.append(data)
            return
        if self._skip:
            return
        if self._heading:
            self._heading_buf.append(data)
        if not self._chrome:
            self._parts.append(data)

    def _meta(self, a: dict) -> None:
        name = (a.get("name") or a.get("property") or "").lower()
        content = a.get("content", "").strip()
        if name in ("description", "og:description") and not self.info.description:
            self.info.description = content
        elif name == "og:site_name":
            self.info.site_name = content
        elif name == "theme-color" and not self.info.theme_color:
            self.info.theme_color = content
        elif name == "og:image" and not self.info.og_image:
            self.info.og_image = self._abs(content)
        elif name == "robots" and "noindex" in content.lower():
            self.info.noindex = True

    def _link(self, a: dict) -> None:
        rel = a.get("rel", "").lower().split()
        href = self._abs(a.get("href"))
        if not href:
            return
        if "stylesheet" in rel:
            self.info.stylesheets.append(href)
        elif "apple-touch-icon" in rel or "icon" in rel:
            self.info.icons.append(href)

    def result(self) -> PageInfo:
        self.info.title = _squash(self.info.title)
        self.info.inline_css = "\n".join(self._css)
        text = "".join(self._parts)
        lines = [_squash(line) for line in text.split("\n")]
        out: list[str] = []
        for line in lines:
            if line:
                out.append(line)
            elif out and out[-1] != "":
                out.append("")
        self.info.text = "\n".join(out).strip()
        self.info.links = list(dict.fromkeys(self.info.links))
        return self.info


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_page(html: str, url: str) -> PageInfo:
    reader = _Reader(url)
    try:
        reader.feed(html or "")
        reader.close()
    except Exception:  # html.parser rarely raises; keep whatever was read
        pass
    return reader.result()
