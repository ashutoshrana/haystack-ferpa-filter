# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-04-24

### Added — Initial release

**Core component**
- `FERPADocumentFilter` — Haystack `Component` that enforces FERPA
  34 CFR § 99 access control at the document retrieval layer
- Two-layer filtering:
  1. Identity pre-filter: student_id + institution_id matching
  2. Category authorization: academic, financial, disciplinary record types
- `FERPADisclosureRecord` — structured audit event per 34 CFR § 99.32
  (student_id, institution_id, record_category, access_decision, timestamp)
- Shared content passthrough: documents without identity metadata
  (course catalogs, policy documents) pass through without restriction
- Configurable enforcement: optional exception raising vs. soft filtering
- Full Haystack pipeline YAML/JSON serialization support

**Tests**
- Student record access — authorized category passes ✅
- Student record access — unauthorized category blocked ✅
- Cross-student isolation — student A cannot access student B records ✅
- Institution boundary — cross-institution access blocked ✅
- Shared content passthrough — non-identity documents pass through ✅
- Audit record generation — FERPADisclosureRecord emitted for each decision ✅

---

## [0.2.0] — 2026-05-23

### Added

**GDPR Article 17 right-to-erasure filter**
- `GDPRRightToErasureFilter` — Haystack component that intercepts documents
  belonging to data subjects who have exercised GDPR Art. 17 erasure rights,
  preventing erased content from entering the LLM context window during the
  window between erasure request and completed vector-store rebuild
- `ErasureTombstone` — in-process registry of erased subject IDs (O(1) lookup);
  designed to be swapped for a Redis-backed set in multi-process deployments
- `ErasureAuditRecord` — Art. 17(3) compliance record capturing subject ID,
  intercept count, vector-store rebuild status, and pipeline context
- `ErasureException` — typed GDPR Art. 17(3) exception codes (`legal_obligation`,
  `legal_claims`, `public_interest`, `freedom_expression`) allowing documents
  to pass through with audit trail when a lawful exception applies
- 11 unit tests covering tombstone lifecycle, exception codes, audit accumulation,
  custom subject-id fields, and shared-content passthrough

**Multi-tenant FERPA filter**
- `MultiTenantFERPAFilter` — Haystack component for consortium RAG and
  cross-institution transfer pipelines; evaluates each document against its
  source institution's authorization scope independently
- `TenantAuthorization` — frozen dataclass specifying per-institution authorized
  categories, requestor ID, and FERPA cross-institution basis citation
  (§99.31(a)(6)(i) or §99.34)
- `MultiTenantDisclosureRecord` — §99.32 audit record spanning multiple
  institutions, with per-institution breakdown of disclosed and blocked counts
- Cross-institution mode: documents from non-home institutions require explicit
  FERPA §99.34 or §99.31(a)(6)(i) basis to pass; missing basis → blocked
- 11 unit tests covering wrong-student blocking, category filtering, unknown
  institution handling, cross-institution basis enforcement, and audit records

**Package**
- All new public symbols exported from top-level `__init__.py`
- `tests/conftest.py` — pytest path fixture replacing dev-only `/tmp/devbuild`
  hack; flat-module imports now work in CI and local environments alike

### Fixed
- CI failure: `test_gdpr_erasure_filter.py` and `test_multi_tenant_ferpa_filter.py`
  used `sys.path.insert(0, "/tmp/devbuild")` — a dev-machine-only path that does
  not exist in GitHub Actions. Replaced with `conftest.py` that inserts the actual
  package source directory at collection time.
