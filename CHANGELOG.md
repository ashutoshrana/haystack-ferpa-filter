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

## [Unreleased]

### Planned
- GDPR Article 17 right-to-erasure filter
- Multi-tenant institution support
- Async filter variant for async Haystack pipelines
- Haystack 3.x compatibility
