"""PostgreSQL + PostGIS + pgvector Normalized Relational Schema & Data Access Layer.

Replaces untyped JSON topology blobs with normalized 6-layer network inventory tables:
  - Layer 0 (OSP Civil): `osp_ducts`, `osp_manholes`
  - Layer 1 (Physical Fiber & Wet-Plant): `osp_cables`, `subsea_cables`, `rfts_units`
  - Layer 2 (DWDM Optical): `oms_links`, `optical_channels`
  - Layer 3 (IP/MPLS Core): `network_nodes`, `ip_links`
  - Layer 4 (RAN & GPON Access): `ran_sites`, `gpon_clusters`
  - Layer 5 (BSS & Commercial SLA): `customers`, `sla_tiers`, `customer_services`
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

from .adapters.embeddings import EMBEDDING_DIM, compute_text_embedding

DB_DSN = os.getenv("NOC_DB_DSN", "postgresql://noc:noc@127.0.0.1:5433/noc")
DEFAULT_EMULATOR_BASE = os.getenv("NOC_EMULATOR_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
RUNBOOKS_FILE = Path(__file__).resolve().parent / "knowledge" / "runbooks.json"


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS connectors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    oem_vendor TEXT NOT NULL,
    category TEXT NOT NULL,
    protocol TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'emulator',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'CONNECTED',
    latency_ms FLOAT DEFAULT 0.0,
    records_synced INTEGER DEFAULT 0,
    last_sync_at TIMESTAMPTZ,
    config_json JSONB DEFAULT '{{}}'::jsonb
);

-- Layer 0: Civil OSP Ducts & Manholes
CREATE TABLE IF NOT EXISTS osp_ducts (
    id TEXT PRIMARY KEY,
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    bridge TEXT,
    trench_length_m FLOAT NOT NULL,
    coords_json JSONB NOT NULL,
    geom GEOMETRY(LineString, 4326)
);

CREATE TABLE IF NOT EXISTS osp_manholes (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    lat FLOAT NOT NULL,
    lon FLOAT NOT NULL,
    slack_coil_m FLOAT NOT NULL,
    geom GEOMETRY(Point, 4326)
);

-- Layer 1: Fibre Cables, Subsea Systems & OTDR RFTS Units
CREATE TABLE IF NOT EXISTS osp_cables (
    id TEXT PRIMARY KEY,
    path_nodes JSONB NOT NULL,
    duct_ids JSONB NOT NULL,
    bridges JSONB NOT NULL,
    fibres INTEGER NOT NULL,
    role TEXT NOT NULL,
    helix_factor FLOAT NOT NULL,
    trench_length_m FLOAT NOT NULL,
    optical_length_m FLOAT NOT NULL,
    splices_json JSONB NOT NULL,
    coords_json JSONB NOT NULL,
    geom GEOMETRY(LineString, 4326)
);

CREATE TABLE IF NOT EXISTS subsea_cables (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cls_node TEXT NOT NULL,
    pfe_id TEXT NOT NULL,
    total_length_km FLOAT NOT NULL,
    repeater_count INTEGER NOT NULL,
    repeater_spacing_km FLOAT NOT NULL,
    design_capacity_tbps FLOAT NOT NULL,
    carried_services_json JSONB DEFAULT '[]'::jsonb,
    telemetry_json JSONB DEFAULT '{{}}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rfts_units (
    id TEXT PRIMARY KEY,
    vendor TEXT NOT NULL,
    connector_id TEXT NOT NULL,
    pop_node TEXT NOT NULL,
    monitored_cables_json JSONB NOT NULL
);

-- Layer 2: Optical Multiplex Sections & DWDM Wavelengths (OCh)
CREATE TABLE IF NOT EXISTS oms_links (
    id TEXT PRIMARY KEY,
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    cable_id TEXT NOT NULL,
    controller_vendor TEXT NOT NULL DEFAULT 'ciena'
);

CREATE TABLE IF NOT EXISTS optical_channels (
    id TEXT PRIMARY KEY,
    rate TEXT NOT NULL,
    freq_thz FLOAT NOT NULL,
    path_nodes_json JSONB NOT NULL,
    service_id TEXT,
    leg_name TEXT,
    controller_id TEXT NOT NULL DEFAULT 'ciena_mcp',
    operational_state TEXT NOT NULL DEFAULT 'UP',
    pm_json JSONB DEFAULT '{{}}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 3: Network Nodes (POPs, Junctions, Customer Sites, Cell Enclosures) & IP Links
CREATE TABLE IF NOT EXISTS network_nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    lat FLOAT NOT NULL,
    lon FLOAT NOT NULL,
    router_json JSONB DEFAULT '{{}}'::jsonb,
    optical_json JSONB DEFAULT '{{}}'::jsonb,
    geom GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS ip_links (
    id TEXT PRIMARY KEY,
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    underlay_id TEXT NOT NULL
);

-- Layer 4: 4G/5G RAN Sites & GPON OLT Splitter Clusters
CREATE TABLE IF NOT EXISTS ran_sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    vendor TEXT NOT NULL,
    controller_id TEXT NOT NULL,
    pop_anchor TEXT NOT NULL,
    hub_site_id TEXT,
    backhaul_type TEXT NOT NULL,
    backhaul_cable_id TEXT,
    mw_link_id TEXT,
    cells_json JSONB NOT NULL,
    downstream_tails_json JSONB NOT NULL,
    battery_backup_hours FLOAT DEFAULT 4.0,
    lat FLOAT,
    lon FLOAT,
    pm_json JSONB DEFAULT '{{}}'::jsonb,
    geom GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS gpon_clusters (
    id TEXT PRIMARY KEY,
    olt_id TEXT NOT NULL,
    pop_node TEXT NOT NULL,
    feeder_cable_id TEXT NOT NULL,
    ont_count INTEGER NOT NULL,
    district TEXT NOT NULL
);

-- Layer 5: Commercial BSS Customers, SLA Tiers & Provisioned Services
CREATE TABLE IF NOT EXISTS sla_tiers (
    tier_name TEXT PRIMARY KEY,
    availability_pct FLOAT NOT NULL,
    mttr_hours FLOAT NOT NULL,
    penalty_per_hour_aed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    name TEXT NOT NULL,
    segment TEXT NOT NULL,
    sla_tier TEXT NOT NULL,
    contact TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_services (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    service_type TEXT NOT NULL,
    bandwidth TEXT NOT NULL,
    ordered_diverse BOOLEAN NOT NULL DEFAULT FALSE,
    legs_json JSONB NOT NULL
);

-- Raw Connector Snapshot Cache (for wire-format inspection & UI compatibility)
CREATE TABLE IF NOT EXISTS topology_state (
    key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Operational Alarms, Correlated Incidents, Runbooks & Immutable Audit Log
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id TEXT PRIMARY KEY,
    incident_id TEXT,
    scenario_id TEXT,
    source_oem TEXT NOT NULL,
    protocol TEXT NOT NULL,
    layer TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    specific_problem TEXT NOT NULL,
    probable_cause TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    raised_at TIMESTAMPTZ NOT NULL,
    extra_json JSONB DEFAULT '{{}}'::jsonb
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
    severity TEXT NOT NULL,
    root_cause_type TEXT NOT NULL,
    root_cause_resource TEXT NOT NULL,
    root_cause_summary TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    alarm_count INTEGER NOT NULL DEFAULT 0,
    fault_location_json JSONB DEFAULT '{{}}'::jsonb,
    impact_json JSONB DEFAULT '{{}}'::jsonb,
    srlg_findings_json JSONB DEFAULT '[]'::jsonb,
    otdr_trace_json JSONB DEFAULT '{{}}'::jsonb,
    ai_copilot_json JSONB DEFAULT '{{}}'::jsonb,
    proposed_actions_json JSONB DEFAULT '[]'::jsonb,
    executed_actions_json JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runbooks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    oem_tags JSONB NOT NULL,
    symptoms TEXT NOT NULL,
    procedure_md TEXT NOT NULL,
    past_tickets_json JSONB NOT NULL,
    embedding vector({EMBEDDING_DIM})
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    detail_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def default_connectors() -> list[dict[str, Any]]:
    base = DEFAULT_EMULATOR_BASE
    kafka_broker = os.getenv("NOC_KAFKA_BOOTSTRAP", "127.0.0.1:19092")
    return [
        {
            "id": "ciena_mcp",
            "name": "Ciena MCP (Manage, Control and Plan 7.2)",
            "oem_vendor": "Ciena",
            "category": "DWDM / Optical Control",
            "protocol": "REST / OpenConfig gNMI / TMF642",
            "endpoint_url": f"{base}/ciena-mcp/nsa/api/v1",
            "mode": "emulator",
            "config_json": {"supports_hitless_reroute": True, "equipment": "Ciena 6500 ROADM / WaveLogic 5e"},
        },
        {
            "id": "nokia_nsp",
            "name": "Nokia NSP / WaveSuite Optical & IP",
            "oem_vendor": "Nokia",
            "category": "DWDM & IP/MPLS Control",
            "protocol": "RESTCONF / OpenConfig / TMF642",
            "endpoint_url": f"{base}/nokia-nsp",
            "mode": "emulator",
            "config_json": {"equipment": "Nokia 1830 PSS-32 & 7750 SR-7s"},
        },
        {
            "id": "nmsworks_cygnet",
            "name": "NMSWorks CygNet Unified OSS",
            "oem_vendor": "NMSWorks Software",
            "category": "Multi-Layer OSS & SIA",
            "protocol": "CygNet REST v2 / TMF639 / TMF642",
            "endpoint_url": f"{base}/nmsworks-cygnet/api/v2",
            "mode": "emulator",
            "config_json": {"domains": ["Core IP", "Enterprise CPE", "GPON Access", "RAN Transport"]},
        },
        {
            "id": "lepton_gis",
            "name": "Lepton SmartInventory / NetworkAccess GIS",
            "oem_vendor": "Lepton Software",
            "category": "Outside-Plant (OSP) GIS",
            "protocol": "OGC WFS 2.0 GeoJSON / PostGIS",
            "endpoint_url": f"{base}/lepton-gis/wfs",
            "mode": "emulator",
            "config_json": {"layers": ["osp:ducts", "osp:cables", "osp:manholes"], "slack_modeling": True},
        },
        {
            "id": "viavi_onmsi",
            "name": "VIAVI ONMSi Remote Fibre Test System (RFTS)",
            "oem_vendor": "VIAVI Solutions",
            "category": "OTDR / Fibre Monitoring",
            "protocol": "REST + Binary Telcordia SR-4731 Rev 2 (.sor)",
            "endpoint_url": f"{base}/viavi-onmsi/api/v1",
            "mode": "emulator",
            "config_json": {"wavelength_nm": 1625, "otu_model": "OTU-8000", "live_monitoring": True},
        },
        {
            "id": "exfo_nova",
            "name": "EXFO Nova Fiber OTDR Monitoring",
            "oem_vendor": "EXFO",
            "category": "OTDR / Fibre Monitoring",
            "protocol": "REST + Binary Telcordia SR-4731 Rev 2 (.sor)",
            "endpoint_url": f"{base}/exfo-nova/api/v1",
            "mode": "emulator",
            "config_json": {"wavelength_nm": 1625, "otu_model": "FG-750"},
        },
        {
            "id": "comviva_bss",
            "name": "Comviva BlueMarble / Ngage BSS & SLA",
            "oem_vendor": "Comviva",
            "category": "BSS / Customer & SLA Inventory",
            "protocol": "TMF629 Customer + TMF638 Service REST",
            "endpoint_url": f"{base}/comviva-bss/tmf-api",
            "mode": "emulator",
            "config_json": {"tracks_sla_penalties": True, "currency": "AED"},
        },
        {
            "id": "ericsson_enm",
            "name": "Ericsson Network Manager (ENM) 4G/5G RAN",
            "oem_vendor": "Ericsson",
            "category": "Mobile RAN (4G/5G gNodeB)",
            "protocol": "3GPP TS 28.532 / TS 32.435 XML / TMF642",
            "endpoint_url": f"{base}/ericsson-enm/api/v1",
            "mode": "emulator",
            "config_json": {"bands": ["n78 (3.5GHz)", "B3 (1800MHz)", "B20 (800MHz)"]},
        },
        {
            "id": "netbox_dcim",
            "name": "NetBox DCIM & Circuit Inventory",
            "oem_vendor": "NetBox Labs",
            "category": "DCIM / IPAM / Circuits",
            "protocol": "NetBox REST v4",
            "endpoint_url": f"{base}/netbox/api",
            "mode": "emulator",
            "config_json": {"sync_sites": True, "sync_circuits": True},
        },
        {
            "id": "cisco_juniper_stream",
            "name": "Cisco IOS-XR & Juniper Junos Trap/Syslog Receiver",
            "oem_vendor": "Cisco / Juniper / Huawei",
            "category": "IP/MPLS Core Telemetry",
            "protocol": "UDP Syslog RFC 5424 (:15514) + SNMPv2c Traps (:15162) + Kafka",
            "endpoint_url": "udp://127.0.0.1:15514,udp://127.0.0.1:15162",
            "mode": "live_listener",
            "config_json": {"kafka_topic": "noc.alarms.raw", "kafka_broker": kafka_broker},
        },
        {
            "id": "jira_sm",
            "name": "Jira Service Management (ITSM & Incident Queue)",
            "oem_vendor": "Atlassian",
            "category": "ITSM / Ticketing",
            "protocol": "Jira REST API v3 (/rest/api/3/issue)",
            "endpoint_url": f"{base}/jira",
            "mode": "emulator",
            "config_json": {"project_key": "NOC", "supports_cloud_api_token": True},
        },
        {
            "id": "servicenow_itsm",
            "name": "ServiceNow ITSM & Field Service (FSM)",
            "oem_vendor": "ServiceNow",
            "category": "ITSM / Field Dispatch / Change",
            "protocol": "ServiceNow Table API (/api/now/table/*)",
            "endpoint_url": f"{base}/servicenow",
            "mode": "emulator",
            "config_json": {"tables": ["incident", "wm_order", "change_request"]},
        },
    ]


def load_seed_runbooks() -> list[dict[str, Any]]:
    if not RUNBOOKS_FILE.exists():
        return []
    return json.loads(RUNBOOKS_FILE.read_text(encoding="utf-8"))


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Handle smooth migration if older 32-dim runbooks.embedding column exists
            cur.execute(
                """
                SELECT atttypmod FROM pg_attribute
                WHERE attrelid = 'runbooks'::regclass AND attname = 'embedding'
                """
            )
            att = cur.fetchone()
            if att and att["atttypmod"] not in (-1, EMBEDDING_DIM):
                cur.execute("ALTER TABLE runbooks DROP COLUMN embedding")
                cur.execute(f"ALTER TABLE runbooks ADD COLUMN embedding vector({EMBEDDING_DIM})")

            cur.execute(SCHEMA_SQL)

            for c in default_connectors():
                cur.execute(
                    """
                    INSERT INTO connectors (id, name, oem_vendor, category, protocol, endpoint_url, mode, config_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        c["id"],
                        c["name"],
                        c["oem_vendor"],
                        c["category"],
                        c["protocol"],
                        c["endpoint_url"],
                        c["mode"],
                        json.dumps(c["config_json"]),
                    ),
                )

            for rb in load_seed_runbooks():
                corpus = f"{rb['title']} {rb['domain']} {rb['symptoms']} {rb['procedure_md']}"
                emb_str = "[" + ",".join(str(x) for x in compute_text_embedding(corpus)) + "]"
                cur.execute(
                    """
                    INSERT INTO runbooks (id, title, domain, oem_tags, symptoms, procedure_md, past_tickets_json, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        domain = EXCLUDED.domain,
                        oem_tags = EXCLUDED.oem_tags,
                        symptoms = EXCLUDED.symptoms,
                        procedure_md = EXCLUDED.procedure_md,
                        past_tickets_json = EXCLUDED.past_tickets_json,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        rb["id"],
                        rb["title"],
                        rb["domain"],
                        json.dumps(rb["oem_tags"]),
                        rb["symptoms"],
                        rb["procedure_md"],
                        json.dumps(rb["past_tickets_json"]),
                        emb_str,
                    ),
                )


def log_audit(actor: str, action_type: str, target_id: str, detail: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (actor, action_type, target_id, detail_json)
                VALUES (%s, %s, %s, %s)
                """,
                (actor, action_type, target_id, json.dumps(detail)),
            )
