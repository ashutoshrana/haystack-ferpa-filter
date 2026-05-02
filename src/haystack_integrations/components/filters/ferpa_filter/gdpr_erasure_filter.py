"""
GDPRRightToErasureFilter — GDPR Article 17 right-to-erasure pre-filter for Haystack RAG.

Prevents documents belonging to a data subject who has exercised their GDPR
Article 17 right to erasure from entering the LLM context window, even when
those documents remain temporarily in the vector store pending full deletion.

The core challenge of GDPR Art. 17 in vector databases: embedding vectors are
not trivially invertible, so full deletion requires re-indexing the collection.
During the window between an erasure request and completed re-index, this
filter ensures deleted subjects' data never reaches the LLM.

Two-layer mechanism:
  1. ErasureTombstone — in-memory or Redis-backed set of erased subject IDs.
     Checked before returning any document. O(1) lookup.
  2. ErasureAuditRecord — Art. 17(3) compliance record: which subject,
     which documents were intercepted, timestamp of erasure request, and
     whether the vector store index rebuild is pending.

Regulatory basis:
    GDPR Art. 17(1) — right to erasure ('right to be forgotten')
    GDPR Art. 17(2) — controller's obligation to inform processors
    GDPR Art. 17(3) — exceptions (legal obligation, public interest, research,
                       legal claims)
    GDPR Art. 5(1)(e) — storage limitation principle

Usage::

    from haystack import Pipeline
    from haystack_integrations.components.filters.ferpa_filter import GDPRRightToErasureFilter

    erasure_filter = GDPRRightToErasureFilter(
        subject_id_field="data_subject_id",
        erased_subjects={"subject_789"},
    )

    pipeline = Pipeline()
    pipeline.add_component("retriever", my_retriever)
    pipeline.add_component("erasure_filter", erasure_filter)
    pipeline.connect("retriever.documents", "erasure_filter.documents")

    result = pipeline.run({"retriever": {"query_embedding": emb}})
    # result["erasure_filter"]["documents"] — erased subject's docs removed
    # result["erasure_filter"]["erasure_audit"] — Art. 17 intercept record

Install:
    pip install haystack-ai haystack-ferpa-filter
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from haystack import Document, component, default_from_dict, default_to_dict

logger = logging.getLogger(__name__)

__all__ = [
    "GDPRRightToErasureFilter",
    "ErasureTombstone",
    "ErasureAuditRecord",
    "ErasureException",
]


@dataclass
class ErasureAuditRecord:
    """
    GDPR Art. 17 compliance record for intercepted documents.

    Created for every pipeline run where at least one document belonging
    to an erased data subject was intercepted.
    """
    subject_id: str
    intercepted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    intercepted_count: int = 0
    total_retrieved: int = 0
    vector_store_rebuild_pending: bool = True
    pipeline_context: str = ""
    exception_applied: Optional[str] = None

    def to_log_entry(self) -> str:
        return (
            f"[GDPR_ERASURE_FILTER] Intercepted {self.intercepted_count} document(s) "
            f"for erased subject={self.subject_id!r} "
            f"context={self.pipeline_context!r} "
            f"rebuild_pending={self.vector_store_rebuild_pending} "
            f"at={self.intercepted_at.isoformat()}"
        )


class ErasureTombstone:
    """
    Registry of data subjects who have exercised GDPR Art. 17 erasure rights.

    Thread-safe in-process implementation. For multi-process deployments,
    replace with a Redis-backed set: SADD gdpr:erased {subject_id}.

    The tombstone is consulted before any document enters the LLM context.
    Documents are intercepted until the vector store rebuild confirms deletion.
    """

    def __init__(self, initial_subjects: Optional[set[str]] = None) -> None:
        self._erased: set[str] = set(initial_subjects or [])

    def add(self, subject_id: str) -> None:
        """Record an erasure request — must be called on Art. 17 receipt."""
        self._erased.add(subject_id)
        logger.info(
            "[GDPR_ERASURE_FILTER] Tombstone added for subject=%r "
            "(GDPR Art. 17 — right to erasure)", subject_id,
        )

    def remove(self, subject_id: str) -> None:
        """Remove from tombstone only after vector store rebuild is confirmed."""
        self._erased.discard(subject_id)

    def is_erased(self, subject_id: str) -> bool:
        return subject_id in self._erased

    def __len__(self) -> int:
        return len(self._erased)


class ErasureException(str):
    """
    GDPR Art. 17(3) exception that permits serving a document despite erasure.

    Permitted exceptions:
        "legal_obligation"  — Art. 17(3)(b): compliance with a legal obligation
        "legal_claims"      — Art. 17(3)(e): establishment/exercise/defence of legal claims
        "public_interest"   — Art. 17(3)(d): public interest (archiving, research, statistics)
        "freedom_expression"— Art. 17(3)(a): freedom of expression and information
    """
    LEGAL_OBLIGATION = "legal_obligation"
    LEGAL_CLAIMS = "legal_claims"
    PUBLIC_INTEREST = "public_interest"
    FREEDOM_EXPRESSION = "freedom_expression"

    _ALLOWED = {LEGAL_OBLIGATION, LEGAL_CLAIMS, PUBLIC_INTEREST, FREEDOM_EXPRESSION}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._ALLOWED


@component
class GDPRRightToErasureFilter:
    """
    Haystack component: intercept documents from erased data subjects.

    Placed immediately after the retriever in a RAG pipeline, this component
    consults the ErasureTombstone and removes documents whose
    ``subject_id_field`` metadata matches an erased subject's identifier.

    When an Art. 17(3) exception applies (e.g., legal_claims), documents
    from erased subjects may pass through — the exception is logged in the
    audit record.

    EU AI Act Art. 10 — data governance: systems must implement mechanisms to
    correct or delete personal data upon request.

    Args:
        subject_id_field: Metadata key identifying the data subject.
            Default "data_subject_id".
        tombstone: ErasureTombstone instance. Shared across pipeline
            instances so that a single add() call covers all pipelines.
        erasure_exception: Optional ErasureException code. When set,
            erased-subject documents are allowed through with an audit
            record noting the exception.
        pipeline_context: Label for audit records (e.g., "student_rag").
        vector_store_rebuild_pending: Set False only after confirming the
            vector store has deleted all embeddings for erased subjects.
    """

    def __init__(
        self,
        subject_id_field: str = "data_subject_id",
        tombstone: Optional[ErasureTombstone] = None,
        erased_subjects: Optional[set[str]] = None,
        erasure_exception: Optional[str] = None,
        pipeline_context: str = "haystack_rag",
        vector_store_rebuild_pending: bool = True,
    ) -> None:
        self.subject_id_field = subject_id_field
        self.tombstone = tombstone or ErasureTombstone(erased_subjects)
        self.erasure_exception = erasure_exception
        self.pipeline_context = pipeline_context
        self.vector_store_rebuild_pending = vector_store_rebuild_pending
        self._audit_records: list[ErasureAuditRecord] = []

        if erasure_exception and not ErasureException.is_valid(erasure_exception):
            raise ValueError(
                f"Invalid GDPR Art. 17(3) exception code: {erasure_exception!r}. "
                f"Permitted: {list(ErasureException._ALLOWED)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return default_to_dict(
            self,
            subject_id_field=self.subject_id_field,
            erasure_exception=self.erasure_exception,
            pipeline_context=self.pipeline_context,
            vector_store_rebuild_pending=self.vector_store_rebuild_pending,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GDPRRightToErasureFilter":
        return default_from_dict(cls, data)

    @component.output_types(documents=list[Document], erasure_audit=list[ErasureAuditRecord])
    def run(self, documents: list[Document]) -> dict[str, Any]:
        """
        Filter out documents belonging to erased subjects.

        Args:
            documents: Retrieved documents from upstream retriever.

        Returns:
            documents: Documents with erased subjects' content removed.
            erasure_audit: List of ErasureAuditRecord for any interceptions.
        """
        total = len(documents)
        passed: list[Document] = []
        intercepted_by_subject: dict[str, int] = {}

        for doc in documents:
            meta = doc.meta or {}
            subject_id = meta.get(self.subject_id_field)

            if subject_id is None or not self.tombstone.is_erased(subject_id):
                passed.append(doc)
                continue

            if self.erasure_exception and ErasureException.is_valid(self.erasure_exception):
                passed.append(doc)
                intercepted_by_subject.setdefault(subject_id, 0)
                intercepted_by_subject[subject_id] += 1
                logger.info(
                    "[GDPR_ERASURE_FILTER] Exception %r applied for subject=%r doc_id=%r",
                    self.erasure_exception, subject_id, doc.id,
                )
            else:
                intercepted_by_subject[subject_id] = intercepted_by_subject.get(subject_id, 0) + 1
                logger.warning(
                    "[GDPR_ERASURE_FILTER] Intercepted doc_id=%r subject=%r (GDPR Art. 17)",
                    doc.id, subject_id,
                )

        audit_records: list[ErasureAuditRecord] = []
        for subject_id, count in intercepted_by_subject.items():
            record = ErasureAuditRecord(
                subject_id=subject_id,
                intercepted_count=count if not self.erasure_exception else 0,
                total_retrieved=total,
                vector_store_rebuild_pending=self.vector_store_rebuild_pending,
                pipeline_context=self.pipeline_context,
                exception_applied=self.erasure_exception,
            )
            logger.info(record.to_log_entry())
            audit_records.append(record)
            self._audit_records.append(record)

        return {"documents": passed, "erasure_audit": audit_records}

    @property
    def audit_records(self) -> list[ErasureAuditRecord]:
        return list(self._audit_records)
