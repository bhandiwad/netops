"""PostgreSQL + PostGIS + pgvector schema and database access layer."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

DB_DSN = os.getenv("NOC_DB_DSN", "postgresql://noc:noc@127.0.0.1:5433/noc")


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


SCHEMA_SQL = """
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
    config_json JSONB DEFAULT '{}'::jsonb
);

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

CREATE TABLE IF NOT EXISTS topology_state (
    key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

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
    extra_json JSONB DEFAULT '{}'::jsonb
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
    fault_location_json JSONB DEFAULT '{}'::jsonb,
    impact_json JSONB DEFAULT '{}'::jsonb,
    srlg_findings_json JSONB DEFAULT '[]'::jsonb,
    otdr_trace_json JSONB DEFAULT '{}'::jsonb,
    ai_copilot_json JSONB DEFAULT '{}'::jsonb,
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
    embedding vector(32)
);
ALTER TABLE runbooks ADD COLUMN IF NOT EXISTS embedding vector(32);


CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    detail_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


DEFAULT_CONNECTORS: list[dict[str, Any]] = [
    {
        "id": "ciena_mcp",
        "name": "Ciena MCP (Manage, Control and Plan 7.2)",
        "oem_vendor": "Ciena",
        "category": "DWDM / Optical Control",
        "protocol": "REST / OpenConfig gNMI / TMF642",
        "endpoint_url": "http://127.0.0.1:8001/ciena-mcp/nsa/api/v1",
        "mode": "emulator",
        "config_json": {"supports_hitless_reroute": True, "equipment": "Ciena 6500 ROADM / WaveLogic 5e"},
    },
    {
        "id": "nokia_nsp",
        "name": "Nokia NSP / WaveSuite Optical & IP",
        "oem_vendor": "Nokia",
        "category": "DWDM & IP/MPLS Control",
        "protocol": "RESTCONF / OpenConfig / TMF642",
        "endpoint_url": "http://127.0.0.1:8001/nokia-nsp",
        "mode": "emulator",
        "config_json": {"equipment": "Nokia 1830 PSS-32 & 7750 SR-7s"},
    },
    {
        "id": "nmsworks_cygnet",
        "name": "NMSWorks CygNet Unified OSS",
        "oem_vendor": "NMSWorks Software",
        "category": "Multi-Layer OSS & SIA",
        "protocol": "CygNet REST v2 / TMF639 / TMF642",
        "endpoint_url": "http://127.0.0.1:8001/nmsworks-cygnet/api/v2",
        "mode": "emulator",
        "config_json": {"domains": ["Core IP", "Enterprise CPE", "GPON Access", "RAN Transport"]},
    },
    {
        "id": "lepton_gis",
        "name": "Lepton SmartInventory / NetworkAccess GIS",
        "oem_vendor": "Lepton Software",
        "category": "Outside-Plant (OSP) GIS",
        "protocol": "OGC WFS 2.0 GeoJSON / PostGIS",
        "endpoint_url": "http://127.0.0.1:8001/lepton-gis/wfs",
        "mode": "emulator",
        "config_json": {"layers": ["osp:ducts", "osp:cables", "osp:manholes"], "slack_modeling": True},
    },
    {
        "id": "viavi_onmsi",
        "name": "VIAVI ONMSi Remote Fibre Test System (RFTS)",
        "oem_vendor": "VIAVI Solutions",
        "category": "OTDR / Fibre Monitoring",
        "protocol": "REST + Binary Telcordia SR-4731 Rev 2 (.sor)",
        "endpoint_url": "http://127.0.0.1:8001/viavi-onmsi/api/v1",
        "mode": "emulator",
        "config_json": {"wavelength_nm": 1625, "otu_model": "OTU-8000", "live_monitoring": True},
    },
    {
        "id": "exfo_nova",
        "name": "EXFO Nova Fiber OTDR Monitoring",
        "oem_vendor": "EXFO",
        "category": "OTDR / Fibre Monitoring",
        "protocol": "REST + Binary Telcordia SR-4731 Rev 2 (.sor)",
        "endpoint_url": "http://127.0.0.1:8001/exfo-nova/api/v1",
        "mode": "emulator",
        "config_json": {"wavelength_nm": 1625, "otu_model": "FG-750"},
    },
    {
        "id": "comviva_bss",
        "name": "Comviva BlueMarble / Ngage BSS & SLA",
        "oem_vendor": "Comviva",
        "category": "BSS / Customer & SLA Inventory",
        "protocol": "TMF629 Customer + TMF638 Service REST",
        "endpoint_url": "http://127.0.0.1:8001/comviva-bss/tmf-api",
        "mode": "emulator",
        "config_json": {"tracks_sla_penalties": True, "currency": "AED"},
    },
    {
        "id": "ericsson_enm",
        "name": "Ericsson Network Manager (ENM) 4G/5G RAN",
        "oem_vendor": "Ericsson",
        "category": "Mobile RAN (4G/5G gNodeB)",
        "protocol": "3GPP TS 28.532 / TMF642",
        "endpoint_url": "http://127.0.0.1:8001/ericsson-enm/api/v1",
        "mode": "emulator",
        "config_json": {"bands": ["n78 (3.5GHz)", "B3 (1800MHz)", "B20 (800MHz)"]},
    },
    {
        "id": "netbox_dcim",
        "name": "NetBox DCIM & Circuit Inventory",
        "oem_vendor": "NetBox Labs",
        "category": "DCIM / IPAM / Circuits",
        "protocol": "NetBox REST v4",
        "endpoint_url": "http://127.0.0.1:8001/netbox/api",
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
        "config_json": {"kafka_topic": "noc.alarms.raw", "kafka_broker": "127.0.0.1:19092"},
    },
    {
        "id": "jira_sm",
        "name": "Jira Service Management (ITSM & Incident Queue)",
        "oem_vendor": "Atlassian",
        "category": "ITSM / Ticketing",
        "protocol": "Jira REST API v3 (/rest/api/3/issue)",
        "endpoint_url": "http://127.0.0.1:8001/jira",
        "mode": "emulator",
        "config_json": {"project_key": "NOC", "supports_cloud_api_token": True},
    },
    {
        "id": "servicenow_itsm",
        "name": "ServiceNow ITSM & Field Service (FSM)",
        "oem_vendor": "ServiceNow",
        "category": "ITSM / Field Dispatch / Change",
        "protocol": "ServiceNow Table API (/api/now/table/*)",
        "endpoint_url": "http://127.0.0.1:8001/servicenow",
        "mode": "emulator",
        "config_json": {"tables": ["incident", "wm_order", "change_request"]},
    },
]

