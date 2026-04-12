# Project Selene — Lunar Colony Network Discovery Challenge

## Overview

This repo contains a dockerized simulation of **Project Selene**, a lunar colony composed of ~12 interconnected habitat pods. Each pod is a small service running in its own container, exposing a lightweight REST API. Together they form a living colony where pods depend on each other for resources like power, water, oxygen, food, data, and medical supplies.

The colony looks healthy. Every pod reports nominal status. But hidden in the dependency graph is a catastrophic fragility — a cascading single point of failure that, if triggered, would collapse the majority of the colony. No individual pod reveals this. It only becomes visible when you build a comprehensive graph of the entire ecosystem and reason about transitive dependencies.

This project is a **take-home exercise for engineering candidates**. The candidate receives the running colony and an open-ended prompt. They build an agent that explores, maps, and analyzes the network — and hopefully discovers what's about to go wrong.

---

## Architecture

### The Colony

The colony consists of the following pods, each running as a separate Docker container on an internal network:

| Pod | Service Name | Role | Port |
|-----|-------------|------|------|
| Helios Station | `helios` | Primary power generation (solar array) | 3001 |
| Artemis Core | `artemis` | Colony command & administration | 3002 |
| Hydroponics Bay | `hydroponics` | Food production | 3003 |
| Aquifer Module | `aquifer` | Primary water recycling & distribution | 3004 |
| Zephyr Hub | `zephyr` | Atmospheric processing & oxygen generation | 3005 |
| Prometheus Lab | `prometheus` | Research & pharmaceutical synthesis | 3006 |
| Medica Ward | `medica` | Medical services | 3007 |
| Terminus Mine | `terminus` | Regolith mining & raw material extraction | 3008 |
| Nexus Relay | `nexus` | Communications relay & data routing | 3009 |
| Forge Works | `forge` | Manufacturing & fabrication | 3010 |
| Vault Reserve | `vault` | Emergency reserves & backup systems | 3011 |
| Sentinel Array | `sentinel` | External monitoring & defense systems | 3012 |

### Internal Network

All pods communicate over a shared Docker network (`selene-net`). Pods reference each other by service name. An **entrypoint gateway** is exposed to the host on port `3000` — this is the only port the candidate's agent should use as a starting point. The gateway returns a welcome message and the address of a single known pod (Artemis Core, the command hub). Everything else must be discovered.

### Pod API Spec

Every pod exposes the following endpoints:

#### `GET /info`
Returns the pod's identity and metadata.
```json
{
  "name": "Helios Station",
  "id": "helios",
  "role": "Primary power generation",
  "population": 12,
  "status": "nominal",
  "uptime_days": 847,
  "metadata": {
    "power_output_kw": 4200,
    "solar_panel_count": 340,
    "battery_reserve_pct": 78
  }
}
```

#### `GET /dependencies`
Returns the pod's **declared** dependencies — what it needs from other pods to function.
```json
{
  "id": "helios",
  "dependencies": [
    {
      "pod_id": "terminus",
      "resource": "silicon_feedstock",
      "criticality": "high",
      "notes": "Required for solar panel maintenance"
    },
    {
      "pod_id": "aquifer",
      "resource": "coolant_water",
      "criticality": "medium",
      "notes": "Thermal regulation for battery banks"
    }
  ]
}
```

#### `GET /supplies`
Returns what this pod **provides** to others. Note: this may not perfectly match what downstream pods declare in `/dependencies`. Discrepancies are intentional.
```json
{
  "id": "helios",
  "supplies": [
    { "pod_id": "zephyr", "resource": "electrical_power" },
    { "pod_id": "hydroponics", "resource": "electrical_power" },
    { "pod_id": "nexus", "resource": "electrical_power" }
  ]
}
```

#### `GET /status`
Returns current operational status. Every pod reports `"nominal"` — this is by design. The crisis is structural, not operational.
```json
{
  "id": "helios",
  "status": "nominal",
  "alerts": [],
  "last_incident": null
}
```

#### `GET /logs`
Returns timestamped event logs. This is where the historical narrative lives — dependency reroutes, decommissioned backups, consolidations. The logs tell the story of how the colony slowly drifted into fragility.
```json
{
  "id": "helios",
  "logs": [
    {
      "timestamp": "2094-03-15T08:30:00Z",
      "event": "dependency_reroute",
      "detail": "Backup power feed from vault decommissioned. Helios now sole power source for grid sector 7."
    },
    {
      "timestamp": "2094-06-22T14:10:00Z",
      "event": "maintenance",
      "detail": "Solar panel cluster B3 repaired. Silicon feedstock from Terminus consumed at 140% forecast."
    }
  ]
}
```

