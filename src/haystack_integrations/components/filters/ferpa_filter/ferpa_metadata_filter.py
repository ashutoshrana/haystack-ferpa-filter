"""
FERPAMetadataFilter — FERPA-compliant document filter for Haystack RAG pipelines.

Enforces identity-scoped access control on retriever results before they reach
the LLM context window. Complies with 34 CFR § 99.31(a)(1) (legitimate educational
interest) and § 99.32 (record of disclosures).

Two filtering layers applied in sequence:

1. Identity pre-filter — removes documents whose student_id or institution_id
   metadata does not match the authorized scope.
2. Category authorization — removes documents whose category is not in the
   authorized set (e.g., only ACADEMIC_RECORD, not DISCIPLINARY).

Public content requires classification="public" and no identity keys.
Private content requires complete identity and category metadata.

Usage::

    from haystack import Pipeline
    from haystack.components.retrievers import InMemoryEmbeddingRetriever
    from haystack_integrations.components.filters.ferpa_filter import FERPAMetadataFilter
    from haystack.document_stores.in_memory import InMemoryDocumentStore

    ferpa_filter = FERPAMetadataFilter(
        student_id="stu_001",
        institution_id="inst_abc",
        authorized_categories=["academic_record", "financial_aid"],
        requesting_user_id="advisor_007",
    )

    pipeline = Pipeline()
    pipeline.add_component("retriever", InMemoryEmbeddingRetriever(doc_store))
    pipeline.add_component("ferpa_filter", ferpa_filter)
    pipeline.connect("retriever.documents", "ferpa_filter.documents")

    result = pipeline.run({"retriever": {"query_embedding": query_emb}})
    # result["ferpa_filter"]["documents"] — only stu_001's authorized records
    # result["ferpa_filter"]["disclosure_record"] — 34 CFR § 99.32 audit entry

Regulatory basis:
    34 CFR § 99.31(a)(1) — legitimate educational interest
    34 CFR § 99.32       — record of disclosures
"""

import logging
from uuid import uuid4
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from haystack import Document, component, default_from_dict, default_to_dict

logger = logging.getLogger(__name__)

_SENTINEL = object()


@dataclass
class FERPADisclosureRecord:
    """
    Structured audit record of a FERPA disclosure event (34 CFR § 99.32).

    Attributes:
        student_id: Identifier of the student whose records were accessed.
        institution_id: Identifier of the institution.
        requesting_user_id: User or system that requested access.
        disclosed_at: UTC timestamp of the disclosure.
        total_retrieved: Documents returned by the retriever before filtering.
        total_disclosed: Documents that passed FERPA filtering.
        categories_disclosed: Record categories included in the result.
        pipeline_context: Label identifying the pipeline or workflow context.
    """

    student_id: str
    institution_id: str
    requesting_user_id: str
    disclosed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_retrieved: int = 0
    total_disclosed: int = 0
    categories_disclosed: list[str] = field(default_factory=list)
    pipeline_context: str = "haystack_pipeline"
    audit_id: str = field(default_factory=lambda: uuid4().hex)

    def to_log_entry(self) -> str:
        return (
            f"[FERPA_DISCLOSURE] student_id={self.student_id!r} "
            f"institution_id={self.institution_id!r} "
            f"requesting_user_id={self.requesting_user_id!r} "
            f"disclosed_at={self.disclosed_at.isoformat()} "
            f"total_retrieved={self.total_retrieved} "
            f"total_disclosed={self.total_disclosed} "
            f"categories_disclosed={self.categories_disclosed!r} "
            f"pipeline_context={self.pipeline_context!r}"
        )


