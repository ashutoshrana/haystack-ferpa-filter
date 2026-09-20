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