#### `GET /comms` (select pods only)
Some pods expose a comms endpoint with inter-pod messages. These contain gossip, rumors, and informal signals that an astute agent might use to triangulate concerns that don't appear in official status.
```json
{
  "id": "artemis",
  "messages": [
    {
      "timestamp": "2094-07-01T09:00:00Z",
      "from": "zephyr",
      "content": "Requesting priority allocation review. Current O2 throughput assumes uninterrupted power from Helios. No contingency if Helios drops below 80%."
    }
  ]
}
```

---

## The Hidden Crisis

**Do not include this section in the candidate-facing README. This is the answer key.**

### The Collapse Scenario: The Aquifer Bottleneck

The colony has slowly consolidated its critical resource flows through **Aquifer Module**. On the surface, Aquifer is just the water recycling pod. But over the past 18 months (visible in `/logs` across multiple pods), the following has happened:

1. **Vault Reserve's backup water system was decommissioned** due to budget reallocation to Sentinel Array upgrades. Aquifer became the sole water source.

2. **Helios Station** depends on Aquifer for coolant water for its battery thermal regulation. Without it, battery reserves degrade within 48 hours and power output drops below critical threshold.

3. **Zephyr Hub** (oxygen) depends on Helios for power. If Helios degrades, Zephyr's atmospheric processing fails within 12 hours.

4. **Hydroponics Bay** depends on Aquifer directly for irrigation AND on Zephyr for CO2/O2 balance. Double dependency through the same chokepoint.

5. **Prometheus Lab** was recently rerouted to receive its water supply through Hydroponics (a cascading dependency) rather than directly from Aquifer, after a pipe infrastructure consolidation. This is visible in the logs but Prometheus's `/dependencies` still lists Aquifer as its source (stale data — another signal for a sharp agent).

6. **Medica Ward** depends on Prometheus for pharmaceutical synthesis. Prometheus failing means Medica loses its drug supply chain.

7. **Forge Works** depends on Terminus for raw materials and Helios for power. Terminus depends on Aquifer for mining slurry processing.

### The Graph

When fully mapped, the transitive dependency graph reveals:

- **Aquifer** is a single point of failure for **10 of 12 pods** within 72 hours
- The only pods not transitively dependent on Aquifer are **Sentinel Array** (self-powered, independent water from ice harvesting) and **Nexus Relay** (low-power, has independent water recycler)
- The cascade path is: Aquifer fails → Helios degrades (48h) → Zephyr fails (12h after Helios) → Hydroponics fails (immediate, dual dependency) → Prometheus fails (was already rerouted through Hydroponics) → Medica fails → colony-wide crisis
- **Vault Reserve**, which should be the backstop, had its water backup decommissioned — this is the detail that makes it a true collapse rather than a recoverable incident

### Signals the Agent Should Catch

- `/supplies` and `/dependencies` don't always agree — reconciling them reveals hidden flows
- `/logs` across multiple pods tell a consistent story of consolidation toward Aquifer
- `/comms` messages from Zephyr and Hydroponics express informal concern about single-source dependencies
- Prometheus's `/dependencies` is stale (says Aquifer, actual flow is through Hydroponics) — cross-referencing with Hydroponics' `/supplies` reveals the truth
- Vault's `/logs` show the backup decommission event — the moment the safety net was removed
- Every pod reports `"nominal"` status — the crisis is invisible at the individual level

### Evaluation Rubric (Internal)

| Signal | What It Tells You |
|--------|------------------|
| Agent discovers all 12 pods autonomously | Basic crawling competence |
| Agent builds a directed dependency graph | Systems thinking, data modeling |
| Agent reconciles `/dependencies` vs `/supplies` discrepancies | Attention to data integrity, adversarial mindset |
| Agent incorporates `/logs` to understand temporal drift | Thinks about systems as evolving, not static |
| Agent identifies Aquifer as critical chokepoint | Core graph analysis — centrality, SPOF detection |
| Agent traces the full cascade path | Deep transitive reasoning |
| Agent flags the Vault decommission as the loss of the safety net | Understands defense in depth |
| Agent catches the stale Prometheus dependency | Data quality awareness |
| Agent uses `/comms` as a soft signal | Creative use of unstructured data |
| Agent produces a clear visualization or report | Communication of findings |
| Agent suggests remediation | Goes beyond analysis to action |

---

## Implementation Plan

### Tech Stack

- **Pod services:** Node.js (Express) or Python (FastAPI) — pick one and use it for all pods
- **Data:** Each pod's data (info, dependencies, supplies, logs, comms) is defined in a JSON config file mounted into the container. One config per pod. This makes the scenario easy to modify.
- **Gateway:** A thin service on port 3000 that returns the entrypoint information
- **Docker Compose:** Single `docker-compose.yml` that brings up all 13 services (gateway + 12 pods) on `selene-net`

