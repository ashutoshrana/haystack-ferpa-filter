"""Ordinary telemetry must not copy restricted audit fields or document metadata."""
import asyncio
import logging
from types import SimpleNamespace

import pytest

from ferpa_metadata_filter import FERPAMetadataFilter
from gdpr_erasure_filter import GDPRRightToErasureFilter, ErasureTombstone
from multi_tenant_ferpa_filter import MultiTenantFERPAFilter, TenantAuthorization

STUDENT = "PRIVATE_STUDENT_CANARY"
TENANT = "PRIVATE_TENANT_CANARY"
CONTEXT = "PRIVATE_CONTEXT_CANARY\nforged log entry"
CATEGORY = "PRIVATE_CATEGORY_CANARY"


def doc(student=STUDENT, tenant=TENANT, category=CATEGORY):
    return SimpleNamespace(id="PRIVATE_DOCUMENT_CANARY", content="PRIVATE_CONTENT_CANARY", meta={
        "student_id": student, "institution_id": tenant, "category": category,
        "data_subject_id": student,
    })


def assert_private_telemetry_absent(caplog, exception=""):
    text = caplog.text + exception
    assert "PRIVATE_" not in text
    assert "forged log entry" not in text
    # Check structured arguments too: a formatter must not merely hide raw values.
    assert all("PRIVATE_" not in repr(record.args) for record in caplog.records)


@pytest.mark.parametrize("async_mode", [False, True])
def test_ferpa_logs_keep_audit_private(caplog, async_mode):
    caplog.set_level(logging.INFO)
    guard = FERPAMetadataFilter(STUDENT, TENANT, [CATEGORY], pipeline_context=CONTEXT)
    documents = [doc(), doc(student="PRIVATE_OTHER_STUDENT_CANARY")]
    result = asyncio.run(guard.run_async(documents)) if async_mode else guard.run(documents)
    assert result["documents"] == documents[:1]
    audit = result["disclosure_record"]
    assert audit.student_id == STUDENT
    assert audit.pipeline_context == CONTEXT
    assert STUDENT in audit.to_log_entry()
    assert caplog.records
    assert_private_telemetry_absent(caplog)


@pytest.mark.parametrize("async_mode", [False, True])
def test_ferpa_denial_exception_is_private(caplog, async_mode):
    guard = FERPAMetadataFilter(STUDENT, TENANT, raise_on_violation=True)
    with pytest.raises(PermissionError) as exc:
        documents = [doc(student="PRIVATE_OTHER_STUDENT_CANARY")]
        if async_mode:
            asyncio.run(guard.run_async(documents))
        else:
            guard.run(documents)
    assert "1 unauthorized" in str(exc.value)
    assert_private_telemetry_absent(caplog, str(exc.value))


@pytest.mark.parametrize("async_mode", [False, True])
def test_multitenant_all_denial_logs_keep_audit_private(caplog, async_mode):
    caplog.set_level(logging.INFO)
    other_tenant = "PRIVATE_OTHER_TENANT_CANARY"
    guard = MultiTenantFERPAFilter(STUDENT, {
        TENANT: TenantAuthorization(TENANT, frozenset({CATEGORY})),
        other_tenant: TenantAuthorization(other_tenant, frozenset({CATEGORY})),
    }, cross_institution_mode=True, home_institution_id=TENANT, pipeline_context=CONTEXT)
    documents = [doc(), doc(student="PRIVATE_OTHER_STUDENT_CANARY"),
                 doc(tenant="PRIVATE_UNKNOWN_TENANT_CANARY"), doc(tenant=other_tenant),
                 doc(category="PRIVATE_DENIED_CATEGORY_CANARY")]
    result = asyncio.run(guard.run_async(documents)) if async_mode else guard.run(documents)
    assert result["documents"] == documents[:1]
    audit = result["disclosure_record"]
    assert audit.student_id == STUDENT
    assert TENANT in audit.per_institution
    assert STUDENT in audit.to_log_entry()
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 4
    assert_private_telemetry_absent(caplog)


@pytest.mark.parametrize("exception_code", [None, "legal_obligation"])
def test_erasure_logs_keep_audit_private(caplog, exception_code):
    caplog.set_level(logging.INFO)
    tombstone = ErasureTombstone()
    tombstone.add(STUDENT)
    guard = GDPRRightToErasureFilter(tombstone=tombstone, pipeline_context=CONTEXT,
                                    erasure_exception=exception_code)
    document = doc()
    result = guard.run([document])
    assert result["documents"] == ([document] if exception_code else [])
    audit = result["erasure_audit"][0]
    assert audit.subject_id == STUDENT
    assert audit.pipeline_context == CONTEXT
    assert STUDENT in audit.to_log_entry()
    assert caplog.records
    assert_private_telemetry_absent(caplog)


def test_invalid_erasure_code_does_not_echo_untrusted_input():
    with pytest.raises(ValueError) as exc:
        GDPRRightToErasureFilter(erasure_exception="PRIVATE_INPUT_CANARY\nforged log entry")
    assert "PRIVATE_" not in str(exc.value)
    assert "forged log entry" not in str(exc.value)


@pytest.mark.parametrize("kind", ["ferpa", "multitenant", "erasure"])
def test_batch_correlation_is_fresh_and_matches_returned_audit(caplog, kind):
    caplog.set_level(logging.INFO)
    if kind == "ferpa":
        guard = FERPAMetadataFilter(STUDENT, TENANT, [CATEGORY])
    elif kind == "multitenant":
        guard = MultiTenantFERPAFilter(STUDENT, {TENANT: TenantAuthorization(TENANT)})
    else:
        guard = GDPRRightToErasureFilter(erased_subjects={STUDENT})
    ids = []
    for async_mode in [False, True]:
        caplog.clear()
        if async_mode and hasattr(guard, "run_async"):
            result = asyncio.run(guard.run_async([doc()]))
        else:
            result = guard.run([doc()])
        audit = result["erasure_audit"][0] if kind == "erasure" else result["disclosure_record"]
        assert len(audit.audit_id) == 32
        assert int(audit.audit_id, 16) >= 0
        assert f"audit_id={audit.audit_id}" in caplog.text
        ids.append(audit.audit_id)
    assert len(set(ids)) == 2


def test_strict_denial_has_fresh_opaque_correlation(caplog):
    import re

    guard = FERPAMetadataFilter(STUDENT, TENANT, raise_on_violation=True)
    ids = []
    for _ in range(2):
        with pytest.raises(PermissionError) as exc:
            guard.run([doc(student="PRIVATE_OTHER_STUDENT_CANARY")])
        ids.append(re.search(r"audit_id=([a-f0-9]{32})", str(exc.value)).group(1))
        assert_private_telemetry_absent(caplog, str(exc.value))
    assert ids[0] != ids[1]
