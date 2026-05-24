# Design Writeup

## Architecture & Design Decisions

The agent is structured as two Python modules invoked by shell entrypoints, running inside the provided rover Docker container.

**Mapping phase** (`agent/mapper.py`): An async HTTP crawler using `httpx` that discovers and ingests all colony data. Discovery uses a hybrid approach — BFS traversal starting from the gateway's entrypoint (Artemis), following dependency and supply references to discover pods dynamically, then cross-checking against a known registry to catch isolated pods (e.g., Sentinel, which has zero dependencies and wouldn't appear in any other pod's dependency chain). In practice, all 12 pods were discovered dynamically in 0.25 seconds via `asyncio.gather` parallelism. The output schema (`map.json`) preserves raw API responses faithfully with Pydantic validation, keyed by pod ID for O(1) lookup during analysis.

**Reporting phase** (`agent/reporter.py`): A two-stage pipeline. First, `graph_analysis.py` pre-computes structured analytics — dependency rankings, single points of failure, supply/dependency consistency checks, cascade failure BFS, and infrastructure change timelines — using plain Python (no networkx needed for 12 nodes). Then the pre-computed analytics and raw colony data are sent to Claude Sonnet in a single prompt. Providing both ensures the LLM has correct quantitative claims to anchor its narrative while having full access to logs and comms for contextual depth.

**Why pre-compute before LLM**: LLMs can miscount graph edges. By computing SPOF relationships and cascade impacts deterministically, the report's quantitative claims are guaranteed correct. The LLM adds narrative synthesis, cross-referencing, and actionable recommendations — tasks it excels at.

## Key Findings

The colony has systematically removed redundancy over its 2.5-year history through a series of individually rational directives that collectively created dangerous concentration risk:

- **Aquifer and Helios are mutually dependent SPOFs** — Aquifer supplies coolant to Helios, Helios supplies power to Aquifer. Either's failure cascades to the other within hours, then propagates to 10 of 12 pods.
- **All water backup was decommissioned** — Vault's secondary water system (Directive 2093-089) and Helios's backup coolant loop (Directive 2094-011) were removed for budget reallocation and efficiency savings. Aquifer now operates at 91.6% capacity with `backup_systems: 0`.
- **Stale dependency data** — Prometheus's water supply was rerouted through Hydroponics (project 2093-P4, Sept 2093), but its dependency record still declares a direct Aquifer connection. This hidden transitive dependency means a Hydroponics failure cuts pharmaceutical synthesis — a risk invisible to any SPOF analysis using declared dependencies alone.
- **Medica has dangerously thin buffers** — 6 hours of oxygen reserve and 12 days of pharmacy stock, with no supplies to other pods (pure terminal consumer).
- **Sentinel is uniquely resilient** — zero dependencies, independent solar (180 kW), and ice-harvested water (120 L/day). It would survive any internal colony failure.

## What I'd Do With More Time

- **Visual dependency graph** — Generate a Mermaid or D3.js diagram embedded in the report showing the dependency web with criticality-weighted edges
- **Quantitative resilience scoring** — Weight SPOFs by criticality level, buffer duration, and cascade depth to produce a single colony resilience index
- **Multi-turn LLM analysis** — Let the LLM ask follow-up questions about specific pods or request additional data slices for deeper investigation
- **Diff-based re-crawl** — Only re-fetch pods whose data changed since last crawl, enabling incremental monitoring
- **Monte Carlo failure simulation** — Model probabilistic failure scenarios with weighted likelihoods to prioritize remediation investments
