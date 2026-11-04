"""
Email layout (M2-0): one branded, plain HTML shell plus a text twin.

Every value put into the HTML goes through ``esc``; templates build their body
from ``paragraph`` / ``button`` / ``rows`` so nothing is concatenated raw. No
images, no tracking pixels, inline styles only (what email clients support).
"""
from __future__ import annotations

from html import escape as _escape

ACCENT = "#c9a24a"


def esc(value: object) -> str:
    return _escape(str(value), quote=True)


def paragraph(text: str) -> str:
    return f'<p style="margin:0 0 14px;line-height:1.55">{esc(text)}</p>'


def button(label: str, url: str) -> str:
    if not url.startswith(("https://", "http://")):
        raise ValueError("button links must be http(s)")
    return (f'<p style="margin:20px 0"><a href="{esc(url)}" style="background:{ACCENT};'
            f'color:#14110a;padding:11px 18px;border-radius:8px;text-decoration:none;'
            f'font-weight:600;display:inline-block">{esc(label)}</a></p>')


def rows(pairs: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#6b6f78">{esc(k)}</td>'
        f'<td style="padding:6px 0;font-weight:600">{esc(v)}</td></tr>' for k, v in pairs)
    return f'<table style="border-collapse:collapse;margin:0 0 14px">{cells}</table>'


def layout(title: str, body_html: str, footer: str = "") -> str:
    foot = f'<p style="color:#8a8f99;font-size:12px;margin-top:28px">{esc(footer)}</p>' if footer else ""
    return (
        '<!doctype html><html><body style="margin:0;background:#f5f5f2;font-family:'
        "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1d1f24\">"
        '<div style="max-width:560px;margin:0 auto;padding:28px 20px">'
        f'<div style="font-weight:700;font-size:15px;color:{ACCENT};margin-bottom:18px">FluidBuddha</div>'
        '<div style="background:#fff;border-radius:12px;padding:26px 24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{esc(title)}</h1>{body_html}</div>'
        f"{foot}</div></body></html>"
    )
