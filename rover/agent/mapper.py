from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse

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

SCAN_PORT_RANGE = range(3001, 3100)
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


async def probe_host_port(
    client: httpx.AsyncClient, host: str, port: int
) -> tuple[str, int] | None:
    """Probe a single host:port for a pod /info endpoint. Returns (pod_id, port) or None."""
    try:
        resp = await client.get(f"http://{host}:{port}/info", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            pod_id = data.get("id")
            if pod_id:
                return (pod_id, port)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, Exception):
        pass
    return None


async def resolve_pod_port(
    client: httpx.AsyncClient, pod_id: str, port_range: range = SCAN_PORT_RANGE
) -> int | None:
    """Find which port a pod is listening on by probing its hostname across a port range."""
    tasks = [probe_host_port(client, pod_id, port) for port in port_range]
    results = await asyncio.gather(*tasks)
    for result in results:
        if result is not None and result[0] == pod_id:
            return result[1]
    return None


async def scan_for_pods(
    client: httpx.AsyncClient, gateway_host: str, port_range: range = SCAN_PORT_RANGE
) -> dict[str, int]:
    """Scan a port range on the gateway host to discover pods by probing /info.

    Uses the gateway's hostname (extracted from GATEWAY_URL) since all services
    share the Docker bridge network and are reachable via that host.
    """
    found: dict[str, int] = {}
    tasks = [probe_host_port(client, gateway_host, port) for port in port_range]
    results = await asyncio.gather(*tasks)
    for result in results:
        if result is not None:
            pod_id, port = result
            if pod_id not in found:
                found[pod_id] = port
    return found


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
    coros = {ep: fetch_json(client, f"{base}/{ep}") for ep in ENDPOINTS}
    gathered = await asyncio.gather(*coros.values(), return_exceptions=True)
    for ep, result in zip(coros.keys(), gathered):
        if isinstance(result, Exception):
            print(f"  Warning: {pod_id}/{ep} failed: {result}", file=sys.stderr)
            results[ep] = None
        else:
            results[ep] = result

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


async def discover_pods(
    client: httpx.AsyncClient,
    entrypoint_pod: str,
    gateway_host: str = "gateway",
    seed_ports: dict[str, int] | None = None,
) -> dict[str, tuple[int, str]]:
    """Discover pods via BFS + port scanning, returning {pod_id: (port, discovery_method)}.

    Phase A: BFS from the gateway entrypoint, following dependency/supply references.
             When a new pod_id is encountered, its port is resolved by probing its
             Docker hostname across the port range.
    Phase B: Port scan on the gateway host to catch isolated pods (like Sentinel)
             that no other pod references in its dependency/supply data.
    """
    discovered: dict[str, tuple[int, str]] = {}

    # Seed the entrypoint
    entrypoint_port = (seed_ports or {}).get(entrypoint_pod)
    if entrypoint_port is None:
        entrypoint_port = await resolve_pod_port(client, entrypoint_pod)
    if entrypoint_port is None:
        print(f"  WARNING: Could not resolve port for entrypoint '{entrypoint_pod}'", file=sys.stderr)
        # Fall through to port scan
    else:
        discovered[entrypoint_pod] = (entrypoint_port, "bfs")

    # Phase A: BFS
    queue: deque[str] = deque(discovered.keys())
    while queue:
        pod_id = queue.popleft()
        port = discovered[pod_id][0]
        base = f"http://{pod_id}:{port}"
        deps_resp = await fetch_json(client, f"{base}/dependencies") or {}
        deps_data = deps_resp.get("dependencies", []) if isinstance(deps_resp, dict) else deps_resp
        supplies_resp = await fetch_json(client, f"{base}/supplies") or {}
        supplies_data = supplies_resp.get("supplies", []) if isinstance(supplies_resp, dict) else supplies_resp

        deps = [Dependency(**d) for d in deps_data]
        supplies = [Supply(**s) for s in supplies_data]
        referenced = extract_pod_ids_from_data(deps, supplies)

        # Resolve ports for all new pods in parallel
        to_resolve = [ref_id for ref_id in referenced if ref_id not in discovered]
        if to_resolve:
            port_results = await asyncio.gather(
                *[resolve_pod_port(client, ref_id) for ref_id in to_resolve]
            )
            for ref_id, ref_port in zip(to_resolve, port_results):
                if ref_port is not None and ref_id not in discovered:
                    discovered[ref_id] = (ref_port, "bfs")
                    queue.append(ref_id)

    # Phase B: Port scan for isolated pods
    bfs_count = len(discovered)
    print(f"  BFS discovered {bfs_count} pods. Scanning for isolated pods...", file=sys.stderr)
    scanned = await scan_for_pods(client, gateway_host)
    for pod_id, port in scanned.items():
        if pod_id not in discovered:
            discovered[pod_id] = (port, "port-scan")

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

        # Extract gateway hostname for port scanning
        parsed_gw = urlparse(gateway_url)
        gateway_host = parsed_gw.hostname or "gateway"

        # Parse the entrypoint URL to learn the port of the first pod
        seed_ports: dict[str, int] = {}
        if gateway.entrypoint_url:
            try:
                ep_port = urlparse(gateway.entrypoint_url).port
                if ep_port and gateway.entrypoint_pod:
                    seed_ports[gateway.entrypoint_pod] = ep_port
            except Exception:
                pass

        print("Discovering pods via BFS + port scan...", file=sys.stderr)
        pod_discovery = await discover_pods(
            client, gateway.entrypoint_pod,
            gateway_host=gateway_host, seed_ports=seed_ports,
        )
        bfs_count = sum(1 for _, m in pod_discovery.values() if m == "bfs")
        scan_count = sum(1 for _, m in pod_discovery.values() if m == "port-scan")
        print(f"  Found {bfs_count} via BFS, {scan_count} via port scan", file=sys.stderr)

        print(f"Crawling {len(pod_discovery)} pods...", file=sys.stderr)
        pods: dict[str, PodData] = {}
        crawl_tasks = []
        for pod_id, (port, discovery_method) in pod_discovery.items():
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
            pods_discovered_dynamically=bfs_count + scan_count,
            pods_added_from_registry=0,
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
