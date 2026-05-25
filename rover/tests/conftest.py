from __future__ import annotations

import pytest

from agent.models import Dependency, LogEntry, PodData, PodStatus, Supply


def make_pod(
    pod_id: str,
    *,
    deps: list[tuple[str, str, str]] | None = None,
    supplies: list[tuple[str, str]] | None = None,
    metadata: dict | None = None,
    logs: list[tuple[str, str, str]] | None = None,
) -> PodData:
    """Helper to build a PodData with minimal boilerplate.

    deps: list of (pod_id, resource, criticality)
    supplies: list of (pod_id, resource)
    logs: list of (timestamp, event, detail)
    """
    return PodData(
        id=pod_id,
        name=pod_id.title(),
        role="test",
        population=10,
        uptime_days=100,
        metadata=metadata or {},
        dependencies=[
            Dependency(pod_id=d[0], resource=d[1], criticality=d[2], notes="")
            for d in (deps or [])
        ],
        supplies=[
            Supply(pod_id=s[0], resource=s[1]) for s in (supplies or [])
        ],
        status=PodStatus(status="nominal"),
        logs=[
            LogEntry(timestamp=l[0], event=l[1], detail=l[2])
            for l in (logs or [])
        ],
        comms=None,
        hostname=pod_id,
        port=3001,
        crawled_at="2094-01-01T00:00:00Z",
        discovered_via="test",
    )


@pytest.fixture
def triangle_colony() -> dict[str, PodData]:
    """A minimal 3-pod colony with a mutual dependency loop (A <-> B) and a leaf C."""
    return {
        "alpha": make_pod(
            "alpha",
            deps=[("beta", "power", "high")],
            supplies=[("beta", "coolant"), ("charlie", "power")],
        ),
        "beta": make_pod(
            "beta",
            deps=[("alpha", "coolant", "medium")],
            supplies=[("alpha", "power")],
        ),
        "charlie": make_pod(
            "charlie",
            deps=[("alpha", "power", "high")],
        ),
    }


@pytest.fixture
def star_colony() -> dict[str, PodData]:
    """A hub-and-spoke colony: hub supplies 4 leaves, no redundancy."""
    pods = {
        "hub": make_pod(
            "hub",
            supplies=[
                ("leaf1", "power"),
                ("leaf2", "power"),
                ("leaf3", "power"),
                ("leaf4", "power"),
            ],
        ),
    }
    for i in range(1, 5):
        pods[f"leaf{i}"] = make_pod(
            f"leaf{i}",
            deps=[("hub", "power", "high")],
        )
    return pods


@pytest.fixture
def independent_colony() -> dict[str, PodData]:
    """A colony where every pod is fully independent (no deps, no supplies)."""
    return {
        "solo1": make_pod("solo1"),
        "solo2": make_pod("solo2"),
        "solo3": make_pod("solo3"),
    }
