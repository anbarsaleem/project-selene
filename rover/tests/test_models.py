from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agent.models import (
    ColonyMap,
    CommMessage,
    CrawlMetadata,
    Dependency,
    GatewayData,
    PodData,
    PodStatus,
    Supply,
)


class TestCommMessage:
    def test_from_field_alias(self):
        msg = CommMessage.model_validate({
            "timestamp": "2094-01-01",
            "from": "engineer_a",
            "to": "engineer_b",
            "content": "hello",
        })
        assert msg.from_field == "engineer_a"

    def test_serializes_with_alias(self):
        msg = CommMessage(
            timestamp="2094-01-01",
            from_field="engineer_a",
            to="engineer_b",
            content="hello",
        )
        data = msg.model_dump(by_alias=True)
        assert "from" in data
        assert "from_field" not in data


class TestPodData:
    def test_minimal_construction(self):
        pod = PodData(
            id="test",
            name="Test Pod",
            role="testing",
            population=5,
            hostname="test",
            port=3001,
            crawled_at="2094-01-01T00:00:00Z",
            discovered_via="test",
        )
        assert pod.dependencies == []
        assert pod.comms is None
        assert pod.metadata == {}

    def test_comms_none_vs_empty(self):
        """comms=None means endpoint returned 404; comms=[] means no messages."""
        pod_no_comms = PodData(
            id="a", name="A", role="r", population=0,
            hostname="a", port=1, crawled_at="t", discovered_via="t",
            comms=None,
        )
        pod_empty_comms = PodData(
            id="b", name="B", role="r", population=0,
            hostname="b", port=1, crawled_at="t", discovered_via="t",
            comms=[],
        )
        assert pod_no_comms.comms is None
        assert pod_empty_comms.comms == []


class TestColonyMapRoundTrip:
    def test_serialize_deserialize(self):
        colony_map = ColonyMap(
            crawl_metadata=CrawlMetadata(
                started_at="2094-01-01T00:00:00Z",
                finished_at="2094-01-01T00:00:01Z",
                duration_seconds=1.0,
                pods_discovered_dynamically=1,
                pods_added_from_registry=0,
            ),
            gateway=GatewayData(
                colony="Test Colony",
                established="2092-01-01",
                population=10,
                status="nominal",
                entrypoint_pod="alpha",
                entrypoint_url="http://alpha:3001",
                entrypoint_description="test",
            ),
            pods={
                "alpha": PodData(
                    id="alpha",
                    name="Alpha",
                    role="test",
                    population=10,
                    dependencies=[
                        Dependency(pod_id="beta", resource="power", criticality="high", notes="")
                    ],
                    supplies=[Supply(pod_id="beta", resource="coolant")],
                    hostname="alpha",
                    port=3001,
                    crawled_at="2094-01-01T00:00:00Z",
                    discovered_via="bfs",
                ),
            },
        )
        json_str = colony_map.model_dump_json(by_alias=True)
        restored = ColonyMap.model_validate(json.loads(json_str))
        assert restored.pods["alpha"].dependencies[0].pod_id == "beta"
        assert restored.crawl_metadata.duration_seconds == 1.0
