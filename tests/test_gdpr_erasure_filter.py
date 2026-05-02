"""Tests for GDPR Art. 17 right-to-erasure Haystack filter."""
from __future__ import annotations
import sys
from unittest.mock import MagicMock

# Stub haystack
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
sys.modules["haystack.core.component"] = MagicMock()

def _make_doc(subject_id=None, doc_id="doc_001"):
    doc = MagicMock()
    doc.id = doc_id
    doc.meta = {"data_subject_id": subject_id} if subject_id else {}
    return doc

sys.path.insert(0, "/tmp/devbuild")
from gdpr_erasure_filter import GDPRRightToErasureFilter, ErasureTombstone, ErasureAuditRecord, ErasureException


class TestErasureTombstone:
    def test_add_and_is_erased(self):
        t = ErasureTombstone()
        t.add("s1")
        assert t.is_erased("s1")

    def test_not_erased_by_default(self):
        t = ErasureTombstone()
        assert not t.is_erased("unknown")

    def test_remove_clears(self):
        t = ErasureTombstone({"s1"})
        t.remove("s1")
        assert not t.is_erased("s1")

    def test_initial_subjects(self):
        t = ErasureTombstone({"a", "b"})
        assert t.is_erased("a") and t.is_erased("b")
        assert len(t) == 2


class TestErasureException:
    def test_valid_exceptions(self):
        for code in ["legal_obligation", "legal_claims", "public_interest", "freedom_expression"]:
            assert ErasureException.is_valid(code)

    def test_invalid_exception(self):
        assert not ErasureException.is_valid("made_up_exception")


class TestGDPRRightToErasureFilter:
    def setup_method(self):
        self.tombstone = ErasureTombstone({"subject_erased"})

    def _make_filter(self, **kwargs):
        f = GDPRRightToErasureFilter(tombstone=self.tombstone, **kwargs)
        # Unwrap component decorator for testing
        return f

    def test_erased_subject_intercepted(self):
        f = self._make_filter()
        docs = [_make_doc("subject_erased"), _make_doc("subject_ok")]
        result = f.run(docs)
        assert len(result["documents"]) == 1
        assert result["documents"][0].meta["data_subject_id"] == "subject_ok"

    def test_no_erased_subjects_pass_all(self):
        tombstone = ErasureTombstone()
        f = GDPRRightToErasureFilter(tombstone=tombstone)
        docs = [_make_doc("s1"), _make_doc("s2")]
        result = f.run(docs)
        assert len(result["documents"]) == 2

    def test_shared_content_passes(self):
        f = self._make_filter()
        shared = _make_doc(subject_id=None)
        result = f.run([shared])
        assert len(result["documents"]) == 1

    def test_audit_record_created_on_intercept(self):
        f = self._make_filter()
        docs = [_make_doc("subject_erased")]
        result = f.run(docs)
        assert len(result["erasure_audit"]) == 1
        audit = result["erasure_audit"][0]
        assert audit.subject_id == "subject_erased"
        assert audit.intercepted_count == 1

    def test_no_audit_record_when_nothing_intercepted(self):
        f = self._make_filter()
        docs = [_make_doc("subject_ok")]
        result = f.run(docs)
        assert len(result["erasure_audit"]) == 0

    def test_legal_claims_exception_allows_erased_doc(self):
        f = self._make_filter(erasure_exception="legal_claims")
        docs = [_make_doc("subject_erased")]
        result = f.run(docs)
        assert len(result["documents"]) == 1

    def test_invalid_exception_raises_on_init(self):
        import pytest
        with pytest.raises(ValueError):
            GDPRRightToErasureFilter(tombstone=self.tombstone, erasure_exception="invalid_code")

    def test_audit_records_property(self):
        f = self._make_filter()
        f.run([_make_doc("subject_erased")])
        f.run([_make_doc("subject_erased")])
        assert len(f.audit_records) == 2

    def test_custom_subject_id_field(self):
        tombstone = ErasureTombstone({"subject_x"})
        f = GDPRRightToErasureFilter(tombstone=tombstone, subject_id_field="custom_id")
        doc = MagicMock()
        doc.id = "d1"
        doc.meta = {"custom_id": "subject_x"}
        result = f.run([doc])
        assert len(result["documents"]) == 0

    def test_vector_store_rebuild_pending_flag_in_audit(self):
        f = self._make_filter(vector_store_rebuild_pending=True)
        f.run([_make_doc("subject_erased")])
        assert f.audit_records[0].vector_store_rebuild_pending is True
