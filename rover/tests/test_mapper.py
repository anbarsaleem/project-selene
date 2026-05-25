from __future__ import annotations

import asyncio

import pytest

from agent.mapper import extract_pod_ids_from_data, crawl_gateway, SCAN_PORT_RANGE
from agent.models import Dependency, Supply, GatewayData


class TestExtractPodIds:
    def test_extracts_from_deps_and_supplies(self):
        deps = [
            Dependency(pod_id="a", resource="power", criticality="high", notes=""),
            Dependency(pod_id="b", resource="water", criticality="medium", notes=""),
        ]
        supplies = [
            Supply(pod_id="b", resource="coolant"),
            Supply(pod_id="c", resource="data"),
        ]
        ids = extract_pod_ids_from_data(deps, supplies)
        assert ids == {"a", "b", "c"}

    def test_empty_inputs(self):
        assert extract_pod_ids_from_data([], []) == set()

    def test_deduplicates(self):
        deps = [Dependency(pod_id="x", resource="a", criticality="high", notes="")]
        supplies = [Supply(pod_id="x", resource="b")]
        ids = extract_pod_ids_from_data(deps, supplies)
        assert ids == {"x"}


class TestScanPortRange:
    def test_range_covers_expected_ports(self):
        assert 3001 in SCAN_PORT_RANGE
        assert 3012 in SCAN_PORT_RANGE
        assert 3099 in SCAN_PORT_RANGE
        assert 3100 not in SCAN_PORT_RANGE
