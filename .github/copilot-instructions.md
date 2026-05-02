# Copilot Instructions — haystack-ferpa-filter

## Project Purpose
`haystack-ferpa-filter` is a Haystack 2.x component that applies FERPA pre-filtering to RAG pipelines serving educational institutions. It blocks or redacts documents containing student education records before they reach the LLM, unless the caller has documented FERPA authorization.

## Core Concepts
- **FERPADocumentFilter** — Haystack `Component` that inspects documents for education record markers and applies §99.31 exception logic
- **FERPA §99.31 Exception Evaluation** — checks if caller qualifies under school official, audit/evaluation, legitimate educational interest, or directory information exemption
- **Redaction** — strips PII fields (SSN, grades, enrollment status, financial aid data) rather than blocking the entire document when partial access is permitted
- **Audit Logging** — every filter decision logged with: timestamp, session_id, document_id, exception_applied, fields_redacted

## Package Structure
```
src/haystack_ferpa_filter/
  component.py       — FERPADocumentFilter (Haystack Component)
  exceptions.py      — FERPA §99.31 exception evaluator
  redactor.py        — PII field redactor
  audit.py           — FilterAuditLog
examples/
  basic_ferpa_rag.py — Haystack pipeline with FERPA pre-filter
tests/
  test_component.py, test_exceptions.py, test_redactor.py
```

## Code Conventions
- Component follows Haystack 2.x `@component` decorator pattern
- All filter decisions produce `FilterAuditLog` entries — no silent drops
- `FERPADocumentFilter` must be usable as a drop-in before any Haystack retriever
- Tests use `pytest`; document content in tests is synthetic (no real student data)
- Compatible with Haystack >= 2.0.0; document this in pyproject.toml

## Regulatory Citations
- FERPA 34 CFR Part 99 — student education record privacy
- FERPA § 99.31 — conditions under which disclosure is permitted
- FERPA § 99.3 — definition of "education records" and "directory information"

## What NOT to Include
- No real student data, grades, or enrollment records in tests or examples
- No institution-specific logic or hardcoded school names
- No customer/client names (SEI, Capella, Strayer) or product names
- The filter must be institution-agnostic — all institution config passed as constructor params

## PR Standards
- PR title: conventional commits — `feat: add directory-information exception` / `fix: SSN redaction regex`
- Every new §99.31 exception needs: implementation + tests + README entry
- Changes to redaction logic must include test covering all FERPA PII field types
