# Public Roadmap

## Current state (v0.1.0)

Core FERPA pre-retrieval filtering is implemented as a Haystack `Component`
with identity scoping, category authorization, audit logging, and shared
content passthrough. Compatible with Haystack 2.x.

---

## Near-term milestones

### 1. GDPR Article 17 right-to-erasure filter

An additional filter layer that checks whether a data subject has submitted
a right-to-erasure request, and suppresses their records from retrieval
accordingly (GDPR Article 17).

### 2. Multi-tenant institution support

Support for deployments where a single Haystack pipeline serves multiple
institutions, with institution-level access boundary enforcement.

### 3. Async filter variant

An async-compatible version of `FERPADocumentFilter` for use with Haystack's
async pipeline execution.

### 4. Haystack 3.x compatibility

Compatibility layer for Haystack 3.x API changes while maintaining
support for Haystack 2.x.

### 5. HIPAA minimum necessary filter

A parallel component enforcing HIPAA Minimum Necessary Rule
(45 CFR § 164.502) for healthcare RAG pipelines built on Haystack.