DEFAULT_RUNBOOKS: list[dict[str, Any]] = [
    {
        "id": "RB-OSP-001",
        "title": "Metro Trunk Fibre Cut Localization, SRLG Audit & Hitless DWDM Restoration",
        "domain": "fibre_osp",
        "oem_tags": ["VIAVI ONMSi", "Lepton GIS", "Ciena MCP", "NMSWorks CygNet"],
        "symptoms": "OTS_LOS_LINE_FAIL, OCH_LOF_CHANNEL_DOWN, INTERFACE_LINK_BFD_DOWN, OTDR_REFLECTIVE_FIBER_BREAK",
        "procedure_md": (
            "1. **Verify Optical Break via RFTS:** Pull latest 1625nm `.sor` trace from VIAVI ONMSi / EXFO Nova.\n"
            "2. **Convert Optical Distance to Street Coordinates:** Subtract cumulative manhole slack coils "
            "(`slack_coil_m` in Lepton GIS) and divide by cable helical stranding factor (`1.015`) before walking "
            "PostGIS duct geometry.\n"
            "3. **Audit Shared-Risk Link Groups (SRLG):** Check if any impacted 1+1 wavelength or dual-homed L3VPN "
            "has its backup leg traversing the same cut duct or bridge.\n"
            "4. **Execute Hitless DWDM Restoration (Gated):** For dual-affected wavelengths (e.g., `OCH-JLC-P`), "
            "re-provision optical path over disjoint East/Inland ring via Ciena MCP REST API.\n"
            "5. **Dispatch OSP Splice Crew:** Open ServiceNow Field Work Order (`wm_order`) with exact manhole brackets "
            "and GPS coordinates, and log master incident in Jira Service Management (`NOC`)."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0084119",
                "date": "2026-08-14",
                "summary": "SZR Interchange 2 civil works cut 144F trunk; initial crew sent 240m off due to unsubtracted manhole slack coils. Always apply slack correction from Lepton GIS.",
                "mttr_hours": 3.2,
            },
            {
                "ticket_id": "INC0087902",
                "date": "2026-09-29",
                "summary": "Jebel Ali 100G wavelength lost both working & protect legs on QZ-BB span; restored in 4 mins via Ciena MCP reroute after engineer approval.",
                "mttr_hours": 0.4,
            },
        ],
    },
    {
        "id": "RB-GPON-002",
        "title": "GPON / Enterprise Mass Outage Triage: 'Dying Gasp' Power Loss vs. Feeder Fibre Cut",
        "domain": "gpon_access",
        "oem_tags": ["NMSWorks CygNet", "GenieACS", "VIAVI ONMSi"],
        "symptoms": "GPON_MASS_ONT_DYING_GASP, CPE_POWER_DOWN_DYING_GASP, OTDR_CONTINUITY_VERIFIED_NO_CUT",
        "procedure_md": (
            "1. **Check OLT Dying-Gasp Ratio:** If >= 80% of offline ONTs/CPEs on a splitter or access cable emitted "
            "G.984 PLOAM `dying-gasp` or 802.3ah power-fail frames within a 1-second window, suspect commercial AC power failure.\n"
            "2. **Corroborate with On-Demand OTDR:** Trigger VIAVI ONMSi 1625nm out-of-band trace on feeder cable. "
            "If end-to-end continuity is intact with normal insertion loss, **DO NOT dispatch an OSP fibre crew**.\n"
            "3. **Action:** Log power-outage advisory ticket in Jira/ServiceNow and notify customer facility contact."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0085310",
                "date": "2026-07-22",
                "summary": "DEWA substation trip in Al Quoz caused 24 ONTs to drop with dying-gasp; avoided AED 4,500 emergency fibre contractor callout by verifying OTDR continuity first.",
                "mttr_hours": 1.1,
            }
        ],
    },
    {
        "id": "RB-OPT-003",
        "title": "Proactive DWDM Pre-FEC BER & OSNR Degradation Remediation",
        "domain": "dwdm_optical",
        "oem_tags": ["Nokia NSP", "Ciena MCP", "EXFO Nova"],
        "symptoms": "OPTICAL_PRE_FEC_BER_TCA_BREACH, OTDR_NON_REFLECTIVE_HIGH_SPLICE_LOSS",
        "procedure_md": (
            "1. **Inspect Pre-FEC BER Slope:** When 15-min Pre-FEC BER crosses `1e-4` while Post-FEC errors are still "
            "zero, the wavelength is within ~1 dB of an uncorrectable cliff.\n"
            "2. **Locate Non-Reflective Pinch/Macro-Bend:** Correlate with EXFO/VIAVI OTDR non-reflective step loss "
            "to identify the specific splice closure where fiber pinch occurred.\n"
            "3. **Action:** Proactively shift wavelength to protection path during maintenance/approval window and "
            "schedule preventive splice re-seat at the identified manhole chamber."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0088204",
                "date": "2026-10-04",
                "summary": "Prevented SLA breach on Silicon Oasis 100G DCI wave by rerouting on Pre-FEC BER TCA alert 40 minutes before complete span loss.",
                "mttr_hours": 0.0,
            }
        ],
    },
    {
        "id": "RB-RAN-004",
        "title": "5G Hub Site Rectifier AC Mains Loss, Battery LVD Countdown & Generator Dispatch",
        "domain": "mobile_ran",
        "oem_tags": ["Ericsson ENM", "VIAVI ONMSi", "ServiceNow FSM"],
        "symptoms": "RAN_RECTIFIER_AC_MAINS_FAIL_LVD_COUNTDOWN, RAN_ENCLOSURE_HIGH_TEMP_HVAC_OFF, BATTERY_DISCHARGE",
        "procedure_md": (
            "1. **Verify Backhaul Fibre Integrity:** Confirm via VIAVI ONMSi that the hub site optical backhaul is intact (ruling out transport fault).\n"
            "2. **Calculate LVD Time-to-Dark:** Monitor 3GPP TS 32.435 `Enclosure.DcBusVoltageV` slope against the `43.2V` Low-Voltage Disconnect threshold.\n"
            "3. **Protect Daisy-Chained Tail Sites:** Identify downstream tail gNodeBs (`RAN_BB_T1`, `RAN_BB_T2`) anchored to the hub CSR.\n"
            "4. **Dispatch Mobile Diesel Generator:** Issue Priority-1 ServiceNow Field Work Order (`wm_order`) to Mobile Power Response Team before LVD trip."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0089112",
                "date": "2026-09-11",
                "summary": "Business Bay hub rectifier breaker trip; mobile generator connected at 43.5V (11 mins before LVD), saving 3 5G sites and 9 sectors from outage.",
                "mttr_hours": 0.6,
            }
        ],
    },
    {
        "id": "RB-MW-005",
        "title": "80 GHz E-Band Microwave Rain-Fade (ACM Downshift) vs. Hardware Transceiver Fault",
        "domain": "mobile_ran",
        "oem_tags": ["Nokia NSP", "Nokia Wavence", "NMSWorks CygNet"],
        "symptoms": "MW_EBAND_RSL_DEEP_FADE_ACM_QPSK, BACKHAUL_QOS_BE_QUEUE_TAIL_DROP, RAIN_ATTENUATION",
        "procedure_md": (
            "1. **Distinguish Weather Fade from ODU Hardware Fault:** Check local TX output power (`+18.0 dBm` nominal) and correlate RSL drop across co-located/adjacent E-band hops.\n"
            "2. **Verify Adaptive Coding & Modulation (ACM) Lock:** Confirm link held carrier lock by downshifting `1024QAM -> QPSK` and DiffServ EF queue is protecting 5G VoNR & F1-C control plane.\n"
            "3. **Suppress Hardware Truck Roll:** Do NOT dispatch tower climbers or swap ODU hardware during active convective rain squall; hold ticket in auto-clear watch window."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0086405",
                "date": "2026-08-03",
                "summary": "Academic City 80GHz hop downshifted to QPSK during 40mm/hr rain cell; auto-recovered to 1024QAM in 22 mins with zero hardware fault.",
                "mttr_hours": 0.3,
            }
        ],
    },
    {
        "id": "RB-SUBSEA-006",
        "title": "Subsea Wet-Plant Repeater Shunt Fault, PFE Rebalance & C-OTDR Localization",
        "domain": "dwdm_optical",
        "oem_tags": ["Ciena MCP", "Subsea PFE", "NMSWorks CygNet"],
        "symptoms": "SUBSEA_PFE_SHUNT_FAULT_REPEATER_SPAN, WHOLESALE_DCI_SUBSEA_PROTECTION_ALERT, COTDR_SHUNT",
        "procedure_md": (
            "1. **Pinpoint Wet-Plant Shunt via PFE Voltage/Current Ratio & C-OTDR:** Combine Cable Landing Station PFE voltage drop (`4120V -> 2890V` at `950mA`) with Coherent OTDR trace to isolate the repeater span and water depth.\n"
            "2. **Reconfigure PFE Polarity:** Switch Jebel Ali CLS `PFE-JBL-01` to single-end constant-current feeding to stabilize optical repeater pump current.\n"
            "3. **Reroute Wholesale 100G/400G DCI Waves:** Shift affected subsea wavelengths onto diverse terrestrial/subsea protection paths via Ciena MCP and notify marine depot."
        ),
        "past_tickets_json": [
            {
                "ticket_id": "INC0083019",
                "date": "2026-06-18",
                "summary": "Repeater Span R07-R08 insulation shunt at 68m depth localized within 400m via C-OTDR; zero customer SLA breach after Ciena MCP wavelength switch.",
                "mttr_hours": 0.5,
            }
        ],
    },
]

