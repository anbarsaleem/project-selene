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


POD_DISPLAY_NAMES: dict[str, str] = {
    "helios": "Helios",
    "artemis": "Artemis",
    "hydroponics": "Hydroponics",
    "aquifer": "Aquifer",
    "zephyr": "Zephyr",
    "prometheus": "Prometheus",
    "medica": "Medica",
    "terminus": "Terminus",
    "nexus": "Nexus",
    "forge": "Forge",
    "vault": "Vault",
    "sentinel": "Sentinel",
}

CRITICALITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def generate_mermaid_diagram(pods: dict[str, PodData]) -> str:
    lines: list[str] = ["graph LR"]

    styles = {
        "power": ("helios",),
        "water": ("aquifer",),
        "atmosphere": ("zephyr",),
        "production": ("hydroponics", "terminus", "forge"),
        "science": ("prometheus", "medica"),
        "command": ("artemis",),
        "support": ("nexus", "vault", "sentinel"),
    }
    style_colors = {
        "power": "#FFD700",
        "water": "#4FC3F7",
        "atmosphere": "#81C784",
        "production": "#FFB74D",
        "science": "#CE93D8",
        "command": "#EF5350",
        "support": "#90A4AE",
    }

    for group, members in styles.items():
        color = style_colors[group]
        lines.append(f"    subgraph {group}[{group.upper()}]")
        for pid in members:
            if pid in pods:
                display = POD_DISPLAY_NAMES.get(pid, pid)
                lines.append(f"        {pid}[{display}]")
        lines.append("    end")
        lines.append(f"    style {group} fill:{color}22,stroke:{color}")

    edge_styles: list[str] = []
    edge_idx = 0
    for pid, pod in sorted(pods.items()):
        for dep in pod.dependencies:
            if dep.pod_id not in pods:
                continue
            crit = dep.criticality
            resource_short = dep.resource.replace("_", " ")
            if crit == "high":
                lines.append(f"    {dep.pod_id} ==>|{resource_short}| {pid}")
                edge_styles.append(f"    linkStyle {edge_idx} stroke:#E53935,stroke-width:3px")
            elif crit == "medium":
                lines.append(f"    {dep.pod_id} -->|{resource_short}| {pid}")
                edge_styles.append(f"    linkStyle {edge_idx} stroke:#FB8C00,stroke-width:2px")
            else:
                lines.append(f"    {dep.pod_id} -.->|{resource_short}| {pid}")
                edge_styles.append(f"    linkStyle {edge_idx} stroke:#78909C,stroke-width:1px")
            edge_idx += 1

    lines.extend(edge_styles)
    return "\n".join(lines)


