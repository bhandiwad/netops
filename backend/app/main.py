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
from pydantic import BaseModel

from shared.sor_codec import parse_sor_bytes
from .adapters.registry import (
    DatabaseBackedOtdrAdapter,
    get_connectors_map,
    get_emulator_control_base_url,
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
from .spatial import locate_fault_on_cable_postgis

app = FastAPI(title="Telco Network Operations Copilot API", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RECENT_WIRE_PACKETS: list[dict[str, Any]] = []
LAST_BENCHMARK_RESULT: dict[str, Any] | None = None
KAFKA_BOOTSTRAP = os.getenv("NOC_KAFKA_BOOTSTRAP", "127.0.0.1:19092")
KAFKA_TOPIC = os.getenv("NOC_KAFKA_TOPIC", "noc.alarms.raw")


async def _kafka_consumer_worker() -> None:
    """Active background Kafka consumer reading from Redpanda topic `noc.alarms.raw`."""
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="noc-copilot-correlator",
            auto_offset_reset="latest",
        )
        await consumer.start()
        try:
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
        finally:
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
    asyncio.create_task(_kafka_consumer_worker())
    try:
        await sync_all_connectors()
    except Exception:
        pass


@app.get("/api/v1/overview")
async def get_overview() -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM connectors ORDER BY id")
            connectors = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT id, node_a, node_b, bridge, trench_length_m, coords_json FROM osp_ducts ORDER BY id")
            ducts = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT id, node_id, name, kind, lat, lon, slack_coil_m FROM osp_manholes ORDER BY id")
            manholes = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT id, path_nodes, duct_ids, bridges, fibres, role,
                       helix_factor, trench_length_m, optical_length_m, splices_json, coords_json
                FROM osp_cables ORDER BY id
                """
            )
            cables = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT key, payload FROM topology_state")
            tstates = {r["key"]: r["payload"] for r in cur.fetchall()}
            cur.execute("SELECT incident_id FROM incidents ORDER BY updated_at DESC")
            inc_ids = [r["incident_id"] for r in cur.fetchall()]
            cur.execute("SELECT * FROM alarms ORDER BY raised_at DESC LIMIT 120")
            alarms = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT id, title, domain, oem_tags, symptoms, procedure_md, past_tickets_json FROM runbooks ORDER BY id")
            runbooks = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 40")
            audits = [dict(r) for r in cur.fetchall()]

    incidents = [get_incident_detail(iid) for iid in inc_ids]
    srlg_findings = audit_all_srlg_diversity()
    dep_graph = build_multilayer_dependency_graph()

    cmap = {c["id"]: c for c in connectors}
    emu_base = get_emulator_control_base_url()
    emu_status: dict[str, Any] = {}
    jira_issues: list[dict[str, Any]] = []
    snow_incidents: list[dict[str, Any]] = []
    snow_work_orders: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r_emu = await client.get(f"{emu_base}/emulator/status")
            if r_emu.status_code == 200:
                emu_status = r_emu.json()
            if "jira_sm" in cmap:
                r_jira = await client.get(cmap["jira_sm"]["endpoint_url"].rstrip("/") + "/rest/api/3/issue")
                if r_jira.status_code == 200:
                    jira_issues = r_jira.json().get("issues", [])
            if "servicenow_itsm" in cmap:
                snow_base = cmap["servicenow_itsm"]["endpoint_url"].rstrip("/")
                r_sinc = await client.get(f"{snow_base}/api/now/table/incident")
                if r_sinc.status_code == 200:
                    snow_incidents = r_sinc.json().get("result", [])
                r_swo = await client.get(f"{snow_base}/api/now/table/wm_order")
                if r_swo.status_code == 200:
                    snow_work_orders = r_swo.json().get("result", [])
    except Exception:
        pass

    return {
        "connectors": connectors,
        "gis": {
            "ducts": ducts,
            "manholes": manholes,
            "cables": cables,
        },
        "topology": tstates.get("topology", {}),
        "bss": tstates.get("comviva_bss", {}),
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


class Tmf642AlarmBatch(BaseModel):
    alarms: list[dict[str, Any]]


@app.post("/api/v1/ingest/tmf642")
async def ingest_tmf642(batch: Tmf642AlarmBatch) -> dict[str, Any]:
    incidents = await correlate_alarms_into_incidents(batch.alarms)
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
    await sync_all_connectors()
    return {
        "incident": incidents[0] if incidents else None,
        "incidents": incidents,
        "alarms_emitted": len(alarms),
    }


@app.post("/api/v1/faults/reset")
async def reset_faults() -> dict[str, Any]:
    emu_base = get_emulator_control_base_url()
    async with httpx.AsyncClient(timeout=6.0) as client:
        await client.post(f"{emu_base}/emulator/faults/clear")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alarms")
            cur.execute("DELETE FROM incidents")
    RECENT_WIRE_PACKETS.clear()
    await sync_all_connectors()
    log_audit("noc_operator", "NETWORK_RESET", "ALL", {"status": "cleared"})
    return {"status": "reset"}


class ApproveActionsRequest(BaseModel):
    approved_by: str = "Lead NOC Engineer"
    action_ids: list[str] | None = None


@app.post("/api/v1/incidents/{incident_id}/approve")
async def approve_incident_actions(incident_id: str, req: ApproveActionsRequest) -> dict[str, Any]:
    updated = await execute_incident_actions(incident_id, req.approved_by, req.action_ids)
    await sync_all_connectors()
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
    return {"ai_copilot": ai_res}


@app.post("/api/v1/connectors/sync")
async def trigger_connector_sync() -> dict[str, Any]:
    return await sync_all_connectors()


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
    log_audit("noc_admin", "UPDATE_CONNECTOR", connector_id, req.model_dump())
    await sync_all_connectors()
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
