# Adoption

## PyPI Downloads

Verified via [pypistats.org](https://pypistats.org/packages/ferpa-haystack).

| Week of | Downloads |
|---------|-----------|
| 2026-04-20 | ~110 |

Downloads are organic — no self-installs, no promotional campaigns.

## How It Is Used

`ferpa-haystack` (installed as `haystack-ferpa-filter`) provides a
Haystack-native document filter component that enforces FERPA access
control at the retrieval layer, before documents enter the LLM context window.

Teams use it to:

1. **Gate retrieval by student identity** — only documents belonging to the
   authenticated student and their authorized institution pass the filter
   (FERPA 34 CFR § 99.3 definition of "education records")
2. **Enforce category authorization** — academic records, financial records,
   disciplinary records each require explicit authorization per § 99.31
3. **Generate FERPA disclosure audit records** — every filter decision
   produces a `FERPADisclosureRecord` per 34 CFR § 99.32 audit log requirement
4. **Pass through shared content** — general institutional documents
   (course catalogs, policy documents) without identity metadata are
   passed through without restriction

## Why Pre-Retrieval

Post-retrieval FERPA filtering is architecturally insufficient:
a document that reaches the LLM context window has already been
"disclosed" under FERPA's definition, regardless of whether the
final response includes the content.

This component enforces FERPA **at the retrieval layer**, before any
document enters the LLM context window.

## Related Packages

- [enterprise-rag-patterns](https://pypi.org/project/enterprise-rag-patterns/) — Broader compliance-aware RAG patterns (FERPA, HIPAA, GDPR, and 65+ regulations)
- [regulated-ai-governance](https://pypi.org/project/regulated-ai-governance/) — Policy enforcement for AI agent frameworks
