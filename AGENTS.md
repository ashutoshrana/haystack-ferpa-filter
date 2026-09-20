# Repository maintenance

## Common Failure Patterns

| Symptom | Root cause | Fix |
|---|---|---|
| Unclassified records bypass authorization | Missing identity/category metadata implied public content | Deny incomplete private metadata; explicit public classification with no conflicting identity tags |
| Serialized multitenant filter lost grants | to_dict omitted tenant authorizations | Serialize and reconstruct tenant maps; verify real SDK roundtrip and async parity |

| Release appears successful without updated package | Reused version with skip-existing and no exact-tag gate | Use fresh versions, reject tag mismatch, test exact commit, validate distributions and clean wheel imports before upload |

| Malformed scope configuration matches malformed private records or applies another tenant grant | Constructors did not validate identity strings or tenant-map key agreement | Reject empty/non-string identities and tenant keys that disagree with authorization institution IDs |

| README pipeline fails at generator connection and describes obsolete public handling | Example wired documents directly to a text generator and retained permissive metadata rules | Use an executable standalone quick start, show PromptBuilder routing and require explicit public classification |
