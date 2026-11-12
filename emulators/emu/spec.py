"""Declarative Topology Dataset Loader for the Multi-OEM Emulator Suite.

Loads reference network inventory (nodes, ducts, cables, optical OMS/OCh,
IP links, RAN sites, GPON clusters, subsea systems, customers, SLA tiers,
and fault scenarios) from a JSON dataset file (`TELCO_DATASET_PATH`,
defaulting to `emulators/datasets/dubai_metro.json`).

IMPORTANT ARCHITECTURAL INVARIANT:
The NOC Copilot backend (`backend/app/`) NEVER imports this module or reads
dataset files directly — it discovers topology, GIS geometry, OTDR `.sor`
traces, alarms, and SLAs strictly via southbound connector adapters!
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "dubai_metro.json"


def load_topology_dataset(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or os.getenv("TELCO_DATASET_PATH", str(DEFAULT_DATASET_PATH)))
    if not target.exists():
        raise FileNotFoundError(f"Topology dataset file not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


DATASET: dict[str, Any] = load_topology_dataset()

OPERATOR_PROFILES: dict[str, dict[str, Any]] = DATASET["operator_profiles"]
NODES: dict[str, dict[str, Any]] = DATASET["nodes"]
DUCTS: list[dict[str, Any]] = DATASET["ducts"]
CABLES: list[dict[str, Any]] = DATASET["cables"]
OPTICAL: dict[str, str] = DATASET["optical_controllers"]
OMS: list[tuple[str, str, str]] = [
    (item["a"], item["b"], item["cable_id"]) for item in DATASET["oms_links"]
]
WAVELENGTHS: list[dict[str, Any]] = DATASET["wavelengths"]
ROUTERS: dict[str, tuple[str, str]] = {
    nid: (cfg["vendor"], cfg["model"]) for nid, cfg in DATASET["routers"].items()
}
IP_LINKS: list[tuple[str, str, str]] = [
    (item["a"], item["b"], item["transport"]) for item in DATASET["ip_links"]
]
RAN_SITES: list[dict[str, Any]] = DATASET["ran_sites"]
GPON_SPLITTER_CLUSTERS: list[dict[str, Any]] = DATASET["gpon_splitter_clusters"]
CUSTOMERS: list[dict[str, Any]] = DATASET["customers"]
SLA_TIERS: dict[str, dict[str, Any]] = DATASET["sla_tiers"]
SERVICES: list[dict[str, Any]] = DATASET["services"]
RFTS: list[dict[str, Any]] = DATASET["rfts"]
SUBSEA_SYSTEMS: list[dict[str, Any]] = DATASET["subsea_systems"]
FAULT_SCENARIOS: list[dict[str, Any]] = DATASET["fault_scenarios"]
