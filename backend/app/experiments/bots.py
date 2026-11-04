"""
Keep automated traffic out of holdout experiments (WS11).

Crawlers, uptime monitors, link previewers, headless browsers and scripts
visit a site without ever converting. Enrolled, they dilute both arms and
shrink the measured lift towards zero — noise a small site can't afford.

Two signals, either is enough:
* the User-Agent names a bot, a monitoring service or an HTTP library, or is
  missing altogether;
* the widget reports ``navigator.webdriver`` (set by Selenium, Puppeteer,
  Playwright and headless Chrome under automation).

Bots aren't enrolled; the widget then simply shows (nobody is held out on the
strength of a guess) and the run counts how many were turned away.
"""
from __future__ import annotations

import re
from typing import Optional

_BOT_UA = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|archiver|scanner|"
    r"facebookexternalhit|embedly|quora link preview|whatsapp|"
    r"headlesschrome|phantomjs|lighthouse|"
    r"pagespeed|gtmetrix|pingdom|uptimerobot|statuscake|site24x7|datadog|newrelic|"
    r"curl/|wget/|python-requests|python-urllib|python-httpx|aiohttp|httpie|"
    r"go-http-client|java/|okhttp|apache-httpclient|axios/|node-fetch|undici|"
    r"scrapy|selenium|puppeteer|playwright|cypress",
    re.IGNORECASE,
)


def is_bot(user_agent: Optional[str], automated: object = False) -> bool:
    if automated is True:
        return True
    ua = (user_agent or "").strip()
    return not ua or bool(_BOT_UA.search(ua))
