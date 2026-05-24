from __future__ import annotations

import json
import sys

from agent.graph_analysis import generate_analysis_summary
from agent.llm_client import generate_report
from agent.models import ColonyMap

MAP_PATH = "/rover/output/map.json"
REPORT_PATH = "/rover/output/report.md"


def build_system_prompt() -> str:
    return (
        "You are a senior infrastructure analyst reviewing the Selene Lunar Colony's "
        "systems for operational resilience ahead of a Phase 3 expansion. You must "
        "produce a thorough Markdown report analyzing systemic risks, single points of "
        "failure, and infrastructure evolution. Base every claim on specific data from "
        "the colony — cite pod names, directive numbers, timestamps, and metrics. "
        "Be direct and analytical, not speculative."
    )


def format_pod_summary(colony_map: ColonyMap) -> str:
    lines: list[str] = []
    for pid, pod in sorted(colony_map.pods.items()):
        lines.append(f"### {pod.name} (`{pid}`, port {pod.port})")
        lines.append(f"- **Role**: {pod.role}")
        lines.append(f"- **Population**: {pod.population}")
        lines.append(f"- **Status**: {pod.status.status}")
        lines.append(f"- **Uptime**: {pod.uptime_days} days")
        lines.append(f"- **Discovery**: {pod.discovered_via}")
        if pod.metadata:
            meta_str = ", ".join(f"{k}: {v}" for k, v in pod.metadata.items())
            lines.append(f"- **Specs**: {meta_str}")
        if pod.dependencies:
            deps = "; ".join(
                f"{d.pod_id} ({d.resource}, {d.criticality})" for d in pod.dependencies
            )
            lines.append(f"- **Depends on**: {deps}")
        else:
            lines.append("- **Depends on**: (none)")
        if pod.supplies:
            sups = "; ".join(f"{s.pod_id} ({s.resource})" for s in pod.supplies)
            lines.append(f"- **Supplies to**: {sups}")
        else:
            lines.append("- **Supplies to**: (none)")
        lines.append("")
    return "\n".join(lines)


def format_logs(colony_map: ColonyMap) -> str:
    all_logs: list[tuple[str, str, str, str]] = []
    for pid, pod in colony_map.pods.items():
        for log in pod.logs:
            all_logs.append((log.timestamp, pid, log.event, log.detail))
    all_logs.sort(key=lambda x: x[0])
    lines = [f"- **[{ts}]** `{pid}` ({event}): {detail}" for ts, pid, event, detail in all_logs]
    return "\n".join(lines)


def format_comms(colony_map: ColonyMap) -> str:
    all_comms: list[tuple[str, str, str, str, str]] = []
    for pid, pod in colony_map.pods.items():
        if pod.comms is None:
            continue
        for msg in pod.comms:
            all_comms.append((msg.timestamp, pid, msg.from_field, msg.to, msg.content))
    all_comms.sort(key=lambda x: x[0])
    if not all_comms:
        return "(no communications data)"
    lines = [
        f"- **[{ts}]** ({pod}) {frm} → {to}: {content}"
        for ts, pod, frm, to, content in all_comms
    ]
    return "\n".join(lines)


def format_analysis(analysis: dict) -> str:
    lines: list[str] = []

    lines.append("### Dependency Rankings (pods ranked by number of dependents)")
    for pod_id, count in analysis["dependency_rankings"]:
        lines.append(f"- **{pod_id}**: {count} pods depend on it")
    lines.append("")

    lines.append("### Single Points of Failure")
    if analysis["single_points_of_failure"]:
        for spof in analysis["single_points_of_failure"]:
            lines.append(
                f"- **{spof['supplier']}** is sole source of `{spof['resource']}` "
                f"for **{spof['consumer']}** (criticality: {spof['criticality']})"
            )
    else:
        lines.append("- None identified")
    lines.append("")

    lines.append("### Supply/Dependency Mismatches")
    if analysis["supply_dependency_mismatches"]:
        for m in analysis["supply_dependency_mismatches"]:
            if m["type"] == "dependency_not_matched_by_supply":
                lines.append(
                    f"- **{m['consumer']}** depends on **{m['supplier']}** for "
                    f"`{m['resource']}`, but {m['supplier']} does NOT list {m['consumer']} "
                    f"in its supplies"
                )
            elif m["type"] == "supply_not_matched_by_dependency":
                lines.append(
                    f"- **{m['supplier']}** claims to supply `{m['resource']}` to "
                    f"**{m['consumer']}**, but {m['consumer']} does NOT list it as a dependency"
                )
    else:
        lines.append("- All supply/dependency relationships are consistent")
    lines.append("")

    lines.append("### Infrastructure Change Timeline")
    for change in analysis["infrastructure_timeline"]:
        lines.append(
            f"- **[{change['timestamp']}]** `{change['pod_id']}` ({change['event']}): "
            f"{change['detail']}"
        )
    lines.append("")

    lines.append("### Cascade Failure Scenarios")
    for pod_id, scenario in analysis["cascade_scenarios"].items():
        lines.append(
            f"\n#### If `{pod_id}` fails ({scenario['total_affected']} pods affected):"
        )
        for affected in scenario["affected_pods"]:
            resources = ", ".join(affected["resources_lost"]) if affected["resources_lost"] else "transitive"
            lines.append(
                f"- Depth {affected['depth']}: **{affected['pod_id']}** loses: {resources}"
            )
    lines.append("")

    lines.append("### Key Metrics")
    for key, val in analysis["key_metrics"].items():
        lines.append(f"- {key.replace('_', ' ').title()}: {val}")

    if "resilience_score" in analysis:
        rs = analysis["resilience_score"]
        lines.append("")
        lines.append(f"### Colony Resilience Index: {rs['composite_score']}/100 (Grade: {rs['grade']})")
        lines.append("Subscores:")
        for key, val in rs["subscores"].items():
            weight = rs["weights"].get(key, 0)
            lines.append(f"- {key.replace('_', ' ').title()}: {val}/100 (weight: {weight:.0%})")
        if rs["mutual_dependency_loops"]:
            lines.append(f"- Mutual dependency penalty: -{rs['mutual_dependency_penalty']} pts "
                         f"({len(rs['mutual_dependency_loops'])} loop(s))")
        spof_b = rs["spof_breakdown"]
        lines.append(f"- SPOF breakdown: {spof_b['high']} high, {spof_b['medium']} medium, {spof_b['low']} low")

    return "\n".join(lines)


