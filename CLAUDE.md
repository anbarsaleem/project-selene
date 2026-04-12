# CLAUDE.md — Project Selene Development Guide

## What This Project Is

Project Selene is a take-home engineering exercise disguised as a space-themed exploration game. Candidates receive a docker-compose environment simulating a lunar colony of ~12 habitat pods. Each pod is a container exposing a REST API. The candidate's job is to build an autonomous agent that discovers, maps, and analyzes the colony — and surfaces a hidden systemic crisis that is invisible at the individual pod level.

This project is used to evaluate how someone thinks about systems, not whether they can write clean code under pressure. The exercise is intentionally open-ended. There is no spec for "done." The signal is in the choices the candidate makes unprompted.

---

## Git Branching & Information Isolation

This is the most critical operational concern in this repo. **The candidate must never see the solution, the crisis design, or any internal evaluation material.**

### Branch Structure

- **`main`** — The interviewee-facing branch. This is what candidates clone. It contains ONLY:
  - `docker-compose.yml`
  - `gateway/` service code
  - `pod-service/` generic service code
  - `configs/` with all pod config JSON files
  - `candidate/README.md` (the prompt they see)
  - This `CLAUDE.md` must NOT be on `main`

- **`internal`** — The private development branch. This contains everything on `main` PLUS:
  - `CLAUDE.md` (this file)
  - `ANSWER_KEY.md` (full crisis description, cascade path, evaluation rubric)
  - `docs/` directory with design notes, storytelling guidelines, config authoring notes
  - Any test agents or solution validators we build internally

### Rules

1. **Never merge `internal` into `main`.** Always cherry-pick or manually port non-sensitive changes.
2. **Never commit files from the list below to `main`:**
   - `CLAUDE.md`
   - `ANSWER_KEY.md`
   - Anything in `docs/`
   - Any file containing the words "answer key", "rubric", "cascade", "collapse scenario", or "single point of failure" in a context that reveals the solution
3. **Before pushing to `main`, always review the diff.** Look for any config comments, log entries, or comms messages that make the crisis too explicit. The data should contain the breadcrumbs — never the conclusion.
4. **Add a `.gitignore` entry on `main`** for `CLAUDE.md`, `ANSWER_KEY.md`, and `docs/` as a safety net. This won't prevent committed files from showing, but it prevents accidental staging.
5. **Add a pre-commit check** (can be a simple grep script in `scripts/`) that scans staged files on `main` for sensitive keywords and blocks the commit if found.

---

## The Crisis Design

### Philosophy

The systemic failure must be **genuinely non-obvious**. This means:

- No single pod's data reveals the crisis on its own
- No single API endpoint tells the story
- The crisis only materializes when you build a **complete transitive dependency graph** and reason about cascade failures
- Every pod reports nominal status — there are zero alerts, zero warnings, zero red flags at the surface level
- The data that reveals the crisis is spread across multiple pods, multiple endpoint types (`/dependencies`, `/supplies`, `/logs`, `/comms`), and requires cross-referencing to assemble

### What "Non-Obvious" Actually Means

Think of it this way: if a candidate writes an agent that only hits `/info` and `/status` on every pod, they should come away thinking the colony is perfectly healthy. If they only build a first-order dependency graph from `/dependencies`, they should see a complex but seemingly reasonable network. The crisis only becomes visible when:

1. They trace **transitive** dependencies (A depends on B, B depends on C, therefore A transitively depends on C)
2. They **reconcile discrepancies** between what pods say they depend on and what other pods say they supply
3. They **read the logs** and notice a temporal pattern of consolidation
4. They compute some measure of **graph centrality** or **single-point-of-failure analysis**

A candidate who builds a shallow crawler and renders a pretty graph should produce something that looks interesting but misses the point. A candidate who thinks deeply about what the graph *means* will find the problem.

### The Specific Crisis: Aquifer Bottleneck

See `ANSWER_KEY.md` for the full cascade path. In summary: Aquifer Module has become a transitive single point of failure for 10 of 12 pods through a series of "reasonable" infrastructure consolidations over 18 months. The backup system (Vault Reserve) was decommissioned. The cascade path runs through power, oxygen, food, pharma, and medical in sequence.

