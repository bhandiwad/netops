"""Public Domain Facade re-exporting modular NOC Copilot subsystems.

All domain logic has been decomposed into single-responsibility packages:
  - `backend/app/schemas/`      — Typed Pydantic v2 contracts
  - `backend/app/adapters/`     — Southbound/Northbound OEM adapters & embedding providers
  - `backend/app/spatial/`      — PostGIS slack-loop & helical stranding localization
  - `backend/app/routing/`      — Dynamic Dijkstra reroutes, SRLG audit & 6-layer DAG
  - `backend/app/correlation/`  — Graph alarm clusterer & pluggable `HypothesisClassifier` registry
"""
from __future__ import annotations

from .adapters.registry import (
    DatabaseBackedOtdrAdapter,
    RestNorthboundActionAdapter,
    get_connectors_map,
    get_emulator_control_base_url,
    sync_all_connectors,
)
from .correlation import (
    LLM_CONFIG,
    correlate_alarms_into_incident,
    correlate_alarms_into_incidents,
    execute_incident_actions,
    generate_ai_copilot_analysis,
    get_incident_detail,
)
from .routing import (
    audit_all_srlg_diversity,
    build_multilayer_dependency_graph,
    compute_dynamic_optical_reroute,
    load_normalized_inventory,
    run_10k_alarm_storm_benchmark,
)
from .spatial import locate_fault_on_cable_postgis

__all__ = [
    "DatabaseBackedOtdrAdapter",
    "LLM_CONFIG",
    "RestNorthboundActionAdapter",
    "audit_all_srlg_diversity",
    "build_multilayer_dependency_graph",
    "compute_dynamic_optical_reroute",
    "correlate_alarms_into_incident",
    "correlate_alarms_into_incidents",
    "execute_incident_actions",
    "generate_ai_copilot_analysis",
    "get_connectors_map",
    "get_emulator_control_base_url",
    "get_incident_detail",
    "load_normalized_inventory",
    "locate_fault_on_cable_postgis",
    "run_10k_alarm_storm_benchmark",
    "sync_all_connectors",
]
