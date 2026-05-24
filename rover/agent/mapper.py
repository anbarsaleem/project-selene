from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone

import httpx

from agent.models import (
    ColonyMap,
    CommMessage,
    CrawlMetadata,
    Dependency,
    GatewayData,
    LogEntry,
    PodData,
    PodStatus,
    Supply,
)

POD_REGISTRY: dict[str, int] = {
    "helios": 3001,
    "artemis": 3002,
    "hydroponics": 3003,
    "aquifer": 3004,
    "zephyr": 3005,
    "prometheus": 3006,
    "medica": 3007,
    "terminus": 3008,
    "nexus": 3009,
    "forge": 3010,
    "vault": 3011,
    "sentinel": 3012,
}

ENDPOINTS = ["info", "dependencies", "supplies", "status", "logs", "comms"]
OUTPUT_PATH = "/rover/output/map.json"


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    for attempt in range(2):
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 0:
                await asyncio.sleep(2)
            else:
                raise


async def crawl_gateway(client: httpx.AsyncClient, gateway_url: str) -> GatewayData:
    data = await fetch_json(client, gateway_url)
    if data is None:
        raise RuntimeError(f"Gateway at {gateway_url} returned 404")
    entrypoint = data.get("entrypoint", {})
    return GatewayData(
        colony=data["colony"],
        established=data["established"],
        population=data["population"],
        status=data["status"],
        entrypoint_pod=entrypoint.get("pod", ""),
        entrypoint_url=entrypoint.get("url", ""),
        entrypoint_description=entrypoint.get("description", ""),
    )


async def crawl_pod(
    client: httpx.AsyncClient, pod_id: str, port: int, discovered_via: str
) -> PodData:
    base = f"http://{pod_id}:{port}"
    now = datetime.now(timezone.utc).isoformat()

    results: dict[str, dict | list | None] = {}
    tasks = {ep: fetch_json(client, f"{base}/{ep}") for ep in ENDPOINTS}
    for ep, coro in tasks.items():
        try:
            results[ep] = await coro
        except Exception as exc:
            print(f"  Warning: {pod_id}/{ep} failed: {exc}", file=sys.stderr)
            results[ep] = None

    info = results.get("info") or {}
    status_data = results.get("status") or {}
    deps_raw = (results.get("dependencies") or {})
    deps_raw = deps_raw.get("dependencies", deps_raw) if isinstance(deps_raw, dict) else deps_raw
    supplies_raw = (results.get("supplies") or {})
    supplies_raw = supplies_raw.get("supplies", supplies_raw) if isinstance(supplies_raw, dict) else supplies_raw
    logs_raw = (results.get("logs") or {})
    logs_raw = logs_raw.get("logs", logs_raw) if isinstance(logs_raw, dict) else logs_raw
    comms_raw = results.get("comms")
    if isinstance(comms_raw, dict):
        comms_raw = comms_raw.get("messages", comms_raw.get("comms", comms_raw))

    dependencies = [Dependency(**d) for d in deps_raw]
    supplies = [Supply(**s) for s in supplies_raw]
    logs = [LogEntry(**entry) for entry in logs_raw]
    comms = [CommMessage.model_validate(m) for m in comms_raw] if comms_raw is not None else None
    pod_status = PodStatus(
        status=status_data.get("status", "unknown"),
        alerts=status_data.get("alerts", []),
        last_incident=status_data.get("last_incident"),
    )

    return PodData(
        id=info.get("id", pod_id),
        name=info.get("name", pod_id),
        role=info.get("role", "unknown"),
        population=info.get("population", 0),
        uptime_days=info.get("uptime_days", 0),
        metadata=info.get("metadata", {}),
        dependencies=dependencies,
        supplies=supplies,
        status=pod_status,
        logs=logs,
        comms=comms,
        hostname=pod_id,
        port=port,
        crawled_at=now,
        discovered_via=discovered_via,
    )


