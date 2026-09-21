"""
Document and DocumentVersion database repository operations (Phase 3).
"""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentVersion


async def get_document_by_id(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> Optional[Document]:
    """Fetch a Document by its UUID primary key, eagerly loading all versions."""
    query = (
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def get_document_by_key(
    db: AsyncSession,
    document_key: str,
) -> Optional[Document]:
    """Fetch a Document by its unique slug/key, eagerly loading all versions."""
    query = (
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.document_key == document_key)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().first()


async def get_document_version_by_id(
    db: AsyncSession,
    version_id: uuid.UUID,
) -> Optional[DocumentVersion]:
    """Fetch a DocumentVersion by its UUID."""
    query = (
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.id == version_id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def get_version_by_hash(
    db: AsyncSession,
    file_hash: str,
) -> Optional[DocumentVersion]:
    """Look up an existing DocumentVersion by its SHA-256 file hash."""
    query = (
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.file_hash == file_hash)
        .order_by(DocumentVersion.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().first()


async def list_documents(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    topic: Optional[str] = None,
    document_type: Optional[str] = None,
) -> Tuple[List[Document], int]:
    """
    List documents with optional topic/type filtering and pagination.

    Returns:
        (items, total_count)
    """
    base_query = select(Document)
    count_query = select(func.count(Document.id))

    if topic:
        base_query = base_query.where(Document.topic == topic)
        count_query = count_query.where(Document.topic == topic)

    if document_type:
        base_query = base_query.where(Document.document_type == document_type)
        count_query = count_query.where(Document.document_type == document_type)

    # Order by updated_at descending
    base_query = (
        base_query.options(selectinload(Document.versions))
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one() or 0

    items_result = await db.execute(base_query)
    items = list(items_result.scalars().all())

    return items, total


async def list_document_versions(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> List[DocumentVersion]:
    """List all versions for a given document ordered by version_number desc."""
    query = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())
