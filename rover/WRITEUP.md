# Design Writeup

## Architecture & Design Decisions

The agent is two Python modules invoked by shell entrypoints inside the rover Docker container: a mapper that discovers and crawls the colony, and a reporter that analyzes the crawled data and produces a written assessment.

### Mapping (`agent/mapper.py`)

The mapper discovers pods through two mechanisms that run in sequence.

First, BFS traversal. The gateway response includes an entrypoint pod name and URL (Artemis on port 3002). The agent parses that URL to get the seed port, then crawls Artemis's `/dependencies` and `/supplies` endpoints to find references to other pod_ids. For each newly-seen pod_id, the agent resolves its port by probing the pod's Docker hostname across port range 3001-3099 with parallel async requests to `/info`. This repeats until no new pods are found. The agent never has hardcoded knowledge of which pod lives on which port.

Second, a port scan on the gateway host across the same range. This catches isolated pods that no other pod references in its dependency or supply data. Sentinel is the canonical example: zero declared dependencies, and no other pod lists it as a supplier. BFS alone can't find it. The port scan can.

All 6 endpoints per pod are fetched concurrently with `asyncio.gather`, and all pods are crawled in parallel. The output (`map.json`) preserves raw API responses with Pydantic validation, keyed by pod ID for O(1) lookup.

### Reporting (`agent/reporter.py`)

The reporting pipeline has two stages. First, `graph_analysis.py` pre-computes structured analytics from the crawled data: dependency rankings, single points of failure, supply/dependency consistency checks, cascade failure BFS, infrastructure change timelines, a Mermaid dependency diagram, and a quantitative resilience index. All of this is plain Python with no external graph libraries (unnecessary for 12 nodes).

Then the pre-computed analytics and raw colony data (including all logs and comms) are sent to Claude Sonnet in a single prompt. The LLM generates the narrative report. The Mermaid diagram is appended deterministically afterward.

The reason for pre-computing before calling the LLM: LLMs miscount graph edges. By computing SPOFs, cascade impacts, and resilience scores in deterministic code, the report's quantitative claims are guaranteed correct. The Mermaid diagram is also generated in code; asking an LLM to produce a 22-edge graph would risk dropped or hallucinated connections. The LLM's job is narrative synthesis, cross-referencing logs with structural findings, and writing actionable recommendations. Those are tasks it's good at.

### Visual Dependency Graph

The Mermaid diagram groups pods into functional subgraphs (power, water, atmosphere, production, science, command, support) with edges styled by criticality: thick red for high, orange for medium, dashed grey for low. This makes the colony's hub-and-spoke topology visible at a glance.

### Colony Resilience Index

A composite 0-100 score from five weighted subscores: redundancy (30%), buffer adequacy (20%), cascade containment (25%), concentration (15%), and independence (10%), minus 15 points per mutual dependency loop. The colony scored 0/100 (Grade F). Cascade containment and concentration both zeroed out, and three mutual dependency loops (helios/aquifer, helios/terminus, aquifer/terminus) applied a cumulative 45-point penalty.

The scaling factors are calibrated to life-support severity thresholds: redundancy zeroes at roughly 25% SPOF density, cascade containment zeroes when more than 83% of pods are affected, and concentration zeroes when any single pod serves more than 67% of the colony. These thresholds are documented inline in the code.

## Discovery Trade-offs

The port scan range (3001-3099) is an assumption about the colony's port allocation convention. A pod on port 4000 would be missed. A broader scan would be more robust but slower; for this Docker Compose environment where services are explicitly mapped to this range, the trade-off is reasonable. In a production system, this would be replaced with DNS service discovery or a service registry API.

## LLM Integration

The LLM call is single-shot rather than multi-turn. The pre-computed analytics ensure quantitative correctness regardless of what the LLM does, so there's no need for a verification loop. A multi-turn approach would let the LLM drill into specific pods, but it would add complexity and latency for marginal benefit at this colony size. The LLM client includes retry logic with exponential backoff for transient failures (rate limits, timeouts, 5xx errors) and validates that the response exceeds a minimum length to catch degenerate outputs.

## SPOF Analysis: Approach and Limitations

The current SPOF finder checks, for each (supplier, consumer, resource) triple, whether the consumer has an alternative supplier for that same resource. If not, the supplier is flagged as a SPOF for that consumer and resource. This is a resource-aware sole-source analysis, not a graph connectivity property.

Specifically, this is not k-connectivity analysis. In graph theory, a graph is k-vertex-connected if it remains connected after removing any (k-1) vertices. By Menger's theorem, this equals the minimum number of vertex-disjoint paths between any pair of nodes. Tarjan's algorithm finds articulation points (the k=1 case) in O(V+E) using DFS with low-link values, and the general k-connectivity problem reduces to max-flow/min-cut.

