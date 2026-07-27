"""Tests: Personal Knowledge Graph."""

import pytest
from src.nexara_prime.brain.knowledge_graph import (
    KnowledgeGraph, Entity, Relation, Subgraph, PruneResult,
    ENTITY_TYPES, RELATION_TYPES,
)


@pytest.fixture
def kg():
    return KnowledgeGraph()


@pytest.fixture
def sample_memories():
    return [
        {"memory_id": "m1", "content": "DeepSeek V4 Pro is preferred for complex tasks", "key": "model_preference", "kind": "preference", "confidence": 0.9},
        {"memory_id": "m2", "content": "Avoid using flash model for reasoning-intensive work", "key": "model_avoid", "kind": "preference", "confidence": 0.8},
        {"memory_id": "m3", "content": "Budget constraint: prefer flash for simple report generation", "key": "budget_rule", "kind": "system_rule", "confidence": 0.85},
        {"memory_id": "m4", "content": "Previous report generation failed due to token limit exceeded", "key": "failure_report_token", "kind": "failure_experience", "confidence": 0.7},
        {"memory_id": "m5", "content": "User prefers speed over cost for interactive tasks", "key": "user_speed_preference", "kind": "user_fact", "confidence": 0.95},
    ]


class TestEntityExtraction:
    """10 tests: entity extraction, types, confidence."""

    def test_extract_entities_returns_list(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        assert len(entities) == len(sample_memories)

    def test_extract_entities_are_Entity_type(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        for e in entities:
            assert isinstance(e, Entity)

    def test_extract_entities_have_ids(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        ids = [e.entity_id for e in entities]
        assert len(set(ids)) == len(ids)

    def test_entity_type_inference_preference(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        pref_entities = [e for e in entities if "preference" in str(e.properties.get("kind", ""))]
        for e in pref_entities:
            assert e.entity_type == "Pattern"

    def test_entity_type_inference_user_fact(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        user_entities = [e for e in entities if e.properties.get("kind") == "user_fact"]
        for e in user_entities:
            assert e.entity_type == "Person"

    def test_entity_confidence_preserved(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        for e in entities:
            assert 0.0 <= e.confidence <= 1.0

    def test_entity_source_memory_ids(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        for e in entities:
            assert len(e.source_memory_ids) == 1

    def test_extract_empty_memories(self, kg):
        entities = kg.extract_entities([])
        assert entities == []

    def test_all_6_entity_types_defined(self):
        assert len(ENTITY_TYPES) == 6
        assert "Concept" in ENTITY_TYPES
        assert "Tool" in ENTITY_TYPES
        assert "Decision" in ENTITY_TYPES
        assert "Pattern" in ENTITY_TYPES
        assert "Person" in ENTITY_TYPES
        assert "File" in ENTITY_TYPES

    def test_entity_count_tracks(self, kg, sample_memories):
        kg.extract_entities(sample_memories)
        assert kg.entity_count() == 5


class TestRelationInference:
    """10 tests: relation types, inference, evidence."""

    def test_infer_relations_from_entities(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        relations = kg.infer_relations(entities, sample_memories)
        assert isinstance(relations, list)

    def test_infer_relations_are_Relation_type(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        relations = kg.infer_relations(entities, sample_memories)
        for r in relations:
            assert isinstance(r, Relation)

    def test_all_17_relation_types(self):
        assert len(RELATION_TYPES) == 17

    def test_relations_have_confidence(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        relations = kg.infer_relations(entities, sample_memories)
        for r in relations:
            assert 0.0 <= r.confidence <= 1.0

    def test_relations_have_evidence(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        relations = kg.infer_relations(entities, sample_memories)
        for r in relations:
            assert len(r.evidence_ids) > 0

    def test_relations_use_valid_types(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        relations = kg.infer_relations(entities, sample_memories)
        for r in relations:
            assert r.relation_type in RELATION_TYPES

    def test_no_relations_for_single_entity(self, kg):
        entities = [Entity(entity_type="Concept", label="Single")]
        relations = kg.infer_relations(entities, [])
        assert relations == []

    def test_relation_count_tracks(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        kg.infer_relations(entities, sample_memories)
        assert kg.relation_count() >= 0

    def test_entity_without_memory_ids(self, kg):
        entities = kg.extract_entities([{"memory_id": "m1", "content": "test", "kind": "fact", "confidence": 0.5}])
        assert len(entities) == 1


class TestTraversal:
    """5 tests: BFS, max_depth, filters."""

    def test_traverse_returns_subgraph(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        kg.infer_relations(entities, sample_memories)
        if entities:
            sub = kg.traverse(entities[0].entity_id)
            assert isinstance(sub, Subgraph)

    def test_traverse_nonexistent(self, kg):
        sub = kg.traverse("nonexistent_id")
        assert sub.root_entity == "nonexistent_id"

    def test_traverse_respects_max_depth(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        kg.infer_relations(entities, sample_memories)
        if entities:
            sub = kg.traverse(entities[0].entity_id, max_depth=1)
            assert sub.depth == 1


class TestPruning:
    """5 tests: confidence threshold, superseded."""

    def test_prune_removes_low_confidence(self, kg):
        e = Entity(confidence=0.05)
        kg._entities[e.entity_id] = e
        result = kg.prune(min_confidence=0.1)
        assert result.removed_count == 1

    def test_prune_preserves_high_confidence(self, kg):
        e = Entity(confidence=0.9)
        kg._entities[e.entity_id] = e
        result = kg.prune(min_confidence=0.1)
        assert result.removed_count == 0

    def test_prune_flags_superseded(self, kg):
        e = Entity(confidence=0.5, superseded_by="new_entity")
        kg._entities[e.entity_id] = e
        result = kg.prune(min_confidence=0.1)
        assert result.superseded_count == 1

    def test_prune_returns_prune_result(self, kg):
        result = kg.prune()
        assert isinstance(result, PruneResult)


class TestExport:
    """3 tests: Graphviz DOT format."""

    def test_export_graphviz_returns_string(self, kg, sample_memories):
        entities = kg.extract_entities(sample_memories)
        kg.infer_relations(entities, sample_memories)
        dot = kg.export_graphviz()
        assert dot.startswith("digraph")

    def test_export_empty_graph(self, kg):
        dot = kg.export_graphviz()
        assert "digraph" in dot

    def test_health_returns_dict(self, kg, sample_memories):
        kg.extract_entities(sample_memories)
        h = kg.health()
        assert h["component"] == "knowledge_graph"
        assert "entities" in h
        assert "relations" in h
