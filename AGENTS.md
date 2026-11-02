# Repository maintenance

## Common Failure Patterns

| Symptom | Root cause | Fix |
|---|---|---|
| Unclassified records bypass authorization | Missing identity/category metadata implied public content | Deny incomplete private metadata; explicit public classification with no conflicting identity tags |
| Serialized multitenant filter lost grants | to_dict omitted tenant authorizations | Serialize and reconstruct tenant maps; verify real SDK roundtrip and async parity |

| Release appears successful without updated package | Reused version with skip-existing and no exact-tag gate | Use fresh versions, reject tag mismatch, test exact commit, validate distributions and clean wheel imports before upload |

| Malformed scope configuration matches malformed private records or applies another tenant grant | Constructors did not validate identity strings or tenant-map key agreement | Reject empty/non-string identities and tenant keys that disagree with authorization institution IDs |

| README pipeline fails at generator connection and describes obsolete public handling | Example wired documents directly to a text generator and retained permissive metadata rules | Use an executable standalone quick start, show PromptBuilder routing and require explicit public classification |
| Restricted identifiers appear in ordinary logs and errors | Components automatically serialized audit records and interpolated caller metadata into telemetry | Log fixed reasons/counts and opaque audit IDs; keep sensitive details in explicitly returned audit records and test captured logs/errors |
| Apache metadata does not match distributed license contents | LICENSE contained only the application notice | Include the complete selected license and check exact license bytes in wheel and source distributions |

| A no-key example initializes a provider and boundary tests inspect only filtered documents | Tutorial required embeddings/credentials and did not observe final prompt assembly | Use real BM25 retrieval, PromptBuilder and a recording generator with explicit oracle IDs, content canaries and a required bypass control |

| Denial raises with an audit ID that has no corresponding record | The violation exception preceded audit creation and omitted a record for caller persistence | Build and attach a zero-disclosure audit before raising, correlate blocked/completion logs, and test sync/async mixed batches |
| Release workflow uses an advisory-affected or mutable publishing action | A dependency update in one repository left equivalent release workflows unchanged | Pin every publishing workflow to the verified patched action commit and validate each workflow before release |

| Version validation fails despite updated source, or native SDK tests see stub modules | Editable distribution metadata retains its installed version, while unit tests install SDK stubs in the same process | Reinstall editable metadata after a version bump and run unit and native integration suites in separate processes |

| A release guard accepts incomplete artifacts or mismatched source-distribution identity | Validation iterated whatever artifacts happened to exist and checked only wheel metadata | Require one wheel and one sdist, stable source/tag identity and both metadata records; exercise missing, extra and mismatched archive fixtures |

| Python 3.10 dev resolution selects an affected file-locking tool dependency | Patched filelock releases require Python 3.11 while Hatch permits an older fallback | Require the patched floor in dev, document dev 3.11+, and run 3.10 core CI with minimal direct test dependencies |

| A saved empty category list cannot reveal whether the caller intended no grants or wildcard | Serialization collapsed omitted/None/empty policies into the same legacy permissive representation | Version the category contract and require explicit host-reviewed migration instead of guessing; preserve the deliberate wildcard choice in new snapshots |

| An unknown private tenant bypasses category authorization | The legacy allow_unknown_institutions branch returned records before any tenant category grant existed | Reject the permissive legacy option and require explicit TenantAuthorization while preserving trusted public classification |

| Native minimum pipeline rejects multitenant document connections although direct filtering passes | Postponed run annotations became string-valued input socket types in Haystack 2.20 and earlier | Keep component socket annotations concrete and test serialized single/multitenant sockets plus real prompt pipelines on the native minimum |

| Release notes omit native boundary fixes added during review | Notes were drafted before final source and SDK qualification were frozen | Reconcile the dated release entry against the final diff, native regression cases and qualification manifest before closing the release |
