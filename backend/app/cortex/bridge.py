"""
Thin host adapter around cortex_memory's KnowledgeTreeService.

One persistent, entity-scoped Knowledge Tree per target website. Ingestion
builds DOCUMENT -> SECTION -> CHUNK nodes (chunks carry 768-dim embeddings);
retrieval is cosine search over those chunks with provenance.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cortex_memory.knowledge_tree import KnowledgeTreeService

from app.config import Settings, site_entity_id
from app.cortex.providers import CortexProviders

logger = logging.getLogger(__name__)


class CortexBridge:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        providers: CortexProviders,
        *,
        site_key: str = "hirebuddha",
    ) -> None:
        self.session = session
        self.settings = settings
        self.site_key = site_key
        self.company_id = settings.cortex_company_id
        self.entity_id = site_entity_id(site_key)
        self.kt = KnowledgeTreeService(
            session, self.company_id, embedding=providers.embedding
        )

    async def ensure_tree(self):
        return await self.kt.get_or_create_knowledge_tree(self.entity_id)

    async def ingest(
        self, content: str, filename: str, document_id: Optional[UUID] = None
    ) -> int:
        tree = await self.ensure_tree()
        return await self.kt.ingest_document(
            tree.id, document_id or uuid4(), content, filename, self.entity_id
        )

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return await self.kt.search(self.entity_id, query, top_k=top_k)
