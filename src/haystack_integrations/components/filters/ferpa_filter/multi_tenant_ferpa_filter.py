"""
MultiTenantFERPAFilter — Multi-institution FERPA filter for Haystack RAG pipelines.

Extends FERPAMetadataFilter to support multiple institutions in a single pipeline
run. Useful for shared infrastructure (consortium RAG, cross-institution transfer
credit evaluation) where a single retrieval may span documents from multiple
institutions.

Each institution's documents are filtered independently against that institution's
authorized categories and requestor scope. Cross-institution disclosure follows
FERPA §99.31(a)(6)(i) (directory information disclosed to other schools) and
§99.34 (disclosures to officials of other schools).

Regulatory basis:
    FERPA 34 CFR § 99.31(a)(1) — legitimate educational interest
    FERPA 34 CFR § 99.31(a)(6)(i) — disclosure to other schools
    FERPA 34 CFR § 99.32 — record of disclosures
    FERPA 34 CFR § 99.34 — disclosures to officials of other schools

Usage::

    from haystack import Pipeline
    from haystack_integrations.components.filters.ferpa_filter import MultiTenantFERPAFilter

    filter = MultiTenantFERPAFilter(
        student_id="stu_001",
        tenant_authorizations={
            "inst_abc": {"categories": ["academic_record"], "requestor": "advisor_007"},
            "inst_xyz": {"categories": ["transcript"], "requestor": "transfer_office"},
        },
        cross_institution_mode=True,
    )

    pipeline = Pipeline()
    pipeline.add_component("retriever", my_retriever)
    pipeline.add_component("ferpa_filter", filter)
    pipeline.connect("retriever.documents", "ferpa_filter.documents")

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
    "MultiTenantFERPAFilter",
    "TenantAuthorization",
    "MultiTenantDisclosureRecord",
]

_SENTINEL = object()


@dataclass(frozen=True)
class TenantAuthorization:
    """
    Per-institution authorization scope for a multi-tenant FERPA pipeline.

    Attributes:
        institution_id: Institution identifier (matched against document metadata).
        authorized_categories: Set of permitted record categories. Empty means
            all categories authorized for the student in this institution.
        requestor_id: User or system requesting access (for §99.32 audit).
        cross_institution_basis: FERPA citation authorizing cross-institution
            disclosure. Required when student's home institution differs.
            E.g., "§99.31(a)(6)(i)" or "§99.34".
    """
    institution_id: str
    authorized_categories: frozenset[str] = field(default_factory=frozenset)
    requestor_id: str = "system"
    cross_institution_basis: str = ""


@dataclass
class MultiTenantDisclosureRecord:
    """
    FERPA §99.32 disclosure record spanning multiple institutions.

    One record per pipeline run; includes per-institution breakdown.
    """
    student_id: str
    disclosed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    per_institution: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_retrieved: int = 0
    total_disclosed: int = 0
    pipeline_context: str = ""

    def to_log_entry(self) -> str:
        return (
            f"[FERPA_MULTI_TENANT] student={self.student_id!r} "
            f"disclosed={self.total_disclosed}/{self.total_retrieved} "
            f"institutions={list(self.per_institution.keys())} "
            f"context={self.pipeline_context!r} "
            f"at={self.disclosed_at.isoformat()}"
        )


@component
class MultiTenantFERPAFilter:
    """
    Haystack component: FERPA-compliant filter for multi-institution RAG pipelines.

    Evaluates each retrieved document against the authorization for its source
    institution. Documents from unknown institutions are blocked by default
    (configurable via ``allow_unknown_institutions``).

    Cross-institution disclosure requires explicit FERPA basis:
    - FERPA §99.31(a)(6)(i): directory information may be disclosed to other schools
      in which the student seeks or intends to enroll.
    - FERPA §99.34: school officials of other schools may receive records without
      consent when the student is enrolled or seeks to enroll there.

    Args:
        student_id: The student whose records are being accessed.
        tenant_authorizations: Mapping of institution_id → TenantAuthorization.
        cross_institution_mode: When True, documents from institutions other than
            the student's home institution require a cross_institution_basis.
        home_institution_id: Student's home institution. Required when
            cross_institution_mode=True.
        allow_unknown_institutions: When False (default), documents from
            institutions not in tenant_authorizations are blocked.
        student_id_field: Metadata key for student identifier.
        institution_id_field: Metadata key for institution identifier.
        category_field: Metadata key for record category.
        pipeline_context: Label for audit records.
    """

    def __init__(
        self,
        student_id: str,
        tenant_authorizations: Optional[dict[str, TenantAuthorization]] = None,
        cross_institution_mode: bool = False,
        home_institution_id: Optional[str] = None,
        allow_unknown_institutions: bool = False,
        student_id_field: str = "student_id",
        institution_id_field: str = "institution_id",
        category_field: str = "category",
        pipeline_context: str = "multi_tenant_rag",
    ) -> None:
        self.student_id = student_id
        self.tenant_authorizations: dict[str, TenantAuthorization] = tenant_authorizations or {}
        self.cross_institution_mode = cross_institution_mode
        self.home_institution_id = home_institution_id
        self.allow_unknown_institutions = allow_unknown_institutions
        self.student_id_field = student_id_field
        self.institution_id_field = institution_id_field
        self.category_field = category_field
        self.pipeline_context = pipeline_context

    def to_dict(self) -> dict[str, Any]:
        return default_to_dict(
            self,
            student_id=self.student_id,
            cross_institution_mode=self.cross_institution_mode,
            home_institution_id=self.home_institution_id,
            allow_unknown_institutions=self.allow_unknown_institutions,
            student_id_field=self.student_id_field,
            institution_id_field=self.institution_id_field,
            category_field=self.category_field,
            pipeline_context=self.pipeline_context,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MultiTenantFERPAFilter":
        return default_from_dict(cls, data)

    @component.output_types(
        documents=list[Document],
        disclosure_record=MultiTenantDisclosureRecord,
    )
    def run(self, documents: list[Document]) -> dict[str, Any]:
        """
        Filter documents across multiple institutions per FERPA.

        Args:
            documents: Documents from an upstream retriever, potentially
                spanning multiple institution namespaces.

        Returns:
            documents: Authorized documents only.
            disclosure_record: Multi-institution §99.32 audit record.
        """
        total_retrieved = len(documents)
        authorized: list[Document] = []
        per_institution: dict[str, dict[str, Any]] = {}

        for doc in documents:
            meta = doc.meta or {}
            doc_student_id = meta.get(self.student_id_field, _SENTINEL)
            doc_institution_id = meta.get(self.institution_id_field, _SENTINEL)

            # Shared content with no identity metadata passes through
            if doc_student_id is _SENTINEL and doc_institution_id is _SENTINEL:
                authorized.append(doc)
                continue

            # Wrong student — always blocked
            if doc_student_id != self.student_id:
                logger.warning(
                    "[FERPA_MULTI_TENANT] Blocked: doc belongs to student=%r, not %r",
                    doc_student_id, self.student_id,
                )
                continue

            institution_id = str(doc_institution_id) if doc_institution_id is not _SENTINEL else None
            auth = self.tenant_authorizations.get(institution_id) if institution_id else None

            if auth is None:
                if self.allow_unknown_institutions:
                    authorized.append(doc)
                    inst_stats = per_institution.setdefault(institution_id or "unknown", {"disclosed": 0, "blocked": 0, "basis": "allow_unknown"})
                    inst_stats["disclosed"] += 1
                else:
                    logger.warning(
                        "[FERPA_MULTI_TENANT] Blocked: institution=%r not in tenant_authorizations",
                        institution_id,
                    )
                    inst_stats = per_institution.setdefault(institution_id or "unknown", {"disclosed": 0, "blocked": 0, "basis": "not_authorized"})
                    inst_stats["blocked"] += 1
                continue

            # Cross-institution check
            if (
                self.cross_institution_mode
                and self.home_institution_id
                and institution_id != self.home_institution_id
                and not auth.cross_institution_basis
            ):
                logger.warning(
                    "[FERPA_MULTI_TENANT] Blocked cross-institution doc: institution=%r "
                    "no FERPA basis specified (requires §99.31(a)(6)(i) or §99.34)",
                    institution_id,
                )
                inst_stats = per_institution.setdefault(institution_id, {"disclosed": 0, "blocked": 0, "basis": "missing_cross_institution_basis"})
                inst_stats["blocked"] += 1
                continue

            # Category authorization
            doc_category = meta.get(self.category_field, _SENTINEL)
            if (
                auth.authorized_categories
                and doc_category is not _SENTINEL
                and doc_category not in auth.authorized_categories
            ):
                logger.warning(
                    "[FERPA_MULTI_TENANT] Blocked: category=%r not authorized for institution=%r",
                    doc_category, institution_id,
                )
                inst_stats = per_institution.setdefault(institution_id, {"disclosed": 0, "blocked": 0, "basis": auth.cross_institution_basis or "§99.31(a)(1)"})
                inst_stats["blocked"] += 1
                continue

            authorized.append(doc)
            inst_stats = per_institution.setdefault(institution_id, {"disclosed": 0, "blocked": 0, "basis": auth.cross_institution_basis or "§99.31(a)(1)"})
            inst_stats["disclosed"] += 1

        record = MultiTenantDisclosureRecord(
            student_id=self.student_id,
            per_institution=per_institution,
            total_retrieved=total_retrieved,
            total_disclosed=len(authorized),
            pipeline_context=self.pipeline_context,
        )
        logger.info(record.to_log_entry())
        return {"documents": authorized, "disclosure_record": record}
