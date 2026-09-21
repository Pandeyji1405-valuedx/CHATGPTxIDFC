"""
ChromaDB vector database service for RBI Knowledge Base (Phase 3).

Manages the persistent vector store, the `rbi_documents` collection,
and vector indexing/querying operations.
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings
from app.services.chunking.text_chunker import DocumentChunk

logger = logging.getLogger(__name__)
settings = get_settings()


class ChromaDBService:
    """
    Service wrapper for ChromaDB persistent collection operations.
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        in_memory: bool = False,
    ):
        self.persist_directory = persist_directory or settings.CHROMADB_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.in_memory = in_memory

        self._client: Optional[ClientAPI] = None
        self._collection: Optional[Collection] = None

    def _get_client(self) -> ClientAPI:
        """Initialize ChromaDB client (PersistentClient or EphemeralClient)."""
        if self._client is None:
            if self.in_memory:
                self._client = chromadb.EphemeralClient()
            else:
                os.makedirs(self.persist_directory, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    def get_collection(self) -> Collection:
        """Get or create the target ChromaDB collection with cosine distance."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> int:
        """
        Upsert text chunks and their embeddings with metadata into ChromaDB.

        Args:
            chunks: List of DocumentChunk objects.
            embeddings: Corresponding list of vector embeddings.

        Returns:
            Number of chunks successfully indexed.

        Raises:
            ValueError: If chunk count does not match embedding count.
            RuntimeError: If ChromaDB indexing encounters an error.
        """
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings."
            )

        collection = self.get_collection()

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            # Ensure all metadata values are primitive types (str, int, float, bool)
            clean_meta = {}
            for k, v in chunk.metadata.items():
                if v is None:
                    clean_meta[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        # Batch upsert (ChromaDB handles upsert idempotently by ID)
        batch_size = 100
        total_indexed = 0

        try:
            for i in range(0, len(ids), batch_size):
                b_ids = ids[i : i + batch_size]
                b_docs = documents[i : i + batch_size]
                b_embs = embeddings[i : i + batch_size]
                b_metas = metadatas[i : i + batch_size]

                collection.upsert(
                    ids=b_ids,
                    documents=b_docs,
                    embeddings=b_embs,
                    metadatas=b_metas,
                )
                total_indexed += len(b_ids)

            logger.info("Successfully indexed %d chunks in collection '%s'", total_indexed, self.collection_name)
            return total_indexed

        except Exception as exc:
            logger.error("Failed to index chunks into ChromaDB: %s", exc)
            raise RuntimeError(f"ChromaDB indexing error: {exc}") from exc

    def delete_version_chunks(self, version_id: uuid.UUID) -> int:
        """
        Remove all indexed chunks belonging to a specific document version.

        Args:
            version_id: UUID of the document version.

        Returns:
            Number of chunks deleted (if known) or 0.
        """
        collection = self.get_collection()
        try:
            # Query IDs first
            existing = collection.get(
                where={"version_id": str(version_id)},
                include=[],
            )
            found_ids = existing.get("ids", [])
            if found_ids:
                collection.delete(ids=found_ids)
                logger.info("Deleted %d chunks for version_id=%s", len(found_ids), version_id)
                return len(found_ids)
            return 0
        except Exception as exc:
            logger.warning("Error deleting chunks for version_id=%s: %s", version_id, exc)
            return 0

    def query_chunks(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k nearest chunks for a query embedding with optional metadata filter.

        Args:
            query_embedding: Query float vector.
            n_results: Number of nearest chunks to retrieve.
            where: Optional ChromaDB metadata filter dict (e.g. {"status": "ACTIVE"}).

        Returns:
            List of result dicts containing chunk_id, text, metadata, distance.
        """
        collection = self.get_collection()
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = collection.query(**kwargs)
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            raise RuntimeError(f"Vector search query failed: {exc}") from exc

        parsed: List[Dict[str, Any]] = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            for i in range(len(ids)):
                parsed.append(
                    {
                        "chunk_id": ids[i],
                        "text": docs[i] if i < len(docs) else "",
                        "metadata": metas[i] if i < len(metas) else {},
                        "distance": dists[i] if i < len(dists) else 0.0,
                    }
                )

        return parsed

    def get_collection_stats(self) -> Dict[str, Any]:
        """Return collection metadata and total chunk count."""
        collection = self.get_collection()
        return {
            "name": self.collection_name,
            "count": collection.count(),
            "persist_directory": self.persist_directory,
        }