SEMANTIC_DIMENSIONS: list[tuple[str, ...]] = [
    ("fibre", "fiber", "cut", "break", "cable", "duct", "trench"),
    ("otdr", "sor", "reflective", "viavi", "exfo", "backscatter"),
    ("slack", "manhole", "helix", "lepton", "postgis", "chamber"),
    ("srlg", "diverse", "diversity", "shared", "redundancy", "dual"),
    ("dying_gasp", "gasp", "ploam", "ont", "gpon", "olt", "genieacs"),
    ("commercial", "substation", "premises", "blackout", "utility"),
    ("pre_fec", "ber", "osnr", "tca", "degradation", "fec"),
    ("splice", "macro", "bend", "pinched", "attenuation", "non_reflective"),
    ("rectifier", "battery", "lvd", "dc_bus", "vrla", "voltage"),
    ("generator", "hvac", "enclosure", "thermal", "cascade", "tail"),
    ("microwave", "eband", "80ghz", "wavence", "odu", "rsl"),
    ("rain", "weather", "acm", "qpsk", "1024qam", "squall", "fade"),
    ("subsea", "wet_plant", "cls", "pfe", "shunt", "repeater", "cotdr"),
    ("marine", "seaward", "leakage", "depth", "branching"),
    ("ciena", "mcp", "roadm", "wavelogic", "och", "oms"),
    ("nokia", "nsp", "1830", "7750", "openconfig", "gnmi"),
    ("ericsson", "enm", "gnb", "5g", "cell", "prb", "rrc"),
    ("cisco", "juniper", "bgp", "bfd", "isis", "mpls", "l3vpn"),
    ("nmsworks", "cygnet", "oss", "sia", "topology"),
    ("comviva", "bss", "sla", "platinum", "penalty", "customer"),
    ("jira", "servicenow", "dispatch", "work_order", "truck"),
    ("reroute", "hitless", "protection", "restoration", "bypass"),
    ("qos", "diffserv", "vonr", "queue", "drop"),
    ("alarm", "storm", "correlation", "root_cause", "copilot"),
    ("bridge", "canal", "szr", "difc", "jebel_ali"),
    ("al_quoz", "silicon_oasis", "karama", "business_bay", "marina"),
    ("100g", "400g", "dci", "wavelength", "wholesale"),
    ("snmp", "syslog", "trap", "kafka", "tmf642"),
    ("3gpp", "xml", "pm", "counter", "telemetry"),
    ("power", "ac_mains", "outage", "suppress", "no_cut"),
    ("critical", "major", "emergency", "mttr"),
    ("runbook", "mop", "procedure", "audit"),
]


def compute_text_embedding_32d(text: str) -> list[float]:
    """Deterministic 32-dimensional normalized telecom semantic vector for pgvector cosine search."""
    import math
    lowered = text.lower().replace("-", "_")
    vec: list[float] = []
    for kw_group in SEMANTIC_DIMENSIONS:
        score = sum(lowered.count(kw) for kw in kw_group)
        vec.append(float(score) + 0.01)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            for c in DEFAULT_CONNECTORS:
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
            for rb in DEFAULT_RUNBOOKS:
                corpus = f"{rb['title']} {rb['domain']} {rb['symptoms']} {rb['procedure_md']}"
                emb_str = "[" + ",".join(str(x) for x in compute_text_embedding_32d(corpus)) + "]"
                cur.execute(
                    """
                    INSERT INTO runbooks (id, title, domain, oem_tags, symptoms, procedure_md, past_tickets_json, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
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
