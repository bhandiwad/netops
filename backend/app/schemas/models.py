"""Typed Domain Contracts for the Multi-Layer Network Operations Copilot.

For non-telecom software engineers:
Think of the entire network as a 6-layer Directed Acyclic Dependency Graph (DAG):
  Layer 0: OSP Ducts & Manhole Chambers (`osp_ducts`, `osp_manholes`)
  Layer 1: Physical Fibre & Subsea Cables (`osp_cables`, `subsea_cables`)
  Layer 2: Optical Multiplex Sections & Wavelengths (`oms_links`, `optical_channels`)
  Layer 3: IP/MPLS Core Links & Routers (`ip_links`, `network_nodes`)
  Layer 4: 4G/5G Mobile RAN Sites & GPON Splitters (`ran_sites`, `gpon_clusters`)
  Layer 5: Enterprise Customer Circuits & SLA Contracts (`customer_services`, `customers`)

When a physical failure occurs at a lower layer, upper layers emit cascading symptom
alarms. Southbound adapters normalize vendor events into `CanonicalAlarm`, the graph
clusterer groups related alarms into `CausalCluster`, and pluggable classifiers emit
a `RootCauseHypothesis`.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CanonicalAlarm(BaseModel):
    """Vendor-neutral alarm normalized from TMF642, RESTCONF, Syslog, SNMP, or Kafka."""

    alarm_id: str
    scenario_id: str | None = None
    source_oem: str
    protocol: str
    layer: str
    resource_id: str
    node_id: str
    severity: str
    specific_problem: str
    probable_cause: str
    raw_text: str
    raised_at: str
    extra: dict[str, Any] = Field(default_factory=dict)


class CausalCluster(BaseModel):
    """A connected component of alarms sharing topological reachability in the 6-layer DAG."""

    cluster_id: str
    anchor_resource_id: str
    alarms: list[CanonicalAlarm]
    involved_resources: set[str] = Field(default_factory=set)
    involved_cables: set[str] = Field(default_factory=set)
    involved_nodes: set[str] = Field(default_factory=set)


class FaultLocation(BaseModel):
    """Spatial & physical localization metadata (WGS84 + optical/trench distances)."""

    lat: float | None = None
    lon: float | None = None
    cable_id: str | None = None
    cut_cables: list[str] = Field(default_factory=list)
    fiber_intact: bool | None = None
    dispatch_verdict: str | None = None
    extra_attributes: dict[str, Any] = Field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.lat is not None:
            out["lat"] = self.lat
        if self.lon is not None:
            out["lon"] = self.lon
        if self.cable_id is not None:
            out["cable_id"] = self.cable_id
        if self.cut_cables:
            out["cut_cables"] = self.cut_cables
        if self.fiber_intact is not None:
            out["fiber_intact"] = self.fiber_intact
        if self.dispatch_verdict is not None:
            out["dispatch_verdict"] = self.dispatch_verdict
        out.update(self.extra_attributes)
        return out


class ProposedAction(BaseModel):
    """Human-gated northbound action targeting an ITSM, FSM, or Optical Controller API."""

    action_id: str
    target_system: str
    connector_id: str
    action_type: str
    title: str
    description: str
    payload: dict[str, Any]
    requires_approval: bool = True


class RootCauseHypothesis(BaseModel):
    """Output of a `HypothesisClassifier` plugin evaluating one `CausalCluster`."""

    classifier_id: str
    root_cause_type: str
    root_cause_resource: str
    title: str
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    fault_location: dict[str, Any] = Field(default_factory=dict)
    otdr_trace_data: dict[str, Any] = Field(default_factory=dict)
    domain_actions: list[ProposedAction] = Field(default_factory=list)
    suppress_default_splice_dispatch: bool = False


class ImpactedService(BaseModel):
    service_id: str
    service_type: str
    bandwidth: str
    customer_id: str
    customer_name: str
    segment: str
    sla_tier: str
    mttr_target_hours: float
    penalty_per_hour_aed: int
    ordered_diverse: bool
    outage_state: str
    legs: list[dict[str, Any]]


class ImpactedRanSite(BaseModel):
    site_id: str
    problem: str
    cells: list[str]
    is_cascaded_tail: bool


class ImpactSummary(BaseModel):
    impacted_service_count: int
    complete_outage_count: int
    total_sla_penalty_per_hour_aed: int
    four_hour_sla_exposure_aed: int
    impacted_services: list[ImpactedService]
    impacted_ran_sites: list[ImpactedRanSite]
    impacted_5g_cell_count: int
    alarm_collapse_ratio: str
    alarms_by_oem: dict[str, int]
    alarms_by_layer: dict[str, int]


class SrlgFinding(BaseModel):
    service_id: str
    service_type: str
    bandwidth: str
    customer_id: str
    customer_name: str
    sla_tier: str
    ordered_diverse: bool
    diversity_compliant: bool
    leg_a_name: str
    leg_b_name: str
    shared_cables: list[str]
    shared_ducts: list[str]
    shared_chambers: list[str]
    shared_bridges: list[str]
    risk_summary: str


# API Request Payloads
class TriggerFaultPayload(BaseModel):
    scenario_id: str | None = None
    fault_type: str | None = None
    target_id: str | None = None
    cut_ratio: float = 0.62


class ConnectorUpdatePayload(BaseModel):
    endpoint_url: str
    mode: str = "emulator"
    enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)


class LlmConfigPayload(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""


class StormBenchmarkPayload(BaseModel):
    storm_size: int = 10000
