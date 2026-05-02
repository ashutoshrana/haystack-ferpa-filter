## Summary
<!-- What does this PR add or fix? -->

## Motivation
<!-- What FERPA compliance gap or educational institution use case does this address? -->

## Changes
- [ ] New §99.31 exception
- [ ] New PII redaction rule
- [ ] Bug fix in filter component
- [ ] Documentation
- [ ] Tests

## Regulatory context
<!-- Which FERPA provision? §99.31? §99.3? -->

## Tests
<!-- Describe the tests added or updated. Use synthetic documents — no real student data. -->

## Checklist
- [ ] Tests pass (`pytest tests/ --no-header`)
- [ ] Lint passes (`ruff check src/ tests/`)
- [ ] Every filter decision produces a `FilterAuditLog` entry (no silent drops)
- [ ] `FERPADocumentFilter` usable as drop-in before any Haystack retriever
- [ ] No real student data, grades, or enrollment records in tests or examples
- [ ] No institution-specific logic or hardcoded school names
- [ ] Patterns work with Haystack >= 2.0.0
