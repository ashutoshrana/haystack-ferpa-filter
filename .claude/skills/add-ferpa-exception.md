---
description: How to add a new FERPA §99.31 exception or redaction rule to haystack-ferpa-filter
---

# Skill: Add a New FERPA Exception or Redaction Rule

Use this when adding a new §99.31 permissible disclosure exception or a new PII field type to haystack-ferpa-filter.

## Adding a §99.31 Exception

### Files to modify
1. `src/haystack_ferpa_filter/exceptions.py` — add the exception class
2. `tests/test_exceptions.py` — add tests for the new exception

### Exception structure

```python
from __future__ import annotations
from dataclasses import dataclass
from haystack_ferpa_filter.audit import FilterAuditLog

@dataclass(frozen=True)
class {ExceptionName}Exception:
    """FERPA § 99.31({letter}) — {exception description}."""
    
    regulation_citation: str = "FERPA 34 CFR § 99.31({letter})"

    def evaluate(self, caller_context: dict, document: dict) -> bool:
        """Return True if this exception permits disclosure."""
        # Check the specific §99.31 condition
        raise NotImplementedError
```

### §99.31 exception inventory
- `(a)(1)` — school officials with legitimate educational interest
- `(a)(2)` — transfer to another school
- `(a)(3)` — authorized representatives for federal/state audit or evaluation
- `(a)(5)` — connection with financial aid
- `(a)(6)` — state/local authorities reporting
- `(a)(11)` — directory information (if not opted out)

### Test requirements
Minimum 3 tests per exception:
1. Caller qualifies → exception granted → APPROVED decision
2. Caller does not qualify → exception denied → DENIED or REQUIRES_HUMAN_REVIEW
3. Missing context field → safe default (REQUIRES_HUMAN_REVIEW, not APPROVED)

## Adding a Redaction Rule

### Files to modify
1. `src/haystack_ferpa_filter/redactor.py` — add the PII field pattern
2. `tests/test_redactor.py` — add tests for the new field type

### FERPA education record PII fields (must cover all)
- SSN / student ID numbers
- Grades, GPA, academic performance
- Enrollment status (full-time/part-time)
- Financial aid amounts and eligibility
- Disciplinary records
- Special education designation
- Class schedules and transcripts
- Date of birth
- Student address and contact info

### Redactor entry

```python
FERPA_PII_PATTERNS = {
    # existing patterns...
    "{field_name}": re.compile(r"YOUR_REGEX_HERE", re.IGNORECASE),
}
```

## README update (required after every new exception or field)

Update the "Supported §99.31 Exceptions" table and the PII field coverage list.

## CHANGELOG entry

```markdown
## [vX.Y.Z] — YYYY-MM-DD

### Added — FERPA § 99.31({letter}) {Exception Name} Exception

- `{ExceptionName}Exception` — permits disclosure for {use case}
- N new tests. Total: **NN passed**.
```
