# ferpa-haystack

[![PyPI](https://img.shields.io/pypi/v/ferpa-haystack.svg)](https://pypi.org/project/ferpa-haystack/)
[![Python](https://img.shields.io/pypi/pyversions/ferpa-haystack.svg)](https://pypi.org/project/ferpa-haystack/)
[![Tests](https://github.com/ashutoshrana/ferpa-haystack/actions/workflows/ci.yml/badge.svg)](https://github.com/ashutoshrana/ferpa-haystack/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/ferpa-haystack.svg)](https://pypi.org/project/ferpa-haystack/)

**FERPA-compliant document filtering for Haystack RAG pipelines.**

Enforces 34 CFR § 99 identity-scoped access control at the retrieval layer — before any document reaches the LLM context window.

---

## The Problem

Standard Haystack pipelines retrieve documents and pass them directly to the LLM with no enforcement of who is allowed to see what. In higher-education deployments, this creates a structural FERPA compliance gap: a student advising chatbot may return another student's academic record, financial aid details, or disciplinary history in response to a query.

This component closes that gap by adding a two-layer compliance filter between your retriever and your LLM.

---

## Architecture

```
Haystack Pipeline
     │
     ▼
InMemoryEmbeddingRetriever (or any retriever)
     │  documents (all retrieved)
     ▼
FERPAMetadataFilter
     │  Layer 1: Identity pre-filter (student_id + institution_id)
     │  Layer 2: Category authorization (academic_record, financial_aid, ...)
     │
     ├── documents ──────────────► LLM (only authorized records)
     └── disclosure_record ──────► Audit log (34 CFR § 99.32)
```

**Documents without identity metadata** (course catalogues, policy handbooks) pass through both layers unchanged — shared knowledge-base content is never blocked.

---

## Installation

```bash
pip install ferpa-haystack
```

---

## Quick Start

```python
from haystack import Pipeline
from haystack.components.generators import OpenAIGenerator
from haystack.components.retrievers import InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack_integrations.components.filters.ferpa_filter import FERPAMetadataFilter

doc_store = InMemoryDocumentStore()

ferpa_filter = FERPAMetadataFilter(
    student_id="stu_001",
    institution_id="univ_abc",
    authorized_categories=["academic_record", "financial_aid"],
    requesting_user_id="advisor_007",
)

pipeline = Pipeline()
pipeline.add_component("retriever", InMemoryEmbeddingRetriever(doc_store))
pipeline.add_component("ferpa_filter", ferpa_filter)
pipeline.add_component("llm", OpenAIGenerator(model="gpt-4o"))

pipeline.connect("retriever.documents", "ferpa_filter.documents")
pipeline.connect("ferpa_filter.documents", "llm.documents")

result = pipeline.run({"retriever": {"query_embedding": query_emb}})

# Only stu_001's authorized records reached the LLM
authorized_docs = result["ferpa_filter"]["documents"]

# 34 CFR § 99.32 audit entry — log this to your compliance system
audit_record = result["ferpa_filter"]["disclosure_record"]
print(audit_record.to_log_entry())
```

---

## Filtering Layers

### Layer 1 — Identity Pre-Filter

Documents are matched against `student_id` and `institution_id` metadata fields.

| Document metadata | Outcome |
|-------------------|---------|
| No `student_id` or `institution_id` | **Pass** — treated as shared content |
| `student_id` matches | **Continue to Layer 2** |
| `student_id` does not match | **Blocked** |

### Layer 2 — Category Authorization

When `authorized_categories` is non-empty, the document's `category` field must be in the authorized set.

```python
# Only academic records and financial aid — disciplinary records are blocked
FERPAMetadataFilter(
    student_id="stu_001",
    institution_id="univ_abc",
    authorized_categories=["academic_record", "financial_aid"],
    # "disciplinary" is blocked even if identity matches
)
```

---

## Audit Record (34 CFR § 99.32)

Every call to `run()` produces a `FERPADisclosureRecord` regardless of how many documents are authorized:

```python
@dataclass
class FERPADisclosureRecord:
    student_id: str
    institution_id: str
    requesting_user_id: str
    disclosed_at: datetime          # UTC timestamp
    total_retrieved: int            # documents from retriever
    total_disclosed: int            # documents that passed filtering
    categories_disclosed: list[str] # record categories in result
    pipeline_context: str           # pipeline/workflow label
```

Log it to your compliance database:

```python
import logging
compliance_logger = logging.getLogger("ferpa.audit")
compliance_logger.info(result["ferpa_filter"]["disclosure_record"].to_log_entry())
```

---

## Configuration

```python
FERPAMetadataFilter(
    student_id="stu_001",
    institution_id="univ_abc",
    authorized_categories=["academic_record"],   # empty = all categories allowed
    requesting_user_id="advisor_007",            # recorded in audit log
    student_id_field="student_id",               # custom meta key
    institution_id_field="institution_id",       # custom meta key
    category_field="category",                   # custom meta key
    pipeline_context="advising_pipeline",        # audit label
    raise_on_violation=False,                    # True = raise PermissionError
)
```

---

## Custom Field Names

If your document store uses different metadata keys:

```python
FERPAMetadataFilter(
    student_id="stu_001",
    institution_id="univ_abc",
    student_id_field="learner_id",        # your custom key
    institution_id_field="campus_code",   # your custom key
    category_field="record_type",         # your custom key
)
```

---

## Pipeline Serialization

The component is fully serializable for YAML/JSON pipeline storage:

```python
pipeline.to_yaml("advising_pipeline.yaml")
pipeline_restored = Pipeline.from_yaml("advising_pipeline.yaml")
```

---

## GDPR Art. 17 Right-to-Erasure Filter

The `GDPRRightToErasureFilter` component intercepts documents from data subjects who have exercised their GDPR Article 17 right to erasure. Because embedding vectors are not trivially invertible, full deletion requires a vector store re-index — this filter enforces erasure **during the gap** between the erasure request and the completed rebuild.

```python
from haystack import Pipeline
from haystack_integrations.components.filters.ferpa_filter import (
    GDPRRightToErasureFilter,
    ErasureTombstone,
)

tombstone = ErasureTombstone(initial_subjects={"subject_789"})

erasure_filter = GDPRRightToErasureFilter(
    subject_id_field="data_subject_id",
    tombstone=tombstone,
    pipeline_context="student_rag",
)

pipeline = Pipeline()
pipeline.add_component("retriever", my_retriever)
pipeline.add_component("erasure_filter", erasure_filter)
pipeline.connect("retriever.documents", "erasure_filter.documents")

result = pipeline.run({"retriever": {"query_embedding": emb}})

# Erased subject's documents removed from context
docs = result["erasure_filter"]["documents"]

# GDPR Art. 17(3) audit records — log to compliance system
for record in result["erasure_filter"]["erasure_audit"]:
    print(record.to_log_entry())
    # "[GDPR_ERASURE_FILTER] Intercepted 2 document(s) for erased subject='subject_789' ..."
```

When an Art. 17(3) exception applies (legal obligation, legal claims, public interest, freedom of expression), pass it via `erasure_exception`:

```python
from haystack_integrations.components.filters.ferpa_filter import ErasureException

GDPRRightToErasureFilter(
    subject_id_field="data_subject_id",
    tombstone=tombstone,
    erasure_exception=ErasureException.LEGAL_CLAIMS,  # Art. 17(3)(e)
)
```

---

## Multi-Institution FERPA Filter (§ 99.34)

The `MultiTenantFERPAFilter` supports consortium RAG pipelines where a single retrieval spans documents from multiple institutions. Each institution's documents are filtered independently against that institution's authorization scope.

Cross-institution disclosure requires an explicit FERPA basis: § 99.31(a)(6)(i) (directory information to other schools) or § 99.34 (officials of other schools).

```python
from haystack import Pipeline
from haystack_integrations.components.filters.ferpa_filter import (
    MultiTenantFERPAFilter,
    TenantAuthorization,
)

multi_filter = MultiTenantFERPAFilter(
    student_id="stu_001",
    tenant_authorizations={
        "inst_abc": TenantAuthorization(
            institution_id="inst_abc",
            authorized_categories=frozenset(["academic_record"]),
            requestor_id="advisor_007",
        ),
        "inst_xyz": TenantAuthorization(
            institution_id="inst_xyz",
            authorized_categories=frozenset(["transcript"]),
            requestor_id="transfer_office",
            cross_institution_basis="§99.34",  # FERPA cross-institution basis required
        ),
    },
    cross_institution_mode=True,
    home_institution_id="inst_abc",
    pipeline_context="transfer_evaluation",
)

pipeline = Pipeline()
pipeline.add_component("retriever", my_retriever)
pipeline.add_component("ferpa_filter", multi_filter)
pipeline.connect("retriever.documents", "ferpa_filter.documents")

result = pipeline.run({"retriever": {"query_embedding": emb}})

# Per-institution §99.32 disclosure record
record = result["ferpa_filter"]["disclosure_record"]
print(record.to_log_entry())
# "[FERPA_MULTI_TENANT] student='stu_001' disclosed=3/7 institutions=['inst_abc', 'inst_xyz'] ..."
```

---

## Component Summary

| Component | Class | Regulation | Install |
|-----------|-------|-----------|---------|
| Identity + category filter | `FERPAMetadataFilter` | FERPA 34 CFR § 99.31/§ 99.32 | `pip install ferpa-haystack` |
| Right-to-erasure filter | `GDPRRightToErasureFilter` | GDPR Art. 17(1)/17(3)/Art. 5(1)(e) | `pip install ferpa-haystack` |
| Multi-institution filter | `MultiTenantFERPAFilter` | FERPA § 99.31(a)(6)(i)/§ 99.34 | `pip install ferpa-haystack` |

---

## Regulatory Basis

| Regulation | Section | What this component enforces |
|-----------|---------|------------------------------|
| FERPA | 34 CFR § 99.31(a)(1) | Legitimate educational interest — only authorized roles access records |
| FERPA | 34 CFR § 99.32 | Record of disclosures — structured audit entry on every access |
| FERPA | 34 CFR § 99.31(a)(6)(i) | Directory information disclosure to other schools (multi-tenant) |
| FERPA | 34 CFR § 99.34 | Cross-institution disclosure to officials of other schools |
| GDPR | Art. 17(1) | Right to erasure — erased subjects' documents blocked from LLM context |
| GDPR | Art. 17(3) | Exceptions: legal obligation, legal claims, public interest, freedom of expression |
| GDPR | Art. 5(1)(e) | Storage limitation — data not retained beyond erasure request |

---

## Related Projects

- **[enterprise-rag-patterns](https://github.com/ashutoshrana/enterprise-rag-patterns)** — FERPA, HIPAA, GDPR compliance patterns for RAG across 50+ regulated sectors
- **[regulated-ai-governance](https://github.com/ashutoshrana/regulated-ai-governance)** — Policy enforcement for AI agents across 25 jurisdictions

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)
