import sys
from pathlib import Path

# Make filter modules importable by flat name (gdpr_erasure_filter, multi_tenant_ferpa_filter).
# Tests mock haystack at module level before importing these; the mock is in place when
# pytest imports each test module because conftest runs first.
_filter_src = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "haystack_integrations"
    / "components"
    / "filters"
    / "ferpa_filter"
)
if str(_filter_src) not in sys.path:
    sys.path.insert(0, str(_filter_src))
