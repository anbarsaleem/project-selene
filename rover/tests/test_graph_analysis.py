from __future__ import annotations

import pytest

from agent.graph_analysis import (
    build_dependency_graph,
    check_supply_dependency_consistency,
    compute_cascade_impact,
    compute_in_degree,
    compute_resilience_score,
    find_single_points_of_failure,
    generate_mermaid_diagram,
    analyze_infrastructure_changes,
)
from tests.conftest import make_pod


class TestBuildDependencyGraph:
    def test_basic_graph_structure(self, triangle_colony):
        graph = build_dependency_graph(triangle_colony)
        assert set(graph.keys()) == {"depends_on", "depended_by", "supplies_to", "supplied_by"}
        assert "beta" in graph["depends_on"]["alpha"]
        assert "alpha" in graph["depended_by"]["beta"]

    def test_empty_colony(self):
        graph = build_dependency_graph({})
        assert graph["depends_on"] == {}

    def test_bidirectional_tracking(self, triangle_colony):
        graph = build_dependency_graph(triangle_colony)
        assert "alpha" in graph["depends_on"]["charlie"]
        assert "charlie" in graph["depended_by"]["alpha"]


class TestComputeInDegree:
    def test_ranking_order(self, star_colony):
        graph = build_dependency_graph(star_colony)
        rankings = compute_in_degree(graph["depended_by"])
        assert rankings[0] == ("hub", 4)

    def test_leaf_nodes_have_zero(self, star_colony):
        graph = build_dependency_graph(star_colony)
        rankings = compute_in_degree(graph["depended_by"])
        leaf_counts = {pid: count for pid, count in rankings if pid.startswith("leaf")}
        assert all(c == 0 for c in leaf_counts.values())

    def test_independent_colony(self, independent_colony):
        graph = build_dependency_graph(independent_colony)
        rankings = compute_in_degree(graph["depended_by"])
        assert all(count == 0 for _, count in rankings)


class TestFindSinglePointsOfFailure:
    def test_detects_spofs(self, star_colony):
        graph = build_dependency_graph(star_colony)
        spofs = find_single_points_of_failure(star_colony, graph["depended_by"])
        assert len(spofs) == 4
        assert all(s["supplier"] == "hub" for s in spofs)

    def test_no_spofs_when_independent(self, independent_colony):
        graph = build_dependency_graph(independent_colony)
        spofs = find_single_points_of_failure(independent_colony, graph["depended_by"])
        assert spofs == []

    def test_mutual_deps_are_spofs(self, triangle_colony):
        graph = build_dependency_graph(triangle_colony)
        spofs = find_single_points_of_failure(triangle_colony, graph["depended_by"])
        suppliers = {(s["supplier"], s["consumer"]) for s in spofs}
        assert ("beta", "alpha") in suppliers
        assert ("alpha", "beta") in suppliers

    def test_redundant_source_not_flagged(self):
        """If a consumer has two sources for the same resource, neither is a SPOF for it."""
        pods = {
            "src1": make_pod("src1", supplies=[("consumer", "power")]),
            "src2": make_pod("src2", supplies=[("consumer", "power")]),
            "consumer": make_pod(
                "consumer",
                deps=[("src1", "power", "high"), ("src2", "power", "high")],
            ),
        }
        graph = build_dependency_graph(pods)
        spofs = find_single_points_of_failure(pods, graph["depended_by"])
        power_spofs = [s for s in spofs if s["consumer"] == "consumer" and s["resource"] == "power"]
        assert power_spofs == []


class TestSupplyDependencyConsistency:
    def test_consistent_colony(self):
        pods = {
            "a": make_pod("a", deps=[("b", "power", "high")]),
            "b": make_pod("b", supplies=[("a", "power")]),
        }
        mismatches = check_supply_dependency_consistency(pods)
        assert mismatches == []

    def test_dep_not_matched_by_supply(self):
        pods = {
            "a": make_pod("a", deps=[("b", "power", "high")]),
            "b": make_pod("b"),
        }
        mismatches = check_supply_dependency_consistency(pods)
        types = [m["type"] for m in mismatches]
        assert "dependency_not_matched_by_supply" in types

    def test_supply_not_matched_by_dep(self):
        pods = {
            "a": make_pod("a"),
            "b": make_pod("b", supplies=[("a", "power")]),
        }
        mismatches = check_supply_dependency_consistency(pods)
        types = [m["type"] for m in mismatches]
        assert "supply_not_matched_by_dependency" in types


