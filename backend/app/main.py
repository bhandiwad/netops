"""NOC Copilot FastAPI Application.

Runs UDP Syslog (:15514), UDP SNMPv2c Trap (:15162), and Redpanda/Kafka consumers,
syncs southbound OEM connectors into normalized PostgreSQL/PostGIS tables,
correlates multi-layer alarms via causal graph clustering + pluggable classifiers,
parses binary SR-4731 .sor OTDR files, audits SRLG diversity, and executes
human-approved northbound actions.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from shared.sor_codec import parse_sor_bytes
from .adapters.registry import (
    DatabaseBackedOtdrAdapter,
    get_connectors_map,
    get_emulator_control_base_url,
    invalidate_connectors_cache,
    sync_all_connectors,
)
from .correlation import (
    LLM_CONFIG,
    correlate_alarms_into_incidents,
    execute_incident_actions,
    generate_ai_copilot_analysis,
    get_incident_detail,
)
from .db import get_conn, init_db, log_audit
from .routing import (
    audit_all_srlg_diversity,
    build_multilayer_dependency_graph,
    run_10k_alarm_storm_benchmark,
)
from .schemas import (
    ConnectorUpdatePayload,
    LlmConfigPayload,
    StormBenchmarkPayload,
    TriggerFaultPayload,
)
from .spatial import import_kml_osp_routes, locate_fault_on_cable_postgis, parse_alarms_csv

app = FastAPI(title="Telco Network Operations Copilot API", version="2.1.0")
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RECENT_WIRE_PACKETS: list[dict[str, Any]] = []
LAST_BENCHMARK_RESULT: dict[str, Any] | None = None
_OVERVIEW_CACHE: dict[str, Any] | None = None
KAFKA_BOOTSTRAP = os.getenv("NOC_KAFKA_BOOTSTRAP", "127.0.0.1:19092")
KAFKA_TOPIC = os.getenv("NOC_KAFKA_TOPIC", "noc.alarms.raw")


def invalidate_overview_cache() -> None:
    global _OVERVIEW_CACHE
    _OVERVIEW_CACHE = None


async def _kafka_consumer_worker() -> None:
    """Active background Kafka consumer reading from Redpanda topic `noc.alarms.raw`."""
    while True:
        consumer = None
        try:
            host, port_str = KAFKA_BOOTSTRAP.split(":")
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port_str)), timeout=0.35)
            writer.close()
            await writer.wait_closed()

            from aiokafka import AIOKafkaConsumer
            consumer = AIOKafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="noc-copilot-correlator",
                auto_offset_reset="latest",
                request_timeout_ms=2500,
                retry_backoff_ms=2000,
            )
            await asyncio.wait_for(consumer.start(), timeout=2.5)
            async for msg in consumer:
                val_str = msg.value.decode("utf-8", errors="replace") if msg.value else "{}"
                RECENT_WIRE_PACKETS.append({
                    "protocol": f"Kafka/{msg.topic} [p{msg.partition}:o{msg.offset}]",
                    "port": 19092,
                    "source_ip": "127.0.0.1",
                    "payload": val_str[:260],
                })
                if len(RECENT_WIRE_PACKETS) > 100:
                    RECENT_WIRE_PACKETS.pop(0)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(15.0)
        finally:
            if consumer is not None:
                try:
                    await consumer.stop()
                except Exception:
                    pass


class _SyslogUdpProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        msg = data.decode("utf-8", errors="replace")
        RECENT_WIRE_PACKETS.append({
            "protocol": "UDP-Syslog-RFC5424",
            "port": 15514,
            "source_ip": addr[0],
            "payload": msg,
        })
        if len(RECENT_WIRE_PACKETS) > 100:
            RECENT_WIRE_PACKETS.pop(0)


class _SnmpTrapUdpProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        msg = data.decode("utf-8", errors="replace")
        RECENT_WIRE_PACKETS.append({
            "protocol": "UDP-SNMPv2c-Trap",
            "port": 15162,
            "source_ip": addr[0],
            "payload": msg,
        })
        if len(RECENT_WIRE_PACKETS) > 100:
            RECENT_WIRE_PACKETS.pop(0)


async def _db_pool_keepalive_worker() -> None:
    """Keep primary pooled PostgreSQL socket warm (<12s idle) across Docker Desktop gVisor NAT windows."""
    while True:
        await asyncio.sleep(8.0)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    loop = asyncio.get_running_loop()
    try:
        await loop.create_datagram_endpoint(_SyslogUdpProtocol, local_addr=("127.0.0.1", 15514))
    except Exception:
        pass
    try:
        await loop.create_datagram_endpoint(_SnmpTrapUdpProtocol, local_addr=("127.0.0.1", 15162))
    except Exception:
        pass
    asyncio.create_task(_db_pool_keepalive_worker())
    if os.getenv("NOC_ENABLE_KAFKA", "0") == "1":
        asyncio.create_task(_kafka_consumer_worker())
    try:
        await sync_all_connectors()
        await get_overview()
    except Exception:
        pass


@app.get("/", response_class=HTMLResponse)
async def backend_landing_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Pandita — Assurance Backend API (:8002)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; max-width: 760px; margin: 40px auto; padding: 0 24px; color: #111827; line-height: 1.55; background: #f8f9fb; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 22px 24px; }
    h1 { font-size: 20px; margin: 0 0 6px 0; }
    p { font-size: 13.5px; color: #4b5563; margin: 0 0 14px 0; }
    .btn { display: inline-block; padding: 7px 14px; border-radius: 8px; background: #111827; color: #fff; text-decoration: none; font-size: 12.5px; font-weight: 500; margin-right: 8px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Fibre Assurance &amp; NOC Backend API (:8002)</h1>
    <p>Core correlation, PostGIS slack localization, binary <code>.sor</code> parsing, and northbound orchestration engine.</p>
    <a class="btn" href="/docs">Open API Swagger (/docs)</a>
    <a class="btn" style="background:#374151;" href="/api/v1/overview">View Live JSON State (/api/v1/overview)</a>
    <a class="btn" style="background:#4b5563;" href="http://127.0.0.1:5173">Open Web UI (:5173)</a>
  </div>
</body>
</html>"""


