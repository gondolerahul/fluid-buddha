"""
Public, read-only widget check.

``GET /widget/config?key=...`` says what a widget key resolves to — the site,
its capability tier and design, and the agent's name — without running an agent
turn (no model or TTS spend, no usage recorded). The console's Install tab uses
it for "Test connection".

``GET /widget/loader.js`` is the one script every install surface points at
(M2-10: WordPress, Shopify, GTM, Webflow, Framer, the React/Vue wrappers)::

    <script src="https://<server>/widget/loader.js" data-key="fbk_..." async></script>

It adds the widget bundle (from ``WIDGET_SDK_BASE``) with the same ``data-*``
attributes, plus ``data-backend``/``data-api`` taken from its own address, so a
plugin needs only the server and the key — and the widget's location can move
without anyone editing their site. ``data-auto="false"`` loads the bundle
without showing the widget (the framework wrappers call ``FluidBuddha.init``
themselves); either way ``fluidbuddha:ready`` fires on ``window`` once it's
loaded. Where a script's attributes can't be set (GTM's sandboxed
``injectScript``), the same settings go in the query string
(``loader.js?key=fbk_...&position=bottom-left``). It is the same for every site
(no key lookup), so it caches.

``GET /widget/gtm-template.tpl`` is a Google Tag Manager custom template for
this server: GTM only lets a template inject scripts from addresses its
permissions list, so the template is generated with this server's address.

Only non-sensitive display settings are returned, so the Origin allow-list is
not applied here: the console checks a key from its own origin, not the
customer's. The turn paths (/chat, /ws/voice) still enforce it.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.config import get_settings
from app.db import session_scope
from app.integrations.gtm import build_template
from app.orchestrator.profile import ensure_profile
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.trust.settings import get_privacy

router = APIRouter(tags=["widget"])


@router.get("/widget/config")
async def widget_config(key: str = Query(..., min_length=1, max_length=200)) -> dict:
    try:
        async with session_scope() as db:
            resolved = await resolve_public_site(db, key=key, site=None, intelligence=None)
            privacy = await get_privacy(db, resolved.site_key)
    except PublicAccessError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    website = resolved.website
    profile = await ensure_profile(resolved.site_key)
    return {
        "site_key": resolved.site_key,
        "intelligence": resolved.intelligence,
        "design": website.design if website else None,
        "accent": website.accent if website else None,
        "agent_name": profile.agent_name,
        "company_name": profile.company_name,
        "languages": profile.languages,
        "widget_language": profile.widget_language,
        "privacy": privacy.public(),
    }


# Kept tiny and dependency-free: it runs on every page of every customer site.
# __SDK__ is a JSON string literal (so quotes and "</script>" can't break out).
_LOADER = r"""/* FluidBuddha loader (M2-10) */
(function(w,d){
  var me=d.currentScript;
  if(!me||w.__fluidBuddhaLoader)return;
  w.__fluidBuddhaLoader=1;
  var ready=function(){try{w.dispatchEvent(new Event('fluidbuddha:ready'))}catch(e){}};
  if(w.FluidBuddha){ready();return;}
  var base=me.src.replace(/[?#].*$/,'').replace(/\/widget\/loader\.js$/,'');
  var s=d.createElement('script');
  s.src=__SDK__;s.async=true;
  for(var i=0,a=me.attributes;i<a.length;i++){
    if(a[i].name.indexOf('data-')===0)s.setAttribute(a[i].name,a[i].value);
  }
  var q=(me.src.split('#')[0].split('?')[1]||'').split('&');
  for(var j=0;j<q.length;j++){
    var kv=q[j].split('='),n=kv[0];
    if(/^(key|position|lang|design|accent|auto|auto-start|tour|navigation)$/.test(n)&&!s.hasAttribute('data-'+n)){
      try{s.setAttribute('data-'+n,decodeURIComponent((kv[1]||'').replace(/\+/g,' ')))}catch(e){}
    }
  }
  if(!s.getAttribute('data-backend'))s.setAttribute('data-backend',base.replace(/^http/,'ws'));
  if(!s.getAttribute('data-api'))s.setAttribute('data-api',base);
  s.onload=ready;
  (d.head||d.documentElement).appendChild(s);
})(window,document);
"""


def loader_script(sdk_base: str) -> str:
    sdk = json.dumps(sdk_base.rstrip("/") + "/fluid-buddha.global.js").replace("</", "<\\/")
    return _LOADER.replace("__SDK__", sdk)


@router.api_route("/widget/loader.js", methods=["GET", "HEAD"], include_in_schema=False)
async def widget_loader() -> Response:
    return Response(
        loader_script(get_settings().widget_sdk_base),
        media_type="application/javascript; charset=utf-8",
        headers={
            # Short, so moving the widget's files reaches every site within minutes.
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


@router.get("/widget/gtm-template.tpl", include_in_schema=False)
async def gtm_template() -> Response:
    return Response(
        build_template(get_settings().public_api_url),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fluidbuddha-gtm-template.tpl"',
                 "Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
