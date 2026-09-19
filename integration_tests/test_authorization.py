"""Real Haystack serialization and authorization checks, isolated from legacy mocks."""
import asyncio

import pytest
from haystack import Document
from haystack_integrations.components.filters.ferpa_filter.ferpa_metadata_filter import FERPAMetadataFilter
from haystack_integrations.components.filters.ferpa_filter.multi_tenant_ferpa_filter import MultiTenantFERPAFilter, TenantAuthorization


@pytest.mark.parametrize("field", ["student_id", "institution_id", "category"])
@pytest.mark.parametrize("value", [None, "", [], {}])
def test_incomplete_private_metadata_denied(field, value):
    meta = {"student_id": "s", "institution_id": "i", "category": "record"}
    meta[field] = value
    doc = Document(content="SECRET_CANARY", meta=meta)
    for guard in guards():
        assert guard.run([doc])["documents"] == []
        assert asyncio.run(guard.run_async([doc]))["documents"] == []


def guards():
    return [FERPAMetadataFilter("s", "i", ["record"]), MultiTenantFERPAFilter("s", {"i": TenantAuthorization("i", frozenset({"record"}))})]


def test_public_and_serialized_scope():
    public = Document(content="PUBLIC", meta={"classification": "public"})
    conflict = Document(content="SECRET_CANARY", meta={"classification": "public", "student_id": "other"})
    allowed = Document(content="ALLOWED", meta={"student_id": "s", "institution_id": "i", "category": "record"})
    for guard in guards():
        saved = guard.to_dict()
        restored = type(guard).from_dict(saved)
        assert restored.to_dict() == saved
        for candidate in [guard, restored]:
            assert candidate.run([public, conflict, allowed])["documents"] == [public, allowed]
            assert asyncio.run(candidate.run_async([public, conflict, allowed]))["documents"] == [public, allowed]


@pytest.mark.parametrize("value", [None, "", "   ", [], 42])
def test_invalid_configured_identity_rejected(value):
    with pytest.raises(ValueError):
        FERPAMetadataFilter(value, "i")
    with pytest.raises(ValueError):
        FERPAMetadataFilter("s", value)
    with pytest.raises(ValueError):
        MultiTenantFERPAFilter(value)


def test_mismatched_tenant_grant_rejected():
    with pytest.raises(ValueError):
        MultiTenantFERPAFilter("s", {"tenant-b": TenantAuthorization("tenant-a")})
