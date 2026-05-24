"""Tests for multi-tenant FERPA filter."""
from __future__ import annotations
import sys
from unittest.mock import MagicMock

# Make @component a pass-through class decorator; @component.output_types a pass-through method decorator
class _ComponentStub:
    def __call__(self, cls):
        return cls  # pass-through
    def output_types(self, **kw):
        return lambda fn: fn  # pass-through

haystack_mod = MagicMock()
haystack_mod.component = _ComponentStub()
haystack_mod.Document = MagicMock
haystack_mod.default_from_dict = MagicMock(side_effect=lambda cls, data: cls(**{k: v for k, v in data.items() if k != "__type__"}))
haystack_mod.default_to_dict = MagicMock(return_value={})
sys.modules["haystack"] = haystack_mod
sys.modules["haystack.core.component"] = haystack_mod.component

def _make_doc(student_id=None, institution_id=None, category=None, doc_id="d1"):
    doc = MagicMock()
    doc.id = doc_id
    doc.meta = {}
    if student_id is not None:
        doc.meta["student_id"] = student_id
    if institution_id is not None:
        doc.meta["institution_id"] = institution_id
    if category is not None:
        doc.meta["category"] = category
    return doc

from multi_tenant_ferpa_filter import MultiTenantFERPAFilter, TenantAuthorization  # noqa: E402


class TestTenantAuthorization:
    def test_frozen(self):
        import pytest
        auth = TenantAuthorization(institution_id="inst_a")
        with pytest.raises((AttributeError, TypeError)):
            auth.institution_id = "other"

    def test_defaults(self):
        auth = TenantAuthorization(institution_id="inst_a")
        assert auth.requestor_id == "system"
        assert len(auth.authorized_categories) == 0


class TestMultiTenantFERPAFilter:
    def _make_filter(self, **kwargs):
        return MultiTenantFERPAFilter(student_id="stu_001", **kwargs)

    def test_wrong_student_blocked(self):
        f = self._make_filter(tenant_authorizations={
            "inst_a": TenantAuthorization("inst_a")
        })
        doc = _make_doc(student_id="stu_other", institution_id="inst_a")
        result = f.run([doc])
        assert len(result["documents"]) == 0

    def test_correct_student_authorized_institution(self):
        f = self._make_filter(tenant_authorizations={
            "inst_a": TenantAuthorization("inst_a")
        })
        doc = _make_doc(student_id="stu_001", institution_id="inst_a")
        result = f.run([doc])
        assert len(result["documents"]) == 1

    def test_unknown_institution_blocked_by_default(self):
        f = self._make_filter(tenant_authorizations={})
        doc = _make_doc(student_id="stu_001", institution_id="inst_unknown")
        result = f.run([doc])
        assert len(result["documents"]) == 0

    def test_unknown_institution_allowed_when_flag_set(self):
        f = self._make_filter(tenant_authorizations={}, allow_unknown_institutions=True)
        doc = _make_doc(student_id="stu_001", institution_id="inst_unknown")
        result = f.run([doc])
        assert len(result["documents"]) == 1

    def test_category_filter_applied(self):
        f = self._make_filter(tenant_authorizations={
            "inst_a": TenantAuthorization("inst_a", authorized_categories=frozenset({"transcript"}))
        })
        ok = _make_doc(student_id="stu_001", institution_id="inst_a", category="transcript")
        blocked = _make_doc(student_id="stu_001", institution_id="inst_a", category="disciplinary", doc_id="d2")
        result = f.run([ok, blocked])
        assert len(result["documents"]) == 1

    def test_shared_content_passes(self):
        f = self._make_filter()
        shared = _make_doc()  # no student_id or institution_id
        result = f.run([shared])
        assert len(result["documents"]) == 1

    def test_cross_institution_blocked_without_basis(self):
        f = self._make_filter(
            tenant_authorizations={
                "inst_foreign": TenantAuthorization("inst_foreign", cross_institution_basis="")
            },
            cross_institution_mode=True,
            home_institution_id="inst_home",
        )
        doc = _make_doc(student_id="stu_001", institution_id="inst_foreign")
        result = f.run([doc])
        assert len(result["documents"]) == 0

    def test_cross_institution_allowed_with_basis(self):
        f = self._make_filter(
            tenant_authorizations={
                "inst_foreign": TenantAuthorization(
                    "inst_foreign",
                    cross_institution_basis="§99.34",
                )
            },
            cross_institution_mode=True,
            home_institution_id="inst_home",
        )
        doc = _make_doc(student_id="stu_001", institution_id="inst_foreign")
        result = f.run([doc])
        assert len(result["documents"]) == 1

    def test_disclosure_record_returned(self):
        f = self._make_filter(tenant_authorizations={
            "inst_a": TenantAuthorization("inst_a")
        })
        doc = _make_doc(student_id="stu_001", institution_id="inst_a")
        result = f.run([doc])
        record = result["disclosure_record"]
        assert record.student_id == "stu_001"
        assert record.total_disclosed == 1

    def test_multi_institution_disclosure_record(self):
        f = self._make_filter(tenant_authorizations={
            "inst_a": TenantAuthorization("inst_a"),
            "inst_b": TenantAuthorization("inst_b"),
        })
        docs = [
            _make_doc("stu_001", "inst_a", doc_id="d1"),
            _make_doc("stu_001", "inst_b", doc_id="d2"),
        ]
        result = f.run(docs)
        assert result["disclosure_record"].total_disclosed == 2
        assert len(result["disclosure_record"].per_institution) == 2