def compute_resilience_score(
    pods: dict[str, PodData],
    spofs: list[dict[str, Any]],
    cascade_scenarios: dict[str, dict[str, Any]],
    depended_by: dict[str, list[str]],
) -> dict[str, Any]:
    total_pods = len(pods)

    # --- Redundancy score (0-100): penalize SPOFs weighted by criticality ---
    # Scaling factor 400: chosen so that a colony where ~25% of possible dependency
    # pairs are unredundant SPOFs scores zero. This reflects that even moderate SPOF
    # density is dangerous in a life-support context.
    high_spofs = sum(1 for s in spofs if s["criticality"] == "high")
    med_spofs = sum(1 for s in spofs if s["criticality"] == "medium")
    low_spofs = sum(1 for s in spofs if s["criticality"] == "low")
    weighted_spof_count = high_spofs * 3 + med_spofs * 2 + low_spofs * 1
    max_possible_spof_weight = total_pods * (total_pods - 1) * 3
    redundancy_score = max(0, 100 - (weighted_spof_count / max_possible_spof_weight) * 400)

    # --- Buffer score (0-100): assess emergency reserves across critical pods ---
    buffer_penalties = 0.0
    buffer_checks = 0
    for pid, pod in pods.items():
        meta = pod.metadata
        if "oxygen_reserve_hours" in meta:
            hours = meta["oxygen_reserve_hours"]
            buffer_checks += 1
            if hours < 24:
                buffer_penalties += (24 - hours) / 24
        if "pharmacy_stock_days" in meta:
            days = meta["pharmacy_stock_days"]
            buffer_checks += 1
            if days < 30:
                buffer_penalties += (30 - days) / 30
        if "backup_systems" in meta:
            buffer_checks += 1
            if meta["backup_systems"] == 0:
                buffer_penalties += 1.0
        if "battery_reserve_pct" in meta:
            pct = meta["battery_reserve_pct"]
            buffer_checks += 1
            if pct < 50:
                buffer_penalties += (50 - pct) / 50
        if "emergency_ration_days" in meta:
            days = meta["emergency_ration_days"]
            buffer_checks += 1
            if days < 30:
                buffer_penalties += (30 - days) / 30
        if "decommissioned_reserves" in meta:
            decomm = meta["decommissioned_reserves"]
            if isinstance(decomm, list) and decomm:
                buffer_checks += 1
                buffer_penalties += min(1.0, len(decomm) * 0.5)
    buffer_score = max(0, 100 - (buffer_penalties / max(buffer_checks, 1)) * 100) if buffer_checks else 50

    # --- Cascade score (0-100): how contained are failures? ---
    # Scaling factor 120: a cascade affecting >83% of pods (120/100*83=~100) scores
    # zero. Slightly above 100 to ensure near-total cascades are penalized harshly
    # even if one or two pods survive.
    if cascade_scenarios:
        worst_cascade = max(s["total_affected"] for s in cascade_scenarios.values())
        cascade_ratio = worst_cascade / total_pods
        cascade_score = max(0, 100 - cascade_ratio * 120)
    else:
        cascade_score = 100.0

    # --- Concentration score (0-100): how evenly distributed are dependents? ---
    # Scaling factor 150: a pod serving >67% of the colony as dependents (150/100*67=~100)
    # zeroes the score. This penalizes hub-and-spoke topologies where one pod serves most others.
    dep_counts = [len(deps) for deps in depended_by.values()]
    max_deps = max(dep_counts) if dep_counts else 0
    mean_deps = sum(dep_counts) / len(dep_counts) if dep_counts else 0
    concentration_ratio = max_deps / total_pods if total_pods else 0
    concentration_score = max(0, 100 - concentration_ratio * 150)

    # --- Independence score (0-100): fraction of pods with zero dependencies ---
    independent_pods = sum(1 for p in pods.values() if not p.dependencies)
    independence_score = (independent_pods / total_pods) * 100 if total_pods else 0

    # --- Mutual dependency penalty ---
    mutual_deps = []
    for pid, pod in pods.items():
        for dep in pod.dependencies:
            partner = pods.get(dep.pod_id)
            if partner:
                for partner_dep in partner.dependencies:
                    if partner_dep.pod_id == pid:
                        pair = tuple(sorted([pid, dep.pod_id]))
                        if pair not in [(m["pods"][0], m["pods"][1]) for m in mutual_deps]:
                            mutual_deps.append({
                                "pods": list(pair),
                                "resources": [dep.resource, partner_dep.resource],
                            })
    mutual_penalty = len(mutual_deps) * 15

    weights = {
        "redundancy": 0.30,
        "buffer_adequacy": 0.20,
        "cascade_containment": 0.25,
        "concentration": 0.15,
        "independence": 0.10,
    }
    subscores = {
        "redundancy": round(redundancy_score, 1),
        "buffer_adequacy": round(buffer_score, 1),
        "cascade_containment": round(cascade_score, 1),
        "concentration": round(concentration_score, 1),
        "independence": round(independence_score, 1),
    }

    composite = sum(subscores[k] * weights[k] for k in weights)
    composite = max(0, round(composite - mutual_penalty, 1))

    grade = (
        "A" if composite >= 80 else
        "B" if composite >= 65 else
        "C" if composite >= 50 else
        "D" if composite >= 35 else
        "F"
    )

    return {
        "composite_score": composite,
        "grade": grade,
        "subscores": subscores,
        "weights": weights,
        "mutual_dependency_loops": mutual_deps,
        "mutual_dependency_penalty": mutual_penalty,
        "spof_breakdown": {"high": high_spofs, "medium": med_spofs, "low": low_spofs},
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

    mermaid_diagram = generate_mermaid_diagram(pods)
    resilience = compute_resilience_score(pods, spofs, cascade_scenarios, depended_by)

    return {
        "dependency_graph": graph,
        "dependency_rankings": rankings,
        "single_points_of_failure": spofs,
        "supply_dependency_mismatches": mismatches,
        "infrastructure_timeline": timeline,
        "cascade_scenarios": cascade_scenarios,
        "mermaid_diagram": mermaid_diagram,
        "resilience_score": resilience,
        "key_metrics": {
            "total_pods": len(pods),
            "total_population": total_population,
            "total_log_entries": total_log_entries,
            "pods_with_comms": pods_with_comms,
            "total_dependencies": sum(len(p.dependencies) for p in pods.values()),
            "total_supplies": sum(len(p.supplies) for p in pods.values()),
        },
    }
