"""
Who may do what in an account (M2-1).

Four roles, each including the ones below it:

* **owner**  — everything, incl. billing changes and SSO settings;
* **admin**  — the team, integrations (they hold signing secrets), privacy and
  visitor erasure, deleting a website or rotating its key, the audit log;
* **editor** — the websites' content and behaviour: knowledge, tours, profile,
  cached answers, experiments, leads;
* **viewer** — read-only.

The rule is applied centrally, from the HTTP method and the route template,
by the authentication dependency itself (``app.auth.security.current_member``),
so a new route is covered the moment it requires a signed-in member: reads
need ``viewer``, changes need ``editor``, unless ``_RULES`` says more. A test
walks every route to keep this table honest.
"""
from __future__ import annotations

import re

ROLES = ("viewer", "editor", "admin", "owner")
_RANK = {r: i for i, r in enumerate(ROLES)}

READ = {"GET", "HEAD", "OPTIONS"}

# (methods or "*", path regex) -> minimum role. First match wins.
_RULES: list[tuple[object, str, str]] = [
    # Billing: Admins can look, only the Owner can pay, change or cancel.
    (READ, r"^/tenant/billing", "admin"),
    ("*", r"^/tenant/billing", "owner"),
    # SSO settings.
    (READ, r"^/tenant/sso", "admin"),
    ("*", r"^/tenant/sso", "owner"),
    # Team and audit log.
    (READ, r"^/tenant/team", "viewer"),
    ("*", r"^/tenant/team", "admin"),
    ("*", r"^/tenant/audit", "admin"),
    # Integrations hold the webhook signing secret, even to read.
    ("*", r"^/tenant/websites/[^/]+/integrations", "admin"),
    # Privacy settings and erasing a visitor's data.
    ({"PUT", "POST", "PATCH", "DELETE"}, r"^/tenant/websites/[^/]+/privacy", "admin"),
    # Deleting a website, or rotating its widget key (breaks live installs).
    ({"DELETE"}, r"^/tenant/websites/[^/]+$", "admin"),
    ({"POST"}, r"^/tenant/websites/[^/]+/rotate-key$", "admin"),
]
_COMPILED = [(m, re.compile(p), r) for m, p, r in _RULES]


def at_least(role: str, needed: str) -> bool:
    return _RANK.get(role, -1) >= _RANK[needed]


def required_role(method: str, path: str) -> str:
    """Minimum role for ``method`` on the route template ``path``."""
    method = method.upper()
    for methods, rx, role in _COMPILED:
        if (methods == "*" or method in methods) and rx.search(path):
            return role
    return "viewer" if method in READ else "editor"


def can_assign(actor: str, role: str) -> bool:
    """Only an Owner can make (or unmake) an Owner; Admins manage the rest."""
    if role == "owner":
        return actor == "owner"
    return at_least(actor, "admin")
