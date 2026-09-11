# Repository maintenance

## Common Failure Patterns

| Symptom | Root cause | Fix |
|---|---|---|
| Unclassified records bypass authorization | Missing identity/category metadata implied public content | Deny incomplete private metadata; explicit public classification with no conflicting identity tags |
| Serialized multitenant filter lost grants | to_dict omitted tenant authorizations | Serialize and reconstruct tenant maps; verify real SDK roundtrip and async parity |
