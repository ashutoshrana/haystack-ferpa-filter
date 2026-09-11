"""Tests for FERPAMetadataFilter."""

from __future__ import annotations

import pytest
from haystack import Document
from haystack_integrations.components.filters.ferpa_filter import (
    FERPADisclosureRecord,
    FERPAMetadataFilter,
)


@pytest.fixture()
def default_filter() -> FERPAMetadataFilter:
    return FERPAMetadataFilter(
        student_id="stu_001",
        institution_id="inst_abc",
        authorized_categories=["academic_record", "financial_aid"],
        requesting_user_id="advisor_007",
    )


@pytest.fixture()
def authorized_doc() -> Document:
    return Document(
        content="GPA: 3.8",
        meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "academic_record"},
    )


@pytest.fixture()
def wrong_student_doc() -> Document:
    return Document(
        content="GPA: 3.5",
        meta={"student_id": "stu_002", "institution_id": "inst_abc", "category": "academic_record"},
    )


@pytest.fixture()
def shared_doc() -> Document:
    return Document(content="Course Catalogue 2025", meta={"classification": "public"})


class TestIdentityFilter:
    def test_authorized_doc_passes(self, default_filter, authorized_doc):
        result = default_filter.run([authorized_doc])
        assert len(result["documents"]) == 1

    def test_wrong_student_blocked(self, default_filter, wrong_student_doc):
        result = default_filter.run([wrong_student_doc])
        assert len(result["documents"]) == 0

    def test_shared_content_passes(self, default_filter, shared_doc):
        result = default_filter.run([shared_doc])
        assert len(result["documents"]) == 1

    def test_mixed_batch(self, default_filter, authorized_doc, wrong_student_doc, shared_doc):
        result = default_filter.run([authorized_doc, wrong_student_doc, shared_doc])
        assert len(result["documents"]) == 2

    def test_wrong_institution_blocked(self, default_filter):
        doc = Document(
            content="...",
            meta={"student_id": "stu_001", "institution_id": "inst_xyz", "category": "academic_record"},
        )
        result = default_filter.run([doc])
        assert len(result["documents"]) == 0

    def test_empty_input(self, default_filter):
        result = default_filter.run([])
        assert result["documents"] == []


class TestCategoryAuthorization:
    def test_authorized_category_passes(self, default_filter):
        doc = Document(
            content="...",
            meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "financial_aid"},
        )
        assert len(default_filter.run([doc])["documents"]) == 1

    def test_unauthorized_category_blocked(self, default_filter):
        doc = Document(
            content="...",
            meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "disciplinary"},
        )
        assert len(default_filter.run([doc])["documents"]) == 0

    def test_no_category_field_blocked(self, default_filter):
        doc = Document(
            content="...",
            meta={"student_id": "stu_001", "institution_id": "inst_abc"},
        )
        assert len(default_filter.run([doc])["documents"]) == 0

    def test_empty_authorized_categories_allows_all(self):
        f = FERPAMetadataFilter(
            student_id="stu_001",
            institution_id="inst_abc",
            authorized_categories=[],
        )
        doc = Document(
            content="...",
            meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "disciplinary"},
        )
        assert len(f.run([doc])["documents"]) == 1


class TestDisclosureRecord:
    def test_record_always_present(self, default_filter, authorized_doc):
        result = default_filter.run([authorized_doc])
        assert "disclosure_record" in result
        assert isinstance(result["disclosure_record"], FERPADisclosureRecord)

    def test_record_counts(self, default_filter, authorized_doc, wrong_student_doc):
        result = default_filter.run([authorized_doc, wrong_student_doc])
        record = result["disclosure_record"]
        assert record.total_retrieved == 2
        assert record.total_disclosed == 1

    def test_record_on_empty_input(self, default_filter):
        result = default_filter.run([])
        record = result["disclosure_record"]
        assert record.total_retrieved == 0
        assert record.total_disclosed == 0

    def test_categories_disclosed(self, default_filter):
        docs = [
            Document(content="a", meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "academic_record"}),
            Document(content="b", meta={"student_id": "stu_001", "institution_id": "inst_abc", "category": "financial_aid"}),
        ]
        record = default_filter.run(docs)["disclosure_record"]
        assert set(record.categories_disclosed) == {"academic_record", "financial_aid"}

    def test_log_entry_format(self, default_filter, authorized_doc):
        record = default_filter.run([authorized_doc])["disclosure_record"]
        log = record.to_log_entry()
        assert "[FERPA_DISCLOSURE]" in log
        assert "student_id=" in log
        assert "total_disclosed=" in log


class TestRaiseOnViolation:
    def test_raises_on_unauthorized(self, wrong_student_doc):
        f = FERPAMetadataFilter(
            student_id="stu_001",
            institution_id="inst_abc",
            raise_on_violation=True,
        )
        with pytest.raises(PermissionError, match="FERPA violation"):
            f.run([wrong_student_doc])

    def test_no_raise_when_all_authorized(self, authorized_doc):
        f = FERPAMetadataFilter(
            student_id="stu_001",
            institution_id="inst_abc",
            raise_on_violation=True,
        )
        result = f.run([authorized_doc])
        assert len(result["documents"]) == 1


class TestSerialization:
    def test_to_dict_round_trip(self, default_filter):
        d = default_filter.to_dict()
        restored = FERPAMetadataFilter.from_dict(d)
        assert restored.student_id == default_filter.student_id
        assert restored.institution_id == default_filter.institution_id
        assert restored.authorized_categories == default_filter.authorized_categories
        assert restored.requesting_user_id == default_filter.requesting_user_id

    def test_from_dict_preserves_all_fields(self):
        original = FERPAMetadataFilter(
            student_id="s1",
            institution_id="i1",
            authorized_categories=["academic_record"],
            requesting_user_id="advisor_1",
            student_id_field="learner_id",
            institution_id_field="campus_code",
            category_field="record_type",
            pipeline_context="test_pipeline",
            raise_on_violation=True,
        )
        restored = FERPAMetadataFilter.from_dict(original.to_dict())
        assert restored.student_id_field == "learner_id"
        assert restored.institution_id_field == "campus_code"
        assert restored.category_field == "record_type"
        assert restored.raise_on_violation is True


class TestCustomFieldNames:
    def test_custom_student_field(self):
        f = FERPAMetadataFilter(
            student_id="s1",
            institution_id="i1",
            student_id_field="learner_id",
            institution_id_field="campus_code",
        )
        doc = Document(content="...", meta={"learner_id": "s1", "campus_code": "i1", "category": "academic_record"})
        assert len(f.run([doc])["documents"]) == 1

    def test_custom_category_field(self):
        f = FERPAMetadataFilter(
            student_id="s1",
            institution_id="i1",
            authorized_categories=["transcript"],
            category_field="record_type",
        )
        doc = Document(content="...", meta={"student_id": "s1", "institution_id": "i1", "record_type": "transcript"})
        assert len(f.run([doc])["documents"]) == 1


class TestAsync:
    @pytest.mark.asyncio
    async def test_run_async_matches_run(self, default_filter, authorized_doc, wrong_student_doc):
        sync_result = default_filter.run([authorized_doc, wrong_student_doc])
        async_result = await default_filter.run_async([authorized_doc, wrong_student_doc])
        assert len(sync_result["documents"]) == len(async_result["documents"])
        assert sync_result["disclosure_record"].total_disclosed == async_result["disclosure_record"].total_disclosed