def extract_pod_ids_from_data(deps: list[Dependency], supplies: list[Supply]) -> set[str]:
    ids: set[str] = set()
    for d in deps:
        ids.add(d.pod_id)
    for s in supplies:
        ids.add(s.pod_id)
    return ids


async def discover_pods(client: httpx.AsyncClient, entrypoint_pod: str) -> dict[str, str]:
    """BFS through dependency/supply references to discover pods dynamically.
    Returns dict of pod_id -> discovery method ("dynamic" or "registry")."""
    discovered: dict[str, str] = {}
    queue: deque[str] = deque()

    if entrypoint_pod in POD_REGISTRY:
        queue.append(entrypoint_pod)
        discovered[entrypoint_pod] = "dynamic"

    while queue:
        pod_id = queue.popleft()
        port = POD_REGISTRY.get(pod_id)
        if port is None:
            continue

        base = f"http://{pod_id}:{port}"
        deps_resp = await fetch_json(client, f"{base}/dependencies") or {}
        deps_data = deps_resp.get("dependencies", []) if isinstance(deps_resp, dict) else deps_resp
        supplies_resp = await fetch_json(client, f"{base}/supplies") or {}
        supplies_data = supplies_resp.get("supplies", []) if isinstance(supplies_resp, dict) else supplies_resp

        deps = [Dependency(**d) for d in deps_data]
        supplies = [Supply(**s) for s in supplies_data]
        referenced = extract_pod_ids_from_data(deps, supplies)

        for ref_id in referenced:
            if ref_id not in discovered and ref_id in POD_REGISTRY:
                discovered[ref_id] = "dynamic"
                queue.append(ref_id)

    # Phase B: fill in any pods not found dynamically
    for pod_id in POD_REGISTRY:
        if pod_id not in discovered:
            discovered[pod_id] = "registry"

    return discovered


async def run_mapping() -> None:
    gateway_url = os.environ.get("GATEWAY_URL", "http://gateway:3000")
    start_time = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    async with httpx.AsyncClient() as client:
        print("Crawling gateway...", file=sys.stderr)
        gateway = await crawl_gateway(client, gateway_url)
        print(f"  Colony: {gateway.colony}, entrypoint: {gateway.entrypoint_pod}", file=sys.stderr)

        print("Discovering pods via dependency graph BFS...", file=sys.stderr)
        pod_discovery = await discover_pods(client, gateway.entrypoint_pod)
        dynamic_count = sum(1 for v in pod_discovery.values() if v == "dynamic")
        registry_count = sum(1 for v in pod_discovery.values() if v == "registry")
        print(f"  Found {dynamic_count} dynamically, {registry_count} from registry", file=sys.stderr)

        print(f"Crawling {len(pod_discovery)} pods...", file=sys.stderr)
        pods: dict[str, PodData] = {}
        crawl_tasks = []
        for pod_id, discovery_method in pod_discovery.items():
            port = POD_REGISTRY[pod_id]
            crawl_tasks.append(crawl_pod(client, pod_id, port, discovery_method))

        results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
        for pod_id, result in zip(pod_discovery.keys(), results):
            if isinstance(result, Exception):
                msg = f"Failed to crawl {pod_id}: {result}"
                print(f"  ERROR: {msg}", file=sys.stderr)
                errors.append(msg)
            else:
                pods[result.id] = result
                comms_status = f"{len(result.comms)} comms" if result.comms else "no comms"
                print(f"  {result.id}: {result.name} ({comms_status})", file=sys.stderr)

    elapsed = time.monotonic() - start_time
    finished_at = datetime.now(timezone.utc).isoformat()

    colony_map = ColonyMap(
        crawl_metadata=CrawlMetadata(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(elapsed, 2),
            pods_discovered_dynamically=dynamic_count,
            pods_added_from_registry=registry_count,
            errors=errors,
        ),
        gateway=gateway,
        pods=pods,
    )

    with open(OUTPUT_PATH, "w") as f:
        f.write(colony_map.model_dump_json(indent=2, by_alias=True))

    print(f"\nMapping complete in {elapsed:.1f}s. {len(pods)} pods written to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_mapping())
