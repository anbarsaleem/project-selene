# Rover — Agent Scaffold

The rover is a Docker container that runs on the colony network alongside the habitat pods. It provides an HTTP interface for triggering your agent and retrieving results.

## Quick Start

```bash
LLM_API_KEY=your-key-here docker compose up --build
```

The rover is available at **http://localhost:8080**. The colony gateway is at **http://localhost:3000**.

Trigger your mapping agent:

```bash
curl -X POST localhost:8080/map
```

Poll for results:

```bash
curl localhost:8080/get-map
```

## What to Implement

Edit two files:

- **`run_mapping.sh`** — Discovers the colony and writes `/rover/output/map.json`
- **`run_reporting.sh`** — Reads `map.json` and writes `/rover/output/report.md`

These shell scripts are your entrypoints. They can call any language or tool — Python, Node, Go, Rust, whatever you install in the Dockerfile.

## Environment Variables

Your scripts inherit these from the container environment:

| Variable | Value | Description |
|----------|-------|-------------|
| `GATEWAY_URL` | `http://gateway:3000` | Colony gateway address (use this, not localhost) |
| `LLM_API_KEY` | *(your key)* | Your LLM provider API key |

## Output Locations

| File | Format | Produced by |
|------|--------|-------------|
| `/rover/output/map.json` | JSON (any structure) | `run_mapping.sh` |
| `/rover/output/report.md` | Markdown | `run_reporting.sh` |

Design the `map.json` schema yourself — there is no required structure.

## Installing Dependencies

Edit the `Dockerfile` to install whatever you need:

```dockerfile
FROM selene-rover-base

# Your dependencies
RUN pip install anthropic httpx networkx
# or: RUN apt-get update && apt-get install -y nodejs npm && npm install openai

COPY . /rover/
RUN chmod +x /rover/run_mapping.sh /rover/run_reporting.sh
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/map` | Start the mapping agent |
| `GET` | `/get-map` | Get mapping results |
| `POST` | `/report` | Start the reporting agent |
| `GET` | `/get-report` | Get the report |
| `GET` | `/health` | Health check |

### Response Codes

- **202** — Job started or still running
- **200** — Job complete, result returned
- **404** — No job has been started yet
- **409** — Job already running
- **500** — Job failed (stderr in response body)

## Colony API Reference

Each habitat pod exposes these endpoints (not all pods support all endpoints):

| Endpoint | Description |
|----------|-------------|
| `/info` | Pod metadata — name, role, population, specs |
| `/status` | Operational status |
| `/dependencies` | What this pod depends on |
| `/supplies` | What this pod provides to others |
| `/logs` | Operational log entries |
| `/comms` | Inter-pod communications (some pods only) |

Start at the gateway (`GATEWAY_URL`) and follow the references to discover the colony.