class TestCascadeImpact:
    def test_star_cascade(self, star_colony):
        graph = build_dependency_graph(star_colony)
        result = compute_cascade_impact(
            "hub", graph["depended_by"], graph["depends_on"], star_colony
        )
        assert result["total_affected"] == 4
        assert all(a["depth"] == 1 for a in result["affected_pods"])

    def test_no_cascade_from_leaf(self, star_colony):
        graph = build_dependency_graph(star_colony)
        result = compute_cascade_impact(
            "leaf1", graph["depended_by"], graph["depends_on"], star_colony
        )
        assert result["total_affected"] == 0

    def test_chain_cascade_depth(self):
        """A -> B -> C -> D: failing A should cascade to B(1), C(2), D(3)."""
        pods = {
            "a": make_pod("a", supplies=[("b", "power")]),
            "b": make_pod("b", deps=[("a", "power", "high")], supplies=[("c", "data")]),
            "c": make_pod("c", deps=[("b", "data", "medium")], supplies=[("d", "heat")]),
            "d": make_pod("d", deps=[("c", "heat", "low")]),
        }
        graph = build_dependency_graph(pods)
        result = compute_cascade_impact("a", graph["depended_by"], graph["depends_on"], pods)
        assert result["total_affected"] == 3
        depths = {a["pod_id"]: a["depth"] for a in result["affected_pods"]}
        assert depths == {"b": 1, "c": 2, "d": 3}


class TestResilienceScore:
    def test_independent_colony_scores_high(self, independent_colony):
        graph = build_dependency_graph(independent_colony)
        spofs = find_single_points_of_failure(independent_colony, graph["depended_by"])
        cascade = {}
        score = compute_resilience_score(
            independent_colony, spofs, cascade, graph["depended_by"]
        )
        assert score["composite_score"] >= 80
        assert score["grade"] in ("A", "B")
        assert score["mutual_dependency_loops"] == []

    def test_star_colony_scores_low(self, star_colony):
        graph = build_dependency_graph(star_colony)
        spofs = find_single_points_of_failure(star_colony, graph["depended_by"])
        cascade = {"hub": compute_cascade_impact(
            "hub", graph["depended_by"], graph["depends_on"], star_colony
        )}
        score = compute_resilience_score(
            star_colony, spofs, cascade, graph["depended_by"]
        )
        assert score["composite_score"] < 50
        assert score["grade"] in ("D", "F")

    def test_mutual_dependency_penalty(self, triangle_colony):
        graph = build_dependency_graph(triangle_colony)
        spofs = find_single_points_of_failure(triangle_colony, graph["depended_by"])
        cascade = {"alpha": compute_cascade_impact(
            "alpha", graph["depended_by"], graph["depends_on"], triangle_colony
        )}
        score = compute_resilience_score(
            triangle_colony, spofs, cascade, graph["depended_by"]
        )
        assert score["mutual_dependency_penalty"] == 15
        assert len(score["mutual_dependency_loops"]) == 1
        loop_pods = set(score["mutual_dependency_loops"][0]["pods"])
        assert loop_pods == {"alpha", "beta"}

    def test_score_clamped_at_zero(self):
        """Even with massive penalties, score should not go negative."""
        pods = {}
        for i in range(6):
            pid = f"pod{i}"
            other = f"pod{(i + 1) % 6}"
            pods[pid] = make_pod(
                pid,
                deps=[(other, "power", "high")],
                supplies=[(other, "coolant")],
            )
        graph = build_dependency_graph(pods)
        spofs = find_single_points_of_failure(pods, graph["depended_by"])
        cascade = {
            pid: compute_cascade_impact(pid, graph["depended_by"], graph["depends_on"], pods)
            for pid in list(pods.keys())[:3]
        }
        score = compute_resilience_score(pods, spofs, cascade, graph["depended_by"])
        assert score["composite_score"] >= 0


class TestMermaidDiagram:
    def test_produces_valid_mermaid(self, triangle_colony):
        diagram = generate_mermaid_diagram(triangle_colony)
        assert diagram.startswith("graph LR")
        assert "subgraph" in diagram

    def test_edge_styles_by_criticality(self):
        pods = {
            "a": make_pod("a", deps=[("b", "power", "high")]),
            "b": make_pod("b", deps=[("a", "data", "low")]),
        }
        diagram = generate_mermaid_diagram(pods)
        assert "==>" in diagram
        assert ".->" in diagram

    def test_empty_colony(self):
        diagram = generate_mermaid_diagram({})
        assert "graph LR" in diagram


class TestInfrastructureTimeline:
    def test_filters_relevant_events(self):
        pods = {
            "a": make_pod("a", logs=[
                ("2093-01-01", "infrastructure_change", "removed backup"),
                ("2093-02-01", "routine_check", "all nominal"),
                ("2093-03-01", "directive", "consolidate systems"),
            ]),
        }
        timeline = analyze_infrastructure_changes(pods)
        assert len(timeline) == 2
        events = [t["event"] for t in timeline]
        assert "routine_check" not in events

    def test_sorted_chronologically(self):
        pods = {
            "a": make_pod("a", logs=[
                ("2094-01-01", "directive", "late"),
            ]),
            "b": make_pod("b", logs=[
                ("2093-01-01", "directive", "early"),
            ]),
        }
        timeline = analyze_infrastructure_changes(pods)
        assert timeline[0]["detail"] == "early"
        assert timeline[1]["detail"] == "late"
