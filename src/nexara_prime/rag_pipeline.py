"""NEXARA PRIME RAG Pipeline — Four-layer memory with Retrieval-Augmented Generation.

Four memory layers:
- Working: ephemeral, session-bound scratchpad
- Episodic: mission execution history, decisions, outcomes
- Semantic: long-term facts, knowledge graphs, verified claims
- Procedural: skills, templates, reusable patterns

RAG Pipeline:
  Ingest → Normalize → Chunk → Embed → Index → Retrieve → Rerank → Cite → Evaluate

Each step is evidence-linked, source-deduplicated, and time-decay-weighted.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import MemoryKind, MemoryRecord, new_id, now_iso


# ── Memory layer classification ──

class MemoryLayer(str, Enum):
    WORKING = "working"       # Ephemeral scratchpad
    EPISODIC = "episodic"     # Mission execution history
    SEMANTIC = "semantic"     # Long-term facts, knowledge
    PROCEDURAL = "procedural" # Skills, templates, patterns


# Layer mapping from MemoryKind
KIND_TO_LAYER: dict[MemoryKind, MemoryLayer] = {
    MemoryKind.SHORT_TERM: MemoryLayer.WORKING,
    MemoryKind.TEMPORARY_CONTEXT: MemoryLayer.WORKING,
    MemoryKind.FACT: MemoryLayer.SEMANTIC,
    MemoryKind.DECISION: MemoryLayer.EPISODIC,
    MemoryKind.FAILURE: MemoryLayer.EPISODIC,
    MemoryKind.FAILURE_EXPERIENCE: MemoryLayer.SEMANTIC,
    MemoryKind.PATCH: MemoryLayer.PROCEDURAL,
    MemoryKind.SKILL_IMPROVEMENT: MemoryLayer.PROCEDURAL,
    MemoryKind.SYSTEM_RULE: MemoryLayer.PROCEDURAL,
    MemoryKind.USER_FACT: MemoryLayer.SEMANTIC,
    MemoryKind.PROJECT_FACT: MemoryLayer.SEMANTIC,
    MemoryKind.PREFERENCE: MemoryLayer.SEMANTIC,
    MemoryKind.UNVERIFIED_INFERENCE: MemoryLayer.WORKING,
}


# ── Capability flags ──

RAG_MOCK_EMBEDDER = "RAG_MOCK_EMBEDDER"
RAG_CHUNKING_ACTIVE = "RAG_CHUNKING_ACTIVE"
RAG_RERANKING_ACTIVE = "RAG_RERANKING_ACTIVE"
RAG_CITATION_ACTIVE = "RAG_CITATION_ACTIVE"
RAG_TIME_DECAY_ACTIVE = "RAG_TIME_DECAY_ACTIVE"


@dataclass
class RAGCapability:
    flags: list[str] = field(default_factory=list)
    embedder_type: str = "mock"
    embedding_dim: int = 384
    max_chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 10
    min_similarity: float = 0.3
    time_decay_half_life_days: float = 30.0


@dataclass
class Document:
    """A raw document to be ingested into the RAG pipeline."""
    doc_id: str = field(default_factory=lambda: new_id("doc"))
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    source_evidence_id: str = ""
    mission_id: str = ""
    memory_kind: MemoryKind = MemoryKind.FACT
    layer: MemoryLayer = MemoryLayer.SEMANTIC
    created_at: str = field(default_factory=now_iso)
    access_tags: list[str] = field(default_factory=list)
    content_hash: str = ""

    def compute_hash(self) -> str:
        canonical = json.dumps({
            "content": self.content, "source_evidence_id": self.source_evidence_id,
        }, sort_keys=True, ensure_ascii=False)
        self.content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.content_hash


@dataclass
class Chunk:
    """A semantic chunk of a document."""
    chunk_id: str = field(default_factory=lambda: new_id("chunk"))
    doc_id: str = ""
    content: str = ""
    index: int = 0
    start_char: int = 0
    end_char: int = 0
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_hash: str = ""

    def compute_hash(self) -> str:
        self.chunk_hash = hashlib.sha256(
            f"{self.doc_id}:{self.index}:{self.content}".encode("utf-8")
        ).hexdigest()
        return self.chunk_hash


@dataclass
class RetrievalResult:
    """A retrieved chunk with relevance score and citation."""
    chunk: Chunk = field(default_factory=Chunk)
    score: float = 0.0
    raw_score: float = 0.0
    rerank_score: float = 0.0
    citation: str = ""
    document: Document | None = None
    evidence_ref: str = ""
    time_decay_factor: float = 1.0


@dataclass
class QueryResult:
    query_id: str = field(default_factory=lambda: new_id("query"))
    query: str = ""
    results: list[RetrievalResult] = field(default_factory=list)
    total_candidates: int = 0
    total_retrieved: int = 0
    evaluation: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class Embedder(ABC):
    """Abstract embedding model."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def dimension(self) -> int: ...