def build_user_prompt(colony_map: ColonyMap, analysis: dict) -> str:
    sections = [
        "# Colony Data for Analysis\n",
        "## Gateway",
        f"- Colony: {colony_map.gateway.colony}",
        f"- Established: {colony_map.gateway.established}",
        f"- Population: {colony_map.gateway.population}",
        f"- Status: {colony_map.gateway.status}",
        f"- Entrypoint: {colony_map.gateway.entrypoint_pod}\n",
        "## Pod Summaries\n",
        format_pod_summary(colony_map),
        "## Pre-computed Analytics\n",
        format_analysis(analysis),
        "## Full Operational Logs (chronological)\n",
        format_logs(colony_map),
        "\n## Inter-Pod Communications (chronological)\n",
        format_comms(colony_map),
        "\n---\n",
        "## Your Task\n",
        "Produce a detailed Markdown infrastructure assessment report with these sections:\n",
        "1. **Executive Summary** — 3-4 sentence overview of colony health and key risks. Include the Colony Resilience Index score and grade from the analytics.",
        "2. **Colony Infrastructure Map** — describe the dependency graph, grouping pods by function. Note: a Mermaid dependency diagram will be appended to the report automatically — do NOT generate one yourself.",
        "3. **Critical Dependencies** — which pods are most depended upon, quantified, with impact analysis",
        "4. **Single Points of Failure Analysis** — deep dive into each SPOF with specific data",
        "5. **Supply Chain Consistency Review** — flag any mismatches between declared dependencies and actual supplies, cross-reference with logs/comms for explanation",
        "6. **Infrastructure Evolution** — what story do the logs, directives, and comms tell about how the colony changed over time? Focus on the pattern of redundancy removal",
        "7. **Cascade Failure Scenarios** — what happens step-by-step if the top 2-3 most critical pods go down?",
        "8. **Colony Resilience Index** — interpret the composite score and subscores. Explain what each subscore measures and why the colony scored as it did. Highlight the mutual dependency penalty.",
        "9. **Recommendations for Phase 3 Expansion** — specific, actionable recommendations based on findings",
        "10. **Appendix: Dependency Matrix** — table showing all pod-to-pod dependencies\n",
        "Use the pre-computed analytics as your quantitative foundation, but add narrative depth ",
        "from the raw logs and comms data. Cite specific directives, timestamps, and metrics. ",
        "The report should be 2000-4000 words.",
    ]
    return "\n".join(sections)


def main() -> None:
    print("Loading map.json...", file=sys.stderr)
    with open(MAP_PATH) as f:
        raw = json.load(f)
    colony_map = ColonyMap.model_validate(raw)
    print(f"  Loaded {len(colony_map.pods)} pods", file=sys.stderr)

    print("Running graph analysis...", file=sys.stderr)
    analysis = generate_analysis_summary(colony_map.pods)
    print(
        f"  {len(analysis['single_points_of_failure'])} SPOFs, "
        f"{len(analysis['supply_dependency_mismatches'])} mismatches, "
        f"{len(analysis['infrastructure_timeline'])} infrastructure events",
        file=sys.stderr,
    )

    print("Building prompts...", file=sys.stderr)
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(colony_map, analysis)
    print(f"  Prompt length: ~{len(user_prompt)} chars", file=sys.stderr)

    print("Calling LLM for report generation...", file=sys.stderr)
    report_md = generate_report(system_prompt, user_prompt)

    mermaid_section = (
        "\n\n---\n\n"
        "## Appendix: Visual Dependency Graph\n\n"
        "The following Mermaid diagram shows all inter-pod dependency relationships. "
        "Edge thickness and color indicate criticality: "
        "**red/thick = high**, **orange/medium = medium**, **grey/dashed = low**.\n\n"
        "```mermaid\n"
        f"{analysis['mermaid_diagram']}\n"
        "```\n"
    )

    with open(REPORT_PATH, "w") as f:
        f.write(report_md)
        f.write(mermaid_section)

    total_len = len(report_md) + len(mermaid_section)
    print(f"Report written to {REPORT_PATH} ({total_len} chars)", file=sys.stderr)


if __name__ == "__main__":
    main()
