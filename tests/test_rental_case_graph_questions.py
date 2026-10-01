"""Observation differences create local questions, never a selected world."""
from copy import deepcopy

from againward.domains.rental.case_graph import empty_graph, import_reading
from againward.domains.rental.case_graph_questions import observation_questions
from againward.evidence.hashing import stable_hash
from tests.test_rental_case_graph import evidence


def rehash(payload):
    payload["extraction_sha256"] = stable_hash({k: v for k, v in payload.items() if k != "extraction_sha256"})
    return payload


def test_labels_do_not_create_conflicts_and_single_response_is_not_independent(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    graph = import_reading(graph, payload, root, role="INDEPENDENT")
    questions = list(observation_questions(graph).values())
    assert graph["issues"] == observation_questions(graph)
    assert len(questions) == 1
    assert questions[0]["kind"] == "OBSERVATION_REVIEW"
    assert questions[0]["details"]["corroborated"] is False
    assert questions[0]["details"]["scope"] == "UNASSIGNED"


def test_complementary_read_adds_observation_without_replacing_primary(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    reread = deepcopy(payload)
    candidate = reread["candidates"][0]
    candidate.update(candidate_id="currency-observation", semantic_type="currency", value_type="CURRENCY",
                     value="EUR", raw_observed_value="EUR")
    # Obtain the actual exact native location rather than assume a model offset.
    from againward.documents.readers import read_document
    unit = read_document(batch.documents[0], root).units[0]
    start = unit.text.index("EUR")
    candidate["source_span"] = [start, start + 3]
    graph = import_reading(graph, rehash(reread), root, role="INDEPENDENT")
    assert len(graph["observations"]) == 2
    assert {row["kind"] for row in observation_questions(graph).values()} == {"OBSERVATION_REVIEW"}
    assert graph["occurrences"] == {}


def test_competing_source_status_is_a_local_issue_not_whole_source_rejection(tmp_path):
    root, batch, payload = evidence(tmp_path)
    candidate = payload["candidates"][0]
    candidate.update(semantic_type="document_status", value_type="ENUM", value="ISSUED",
                     normalization_notes="Model interpretation, subject to review")
    graph = import_reading(empty_graph(batch), rehash(payload), root, role="PRIMARY")
    alternate = deepcopy(payload)
    alternate["candidates"][0]["value"] = "DRAFT"
    graph = import_reading(graph, rehash(alternate), root, role="INDEPENDENT")
    conflicts = [q for q in observation_questions(graph).values() if q["kind"] == "SEMANTIC_CONFLICT"]
    assert len(conflicts) == 1
    assert conflicts[0]["details"]["semantic_type"] == "document_status"
    assert len(conflicts[0]["observation_ids"]) == 2
    assert len(graph["readings"]) == 2
    assert all(o["disposition"] == "UNRESOLVED" for o in graph["observations"].values())
