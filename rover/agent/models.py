from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GatewayData(BaseModel):
    colony: str
    established: str
    population: int
    status: str
    entrypoint_pod: str
    entrypoint_url: str
    entrypoint_description: str


class Dependency(BaseModel):
    pod_id: str
    resource: str
    criticality: str
    notes: str


class Supply(BaseModel):
    pod_id: str
    resource: str


class LogEntry(BaseModel):
    timestamp: str
    event: str
    detail: str


class CommMessage(BaseModel):
    timestamp: str
    from_field: str = Field(alias="from")
    to: str
    content: str

    model_config = {"populate_by_name": True}


class PodStatus(BaseModel):
    status: str
    alerts: list[str] = []
    last_incident: Optional[str] = None


class PodData(BaseModel):
    id: str
    name: str
    role: str
    population: int
    uptime_days: int = 0
    metadata: dict[str, Any] = {}

    dependencies: list[Dependency] = []
    supplies: list[Supply] = []
    status: PodStatus = PodStatus(status="unknown")
    logs: list[LogEntry] = []
    comms: Optional[list[CommMessage]] = None

    hostname: str
    port: int
    crawled_at: str
    discovered_via: str  # "dynamic" or "registry"


class CrawlMetadata(BaseModel):
    started_at: str
    finished_at: str
    duration_seconds: float
    pods_discovered_dynamically: int
    pods_added_from_registry: int
    errors: list[str] = []


class ColonyMap(BaseModel):
    crawl_metadata: CrawlMetadata
    gateway: GatewayData
    pods: dict[str, PodData]