### Anti-Leakage in Config Data

When authoring pod configs, follow these rules to avoid making the crisis obvious:

**In `/dependencies` and `/supplies`:**
- Never use the word "critical" or "sole" to describe the Aquifer dependency specifically. Other pods can use strong language about their dependencies — just not in a way that singles out Aquifer
- Aquifer should have a moderate number of declared dependents — not dramatically more than other pods. The transitive fan-out is what makes it dangerous, not the first-order count
- Some dependencies on Aquifer should be labeled `"criticality": "medium"` even when they're structurally critical. Pods underestimate their own fragility — this is realistic and makes the exercise harder

**In `/logs`:**
- The consolidation events should be written as routine operational decisions, not ominous warnings. "Backup water system transferred to maintenance reserve to free capacity for Sentinel Array upgrade" — not "Removed last safety net for water supply"
- Spread the consolidation story across many pods' logs. No single pod's log file should read as a smoking gun
- Mix the important events in with mundane maintenance noise — panel repairs, software updates, personnel rotations, routine inspections
- The timestamps should span 18 months and the consolidation should be gradual, not a sudden change

**In `/comms`:**
- Comms messages should be informal, conversational, and ambiguous. A pod engineer expressing mild concern about resource allocation is a breadcrumb. A message saying "we are dangerously dependent on Aquifer" is a spoiler
- Not every pod needs comms. Maybe 4-5 pods have this endpoint. The rest return 404
- Include comms that are irrelevant noise — social messages, scheduling, complaints about food. The signal should be buried in normal human chatter

**In `/status`:**
- Every pod reports `"nominal"`. No exceptions. No "degraded", no "warning", no alerts. The whole point is that the system looks fine from the inside

**In `/info` metadata:**
- Pod metadata should be interesting and detailed but never directly reveal the crisis. Aquifer's metadata might show throughput numbers that, if you knew what to look for, suggest it's running near capacity — but the numbers alone don't scream "failure imminent"

---

## Storytelling & Theme

### Tone

The colony is **mundane-professional**, not dramatic sci-fi. Think of it as an industrial operation that happens to be on the Moon. Pod names are evocative (Helios, Artemis, Zephyr) but the data is bureaucratic — maintenance logs, resource allocation notes, operational metrics. This grounds the exercise and makes it feel like a real system rather than a game.

The underlying narrative is one of **organizational drift** — a colony that made a series of individually rational decisions (consolidate redundant systems, reallocate budget, simplify supply chains) that collectively created a catastrophic fragility. This mirrors real-world infrastructure failures and is thematically aligned with the kind of thinking we need from candidates: the ability to see emergent systemic risk that no individual stakeholder is aware of.

### World-Building Rules

- The colony has been operational for **~2.5 years** (established early 2092, current date in-universe is mid-2094)
- Population is **~150 people** spread across the pods. Each pod has 8-20 residents depending on its role
- The colony is **remote but not isolated** — there are references to Earth-side administration, supply ships, and communication with mission control, but these are background flavor, not mechanically relevant
- The mood is **optimistic but stretched**. The colony is proud of its growth but resources are tight. Consolidation happened because of budget pressure, not malice
- **No villains.** The crisis is systemic, not caused by sabotage or negligence. Every decision that led to the bottleneck was defensible in isolation. This is important — it reflects how real infrastructure fails

### Writing Style for Config Data

- **Logs** should read like terse operational records. Short sentences. Jargon is fine. "Rerouted secondary water feed from Vault bypass to primary Aquifer loop per Directive 2094-031. Estimated savings: 12kW/day."
- **Comms** should read like Slack messages between engineers. Casual, sometimes abbreviated, occasionally frustrated. "hey — heads up, we're pulling pharma synthesis water through your irrigation line now. shouldn't affect your throughput but lmk if you see pressure drops"
- **Info/metadata** should read like a dashboard — numbers, units, technical specs. No narrative.
- **Status** is always one word: `"nominal"`. The irony is the point.