class MockEmbedder(Embedder):
    """Deterministic mock embedder using hashed TF-like vectors."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            # Deterministic pseudo-embedding from content hash
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec = []
            for i in range(self._dim):
                byte_val = h[i % len(h)]
                # Normalize to [-1, 1]
                vec.append((byte_val / 127.5) - 1.0)
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


class VectorIndex:
    """In-memory vector index with cosine similarity search."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def add(self, chunk: Chunk, embedding: list[float]) -> None:
        self._chunks.append(chunk)
        self._vectors.append(embedding)

    def remove(self, chunk_id: str) -> bool:
        for i, c in enumerate(self._chunks):
            if c.chunk_id == chunk_id:
                self._chunks.pop(i)
                self._vectors.pop(i)
                return True
        return False

    def search(
        self, query_embedding: list[float], top_k: int = 10,
        min_similarity: float = 0.0,
        layer_filter: list[MemoryLayer] | None = None,
        access_tags: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        results: list[tuple[Chunk, float]] = []

        for chunk, vec in zip(self._chunks, self._vectors):
            # Layer filter
            if layer_filter:
                chunk_layer = chunk.metadata.get("layer")
                if chunk_layer and MemoryLayer(chunk_layer) not in layer_filter:
                    continue

            # Access control
            if access_tags:
                chunk_tags = chunk.metadata.get("access_tags", [])
                if not any(t in chunk_tags for t in access_tags):
                    continue

            sim = self._cosine_similarity(query_embedding, vec)
            if sim >= min_similarity:
                results.append((chunk, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def size(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()


class RAGPipeline:
    """Complete RAG pipeline: Ingest → Normalize → Chunk → Embed → Index → Retrieve → Rerank → Cite → Evaluate."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        *,
        max_chunk_size: int = 512,
        chunk_overlap: int = 64,
        top_k: int = 10,
        min_similarity: float = 0.3,
        time_decay_half_life_days: float = 30.0,
        enable_reranking: bool = True,
        enable_citation: bool = True,
        enable_time_decay: bool = True,
    ) -> None:
        self.embedder = embedder or MockEmbedder()
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.time_decay_half_life_days = time_decay_half_life_days
        self.enable_reranking = enable_reranking
        self.enable_citation = enable_citation
        self.enable_time_decay = enable_time_decay

        self.index = VectorIndex()
        self._documents: dict[str, Document] = {}
        self._chunk_to_doc: dict[str, str] = {}  # chunk_id -> doc_id
        self._doc_hash_index: dict[str, str] = {}  # content_hash → doc_id

    # ── Step 1: Ingest ──

    def ingest(
        self, content: str, *,
        metadata: dict[str, Any] | None = None,
        source_evidence_id: str = "",
        mission_id: str = "",
        memory_kind: MemoryKind = MemoryKind.FACT,
        access_tags: list[str] | None = None,
    ) -> Document:
        """Ingest a raw document into the pipeline."""
        doc = Document(
            content=content,
            metadata=metadata or {},
            source_evidence_id=source_evidence_id,
            mission_id=mission_id,
            memory_kind=memory_kind,
            layer=KIND_TO_LAYER.get(memory_kind, MemoryLayer.SEMANTIC),
            access_tags=access_tags or [],
        )
        doc.compute_hash()

        # Source deduplication
        existing_id = self._doc_hash_index.get(doc.content_hash)
        if existing_id:
            existing = self._documents.get(existing_id)
            if existing:
                existing.metadata.setdefault("duplicate_of", existing_id)
                return existing

        return doc

    # ── Step 2: Normalize ──

    def normalize(self, doc: Document) -> Document:
        """Normalize document content — clean whitespace, normalize unicode."""
        content = doc.content

        # Collapse whitespace
        content = re.sub(r'[ \t]+', ' ', content)
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Strip control characters (keep newlines, tabs)
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

        # Normalize unicode
        import unicodedata
        content = unicodedata.normalize('NFKC', content)

        doc.content = content.strip()
        doc.compute_hash()
        return doc

    # ── Step 3: Chunk ──

    def chunk(self, doc: Document) -> list[Chunk]:
        """Split document into semantic chunks with overlap."""
        content = doc.content
        if not content:
            return []

        chunks: list[Chunk] = []
        start = 0
        idx = 0

        while start < len(content):
            end = min(start + self.max_chunk_size, len(content))

            # Try to break at sentence/paragraph boundary
            if end < len(content):
                # Look back for a good break point
                for sep in ['\n\n', '\n', '. ', '! ', '? ', '; ', ', ']:
                    last_sep = content.rfind(sep, start, end)
                    if last_sep > start + self.max_chunk_size // 2:
                        end = last_sep + len(sep.rstrip())
                        break

            chunk_content = content[start:end].strip()
            if chunk_content:
                chunk = Chunk(
                    doc_id=doc.doc_id,
                    content=chunk_content,
                    index=idx,
                    start_char=start,
                    end_char=end,
                    metadata={
                        "doc_id": doc.doc_id,
                        "source_evidence_id": doc.source_evidence_id,
                        "mission_id": doc.mission_id,
                        "memory_kind": doc.memory_kind.value,
                        "layer": doc.layer.value,
                        "access_tags": doc.access_tags,
                        "created_at": doc.created_at,
                        **doc.metadata,
                    },
                )
                chunk.compute_hash()
                chunks.append(chunk)
                idx += 1

            start = end - self.chunk_overlap if end < len(content) else len(content)

        return chunks

    # ── Step 4: Embed ──

    def embed_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Generate embeddings for chunks."""
        if not chunks:
            return chunks
        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
        return chunks

    # ── Step 5: Index ──

    def index_document(self, doc: Document) -> int:
        """Full ingest pipeline: normalize → chunk → embed → index."""
        doc = self.normalize(doc)

        # Deduplication check
        existing_id = self._doc_hash_index.get(doc.content_hash)
        if existing_id:
            return 0  # Already indexed

        chunks = self.chunk(doc)
        chunks = self.embed_chunks(chunks)

        for chunk in chunks:
            self.index.add(chunk, chunk.embedding)

        self._documents[doc.doc_id] = doc
        self._doc_hash_index[doc.content_hash] = doc.doc_id

        return len(chunks)

    # ── Step 6: Retrieve ──

    def retrieve(
        self, query: str, *,
        top_k: int | None = None,
        min_similarity: float | None = None,
        layer_filter: list[MemoryLayer] | None = None,
        access_tags: list[str] | None = None,
        mission_id: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve relevant chunks for a query."""
        started = time.monotonic()

        query_embedding = self.embedder.embed([query])[0]

        raw_results = self.index.search(
            query_embedding,
            top_k=top_k or self.top_k,
            min_similarity=min_similarity or self.min_similarity,
            layer_filter=layer_filter,
            access_tags=access_tags,
        )

        results: list[RetrievalResult] = []
        for chunk, score in raw_results:
            doc = self._documents.get(chunk.doc_id)
            rr = RetrievalResult(
                chunk=chunk,
                score=score,
                raw_score=score,
                document=doc,
                evidence_ref=doc.source_evidence_id if doc else "",
            )

            # Time decay
            if self.enable_time_decay and doc:
                rr.time_decay_factor = self._compute_time_decay(doc.created_at)
                rr.score *= rr.time_decay_factor

            # Mission boost
            if mission_id and doc and doc.mission_id == mission_id:
                rr.score *= 1.2  # 20% boost for same-mission content

            results.append(rr)

        return results

    # ── Step 7: Rerank ──

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Rerank results using heuristic cross-attention scoring."""
        if not self.enable_reranking:
            return results

        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for rr in results:
            content_lower = rr.chunk.content.lower()

            # Term overlap bonus
            content_terms = set(content_lower.split())
            overlap = len(query_terms & content_terms)
            term_bonus = overlap / max(len(query_terms), 1)

            # Exact phrase bonus
            phrase_bonus = 0.0
            if query_lower in content_lower:
                phrase_bonus = 0.3

            # Position bonus: earlier chunks in same doc get slight boost
            position_bonus = max(0.0, 0.1 * (1.0 - rr.chunk.index / 10.0))

            rr.rerank_score = rr.score + term_bonus * 0.15 + phrase_bonus + position_bonus
            rr.score = rr.rerank_score

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    # ── Step 8: Cite ──

    def cite(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Generate citations for retrieved results."""
        if not self.enable_citation:
            return results

        for rr in results:
            doc = rr.document
            if not doc:
                continue

            parts: list[str] = []
            if doc.source_evidence_id:
                parts.append(f"evidence:{doc.source_evidence_id}")
            if doc.mission_id:
                parts.append(f"mission:{doc.mission_id}")
            parts.append(f"doc:{doc.doc_id}")
            parts.append(f"chunk:{rr.chunk.index}")

            rr.citation = " | ".join(parts)
            rr.evidence_ref = doc.source_evidence_id

        return results

    # ── Step 9: Evaluate ──

    def evaluate(self, query: str, results: list[RetrievalResult]) -> dict[str, Any]:
        """Evaluate retrieval quality — relevance scores, coverage, confidence."""
        if not results:
            return {
                "relevant": False,
                "confidence": 0.0,
                "coverage": 0.0,
                "hallucination_risk": "high",
                "recommendation": "No relevant memories found. Consider expanding search or ingesting more data.",
            }

        scores = [r.score for r in results]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        confidence = min(1.0, max_score * 1.2)

        # Coverage: how many different documents?
        unique_docs = len({r.chunk.doc_id for r in results})

        # Hallucination risk assessment
        if max_score < 0.4:
            hallucination_risk = "high"
        elif max_score < 0.6:
            hallucination_risk = "medium"
        elif max_score < 0.8:
            hallucination_risk = "low"
        else:
            hallucination_risk = "minimal"

        # Evidence-backed
        evidence_backed = sum(1 for r in results if r.evidence_ref)
        evidence_ratio = evidence_backed / len(results) if results else 0.0

        return {
            "relevant": max_score >= self.min_similarity,
            "confidence": confidence,
            "coverage": unique_docs,
            "hallucination_risk": hallucination_risk,
            "evidence_backed_ratio": evidence_ratio,
            "avg_score": avg_score,
            "max_score": max_score,
            "result_count": len(results),
            "recommendation": (
                "High-confidence retrieval with evidence backing." if hallucination_risk == "minimal"
                else "Moderate confidence — verify key claims." if hallucination_risk == "low"
                else "Low confidence — cross-check with other sources." if hallucination_risk == "medium"
                else "High hallucination risk — do not use without human verification."
            ),
        }

    # ── Full Query Pipeline ──

    def query(
        self, query_text: str, *,
        top_k: int | None = None,
        min_similarity: float | None = None,
        layer_filter: list[MemoryLayer] | None = None,
        access_tags: list[str] | None = None,
        mission_id: str | None = None,
        include_evaluation: bool = True,
    ) -> QueryResult:
        """Execute the full query pipeline: Retrieve → Rerank → Cite → Evaluate."""
        started = time.monotonic()

        # Retrieve
        results = self.retrieve(
            query_text, top_k=top_k, min_similarity=min_similarity,
            layer_filter=layer_filter, access_tags=access_tags,
            mission_id=mission_id,
        )
        total_candidates = len(results)

        # Rerank
        results = self.rerank(query_text, results)

        # Cite
        results = self.cite(results)

        # Evaluate
        evaluation = self.evaluate(query_text, results) if include_evaluation else {}

        duration = (time.monotonic() - started) * 1000

        return QueryResult(
            query=query_text,
            results=results[:top_k or self.top_k],
            total_candidates=total_candidates,
            total_retrieved=min(len(results), top_k or self.top_k),
            evaluation=evaluation,
            duration_ms=duration,
        )

    # ── Time Decay ──

    def _compute_time_decay(self, created_at: str) -> float:
        """Compute exponential time decay factor. Older memories → lower weight."""
        try:
            from datetime import datetime, timezone
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = (now - created).total_seconds() / 86400.0
            # Exponential decay: weight = 2^(-age / half_life)
            decay = math.pow(2, -age_days / self.time_decay_half_life_days)
            return max(0.1, decay)  # Floor at 0.1
        except (ValueError, TypeError):
            return 1.0

    # ── Memory layer helpers ──

    def get_by_layer(self, layer: MemoryLayer, limit: int = 50) -> list[Document]:
        """Get documents in a specific memory layer."""
        return [d for d in self._documents.values() if d.layer == layer][:limit]

    def get_episodic_for_mission(self, mission_id: str) -> list[Document]:
        """Get episodic memories for a specific mission."""
        return [d for d in self._documents.values()
                if d.layer == MemoryLayer.EPISODIC and d.mission_id == mission_id]

    def get_semantic_by_key(self, key_prefix: str, limit: int = 20) -> list[Document]:
        """Search semantic memory by metadata key prefix."""
        results: list[Document] = []
        for doc in self._documents.values():
            if doc.layer == MemoryLayer.SEMANTIC:
                for k, v in doc.metadata.items():
                    if isinstance(v, str) and v.startswith(key_prefix):
                        results.append(doc)
                        break
        return results[:limit]

    # ── Lifecycle ──

    def probe_capability(self) -> RAGCapability:
        return RAGCapability(
            flags=[RAG_MOCK_EMBEDDER if isinstance(self.embedder, MockEmbedder) else ""],
            embedder_type="mock" if isinstance(self.embedder, MockEmbedder) else "unknown",
            embedding_dim=self.embedder.dimension(),
            max_chunk_size=self.max_chunk_size,
            chunk_overlap=self.chunk_overlap,
            top_k=self.top_k,
            min_similarity=self.min_similarity,
            time_decay_half_life_days=self.time_decay_half_life_days,
        )

    def stats(self) -> dict[str, Any]:
        """Return pipeline statistics."""
        layers_count: dict[str, int] = {}
        for doc in self._documents.values():
            layer = doc.layer.value
            layers_count[layer] = layers_count.get(layer, 0) + 1
        return {
            "total_documents": len(self._documents),
            "total_chunks": self.index.size(),
            "layers": layers_count,
            "index_size": self.index.size(),
        }

    def clear_working_memory(self) -> int:
        """Clear all working memory (ephemeral), including index entries."""
        count = 0
        to_remove = [doc_id for doc_id, doc in self._documents.items()
                     if doc.layer == MemoryLayer.WORKING]
        chunks_to_remove = [
            chunk_id for chunk_id, doc_id in self._chunk_to_doc.items()
            if doc_id in to_remove
        ]
        for chunk_id in chunks_to_remove:
            self.index.remove(chunk_id)
            del self._chunk_to_doc[chunk_id]
        for doc_id in to_remove:
            del self._documents[doc_id]
            count += 1
        return count