The current approach answers a different question: "does this consumer have exactly one source for this resource?" That's strictly a 1-hop check on the consumer's declared dependency list. It catches direct sole-source relationships but not transitive ones. If pod A depends on B for power and B depends on C for power, and C is the only power generator in the colony, then C is a transitive SPOF for A. The current code won't flag that because it only examines A's direct dependencies and sees B.

For Selene's 12-pod colony, this gap is partially covered by the cascade analysis, which does trace transitive impact via BFS from each failed pod. But the SPOF list itself remains first-hop only. A more complete approach would layer Tarjan's bridge/articulation-point detection for structural chokepoints, then overlay resource-specific analysis on top. That would distinguish between "this pod is a sole source of one resource to one consumer" and "removing this pod structurally fragments the colony graph."

## Time Complexity and Scaling

The table below lists the time complexity of each major operation. V is the number of pods, E is the number of dependency edges, D is the maximum number of dependencies per pod, L is the total number of log entries across all pods, and P is the port scan range size.

| Operation | Complexity | Notes |
|---|---|---|
| `build_dependency_graph` | O(V + E) | Single pass through pods and their edges |
| `compute_in_degree` | O(V log V) | Counting is O(V), sorting dominates |
| `find_single_points_of_failure` | O(E × D) | For each edge, scans consumer's dep list for alternatives. Worst case O(V³) if the graph is complete |
| `check_supply_dependency_consistency` | O(E) | Set lookups for each edge in both directions |
| `compute_cascade_impact` (per pod) | O(V + E) | Standard BFS |
| `analyze_infrastructure_changes` | O(L + C log C) | Filters L log entries, sorts C infrastructure changes |
| `generate_mermaid_diagram` | O(V + E) | One pass for subgraphs, one for edges |
| `compute_resilience_score` | O(V × D²) | Mutual dependency detection checks all dep pairs per pod |
| Pod discovery (BFS + scan) | O(V × P) | Each new pod requires probing up to P ports |
| Pod crawling | O(V × 6) network calls | Parallelized via `asyncio.gather` at both levels |

For Selene's 12 pods, 22 edges, and ~94 log entries, all of this completes in well under a second. The interesting question is what happens at larger scales.

**~100 pods.** Everything still works. Port scanning produces roughly 100 × 99 = 10K probes, which async handles comfortably. SPOF detection remains fast because infrastructure graphs at this scale are typically sparse (D stays small even as V grows). The main pressure point is the LLM prompt: 100 pods worth of logs and comms may push past context limits. You'd need to summarize or chunk the input.

**~1,000 pods.** Port scanning at O(V × P) starts to drag, especially if the port range needs to be wider. Service discovery (DNS-SD, Consul, Kubernetes service API) would replace it. The SPOF finder's O(E × D) remains manageable for sparse graphs but grows toward O(V²) if average dependency counts increase linearly with colony size. The cascade BFS is still fine per-pod, but running it for all V pods would be O(V × (V + E)), which at V=1000 and E=5000 starts taking noticeable time. You'd want to preselect which pods to simulate failure for (the current code already does this, running cascades only for the top 3 by in-degree). The LLM integration needs a fundamentally different approach: either RAG with selective retrieval, or hierarchical summarization where sub-clusters are analyzed independently and results are aggregated.

**~10,000+ pods.** The brute-force SPOF finder becomes a bottleneck. With E potentially O(V²) in a dense graph, O(E × D) approaches O(V³). Tarjan's algorithm for articulation points and bridges would provide the structural SPOF analysis in O(V + E), with resource-specific checks layered on top using indexed lookups (resource type to supplier list) instead of linear scans. Cascade analysis for all pods is infeasible; you'd sample or compute reachability via matrix methods. The Mermaid diagram becomes unrenderable at this scale; visualization would need to shift to aggregated cluster views or interactive graph exploration (e.g., D3/Sigma.js with level-of-detail rendering). The crawling itself is I/O-bound but manageable with connection pooling and rate limiting; the analysis pipeline is the real constraint.

The system's architecture separates crawling from analysis cleanly, which means the analysis layer could be swapped for more scalable algorithms without touching the data collection. The Pydantic models and `map.json` intermediate format would remain the same.

## Testing

The test suite (`tests/`) has 34 tests across three modules.

