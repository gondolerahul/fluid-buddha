"""The public status page (M3-6): server-rendered, no scripts, refreshes itself."""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

_OVERALL = {"operational": ("All systems operational", "#3caa6e"),
            "degraded": ("Some systems are degraded", "#d9a520"),
            "outage": ("Some systems are down", "#d9534f")}
_STATE = {"up": ("Operational", "#3caa6e"), "degraded": ("Degraded", "#d9a520"), "down": ("Down", "#d9534f"),
          None: ("No data", "#4a4f5c")}
_STATUS = {"investigating": "Investigating", "identified": "Identified", "monitoring": "Monitoring",
           "resolved": "Resolved", "scheduled": "Scheduled"}


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return iso


def render(s: dict[str, Any], *, title: str) -> str:
    head, colour = _OVERALL[s["overall"]]
    comps = []
    for c in s["components"]:
        label, col = _STATE[c["state"]]
        bars = "".join(
            f'<i style="background:{_STATE[d["state"]][1]}" title="{escape(d["day"])}: '
            f'{escape(_STATE[d["state"]][0])}{"" if d["uptime"] is None else f" · {d["uptime"] * 100:.2f}%"}"></i>'
            for d in c["days"])
        uptime = "—" if c["uptime"] is None else f"{c['uptime'] * 100:.2f}% uptime"
        comps.append(
            f'<section class="comp"><div class="row"><strong>{escape(c["label"])}</strong>'
            f'<span style="color:{col}">{label}</span></div><div class="bars">{bars}</div>'
            f'<div class="row faint"><span>{len(c["days"])} days ago</span><span>{uptime}</span><span>Today</span></div>'
            "</section>")
    open_ = [i for i in s["incidents"] if i["status"] != "resolved"]
    past = [i for i in s["incidents"] if i["status"] == "resolved"]

    def incident(i: dict[str, Any]) -> str:
        ups = "".join(f'<li><b>{escape(_STATUS.get(u["status"], u["status"]))}</b> — {escape(u["body"])}'
                      f'<div class="faint">{escape(_when(u["at"]))}</div></li>' for u in i["updates"])
        imp = "Maintenance" if i["impact"] == "maintenance" else f'{i["impact"].capitalize()} impact'
        return (f'<article class="inc inc-{escape(i["impact"])}"><h3>{escape(i["title"])}</h3>'
                f'<div class="faint">{escape(imp)} · {escape(", ".join(i["components"]) or "all systems")}</div>'
                f"<ul>{ups}</ul></article>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>{escape(title)} status</title>
<style>
body{{margin:0;background:#0c0d11;color:#eef0f4;font-family:ui-sans-serif,system-ui,sans-serif;line-height:1.5}}
.wrap{{max-width:860px;margin:0 auto;padding:36px 20px 60px}}h1{{font-size:1.4rem;margin:0 0 20px}}
.banner{{padding:16px 20px;border-radius:12px;font-weight:600;margin-bottom:28px;color:#0c0d11}}
.comp{{background:#15171d;border-radius:12px;padding:16px 18px;margin-bottom:12px}}
.row{{display:flex;justify-content:space-between;gap:12px}}.faint{{color:#8a91a0;font-size:.8rem}}
.bars{{display:flex;gap:2px;margin:12px 0 6px;height:30px}}.bars i{{flex:1;border-radius:2px;min-width:2px}}
h2{{font-size:1.05rem;margin:32px 0 12px}}.inc{{background:#15171d;border-radius:12px;padding:14px 18px;margin-bottom:12px;border-left:4px solid #d9a520}}
.inc-critical{{border-left-color:#d9534f}}.inc-maintenance{{border-left-color:#5b8def}}.inc h3{{margin:0 0 4px;font-size:1rem}}
.inc ul{{list-style:none;padding:0;margin:10px 0 0}}.inc li{{margin-bottom:8px}}
footer{{margin-top:40px}}
</style></head>
<body><div class="wrap">
<h1>{escape(title)} status</h1>
<div class="banner" role="status" style="background:{colour}">{escape(head)}</div>
{"".join(incident(i) for i in open_)}
{"".join(comps)}
<h2>Past incidents (14 days)</h2>
{"".join(incident(i) for i in past) or '<p class="faint">No incidents.</p>'}
<footer class="faint">Checked every minute · updated {escape(_when(s["generated_at"]))} ·
<a href="/status.json" style="color:#8a91a0">status.json</a></footer>
</div></body></html>"""
