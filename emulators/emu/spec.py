"""Declarative Topology Dataset Loader for the Multi-OEM Emulator Suite.

Loads reference network inventory (nodes, ducts, cables, optical OMS/OCh,
IP links, RAN sites, GPON clusters, subsea systems, customers, SLA tiers,
and fault scenarios) from JSON dataset files (`emulators/datasets/*.json`),
supporting live runtime region switching (`uae_dubai`, `india_ncr`, or custom
`TELCO_DATASET_PATH`).

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

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
DEFAULT_DATASET_PATH = DATASETS_DIR / "dubai_metro.json"

REGION_DATASETS: dict[str, dict[str, Any]] = {
    "uae_dubai": {
        "region_id": "uae_dubai",
        "label": "UAE — Dubai Metro",
        "short_label": "UAE · Dubai",
        "currency": "AED",
        "path": str(DATASETS_DIR / "dubai_metro.json"),
    },
    "india_ncr": {
        "region_id": "india_ncr",
        "label": "India — Delhi NCR",
        "short_label": "India · Delhi NCR",
        "currency": "INR",
        "path": str(DATASETS_DIR / "delhi_ncr_metro.json"),
    },
}


def load_topology_dataset(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or os.getenv("TELCO_DATASET_PATH", str(DEFAULT_DATASET_PATH)))
    if not target.exists():
        raise FileNotFoundError(f"Topology dataset file not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


DATASET: dict[str, Any] = {}
OPERATOR_PROFILES: dict[str, dict[str, Any]] = {}
NODES: dict[str, dict[str, Any]] = {}
DUCTS: list[dict[str, Any]] = []
CABLES: list[dict[str, Any]] = []
OPTICAL: dict[str, str] = {}
OMS: list[tuple[str, str, str]] = []
WAVELENGTHS: list[dict[str, Any]] = []
ROUTERS: dict[str, tuple[str, str]] = {}
IP_LINKS: list[tuple[str, str, str]] = []
RAN_SITES: list[dict[str, Any]] = []
GPON_SPLITTER_CLUSTERS: list[dict[str, Any]] = []
CUSTOMERS: list[dict[str, Any]] = []
SLA_TIERS: dict[str, dict[str, Any]] = {}
SERVICES: list[dict[str, Any]] = []
RFTS: list[dict[str, Any]] = []
SUBSEA_SYSTEMS: list[dict[str, Any]] = []
FAULT_SCENARIOS: list[dict[str, Any]] = []


def _apply_dataset_in_place(raw: dict[str, Any]) -> dict[str, Any]:
    """Mutate module-level collections in-place so all importers see the new region immediately."""
    DATASET.clear()
    DATASET.update(raw)

    OPERATOR_PROFILES.clear()
    OPERATOR_PROFILES.update(raw["operator_profiles"])

    NODES.clear()
    NODES.update(raw["nodes"])

    DUCTS[:] = list(raw["ducts"])
    CABLES[:] = list(raw["cables"])

    OPTICAL.clear()
    OPTICAL.update(raw["optical_controllers"])

    OMS[:] = [(item["a"], item["b"], item["cable_id"]) for item in raw["oms_links"]]
    WAVELENGTHS[:] = list(raw["wavelengths"])

    ROUTERS.clear()
    ROUTERS.update({nid: (cfg["vendor"], cfg["model"]) for nid, cfg in raw["routers"].items()})

    IP_LINKS[:] = [(item["a"], item["b"], item["transport"]) for item in raw["ip_links"]]
    RAN_SITES[:] = list(raw["ran_sites"])
    GPON_SPLITTER_CLUSTERS[:] = list(raw["gpon_splitter_clusters"])
    CUSTOMERS[:] = list(raw["customers"])

    SLA_TIERS.clear()
    SLA_TIERS.update(raw["sla_tiers"])

    SERVICES[:] = list(raw["services"])
    RFTS[:] = list(raw["rfts"])
    SUBSEA_SYSTEMS[:] = list(raw["subsea_systems"])
    FAULT_SCENARIOS[:] = list(raw["fault_scenarios"])
    return DATASET


def reload_dataset(region_id: str | None = None, path: str | Path | None = None) -> dict[str, Any]:
    if region_id:
        if region_id not in REGION_DATASETS:
            raise ValueError(f"Unknown region_id '{region_id}'. Available: {list(REGION_DATASETS)}")
        raw = load_topology_dataset(REGION_DATASETS[region_id]["path"])
    else:
        raw = load_topology_dataset(path)
    return _apply_dataset_in_place(raw)


def list_available_regions() -> list[dict[str, Any]]:
    return [
        {
            "region_id": cfg["region_id"],
            "label": cfg["label"],
            "short_label": cfg["short_label"],
            "currency": cfg["currency"],
        }
        for cfg in REGION_DATASETS.values()
    ]


# Initial load on module import
reload_dataset()
