# Project Selene — Lunar Colony Infrastructure Assessment

## Background

You are a systems engineer contracted by the **Selene Lunar Colony Administration**. The colony was established in early 2092 on the lunar south pole and has been continuously operational for over two and a half years. It currently supports 147 residents across twelve interconnected habitat pods, each responsible for a critical function: power generation, water recycling, food production, atmospheric processing, medical services, mining, manufacturing, communications, research, and emergency reserves.

All systems report nominal. The colony is stable and productive. Colony leadership is now planning a Phase 3 expansion and has commissioned an independent infrastructure review. They want a comprehensive map of how the colony's pods depend on each other and an assessment of the colony's operational resilience.

## Getting Started

```bash
docker compose up
```

The colony gateway is available at **http://localhost:3000**. It will direct you to your first point of contact within the colony. Everything else must be discovered.

Each pod exposes a REST API. Explore the available endpoints to understand what data each pod provides. The individual pods are also accessible on ports 3001-3012.

## Your Task

Build an **autonomous agent** that:

1. Discovers the full colony network starting from the gateway
2. Maps the infrastructure — pods, dependencies, resource flows
3. Produces a **report or visualization** of its findings

Use whatever language, LLM, framework, or tools you prefer. TypeScript or Python preferred but not required. Vibe coding is encouraged — we care about how you think, not how you type.

## Deliverables

- Your agent code
- The output report or visualization it produces
- A short writeup (~1 page) of your design decisions, what your agent found, and what you would do with more time

## Rover Scaffold

A ready-to-use  scaffold is provided in the `rover/` directory. It runs as a container on the colony network and gives you:

- Two shell script entrypoints (`run_mapping.sh` and `run_reporting.sh`) that can call any language or framework
- HTTP endpoints to trigger your agent and retrieve results
- `GATEWAY_URL` and `LLM_API_KEY` environment variables pre-configured

See `rover/README.md` for details.

## Time Budget

3-5 hours. This is a guideline, not a hard limit. We'd rather see thoughtful work than rushed completeness.
