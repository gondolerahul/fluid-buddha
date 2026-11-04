"""Per-site privacy settings (WS8). A site without a row gets the defaults, so
the public path reads without writing."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TRANSCRIPT_RETENTION_DAYS = (0, 30, 90, 180, 365)
LEAD_RETENTION_DAYS = (0, 90, 180, 365, 730)
# How long a shared recap link works (M2-6).
RECAP_DAYS = (7, 30, 90, 180, 365)
DEFAULT_RECAP_DAYS = 90
DEFAULT_TRANSCRIPT_DAYS = 90


@dataclass
class Privacy:
    redact_pii: bool = True
    consent_required: bool = True
    privacy_policy_url: Optional[str] = None
    transcript_retention_days: int = DEFAULT_TRANSCRIPT_DAYS   # 0 = keep
    lead_retention_days: int = 0                               # 0 = keep
    recap_days: int = DEFAULT_RECAP_DAYS

    def to_dict(self) -> dict:
        return asdict(self)

    def public(self) -> dict:
        """What the widget needs to word its consent prompt."""
        return {
            "consent_required": self.consent_required,
            "policy_url": self.privacy_policy_url,
            "retention_days": self.transcript_retention_days,
            "redacts_pii": self.redact_pii,
        }


_COLS = ("redact_pii, consent_required, privacy_policy_url, "
         "transcript_retention_days, lead_retention_days, recap_days")


async def get_privacy(db: AsyncSession, site_key: str) -> Privacy:
    row = (await db.execute(text(f"SELECT {_COLS} FROM site_privacy WHERE site_key=:s"),
                            {"s": site_key})).mappings().first()
    return Privacy(**row) if row else Privacy()


async def save_privacy(db: AsyncSession, site_key: str, p: Privacy) -> Privacy:
    await db.execute(text(
        f"INSERT INTO site_privacy (site_key, {_COLS}) VALUES "
        "(:s, :rp, :cr, :url, :td, :ld, :rd) "
        "ON CONFLICT (site_key) DO UPDATE SET redact_pii=EXCLUDED.redact_pii, "
        "consent_required=EXCLUDED.consent_required, "
        "privacy_policy_url=EXCLUDED.privacy_policy_url, "
        "transcript_retention_days=EXCLUDED.transcript_retention_days, "
        "lead_retention_days=EXCLUDED.lead_retention_days, "
        "recap_days=EXCLUDED.recap_days, updated_at=now()"
    ), {"s": site_key, "rp": p.redact_pii, "cr": p.consent_required,
        "url": p.privacy_policy_url, "td": p.transcript_retention_days,
        "ld": p.lead_retention_days, "rd": p.recap_days})
    await db.commit()
    return p