### What the Candidate Sees

The candidate-facing README (`candidate/README.md`) should:

- Set the scene in 2-3 paragraphs. You are an engineer contracted by the Selene Lunar Colony Administration. The colony has been operational for over two years. All systems report nominal. Colony leadership wants an independent assessment of infrastructure resilience.
- Explain the entrypoint: `docker compose up`, hit `localhost:3000`, follow the thread
- State the deliverable: an autonomous agent that maps the colony and produces a report on its findings. TypeScript or Python preferred. Any LLM or framework is fair game. Vibe coding encouraged. 3-5 hours.
- Ask for a short writeup of design decisions
- **Say nothing about what they should find.** No hints. No "look for systemic risk." No "the colony may not be as healthy as it appears." The prompt is purely about discovery and mapping. If they find the crisis, it's because their agent and their thinking were good enough to surface it.

---

## Technical Implementation

### Pod Service Architecture

A single generic service that reads its personality from a mounted JSON config:

- One `Dockerfile`, one codebase, twelve containers
- On startup, the service reads `/config/pod.json` (mounted via docker-compose volume) and serves all endpoints from that data
- No inter-container communication at runtime. Pods don't actually talk to each other — they just reference each other in their data. The agent is the one that traverses the graph.
- Use Express.js (Node 20 Alpine). Keep it minimal — the service is ~100 lines of code.

### Gateway Service

- Runs on port 3000, the only host-exposed port besides the individual pod ports
- Returns a JSON welcome message with the colony name, a brief flavor paragraph, and the address of the first pod to visit (`artemis` on port 3002)
- This is the candidate's starting point. Their agent should begin here and discover everything else by following references.

### Docker Compose

- All services on a shared network (`selene-net`)
- Each pod service maps a config file from `configs/{id}.json` to `/config/pod.json` inside the container
- Expose each pod's port to the host (3001-3012) so the candidate's agent can reach them from outside Docker
- Gateway on port 3000
- Use `depends_on` for startup ordering if needed but keep it simple

### Candidate Accessibility

- `docker compose up` must work on a fresh clone with Docker installed. No other setup.
- No build step beyond what docker-compose handles
- No environment variables required
- No external dependencies or API keys
- The whole stack should start in under 30 seconds and use under 512MB RAM total

---

## Development Workflow

1. **Always work on the `internal` branch** for anything sensitive
2. When making changes to pod configs, service code, or docker-compose: make the change on `internal`, test it, then cherry-pick the non-sensitive commits to `main`
3. **Test the candidate experience regularly.** Clone `main` into a fresh directory, run `docker compose up`, and try to find the crisis yourself. If it's too easy, the configs need more noise and subtlety. If the data is broken or inconsistent in a way that's confusing rather than revealing, fix it.
4. When authoring configs, write all 12 together as a system. The dependency graph, the log timeline, and the comms chatter need to be internally consistent. Don't write them one at a time in isolation.
5. **Validate the graph.** Maintain a simple script (on `internal` only) that reads all 12 configs and outputs the full dependency graph, transitive closure, and identifies the cascade path. Use this to verify that the crisis is intact and discoverable after any config changes.

---

## Summary of Files by Branch

### `main` (candidate-facing)
```
project-selene/
├── candidate/
│   └── README.md
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
├── gateway/
│   ├── Dockerfile
│   ├── package.json
│   └── index.js
├── pod-service/
│   ├── Dockerfile
│   ├── package.json
│   └── index.js
├── docker-compose.yml
├── .gitignore
└── README.md              # Points to candidate/README.md, minimal
```

### `internal` (private, never shared)
```
All of the above, plus:
├── CLAUDE.md              # This file
├── ANSWER_KEY.md          # Full crisis details + evaluation rubric
├── docs/
│   ├── crisis-design.md
│   ├── config-authoring.md
│   └── evaluation-notes.md
├── scripts/
│   ├── validate-graph.js  # Reads configs, outputs dependency analysis
│   └── check-leakage.sh   # Pre-commit hook to scan for sensitive content
└── solutions/
    └── reference-agent/   # Our own solution agent for testing
```