`test_graph_analysis.py` covers dependency graph construction, in-degree ranking, SPOF detection (including a negative case verifying that redundant sources are not flagged), supply/dependency consistency checking, cascade impact computation across several graph topologies (star, chain, triangle with mutual dependencies), resilience scoring behavior (independent colonies score high, hub-and-spoke scores low, mutual dependency penalties apply correctly, scores clamp at zero), Mermaid diagram generation, and infrastructure timeline filtering.

`test_models.py` covers Pydantic serialization round-trips, the `from` field alias on CommMessage, and the semantic distinction between `comms=None` (endpoint returned 404) and `comms=[]` (endpoint exists but empty).

`test_mapper.py` covers the pod ID extraction utility and verifies the port scan range includes expected ports.

The tests use three fixture topologies (triangle with mutual loop, hub-and-spoke star, fully independent) to exercise different graph shapes. The LLM call and network I/O are not tested; those are integration boundaries that would need either live services or mock HTTP servers.

## How the Solution Evolved

The current implementation went through several iterations. Documenting what changed and why matters as much as the final design.

**V1: Hardcoded registry with BFS validation.** The initial mapper had a `POD_REGISTRY` dict mapping all 12 pod names to their ports. BFS traversal from the gateway "discovered" pods by following dependency/supply references, but gated every discovery through this registry. A pod_id not in the dict was silently ignored, and a fallback loop added any registry entries that BFS missed. This worked fine (all 12 pods crawled correctly), but the discovery was cosmetic. The agent couldn't find a 13th pod if one appeared. The writeup at the time called this a "hybrid approach," which was technically accurate but obscured the limitation.

**V2: True autonomous discovery.** The registry was removed entirely. The agent seeds from the gateway response, resolves each newly-referenced pod_id by probing its Docker hostname across the port range, and runs a port scan to catch isolated pods. The trade-off is the port range assumption (3001-3099), discussed in the Discovery section above.

**Concurrency fix.** The original `crawl_pod` built a dict of coroutines for the 6 endpoints but awaited them one at a time in a for loop. Cross-pod parallelism with `asyncio.gather` was correct, but within each pod the requests were serial. This was replaced with `asyncio.gather` over all endpoint coroutines within each pod, so both levels run concurrently.

**LLM client hardened.** The original was 16 lines with a bare `messages.create` call. No retries, no timeout, no validation. It was replaced with exponential backoff for transient errors and a minimum response length check.

**Resilience scoring documented.** The scaling factors (400 for redundancy, 120 for cascade, 150 for concentration) were originally unexplained magic numbers. They now have inline comments explaining what colony state zeroes each score and why those thresholds make sense for life-support infrastructure.

**Tests added.** The initial submission had none. The 34-test suite was added to cover the deterministic analysis pipeline, using synthetic topologies rather than real colony data, so the tests verify that the algorithms generalize.

## Key Findings

The colony has systematically removed redundancy over its 2.5-year history through individually reasonable directives that collectively created dangerous concentration risk.

**Aquifer and Helios are mutually dependent SPOFs.** Aquifer supplies coolant to Helios; Helios supplies power to Aquifer. Either one failing cascades to the other within hours, then propagates to 10 of 12 pods.

**All water backup was decommissioned.** Vault's secondary water system (Directive 2093-089) and Helios's backup coolant loop (Directive 2094-011) were removed for budget and efficiency reasons. Aquifer now runs at 91.6% capacity with `backup_systems: 0`.

**Stale dependency data.** Prometheus's water supply was rerouted through Hydroponics (project 2093-P4, Sept 2093), but its dependency record still says it connects directly to Aquifer. A Hydroponics failure would cut pharmaceutical synthesis, but this risk is invisible to any analysis that trusts the declared dependency graph.

**Medica has dangerously thin buffers.** 6 hours of oxygen reserve and 12 days of pharmacy stock, with no supplies to other pods. It's a pure terminal consumer.

**Sentinel is uniquely resilient.** Zero dependencies, independent solar (180 kW), and ice-harvested water (120 L/day). It would survive any internal colony failure.

## What I'd Do With More Time

- **Multi-turn LLM analysis.** Let the LLM ask follow-up questions about specific pods or request additional data slices rather than doing everything in one shot.
- **Transitive SPOF detection.** Layer Tarjan's articulation-point algorithm under the resource-specific analysis to catch structural chokepoints that the current first-hop check misses.
- **Diff-based re-crawl.** Only re-fetch pods whose data changed since last crawl, enabling incremental monitoring.
- **Monte Carlo failure simulation.** Model probabilistic failure scenarios with weighted likelihoods to prioritize remediation investments.
- **Integration tests with mock servers.** Stand up lightweight HTTP servers mimicking the pod API to test the crawler end-to-end without Docker.
