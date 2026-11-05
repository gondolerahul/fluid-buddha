"""
A quote request as a one-page PDF (M2-8 follow-up).

The site's team downloads it from the console (Actions → recent runs) to file
or forward. Written out by hand — a single page of text needs no PDF library:
Helvetica with WinAnsi encoding, so Latin text and ₹ (as "Rs.") come out
exactly; characters outside that set (e.g. Devanagari names) print as "?".
"""
from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any

_W, _H = 595, 842          # A4 in points
_LEFT, _TOP = 56, 780
_MAX_LINES = 46


def _pdf_text(s: str) -> bytes:
    s = (s or "").replace("₹ ", "Rs. ").replace("₹", "Rs. ").replace("’", "'").replace("“", '"').replace("”", '"')
    raw = s.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def quote_pdf(*, company: str, action_label: str, run: dict[str, Any]) -> bytes:
    created = run.get("created_at")
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except ValueError:
            created = None
    when = created.strftime("%d %b %Y, %H:%M UTC") if isinstance(created, datetime) else ""
    ref = str(run.get("id", ""))[:8].upper()

    lines: list[tuple[str, int, str]] = [            # (font, size, text)
        ("F2", 20, f"Quote request: {action_label}"),
        ("F1", 11, f"{company} - reference {ref}" + (f" - {when}" if when else "")),
        ("F1", 11, ""),
    ]
    for item in run.get("summary") or []:
        label, value = str(item.get("label", "")), str(item.get("value", ""))
        wrapped = textwrap.wrap(value, 70) or [""]
        lines.append(("F2", 11, label))
        lines += [("F1", 11, w) for w in wrapped]
        lines.append(("F1", 6, ""))
    lines += [("F1", 11, ""),
              ("F1", 9, "Sent by a visitor through the website's FluidBuddha agent. Reply to the visitor "
                        "at the email above.")]
    lines = lines[:_MAX_LINES]

    ops = [b"BT"]
    y = _TOP
    for font, size, text_ in lines:
        ops.append(f"/{font} {size} Tf 1 0 0 1 {_LEFT} {y} Tm".encode() + b" (" + _pdf_text(text_) + b") Tj")
        y -= int(size * 1.45) if text_ else int(size * 0.9)
    ops.append(b"ET")
    # A thin accent line under the title.
    ops.append(f"0.79 0.64 0.29 RG 1.5 w {_LEFT} {_TOP - 12} m {_W - _LEFT} {_TOP - 12} l S".encode())
    stream = b"\n".join(ops)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_W} {_H}] "
        f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        f"<< /Title ({_pdf_text('Quote request ' + ref).decode('latin-1')}) /Producer (FluidBuddha) >>".encode(),
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {len(objects)} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)
