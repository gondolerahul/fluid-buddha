"""
Text out of uploaded or crawled documents (WS9): PDF, DOCX, and plain text.

PDF uses ``pypdf`` (pure Python). DOCX is a zip of XML, so it is read with the
standard library: paragraphs from ``word/document.xml``, with headings and list
items kept on their own lines. Scanned PDFs (images only) have no text layer;
they come back empty and are rejected with a clear message rather than OCR'd.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

MAX_TEXT_CHARS = 2_000_000
_MAX_PDF_PAGES = 300
# A decompressed DOCX part larger than this is refused (zip bomb guard).
_MAX_DOCX_XML = 30_000_000

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocumentError(ValueError):
    """The file can't be turned into text."""


def kind_of(filename: str, content_type: str = "") -> str:
    """'pdf', 'docx' or 'text' from the name (or the type when the name is bare)."""
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".pdf") or ctype == "application/pdf":
        return "pdf"
    if name.endswith(".docx") or "wordprocessingml" in ctype:
        return "docx"
    return "text"


def extract_text(raw: bytes, filename: str, content_type: str = "") -> str:
    kind = kind_of(filename, content_type)
    if kind == "pdf":
        text = pdf_text(raw)
    elif kind == "docx":
        text = docx_text(raw)
    else:
        text = raw.decode("utf-8", errors="replace")
    text = _tidy(text)[:MAX_TEXT_CHARS]
    if not text:
        if kind == "pdf":
            raise DocumentError("This PDF has no text layer (is it a scan?). "
                                "Upload a text PDF or paste the text.")
        raise DocumentError("The file has no readable text.")
    return text


def pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is required
        raise DocumentError("PDF support isn't installed on this server.") from exc
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            try:
                reader.decrypt("")  # many "protected" PDFs open with no password
            except Exception as exc:
                raise DocumentError("This PDF is password-protected.") from exc
        pages = []
        for page in reader.pages[:_MAX_PDF_PAGES]:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages)
    except DocumentError:
        raise
    except Exception as exc:  # pypdf raises many kinds on a malformed file
        raise DocumentError("This file isn't a readable PDF.") from exc


def docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML:
                raise DocumentError("This document is too large to read.")
            xml = z.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DocumentError("This file isn't a readable .docx document.") from exc
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise DocumentError("This file isn't a readable .docx document.") from exc
    lines: list[str] = []
    for para in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in para.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        line = "".join(parts).strip()
        if line:
            style = para.find(f"{_W}pPr/{_W}pStyle")
            val = (style.get(f"{_W}val") if style is not None else "") or ""
            if val.lower().startswith(("heading", "title")):
                line = "\n" + line  # a heading opens a new section
            lines.append(line)
    return "\n".join(lines)


def _tidy(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
