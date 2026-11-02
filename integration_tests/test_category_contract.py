import pytest
from haystack import Document, Pipeline, component
from haystack.components.builders import PromptBuilder
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from haystack_integrations.components.filters.ferpa_filter import FERPAMetadataFilter, MultiTenantFERPAFilter, TenantAuthorization

@component
class Recorder:
    @component.output_types(prompt=str)
    def run(self, prompt: str):
        return {"prompt": prompt}


def prompt_after_roundtrip(gate, output, inputs):
    gate = type(gate).from_dict(gate.to_dict())
    store = InMemoryDocumentStore()
    store.write_documents([
        Document(content="record ACADEMIC", meta={"student_id": "s", "institution_id": "i", "category": "academic_record"}),
        Document(content="record DIRECTORY", meta={"student_id": "s", "institution_id": "i", "category": "directory_information"}),
        Document(content="record OTHER", meta={"student_id": "other", "institution_id": "i", "category": "academic_record"}),
        Document(content="record UNKNOWN", meta={"student_id": "s", "institution_id": "unknown", "category": "academic_record"}),
        Document(content="record UNTAGGED"),
        Document(content="record PUBLIC", meta={"classification": "public"}),
        Document(content="record CONFLICT", meta={"classification": "public", "student_id": "other", "institution_id": "i", "category": "academic_record"}),
    ])
    pipeline = Pipeline()
    pipeline.add_component("retriever", InMemoryBM25Retriever(store, top_k=10))
    pipeline.add_component("gate", gate)
    pipeline.add_component("prompt", PromptBuilder(template="{% for d in documents %}{{ d.content }}\n{% endfor %}", required_variables=["documents"]))
    pipeline.add_component("model", Recorder())
    pipeline.connect("retriever.documents", "gate.documents")
    pipeline.connect("gate." + output, "prompt.documents")
    pipeline.connect("prompt.prompt", "model.prompt")
    return pipeline.run({"retriever": {"query": "record"}, "gate": inputs})["model"]["prompt"]


def assert_prompt(prompt, mode):
    assert "PUBLIC" in prompt
    assert ("ACADEMIC" in prompt) == (mode in ("grant", "unrestricted"))
    assert ("DIRECTORY" in prompt) == (mode == "unrestricted")
    for forbidden in ("OTHER", "UNKNOWN", "UNTAGGED", "CONFLICT"):
        assert forbidden not in prompt


@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("mode", ["omitted", "none", "empty", "grant", "unrestricted"])
def test_category_contract_at_model_prompt(multi, mode):
    args = {}
    if mode != "omitted":
        args["authorized_categories"] = None if mode == "none" else ["academic_record"] if mode == "grant" else []
    if mode == "unrestricted":
        args["unrestricted_categories"] = True
    if multi:
        args["authorized_categories"] = frozenset(args.get("authorized_categories") or [])
        gate = MultiTenantFERPAFilter("s", {"i": TenantAuthorization("i", **args)})
    else:
        gate = FERPAMetadataFilter("s", "i", **args)
    assert_prompt(prompt_after_roundtrip(gate, "documents", {}), mode)


@pytest.mark.parametrize("kind", [FERPAMetadataFilter, MultiTenantFERPAFilter])
def test_legacy_serialization_requires_explicit_migration(kind):
    with pytest.raises(ValueError, match="migration"):
        kind.from_dict({"init_parameters": {}})


@pytest.mark.parametrize("value", ["false", 1, None])
def test_unrestricted_is_strict_bool(value):
    with pytest.raises(ValueError, match="bool"):
        FERPAMetadataFilter("s", "i", unrestricted_categories=value)
    with pytest.raises(ValueError, match="bool"):
        TenantAuthorization("i", unrestricted_categories=value)


def test_unknown_private_opt_in_is_rejected():
    with pytest.raises(ValueError, match="TenantAuthorization"):
        MultiTenantFERPAFilter("s", allow_unknown_institutions=True)


@pytest.mark.parametrize("kind", [FERPAMetadataFilter, MultiTenantFERPAFilter])
@pytest.mark.parametrize("value", ["2", 2.0, True])
def test_serialization_marker_is_strict(kind, value):
    with pytest.raises(ValueError):
        kind.from_dict({"init_parameters": {"category_contract_version": value}})


@pytest.mark.parametrize("value", ["false", 1, None])
def test_serialized_unrestricted_is_strict(value):
    data = FERPAMetadataFilter("s", "i").to_dict()
    data["init_parameters"]["unrestricted_categories"] = value
    with pytest.raises(ValueError, match="bool"):
        FERPAMetadataFilter.from_dict(data)
    data = MultiTenantFERPAFilter("s", {"i": TenantAuthorization("i")}).to_dict()
    data["init_parameters"]["tenant_authorizations"]["i"]["unrestricted_categories"] = value
    with pytest.raises(ValueError, match="bool"):
        MultiTenantFERPAFilter.from_dict(data)


@pytest.mark.parametrize("multi", [False, True])
def test_roundtripped_component_declares_concrete_document_input(multi):
    # Haystack 2.3.1 compares socket types without resolving annotation strings.
    gate = MultiTenantFERPAFilter("s", {"i": TenantAuthorization("i")}) if multi else FERPAMetadataFilter("s", "i")
    gate = type(gate).from_dict(gate.to_dict())
    assert gate.__haystack_input__._sockets_dict["documents"].type == list[Document]