@app.get("/api/v1/overview")
async def get_overview() -> dict[str, Any]:
    global _OVERVIEW_CACHE
    if _OVERVIEW_CACHE is not None:
        return {
            **_OVERVIEW_CACHE,
            "last_benchmark": LAST_BENCHMARK_RESULT,
            "wire_packets": list(reversed(RECENT_WIRE_PACKETS[-25:])),
            "llm_config": {
                "provider": LLM_CONFIG["provider"],
                "model": LLM_CONFIG["model"],
                "api_key_configured": bool(LLM_CONFIG.get("api_key")),
            },
        }

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT json_build_object(
                    'connectors', COALESCE((SELECT json_agg(t) FROM (SELECT * FROM connectors ORDER BY id) t), '[]'::json),
                    'ducts', COALESCE((SELECT json_agg(t) FROM (SELECT id, node_a, node_b, bridge, trench_length_m, coords_json FROM osp_ducts ORDER BY id) t), '[]'::json),
                    'manholes', COALESCE((SELECT json_agg(t) FROM (SELECT id, node_id, name, kind, lat, lon, slack_coil_m FROM osp_manholes ORDER BY id) t), '[]'::json),
                    'cables', COALESCE((SELECT json_agg(t) FROM (SELECT id, path_nodes, duct_ids, bridges, fibres, role, helix_factor, trench_length_m, optical_length_m, splices_json, coords_json FROM osp_cables ORDER BY id) t), '[]'::json),
                    'tstates', COALESCE((SELECT json_object_agg(key, payload) FROM topology_state), '{}'::json),
                    'inc_rows', COALESCE((SELECT json_agg(t) FROM (SELECT * FROM incidents ORDER BY updated_at DESC) t), '[]'::json),
                    'alarms', COALESCE((SELECT json_agg(t) FROM (SELECT * FROM alarms ORDER BY raised_at DESC LIMIT 200) t), '[]'::json),
                    'runbooks', COALESCE((SELECT json_agg(t) FROM (SELECT id, title, domain, oem_tags, symptoms, procedure_md, past_tickets_json FROM runbooks ORDER BY id) t), '[]'::json),
                    'audits', COALESCE((SELECT json_agg(t) FROM (SELECT * FROM audit_log ORDER BY id DESC LIMIT 40) t), '[]'::json),
                    'net_nodes', COALESCE((SELECT json_agg(t) FROM (SELECT id, name, kind, lat, lon, router_json, optical_json FROM network_nodes) t), '[]'::json),
                    'oms_links', COALESCE((SELECT json_agg(t) FROM oms_links t), '[]'::json),
                    'wavelengths', COALESCE((SELECT json_agg(t) FROM optical_channels t), '[]'::json),
                    'ip_links', COALESCE((SELECT json_agg(t) FROM ip_links t), '[]'::json),
                    'ran_sites', COALESCE((SELECT json_agg(t) FROM (SELECT id, name, vendor, controller_id, pop_anchor, hub_site_id, backhaul_type, backhaul_cable_id, mw_link_id, cells_json, downstream_tails_json, battery_backup_hours, lat, lon, pm_json FROM ran_sites) t), '[]'::json),
                    'gpon_clusters', COALESCE((SELECT json_agg(t) FROM gpon_clusters t), '[]'::json),
                    'subsea_cables', COALESCE((SELECT json_agg(t) FROM subsea_cables t), '[]'::json),
                    'sla_tiers', COALESCE((SELECT json_agg(t) FROM sla_tiers t), '[]'::json),
                    'customers', COALESCE((SELECT json_agg(t) FROM customers t), '[]'::json),
                    'rfts_rows', COALESCE((SELECT json_agg(t) FROM (SELECT id, vendor, pop_node, monitored_cables_json FROM rfts_units) t), '[]'::json),
                    'services', COALESCE((SELECT json_agg(t) FROM customer_services t), '[]'::json)
                ) AS bundle
                """
            )
            bundle = (cur.fetchone() or {}).get("bundle") or {}

    connectors = bundle.get("connectors", [])
    ducts = bundle.get("ducts", [])
    manholes = bundle.get("manholes", [])
    cables = bundle.get("cables", [])
    tstates = bundle.get("tstates", {})
    inc_rows = bundle.get("inc_rows", [])
    alarms = bundle.get("alarms", [])
    runbooks = bundle.get("runbooks", [])
    audits = bundle.get("audits", [])
    net_nodes = {r["id"]: r for r in bundle.get("net_nodes", [])}
    oms_links = bundle.get("oms_links", [])
    wavelengths = {r["id"]: r for r in bundle.get("wavelengths", [])}
    ip_links = bundle.get("ip_links", [])
    ran_sites = {r["id"]: r for r in bundle.get("ran_sites", [])}
    gpon_clusters = {r["id"]: r for r in bundle.get("gpon_clusters", [])}
    subsea_cables = {r["id"]: r for r in bundle.get("subsea_cables", [])}
    sla_tiers = {r["tier_name"]: r for r in bundle.get("sla_tiers", [])}
    customers = {r["id"]: r for r in bundle.get("customers", [])}
    rfts_rows = bundle.get("rfts_rows", [])
    services = bundle.get("services", [])

    monitored_cables_set: set[str] = set()
    for rtu in rfts_rows:
        mc = rtu.get("monitored_cables_json") or []
        if isinstance(mc, str):
            try:
                mc = json.loads(mc)
            except Exception:
                mc = []
        monitored_cables_set.update(mc)

    for c in cables:
        is_rfts = bool(c["id"] in monitored_cables_set and c.get("role") in ("trunk", "dark"))
        c["rfts_monitored"] = is_rfts
        c["monitoring_mode"] = "auto_rfts_1625nm" if is_rfts else "handheld_otdr_sor"

    oms_by_pair: dict[tuple[str, str], str] = {}
    for oms in oms_links:
        oms_by_pair[(oms["node_a"], oms["node_b"])] = oms["cable_id"]
        oms_by_pair[(oms["node_b"], oms["node_a"])] = oms["cable_id"]

    inv = {
        "nodes": net_nodes,
        "ducts": {d["id"]: d for d in ducts},
        "cables": {c["id"]: c for c in cables},
        "oms_links": oms_links,
        "oms_by_pair": oms_by_pair,
        "wavelengths": wavelengths,
        "ip_links": ip_links,
        "ran_sites": ran_sites,
        "gpon_clusters": gpon_clusters,
        "subsea_cables": subsea_cables,
        "sla_tiers": sla_tiers,
        "customers": customers,
        "services": services,
    }

    alarms_by_inc: dict[str, list[dict[str, Any]]] = {}
    for alm in alarms:
        iid = alm.get("incident_id")
        if iid:
            alarms_by_inc.setdefault(iid, []).append(alm)

    incidents = [
        {
            "incident_id": inc["incident_id"],
            "title": inc["title"],
            "status": inc["status"],
            "severity": inc["severity"],
            "root_cause_type": inc["root_cause_type"],
            "root_cause_resource": inc["root_cause_resource"],
            "root_cause_summary": inc["root_cause_summary"],
            "confidence": inc["confidence"],
            "alarm_count": inc["alarm_count"],
            "fault_location": inc["fault_location_json"],
            "impact": inc["impact_json"],
            "srlg_findings": inc["srlg_findings_json"],
            "otdr_trace": inc["otdr_trace_json"],
            "ai_copilot": inc["ai_copilot_json"],
            "proposed_actions": inc["proposed_actions_json"],
            "executed_actions": inc["executed_actions_json"],
            "alarms": alarms_by_inc.get(inc["incident_id"], []),
            "created_at": inc["created_at"].isoformat() if hasattr(inc.get("created_at"), "isoformat") else inc.get("created_at"),
            "updated_at": inc["updated_at"].isoformat() if hasattr(inc.get("updated_at"), "isoformat") else inc.get("updated_at"),
        }
        for inc in inc_rows
    ]

    srlg_findings = audit_all_srlg_diversity(inv)
    dep_graph = build_multilayer_dependency_graph(inv, active_alarms=alarms)

    cmap = {c["id"]: c for c in connectors}
    emu_base = get_emulator_control_base_url()
    emu_status: dict[str, Any] = {}
    jira_issues: list[dict[str, Any]] = []
    snow_incidents: list[dict[str, Any]] = []
    snow_work_orders: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            tasks: list[Any] = [client.get(f"{emu_base}/emulator/status")]
            has_jira = "jira_sm" in cmap
            has_snow = "servicenow_itsm" in cmap
            if has_jira:
                tasks.append(client.get(cmap["jira_sm"]["endpoint_url"].rstrip("/") + "/rest/api/3/issue"))
            if has_snow:
                snow_base = cmap["servicenow_itsm"]["endpoint_url"].rstrip("/")
                tasks.append(client.get(f"{snow_base}/api/now/table/incident"))
                tasks.append(client.get(f"{snow_base}/api/now/table/wm_order"))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            idx = 0
            r_emu = results[idx]; idx += 1
            if not isinstance(r_emu, Exception) and r_emu.status_code == 200:
                emu_status = r_emu.json()
            if has_jira:
                r_jira = results[idx]; idx += 1
                if not isinstance(r_jira, Exception) and r_jira.status_code == 200:
                    jira_issues = r_jira.json().get("issues", [])
            if has_snow:
                r_sinc = results[idx]; idx += 1
                r_swo = results[idx]; idx += 1
                if not isinstance(r_sinc, Exception) and r_sinc.status_code == 200:
                    snow_incidents = r_sinc.json().get("result", [])
                if not isinstance(r_swo, Exception) and r_swo.status_code == 200:
                    snow_work_orders = r_swo.json().get("result", [])
    except Exception:
        pass

    bss_state = tstates.get("comviva_bss", {})
    active_currency = (
        emu_status.get("currency")
        or (bss_state.get("currency") if isinstance(bss_state, dict) else None)
        or "AED"
    )

    pop_ids = [nid for nid, n in net_nodes.items() if n.get("kind") == "pop"] or ["POP-01", "POP-02"]
    cust_ids = [nid for nid, n in net_nodes.items() if n.get("kind") == "customer"] or pop_ids
    ran_ids = list(ran_sites.keys()) or ["GNB-01"]
    duct_ids = [d["id"] for d in ducts] or ["DUCT-01"]
    background_noise = {
        "suppressed_total": 38,
        "flapping_transceivers": 17,
        "planned_maintenance_crq": 12,
        "transient_ran_warnings": 9,
        "events": [
            {
                "id": "SUP-CRQ-101",
                "category": "PLANNED_CRQ",
                "severity": "MINOR",
                "resource_id": f"RTR-{pop_ids[0]}",
                "source_oem": "servicenow_itsm",
                "reason": "Muted by active Change Window CHG0049118 (BGP policy maintenance)",
                "raw_text": f"RTR-{pop_ids[0]}: BGP peer maintenance state — auto-suppressed under approved CRQ window.",
            },
            {
                "id": "SUP-DOM-102",
                "category": "SFP_DOM_WARN",
                "severity": "WARNING",
                "resource_id": f"CPE-{cust_ids[0]}-Gi0/0/1",
                "source_oem": "nmsworks_cygnet",
                "reason": "Chronic dirty-ferrule Rx power warning (-19.4 dBm; stable 14d, non-service-affecting)",
                "raw_text": f"CPE-{cust_ids[0]}: Transceiver Rx optical power low warning (-19.4 dBm), zero CRC errors.",
            },
            {
                "id": "SUP-FLP-103",
                "category": "FLAP_DAMPENED",
                "severity": "MINOR",
                "resource_id": f"RTR-{pop_ids[-1]}:TenGigE0/2/0/4",
                "source_oem": "cisco_syslog",
                "reason": "Hold-down timer dampened sub-50ms transient CPE port bounce (x6 in 15m)",
                "raw_text": f"RTR-{pop_ids[-1]}: Sub-threshold interface micro-flap dampened; BFD session remained UP.",
            },
            {
                "id": "SUP-CRQ-104",
                "category": "PLANNED_CRQ",
                "severity": "WARNING",
                "resource_id": duct_ids[0],
                "source_oem": "servicenow_itsm",
                "reason": "Scheduled civil manhole lid & sub-duct inspection CHG0049102 (no optical loss)",
                "raw_text": f"Civil chamber access sensor open near {duct_ids[0]} — matched scheduled CHG0049102.",
            },
            {
                "id": "SUP-RAN-105",
                "category": "RAN_TRANSIENT",
                "severity": "WARNING",
                "resource_id": ran_ids[0],
                "source_oem": "ericsson_enm",
                "reason": "Ambient RRH cabinet temperature warning (41.2°C < 55°C critical threshold)",
                "raw_text": f"{ran_ids[0]}: Outdoor RRU thermal sensor minor high warning; fan speed nominal.",
            },
            {
                "id": "SUP-RAN-106",
                "category": "RAN_TRANSIENT",
                "severity": "MINOR",
                "resource_id": ran_ids[-1],
                "source_oem": "nokia_nsp",
                "reason": "Brief PRB congestion spike cleared within 60s soak window",
                "raw_text": f"{ran_ids[-1]}: DL PRB utilization >88% for 25s — auto-cleared before soak expiry.",
            },
        ],
    }

    payload = {
        "active_region": emu_status.get("active_region", "uae_dubai"),
        "region_name": emu_status.get("region_name", "UAE — Dubai Metro"),
        "currency": active_currency,
        "map_center": emu_status.get("map_center", [55.245, 25.155]),
        "map_zoom": emu_status.get("map_zoom", 10.9),
        "available_regions": emu_status.get("available_regions", []),
        "background_noise": background_noise,
        "connectors": connectors,
        "gis": {
            "ducts": ducts,
            "manholes": manholes,
            "cables": cables,
        },
        "topology": tstates.get("topology", {}),
        "bss": bss_state,
        "ciena_fres": tstates.get("ciena_fres", {}),
        "nokia_optical": tstates.get("nokia_optical", {}),
        "ran_telemetry": tstates.get("ericsson_ran", {}),
        "dependency_graph": dep_graph,
        "last_benchmark": LAST_BENCHMARK_RESULT,
        "srlg_findings": srlg_findings,
        "incidents": [i for i in incidents if i is not None],
        "alarms": alarms,
        "runbooks": runbooks,
        "audit_log": audits,
        "wire_packets": list(reversed(RECENT_WIRE_PACKETS[-25:])),
        "scenarios": emu_status.get("scenarios", []),
        "operator_profiles": emu_status.get("operator_profiles", {}),
        "external_tickets": {
            "jira_issues": jira_issues,
            "servicenow_incidents": snow_incidents,
            "servicenow_work_orders": snow_work_orders,
        },
        "llm_config": {
            "provider": LLM_CONFIG["provider"],
            "model": LLM_CONFIG["model"],
            "api_key_configured": bool(LLM_CONFIG.get("api_key")),
        },
    }
    _OVERVIEW_CACHE = payload
    return payload


class Tmf642AlarmBatch(BaseModel):
    alarms: list[dict[str, Any]]


@app.post("/api/v1/ingest/tmf642")
async def ingest_tmf642(batch: Tmf642AlarmBatch) -> dict[str, Any]:
    incidents = await correlate_alarms_into_incidents(batch.alarms)
    invalidate_overview_cache()
    return {
        "status": "correlated",
        "incident_id": incidents[0]["incident_id"] if incidents else None,
        "incident_ids": [i["incident_id"] for i in incidents],
    }


@app.post("/api/v1/faults/trigger")
async def trigger_fault(req: TriggerFaultPayload) -> dict[str, Any]:
    emu_base = get_emulator_control_base_url()
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{emu_base}/emulator/faults/inject",
            json={**req.model_dump(), "skip_webhook": True},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json()

    alarms = data.get("alarms", [])
    incidents = await correlate_alarms_into_incidents(alarms)
    await sync_all_connectors(include_static_topology=False)
    invalidate_overview_cache()
    return {
        "incident": incidents[0] if incidents else None,
        "incidents": incidents,
        "alarms_emitted": len(alarms),
    }


class RegionSwitchPayload(BaseModel):
    region_id: str


@app.post("/api/v1/region/switch")
async def switch_region(req: RegionSwitchPayload) -> dict[str, Any]:
    global LAST_BENCHMARK_RESULT
    invalidate_overview_cache()
    emu_base = get_emulator_control_base_url()
    async with httpx.AsyncClient(timeout=12.0) as client:
        r = await client.post(
            f"{emu_base}/emulator/dataset/switch",
            json={"region_id": req.region_id},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        sw_data = r.json()

    RECENT_WIRE_PACKETS.clear()
    LAST_BENCHMARK_RESULT = None
    await sync_all_connectors(clear_existing=True)
    log_audit("noc_operator", "REGION_SWITCHED", req.region_id, sw_data)
    invalidate_overview_cache()
    await get_overview()
    return sw_data


@app.post("/api/v1/faults/reset")
async def reset_faults() -> dict[str, Any]:
    emu_base = get_emulator_control_base_url()
    async with httpx.AsyncClient(timeout=6.0) as client:
        await client.post(f"{emu_base}/emulator/faults/clear")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alarms; DELETE FROM incidents")
    RECENT_WIRE_PACKETS.clear()
    await sync_all_connectors(include_static_topology=False)
    log_audit("noc_operator", "NETWORK_RESET", "ALL", {"status": "cleared"})
    invalidate_overview_cache()
    return {"status": "reset"}


class ApproveActionsRequest(BaseModel):
    approved_by: str = "Lead NOC Engineer"
    action_ids: list[str] | None = None


@app.post("/api/v1/incidents/{incident_id}/approve")
async def approve_incident_actions(incident_id: str, req: ApproveActionsRequest) -> dict[str, Any]:
    updated = await execute_incident_actions(incident_id, req.approved_by, req.action_ids)
    await sync_all_connectors(include_static_topology=False)
    invalidate_overview_cache()
    return {"incident": updated}


@app.post("/api/v1/incidents/{incident_id}/regenerate-ai")
async def regenerate_incident_ai(incident_id: str) -> dict[str, Any]:
    inc = get_incident_detail(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    ai_res = await generate_ai_copilot_analysis(
        incident_id=inc["incident_id"],
        root_cause_type=inc["root_cause_type"],
        root_cause_resource=inc["root_cause_resource"],
        root_cause_summary=inc["root_cause_summary"],
        fault_location=inc["fault_location"],
        impact_bundle=inc["impact"],
        srlg_findings=inc["srlg_findings"],
        alarms=inc["alarms"],
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET ai_copilot_json = %s, updated_at = NOW() WHERE incident_id = %s",
                (json.dumps(ai_res), incident_id),
            )
    invalidate_overview_cache()
    return {"ai_copilot": ai_res}


@app.post("/api/v1/connectors/sync")
async def trigger_connector_sync() -> dict[str, Any]:
    res = await sync_all_connectors()
    invalidate_overview_cache()
    return res


@app.put("/api/v1/connectors/{connector_id}")
async def update_connector(connector_id: str, req: ConnectorUpdatePayload) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE connectors
                SET endpoint_url = %s, mode = %s, enabled = %s, config_json = %s
                WHERE id = %s
                RETURNING *
                """,
                (req.endpoint_url, req.mode, req.enabled, json.dumps(req.config_json), connector_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Connector not found")
    invalidate_connectors_cache()
    log_audit("noc_admin", "UPDATE_CONNECTOR", connector_id, req.model_dump())
    await sync_all_connectors()
    invalidate_overview_cache()
    return dict(row)


@app.post("/api/v1/settings/llm")
async def update_llm_settings(req: LlmConfigPayload) -> dict[str, Any]:
    LLM_CONFIG["provider"] = req.provider
    LLM_CONFIG["model"] = req.model
    if req.api_key.strip():
        LLM_CONFIG["api_key"] = req.api_key.strip()
    return {
        "provider": LLM_CONFIG["provider"],
        "model": LLM_CONFIG["model"],
        "api_key_configured": bool(LLM_CONFIG.get("api_key")),
    }


@app.get("/api/v1/otdr/cable/{cable_id}")
async def inspect_cable_otdr(cable_id: str) -> dict[str, Any]:
    otdr_adapter = DatabaseBackedOtdrAdapter()
    res = await otdr_adapter.fetch_and_parse_sor(cable_id)
    if res is None:
        raise HTTPException(status_code=404, detail=f"No .sor trace available for {cable_id}")
    parsed, byte_len = res
    loc = None
    if parsed.fault_distance_optical_m is not None:
        loc = locate_fault_on_cable_postgis(cable_id, parsed.fault_distance_optical_m)
    return {
        "cable_id": parsed.cable_id,
        "wavelength_nm": parsed.wavelength_nm,
        "supplier_name": parsed.supplier_name,
        "unit_name": parsed.unit_name,
        "serial_number": parsed.serial_number,
        "refractive_index": parsed.refractive_index,
        "pulse_width_ns": parsed.pulse_width_ns,
        "range_m": parsed.range_m,
        "sample_spacing_m": parsed.sample_spacing_m,
        "crc_valid": parsed.crc_valid,
        "binary_size_bytes": byte_len,
        "fault_distance_optical_m": parsed.fault_distance_optical_m,
        "key_events": [vars(e) for e in parsed.key_events],
        "trace_points_db": parsed.trace_points_db[::4],
        "postgis_localization": loc,
    }


@app.post("/api/v1/otdr/parse-sor")
async def upload_and_parse_sor(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    parsed = parse_sor_bytes(raw)
    loc = None
    if parsed.fault_distance_optical_m is not None:
        try:
            loc = locate_fault_on_cable_postgis(parsed.cable_id, parsed.fault_distance_optical_m)
        except Exception:
            loc = None
    return {
        "filename": file.filename,
        "cable_id": parsed.cable_id,
        "wavelength_nm": parsed.wavelength_nm,
        "supplier_name": parsed.supplier_name,
        "unit_name": parsed.unit_name,
        "crc_valid": parsed.crc_valid,
        "fault_distance_optical_m": parsed.fault_distance_optical_m,
        "key_events": [vars(e) for e in parsed.key_events],
        "trace_points_db": parsed.trace_points_db[::4],
        "postgis_localization": loc,
    }


@app.post("/api/v1/import/kml")
async def upload_and_import_kml(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    try:
        imported = import_kml_osp_routes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    emu_base = get_emulator_control_base_url()
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            await client.post(
                f"{emu_base}/emulator/osp/import",
                json={
                    "cables": imported["cables"],
                    "ducts": imported["ducts"],
                    "manholes": imported["manholes"],
                },
            )
    except Exception:
        pass

    log_audit(
        "noc_operator",
        "IMPORT_KML_OSP",
        file.filename or "route.kml",
        {
            "cables": [c["id"] for c in imported["cables"]],
            "chambers": imported["imported_chamber_count"],
        },
    )
    invalidate_overview_cache()
    return {
        "filename": file.filename,
        "imported_cable_count": imported["imported_cable_count"],
        "imported_chamber_count": imported["imported_chamber_count"],
        "primary_cable_id": imported["cables"][0]["id"] if imported["cables"] else None,
        "cables": imported["cables"],
    }


@app.post("/api/v1/import/alarms-csv")
async def upload_and_correlate_alarms_csv(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    try:
        alarms = parse_alarms_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    incidents = await correlate_alarms_into_incidents(alarms)
    log_audit(
        "noc_operator",
        "IMPORT_ALARMS_CSV",
        file.filename or "alarms.csv",
        {"alarms_imported": len(alarms), "incidents_created": len(incidents)},
    )
    invalidate_overview_cache()
    return {
        "filename": file.filename,
        "alarms_imported": len(alarms),
        "incidents": incidents,
        "incident": incidents[0] if incidents else None,
    }


@app.post("/api/v1/benchmark/storm")
async def execute_storm_benchmark(req: StormBenchmarkPayload) -> dict[str, Any]:
    global LAST_BENCHMARK_RESULT
    size = max(1000, min(50000, req.storm_size))
    res = run_10k_alarm_storm_benchmark(size)
    LAST_BENCHMARK_RESULT = res
    return res


@app.get("/api/v1/telemetry/3gpp-xml")
async def fetch_3gpp_xml_preview() -> dict[str, Any]:
    cmap = get_connectors_map(only_enabled=True)
    if "ericsson_enm" not in cmap:
        return {"xml": ""}
    enm_base = cmap["ericsson_enm"]["endpoint_url"].rstrip("/")
    async with httpx.AsyncClient(timeout=4.0) as client:
        r = await client.get(f"{enm_base}/pm-counters.xml")
        return {"xml": r.text if r.status_code == 200 else ""}
