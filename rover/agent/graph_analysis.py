from __future__ import annotations

from collections import deque
from typing import Any

from agent.models import PodData


def build_dependency_graph(pods: dict[str, PodData]) -> dict[str, dict[str, list[str]]]:
    depends_on: dict[str, list[str]] = {pid: [] for pid in pods}
    depended_by: dict[str, list[str]] = {pid: [] for pid in pods}
    supplies_to: dict[str, list[str]] = {pid: [] for pid in pods}
    supplied_by: dict[str, list[str]] = {pid: [] for pid in pods}

    for pid, pod in pods.items():
        for dep in pod.dependencies:
            depends_on[pid].append(dep.pod_id)
            if dep.pod_id in depended_by:
                depended_by[dep.pod_id].append(pid)
        for sup in pod.supplies:
            supplies_to[pid].append(sup.pod_id)
            if sup.pod_id in supplied_by:
                supplied_by[sup.pod_id].append(pid)

    return {
        "depends_on": depends_on,
        "depended_by": depended_by,
        "supplies_to": supplies_to,
        "supplied_by": supplied_by,
    }


def compute_in_degree(depended_by: dict[str, list[str]]) -> list[tuple[str, int]]:
    ranked = [(pid, len(dependents)) for pid, dependents in depended_by.items()]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def find_single_points_of_failure(
    pods: dict[str, PodData], depended_by: dict[str, list[str]]
) -> list[dict[str, Any]]:
    spofs: list[dict[str, Any]] = []

    for supplier_id, dependents in depended_by.items():
        if not dependents:
            continue
        for consumer_id in dependents:
            consumer = pods.get(consumer_id)
            if consumer is None:
                continue
            for dep in consumer.dependencies:
                if dep.pod_id != supplier_id:
                    continue
                alternative_sources = [
                    d.pod_id
                    for d in consumer.dependencies
                    if d.pod_id != supplier_id and d.resource == dep.resource
                ]
                if not alternative_sources:
                    spofs.append({
                        "supplier": supplier_id,
                        "consumer": consumer_id,
                        "resource": dep.resource,
                        "criticality": dep.criticality,
                    })

    return spofs


def check_supply_dependency_consistency(pods: dict[str, PodData]) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []

    for pid, pod in pods.items():
        for dep in pod.dependencies:
            supplier = pods.get(dep.pod_id)
            if supplier is None:
                mismatches.append({
                    "type": "dependency_references_unknown_pod",
                    "consumer": pid,
                    "supplier": dep.pod_id,
                    "resource": dep.resource,
                })
                continue
            supply_targets = {s.pod_id for s in supplier.supplies}
            if pid not in supply_targets:
                mismatches.append({
                    "type": "dependency_not_matched_by_supply",
                    "consumer": pid,
                    "supplier": dep.pod_id,
                    "resource": dep.resource,
                })

    for pid, pod in pods.items():
        for sup in pod.supplies:
            consumer = pods.get(sup.pod_id)
            if consumer is None:
                continue
            dep_sources = {d.pod_id for d in consumer.dependencies}
            if pid not in dep_sources:
                mismatches.append({
                    "type": "supply_not_matched_by_dependency",
                    "supplier": pid,
                    "consumer": sup.pod_id,
                    "resource": sup.resource,
                })

    return mismatches


def analyze_infrastructure_changes(pods: dict[str, PodData]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for pid, pod in pods.items():
        for log in pod.logs:
            if log.event in ("infrastructure_change", "directive", "expansion"):
                changes.append({
                    "pod_id": pid,
                    "timestamp": log.timestamp,
                    "event": log.event,
                    "detail": log.detail,
                })
    changes.sort(key=lambda x: x["timestamp"])
    return changes


def compute_cascade_impact(
    failed_pod: str,
    depended_by: dict[str, list[str]],
    depends_on: dict[str, list[str]],
    pods: dict[str, PodData],
) -> dict[str, Any]:
    affected: list[dict[str, Any]] = []
    visited: set[str] = {failed_pod}
    queue: deque[tuple[str, int]] = deque()

    for dep_id in depended_by.get(failed_pod, []):
        if dep_id not in visited:
            queue.append((dep_id, 1))
            visited.add(dep_id)

    while queue:
        pod_id, depth = queue.popleft()
        pod = pods.get(pod_id)
        resources_lost = []
        if pod:
            for dep in pod.dependencies:
                if dep.pod_id in visited:
                    resources_lost.append(dep.resource)

        affected.append({
            "pod_id": pod_id,
            "depth": depth,
            "resources_lost": resources_lost,
        })

        for next_id in depended_by.get(pod_id, []):
            if next_id not in visited:
                visited.add(next_id)
                queue.append((next_id, depth + 1))

    return {
        "failed_pod": failed_pod,
        "total_affected": len(affected),
        "affected_pods": affected,
    }


def generate_analysis_summary(pods: dict[str, PodData]) -> dict[str, Any]:
    graph = build_dependency_graph(pods)
    depended_by = graph["depended_by"]
    depends_on = graph["depends_on"]

    rankings = compute_in_degree(depended_by)
    spofs = find_single_points_of_failure(pods, depended_by)
    mismatches = check_supply_dependency_consistency(pods)
    timeline = analyze_infrastructure_changes(pods)

    top_pods = [pid for pid, count in rankings[:3] if count > 0]
    cascade_scenarios = {}
    for pod_id in top_pods:
        cascade_scenarios[pod_id] = compute_cascade_impact(
            pod_id, depended_by, depends_on, pods
        )

    pods_with_comms = sum(1 for p in pods.values() if p.comms is not None)
    total_log_entries = sum(len(p.logs) for p in pods.values())
    total_population = sum(p.population for p in pods.values())

    return {
        "dependency_graph": graph,
        "dependency_rankings": rankings,
        "single_points_of_failure": spofs,
        "supply_dependency_mismatches": mismatches,
        "infrastructure_timeline": timeline,
        "cascade_scenarios": cascade_scenarios,
        "key_metrics": {
            "total_pods": len(pods),
            "total_population": total_population,
            "total_log_entries": total_log_entries,
            "pods_with_comms": pods_with_comms,
            "total_dependencies": sum(len(p.dependencies) for p in pods.values()),
            "total_supplies": sum(len(p.supplies) for p in pods.values()),
        },
    }