### Directory Structure

```
project-selene/
├── README.md                    # Candidate-facing README (without crisis details)
├── ANSWER_KEY.md                # Internal: crisis details + rubric
├── docker-compose.yml
├── gateway/
│   ├── Dockerfile
│   ├── package.json
│   └── index.js
├── pod-service/
│   ├── Dockerfile               # Single image, config-driven
│   ├── package.json
│   └── index.js                 # Generic pod server, reads config at startup
├── configs/
│   ├── helios.json
│   ├── artemis.json
│   ├── hydroponics.json
│   ├── aquifer.json
│   ├── zephyr.json
│   ├── prometheus.json
│   ├── medica.json
│   ├── terminus.json
│   ├── nexus.json
│   ├── forge.json
│   ├── vault.json
│   └── sentinel.json
└── candidate/
    └── README.md                # The prompt the candidate actually sees
```

### Key Design Decisions

- **One generic pod service, many configs.** Every pod runs the same Express/FastAPI app. The personality, dependencies, logs, and comms are all driven by the JSON config file. This keeps the codebase tiny and makes it trivial to tweak the scenario.
- **Config-driven discrepancies.** The `/dependencies` and `/supplies` mismatches are authored directly in the config files. For example, `prometheus.json` lists `aquifer` as a dependency, but `hydroponics.json` lists `prometheus` in its supplies. The code doesn't need to be clever — the data is just intentionally inconsistent.
- **Logs tell the story.** Each config's `logs` array is a hand-written narrative. The timestamps should span ~18 months and tell a coherent story of gradual consolidation when read across all pods chronologically.
- **Gateway as the only entrypoint.** The candidate's agent starts at `localhost:3000` and gets pointed to `artemis:3002`. From there, it must discover other pods by following dependency/supply references. Some pods may only be reachable by chaining — e.g., Sentinel is only referenced in Artemis's supplies list.
- **All pods report nominal.** This is critical. The exercise is about structural analysis, not alert triage.

### Config File Schema

Each pod config JSON should follow this structure:

```json
{
  "id": "helios",
  "name": "Helios Station",
  "role": "Primary power generation",
  "population": 12,
  "status": "nominal",
  "uptime_days": 847,
  "metadata": {
    "power_output_kw": 4200,
    "solar_panel_count": 340,
    "battery_reserve_pct": 78
  },
  "dependencies": [
    {
      "pod_id": "terminus",
      "resource": "silicon_feedstock",
      "criticality": "high",
      "notes": "Required for solar panel maintenance"
    }
  ],
  "supplies": [
    {
      "pod_id": "zephyr",
      "resource": "electrical_power"
    }
  ],
  "logs": [
    {
      "timestamp": "2094-03-15T08:30:00Z",
      "event": "dependency_reroute",
      "detail": "Backup power feed from Vault decommissioned."
    }
  ],
  "comms": [
    {
      "timestamp": "2094-07-01T09:00:00Z",
      "from": "zephyr",
      "content": "Requesting priority allocation review..."
    }
  ]
}
```

### Candidate-Facing README (candidate/README.md)

The candidate should receive a stripped-down README that contains:

1. **The scenario:** You are an engineer for the Selene Lunar Colony Administration. The colony has been running for over two years. All systems report nominal. Leadership has asked you to build an autonomous agent that maps the colony's infrastructure and assesses its resilience.
2. **The entrypoint:** `docker compose up`, then hit `localhost:3000`.
3. **The deliverable:** An agent (language of your choice, but TypeScript or Python preferred) that autonomously discovers the colony network, builds a representation of the ecosystem, and produces a report or visualization of its findings. Include a short writeup of your design decisions and what you'd do with more time.
4. **The constraints:** You may use any LLM, framework, or tool. Vibe coding is encouraged. We care about how you think, not how you type. Budget 3-5 hours.
5. **No hints about the crisis.** The candidate should discover it, not be told to look for it.

---

## Build Notes

- Use `node:20-alpine` or `python:3.12-slim` as base images to keep containers lightweight
- Each pod container needs ~32MB RAM max — the whole colony should run comfortably on any dev machine
- Pod service should respond within 50ms — no artificial delays unless we want to simulate network latency as an extra challenge
- Consider adding a `GET /` on each pod that returns a brief human-readable welcome message with the pod name, so agents that just hit the root path get something useful
- All inter-pod references use the Docker service name (e.g., `helios`, `aquifer`) — the candidate's agent accesses them via `localhost:{port}` from outside the network