"""
Ingestion CLI — populate the CORTEX memory for a site.

    python -m ingestion.ingest --site hirebuddha
    python -m ingestion.ingest --site hirebuddha --reset

Runs standalone (no FastAPI). With MOCK_AI=true it uses 768-dim hash embeddings
so it works with zero Google Cloud setup; flip MOCK_AI=false to embed with
Vertex text-embedding-004.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.ai.factory import build_engines
from app.config import get_settings, site_entity_id
from app.cortex.bridge import CortexBridge
from app.cortex.providers import build_cortex_providers
from app.db import SessionLocal, init_db
from app.logging_config import configure_logging
from app.orchestrator.profile import ensure_profile
from app.orchestrator.tour import plan_tour
from app.orchestrator.tour_store import save_plan
from ingestion.scraper import SourceDocument, load_site_documents

logger = logging.getLogger("ingest")


async def _reset_site(site_key: str) -> None:
    """Delete the site's knowledge tree (and cascade its nodes) for re-ingest."""
    settings = get_settings()
    entity_id = site_entity_id(site_key)
    async with SessionLocal() as db:
        await db.execute(
            text("DELETE FROM cortex_trees WHERE entity_id = :eid AND company_id = :cid"),
            {"eid": str(entity_id), "cid": str(settings.cortex_company_id)},
        )
        await db.commit()
    logger.info("Reset knowledge tree for site=%s", site_key)


async def _document_count(site_key: str) -> int:
    """How many DOCUMENT nodes the site already has (0 == not ingested yet)."""
    settings = get_settings()
    entity_id = site_entity_id(site_key)
    async with SessionLocal() as db:
        res = await db.execute(
            text(
                "SELECT COUNT(*) FROM cortex_nodes n "
                "JOIN cortex_trees t ON n.tree_id = t.id "
                "WHERE t.entity_id = :eid AND t.company_id = :cid "
                "AND n.node_type = 'document'"
            ),
            {"eid": str(entity_id), "cid": str(settings.cortex_company_id)},
        )
        return int(res.scalar() or 0)


async def ingest_documents(site_key: str, documents: list[SourceDocument]) -> int:
    """Ingest a list of :class:`SourceDocument` into a site's CORTEX tree and
    return the number of nodes created. Reusable by both the CLI and the admin
    dashboard's per-website ingestion (it opens its own DB session)."""
    settings = get_settings()
    providers = build_cortex_providers(settings)
    total_nodes = 0
    async with SessionLocal() as db:
        bridge = CortexBridge(db, settings, providers, site_key=site_key)
        await bridge.ensure_tree()
        for doc in documents:
            n = await bridge.ingest(doc.content, doc.filename, doc.document_id)
            total_nodes += n
            logger.info("  ingested %-44s route=%-26s nodes=%d",
                        doc.filename, doc.route, n)
        await db.commit()
    return total_nodes


async def plan_and_save_tour(site_key: str, documents: list[SourceDocument]) -> None:
    """Author + persist the guided tour from a site's documents (best-effort)."""
    settings = get_settings()
    try:
        await ensure_profile(site_key)  # agent name / company / closing example
        engines = build_engines(settings)
        plan = await plan_tour(
            site_key=site_key, documents=documents, llm=engines.llm, settings=settings
        )
        async with SessionLocal() as db:
            await save_plan(db, plan, keep_edited=True)
    except Exception as exc:
        logger.warning("tour planning skipped for site=%s: %s", site_key, exc)


async def run(site_key: str, reset: bool, if_empty: bool = False) -> None:
    settings = get_settings()
    await init_db()
    if reset:
        await _reset_site(site_key)
    elif if_empty:
        existing = await _document_count(site_key)
        if existing > 0:
            logger.info("site=%s already ingested (%d docs) — skipping", site_key, existing)
            return

    documents = load_site_documents(site_key)
    if not documents:
        logger.warning("No source documents found for site=%s", site_key)
        return

    total_nodes = await ingest_documents(site_key, documents)

    # Author the guided tour from the freshly-ingested page structure (Req 5).
    # Planned once here so runtime playback needs no LLM and stays perfectly
    # in sync. Best-effort: a tour failure must never fail the ingest.
    await plan_and_save_tour(site_key, documents)

    logger.info(
        "Done. site=%s docs=%d nodes=%d  (mock_ai=%s)",
        site_key, len(documents), total_nodes, settings.mock_ai,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a site into CORTEX memory.")
    parser.add_argument("--site", default="hirebuddha")
    parser.add_argument("--reset", action="store_true",
                        help="Drop the site's existing knowledge tree first.")
    parser.add_argument("--if-empty", action="store_true",
                        help="Skip ingestion if the site already has documents.")
    args = parser.parse_args()

    configure_logging(get_settings().log_level)
    asyncio.run(run(args.site, args.reset, args.if_empty))


if __name__ == "__main__":
    main()