@component
class FERPAMetadataFilter:
    """
    Haystack component that enforces FERPA identity-scope filtering on retrieved
    documents before they enter the LLM context window.

    Connects to any retriever output and emits only the documents that fall within
    the authorized identity scope. Always emits a FERPADisclosureRecord for
    downstream compliance logging (34 CFR § 99.32).

    Two enforcement layers:

    1. Identity pre-filter: student_id and institution_id in Document.meta must
       match the authorized scope. Documents with neither field pass only when explicitly classified public.

    2. Category authorization: when authorized_categories is non-empty, the
       document's category field must be in the authorized set.

    Args:
        student_id: Authorized student identifier.
        institution_id: Authorized institution identifier.
        authorized_categories: Permitted record category strings.
            Empty list means all categories are allowed.
        requesting_user_id: Identifier of the requesting user (for audit log).
        student_id_field: Meta key for student identifier. Default: "student_id".
        institution_id_field: Meta key for institution identifier. Default: "institution_id".
        category_field: Meta key for record category. Default: "category".
        pipeline_context: Label for the audit record. Default: "haystack_pipeline".
        raise_on_violation: When True, raise PermissionError on unauthorized docs.
            When False (default), silently remove and emit WARNING.
    """

    def __init__(
        self,
        student_id: str,
        institution_id: str,
        authorized_categories: list[str] | None = None,
        requesting_user_id: str = "unknown",
        student_id_field: str = "student_id",
        institution_id_field: str = "institution_id",
        category_field: str = "category",
        pipeline_context: str = "haystack_pipeline",
        raise_on_violation: bool = False,
    ) -> None:
        for name, value in (("student_id", student_id), ("institution_id", institution_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        self.student_id = student_id
        self.institution_id = institution_id
        self.authorized_categories = list(authorized_categories) if authorized_categories else []
        self.requesting_user_id = requesting_user_id
        self.student_id_field = student_id_field
        self.institution_id_field = institution_id_field
        self.category_field = category_field
        self.pipeline_context = pipeline_context
        self.raise_on_violation = raise_on_violation

    def to_dict(self) -> dict[str, Any]:
        return default_to_dict(
            self,
            student_id=self.student_id,
            institution_id=self.institution_id,
            authorized_categories=self.authorized_categories,
            requesting_user_id=self.requesting_user_id,
            student_id_field=self.student_id_field,
            institution_id_field=self.institution_id_field,
            category_field=self.category_field,
            pipeline_context=self.pipeline_context,
            raise_on_violation=self.raise_on_violation,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FERPAMetadataFilter":
        return default_from_dict(cls, data)

    @component.output_types(documents=list[Document], disclosure_record=FERPADisclosureRecord)
    def run(self, documents: list[Document]) -> dict[str, Any]:
        """
        Filter documents to the authorized identity scope.

        Args:
            documents: Documents from an upstream retriever.

        Returns:
            documents: Authorized documents only.
            disclosure_record: FERPADisclosureRecord for compliance logging.

        Raises:
            PermissionError: Only when raise_on_violation=True and unauthorized
                documents were detected.
        """
        audit_id = uuid4().hex
        total_retrieved = len(documents)
        authorized: list[Document] = []

        for doc in documents:
            if self._is_authorized(doc):
                authorized.append(doc)

        removed = total_retrieved - len(authorized)

        if removed > 0:
            if self.raise_on_violation:
                raise PermissionError(
                    f"FERPA violation: {removed} unauthorized document(s) blocked. audit_id={audit_id}"
                )
            logger.warning(
                "[FERPA_FILTER] Blocked %d unauthorized document(s)", removed,
            )

        record = FERPADisclosureRecord(
            student_id=self.student_id,
            institution_id=self.institution_id,
            requesting_user_id=self.requesting_user_id,
            total_retrieved=total_retrieved,
            total_disclosed=len(authorized),
            categories_disclosed=self._extract_categories(authorized),
            pipeline_context=self.pipeline_context,
            audit_id=audit_id,
        )
        logger.info("[FERPA_FILTER] Completed audit_id=%s retrieved=%d disclosed=%d", audit_id, total_retrieved, len(authorized))
        return {"documents": authorized, "disclosure_record": record}

    @component.output_types(documents=list[Document], disclosure_record=FERPADisclosureRecord)
    async def run_async(self, documents: list[Document]) -> dict[str, Any]:
        """Async variant of run — filtering is CPU-bound, runs synchronously."""
        return self.run(documents)

    def _is_authorized(self, doc: Document) -> bool:
        meta = doc.meta or {}
        doc_student_id = meta.get(self.student_id_field, _SENTINEL)
        doc_institution_id = meta.get(self.institution_id_field, _SENTINEL)

        # Only trusted, explicitly public content can omit identity metadata
        if meta.get("classification") == "public" and doc_student_id is _SENTINEL and doc_institution_id is _SENTINEL:
            return True

        if doc_student_id != self.student_id:
            return False
        if doc_institution_id != self.institution_id:
            return False

        doc_category = meta.get(self.category_field)
        if not isinstance(doc_category, str) or not doc_category.strip():
            return False
        if self.authorized_categories:
            if doc_category not in self.authorized_categories:
                return False

        return True

    def _extract_categories(self, documents: list[Document]) -> list[str]:
        categories: set[str] = set()
        for doc in documents:
            meta = doc.meta or {}
            cat = meta.get(self.category_field)
            if cat is not None:
                categories.add(str(cat))
        return sorted(categories)
