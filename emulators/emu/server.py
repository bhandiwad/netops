"""Multi-OEM Telco Systems Emulator Suite.

Exposes protocol-authentic endpoints for:
  - Ciena MCP (DWDM optical alarms, OCh/OMS FREs, OpenConfig PM telemetry, hitless reroute)
  - Nokia NSP (Optical & IP alarms, gNMI/OpenConfig Pre-FEC BER & OSNR telemetry)
  - NMSWorks CygNet OSS (Unified multi-layer topology, circuits, alarms)
  - NetBox DCIM/Circuits (REST /api/dcim/*, /api/circuits/*)
  - Lepton Software SmartInventory GIS (OGC WFS GeoJSON for ducts, cables, manholes, slack loops)
  - VIAVI ONMSi & EXFO Nova Fiber RFTS (binary Telcordia SR-4731 .sor OTDR trace files)
  - Ericsson ENM & GPON OLT / GenieACS (4G/5G gNodeB/eNodeB alarms, microwave, dying-gasp vs LOSi)
  - Comviva BlueMarble / Ngage BSS (TMF629 customers, TMF638 services, SLA tiers & penalties)
  - Jira Service Management REST v3 (/jira/rest/api/3/issue)
  - ServiceNow ITSM & FSM Table API (/servicenow/api/now/table/incident, wm_order, change_request)

Also emits live UDP RFC 5424 Syslog datagrams, UDP SNMPv2c trap datagrams,
and publishes to Redpanda/Kafka topic `noc.alarms.raw` when faults are injected.
"""
from __future__ import annotations

import asyncio
import json
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.sor_codec import generate_sor_bytes, parse_sor_bytes  # noqa: E402
from .roads import _interpolate_along_coords, build_or_load_osp_geometry  # noqa: E402
from .spec import (  # noqa: E402
    CABLES,
    CUSTOMERS,
    DUCTS,
    FAULT_SCENARIOS,
    GPON_SPLITTER_CLUSTERS,
    IP_LINKS,
    NODES,
    OMS,
    OPERATOR_PROFILES,
    OPTICAL,
    RAN_SITES,
    RFTS,
    ROUTERS,
    SERVICES,
    SLA_TIERS,
    SUBSEA_SYSTEMS,
    WAVELENGTHS,
)

app = FastAPI(title="Multi-OEM Telco Emulator Suite", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------- runtime state
OSP_DATA: dict[str, Any] = {}
ACTIVE_FAULTS: dict[str, dict[str, Any]] = {}
ACTIVE_ALARMS: list[dict[str, Any]] = []
GENERATED_SOR_TRACES: dict[str, bytes] = {}  # cable_id -> raw .sor bytes
OTDR_MEASUREMENT_META: dict[str, dict[str, Any]] = {}
OPTICAL_PM_STATE: dict[str, dict[str, Any]] = {}
REROUTED_WAVELENGTHS: dict[str, dict[str, Any]] = {}
RAN_PM_STATE: dict[str, dict[str, Any]] = {}
SUBSEA_STATE: dict[str, dict[str, Any]] = {}


JIRA_ISSUES: list[dict[str, Any]] = []
SERVICENOW_INCIDENTS: list[dict[str, Any]] = []
SERVICENOW_WORK_ORDERS: list[dict[str, Any]] = []
SERVICENOW_CHANGES: list[dict[str, Any]] = [
    {
        "sys_id": "chg-9001",
        "number": "CHG0049102",
        "short_description": "Scheduled RTA municipal duct inspection near Al Garhoud Bridge",
        "state": "Scheduled",
        "cmdb_ci": "D-GB-KRM",
        "start_date": "2026-10-31T22:00:00Z",
        "end_date": "2026-11-01T02:00:00Z",
        "risk": "Moderate",
    },
    {
        "sys_id": "chg-9002",
        "number": "CHG0049118",
        "short_description": "Planned BGP route-reflector policy update on KRM Nokia 7750",
        "state": "Scheduled",
        "cmdb_ci": "RTR-KRM-01",
        "start_date": "2026-11-01T01:00:00Z",
        "end_date": "2026-11-01T03:00:00Z",
        "risk": "Low",
    },
]

COPILOT_WEBHOOK_URL = "http://127.0.0.1:8002/api/v1/ingest/tmf642"
COPILOT_SYSLOG_PORT = 15514
COPILOT_SNMP_PORT = 15162
KAFKA_BOOTSTRAP = "127.0.0.1:19092"
KAFKA_TOPIC = "noc.alarms.raw"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_baseline_traces_and_pm() -> None:
    """Generate clean baseline .sor traces for all cables and healthy optical PM counters."""
    cables_by_id = {c["id"]: c for c in OSP_DATA.get("cables", [])}
    rfts_by_cable: dict[str, dict[str, Any]] = {}
    for rtu in RFTS:
        for cid in rtu["monitors"]:
            rfts_by_cable[cid] = rtu

    for cid, cinfo in cables_by_id.items():
        rtu = rfts_by_cable.get(cid, {"id": "ONMSI-RTU-QZ", "vendor": "viavi", "pop": cinfo["path_nodes"][0]})
        supplier = "VIAVI Solutions" if rtu["vendor"] == "viavi" else "EXFO Inc."
        unit = "ONMSi OTU-8000" if rtu["vendor"] == "viavi" else "Nova Fiber FG-750"
        splices = [
            (sp["optical_distance_m"], sp["manhole_id"])
            for sp in cinfo["splices"][1:-1]
        ]
        sor_bytes = generate_sor_bytes(
            cable_id=cid,
            fiber_number=1,
            wavelength_nm=1625,
            location_a=cinfo["path_nodes"][0],
            location_b=cinfo["path_nodes"][-1],
            supplier_name=supplier,
            unit_name=unit,
            serial_number=rtu["id"],
            total_optical_length_m=cinfo["optical_length_m"],
            splice_distances_m=splices,
            cut_distance_optical_m=None,
        )
        GENERATED_SOR_TRACES[cid] = sor_bytes
        OTDR_MEASUREMENT_META[cid] = {
            "cable_id": cid,
            "rtu_id": rtu["id"],
            "vendor": rtu["vendor"],
            "launch_node": cinfo["path_nodes"][0],
            "status": "HEALTHY",
            "optical_length_m": cinfo["optical_length_m"],
            "fault_distance_optical_m": None,
            "measured_at": _now_iso(),
        }

    for och in WAVELENGTHS:
        OPTICAL_PM_STATE[och["id"]] = {
            "och_id": och["id"],
            "rate": och["rate"],
            "freq_thz": och["freq"],
            "path": och["path"],
            "osnr_db": 26.4 if och["rate"] == "100G" else 28.1,
            "pre_fec_ber": 1.2e-6,
            "post_fec_ber": 0.0,
            "rx_power_dbm": -7.8,
            "tx_power_dbm": 1.5,
            "operational_state": "UP",
            "updated_at": _now_iso(),
        }

    for site in RAN_SITES:
        is_mw = site["backhaul_type"] == "microwave_eband"
        RAN_PM_STATE[site["id"]] = {
            "site_id": site["id"],
            "name": site["name"],
            "vendor": site["vendor"],
            "pop_anchor": site["pop_anchor"],
            "backhaul_type": site["backhaul_type"],
            "cells": site["cells"],
            "operational_state": "ENABLED_NORMAL",
            "dl_prb_util_pct": 54.2 if "HUB" in site["id"] else 38.6,
            "ul_prb_util_pct": 28.4,
            "rrc_conn_success_pct": 99.84,
            "erab_drop_rate_pct": 0.08,
            "ul_sinr_db": 18.5,
            "active_ues": 420 if "HUB" in site["id"] else 185,
            "ac_mains_status": "ONLINE",
            "dc_bus_voltage_v": 53.8,
            "lvd_disconnect_threshold_v": 43.2,
            "battery_remaining_mins": int(site["battery_backup_hours"] * 60),
            "cabinet_temp_c": 29.4,
            "mw_link_id": site.get("mw_link_id"),
            "mw_rsl_dbm": -38.2 if is_mw else None,
            "mw_snr_db": 32.5 if is_mw else None,
            "mw_acm_modulation": "1024QAM (10 Gbps)" if is_mw else None,
            "rain_rate_mm_hr": 0.0 if is_mw else None,
            "updated_at": _now_iso(),
        }

    for sub in SUBSEA_SYSTEMS:
        SUBSEA_STATE[sub["id"]] = {
            **sub,
            "operational_state": "NORMAL_DOUBLE_END_FEED",
            "pfe_voltage_v": 4120.0,
            "pfe_current_ma": 950.0,
            "earth_leakage_ma": 0.2,
            "shunt_fault_detected": False,
            "cotdr_shunt_distance_km": None,
            "fault_span": None,
            "water_depth_m": None,
            "updated_at": _now_iso(),
        }



@app.on_event("startup")
async def _on_startup() -> None:
    global OSP_DATA
    OSP_DATA = build_or_load_osp_geometry()
    _init_baseline_traces_and_pm()


# ---------------------------------------------------------------- UDP + Kafka + Webhook Emitters
def _send_udp_syslog(hostname: str, app_name: str, msg: str, severity: int = 3) -> None:
    """Emit a real RFC 5424 Syslog UDP datagram to the Copilot syslog listener."""
    pri = (23 << 3) | severity  # local7
    ts = _now_iso()
    wire = f"<{pri}>1 {ts} {hostname} {app_name} - - - {msg}".encode("utf-8")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(wire, ("127.0.0.1", COPILOT_SYSLOG_PORT))
        sock.close()
    except Exception:
        pass


def _send_udp_snmp_trap( trap_payload: dict[str, Any]) -> None:
    """Emit a structured SNMPv2c trap datagram over UDP to the Copilot trap listener."""
    wire = json.dumps({"pdu": "SNMPv2-Trap-PDU", **trap_payload}).encode("utf-8")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(wire, ("127.0.0.1", COPILOT_SNMP_PORT))
        sock.close()
    except Exception:
        pass


async def _publish_alarms_to_kafka_and_webhook(
    alarms: list[dict[str, Any]],
    skip_webhook: bool = False,
) -> None:
    # 1. Publish to Redpanda / Kafka
    try:
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, request_timeout_ms=3000)
        await producer.start()
        try:
            for a in alarms:
                await producer.send_and_wait(
                    KAFKA_TOPIC,
                    json.dumps(a).encode("utf-8"),
                    key=a["alarm_id"].encode("utf-8"),
                )
        finally:
            await producer.stop()
    except Exception:
        pass

    # 2. Push TMF642 AlarmCreateEvent webhook to Copilot backend when invoked externally
    if not skip_webhook:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.post(COPILOT_WEBHOOK_URL, json={"alarms": alarms})
        except Exception:
            pass


# ---------------------------------------------------------------- Fault Synthesis Engine
def _optical_cut_distance_for_cable(cinfo: dict[str, Any], cut_ratio: float) -> tuple[float, float, float, float]:
    """Given a cut_ratio [0.05..0.95] along trench, compute:
    (trench_cut_m, optical_cut_m, cut_lat, cut_lon)
    accounting for helix factor and manhole slack coils passed prior to the cut.
    """
    trench_total = float(cinfo["trench_length_m"])
    trench_cut_m = round(trench_total * cut_ratio, 1)
    helix = float(cinfo.get("helix_factor", 1.015))
    slack_passed_m = 0.0
    for sp in cinfo["splices"][:-1]:
        if sp["trench_distance_m"] <= trench_cut_m:
            slack_passed_m += float(sp["slack_added_m"])
    optical_cut_m = round(trench_cut_m * helix + slack_passed_m, 1)
    cut_lon, cut_lat = _interpolate_along_coords(cinfo["coordinates"], cut_ratio)
    return trench_cut_m, optical_cut_m, cut_lat, cut_lon


def _synthesize_cable_cut_alarms(cable_id: str, cut_ratio: float, scenario_id: str) -> list[dict[str, Any]]:
    cables_by_id = {c["id"]: c for c in OSP_DATA["cables"]}
    if cable_id not in cables_by_id:
        raise ValueError(f"Unknown cable {cable_id}")
    cinfo = cables_by_id[cable_id]
    trench_cut_m, optical_cut_m, cut_lat, cut_lon = _optical_cut_distance_for_cable(cinfo, cut_ratio)

    # Update binary .sor trace for this cable with reflective break at optical_cut_m
    rfts_by_cable = {cid: rtu for rtu in RFTS for cid in rtu["monitors"]}
    rtu = rfts_by_cable.get(cable_id, {"id": "ONMSI-RTU-QZ", "vendor": "viavi", "pop": cinfo["path_nodes"][0]})
    supplier = "VIAVI Solutions" if rtu["vendor"] == "viavi" else "EXFO Inc."
    unit = "ONMSi OTU-8000" if rtu["vendor"] == "viavi" else "Nova Fiber FG-750"
    splices = [(sp["optical_distance_m"], sp["manhole_id"]) for sp in cinfo["splices"][1:-1]]
    GENERATED_SOR_TRACES[cable_id] = generate_sor_bytes(
        cable_id=cable_id,
        fiber_number=1,
        wavelength_nm=1625,
        location_a=cinfo["path_nodes"][0],
        location_b=cinfo["path_nodes"][-1],
        supplier_name=supplier,
        unit_name=unit,
        serial_number=rtu["id"],
        total_optical_length_m=cinfo["optical_length_m"],
        splice_distances_m=splices,
        cut_distance_optical_m=optical_cut_m,
    )
    OTDR_MEASUREMENT_META[cable_id] = {
        "cable_id": cable_id,
        "rtu_id": rtu["id"],
        "vendor": rtu["vendor"],
        "launch_node": cinfo["path_nodes"][0],
        "status": "FIBER_BREAK",
        "optical_length_m": cinfo["optical_length_m"],
        "fault_distance_optical_m": optical_cut_m,
        "measured_at": _now_iso(),
    }

    now = _now_iso()
    alarms: list[dict[str, Any]] = []

    def add_alarm(
        source_oem: str,
        protocol: str,
        layer: str,
        resource_id: str,
        node_id: str,
        severity: str,
        specific_problem: str,
        probable_cause: str,
        raw_text: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        alm = {
            "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
            "scenario_id": scenario_id,
            "source_oem": source_oem,
            "protocol": protocol,
            "layer": layer,
            "resource_id": resource_id,
            "node_id": node_id,
            "severity": severity,
            "specific_problem": specific_problem,
            "probable_cause": probable_cause,
            "raw_text": raw_text,
            "raised_at": now,
            "extra": extra or {},
        }
        alarms.append(alm)

    # 1. VIAVI ONMSi / EXFO Nova OTDR reflective break alarm
    rfts_oem = "viavi_onmsi" if rtu["vendor"] == "viavi" else "exfo_nova"
    add_alarm(
        source_oem=rfts_oem,
        protocol="RFTS-REST+SOR",
        layer="fibre_osp",
        resource_id=cable_id,
        node_id=cinfo["path_nodes"][0],
        severity="CRITICAL",
        specific_problem="OTDR_REFLECTIVE_FIBER_BREAK",
        probable_cause="Optical Fiber Break / High Reflectance Event (-18.4 dB)",
        raw_text=(
            f"[{rtu['id']}] 1625nm OTDR trace alarm on {cable_id} from {cinfo['path_nodes'][0]}: "
            f"Reflective break at optical distance {optical_cut_m:.1f} m (loss > 28.5 dB, refl -18.4 dB). "
            f"SR-4731 .sor trace ready."
        ),
        extra={
            "cable_id": cable_id,
            "rtu_id": rtu["id"],
            "launch_node": cinfo["path_nodes"][0],
            "optical_distance_m": optical_cut_m,
            "sor_url": f"/viavi-onmsi/api/v1/traces/{cable_id}.sor",
        },
    )

    # 2. Optical OMS & OCh alarms (Ciena MCP / Nokia NSP)
    u_node, v_node = cinfo["path_nodes"][0], cinfo["path_nodes"][-1]
    for oms_a, oms_b, oms_cable in OMS:
        if oms_cable == cable_id:
            opt_vendor = OPTICAL.get(oms_a, "ciena")
            oem_name = "ciena_mcp" if opt_vendor == "ciena" else "nokia_nsp"
            model_name = "Ciena 6500 ROADM" if opt_vendor == "ciena" else "Nokia 1830 PSS-32"
            add_alarm(
                source_oem=oem_name,
                protocol="RESTCONF/TMF642",
                layer="dwdm_optical",
                resource_id=f"OMS-{oms_a}-{oms_b}",
                node_id=oms_a,
                severity="CRITICAL",
                specific_problem="OTS_LOS_LINE_FAIL",
                probable_cause="Loss of Signal on Optical Multiplex Section",
                raw_text=f"{model_name} {oms_a} degree->{oms_b}: OTS-LOS / OSC-LOS RxPower=-40.0dBm on {cable_id}",
                extra={"cable_id": cable_id, "peer_node": oms_b},
            )
            add_alarm(
                source_oem=oem_name,
                protocol="RESTCONF/TMF642",
                layer="dwdm_optical",
                resource_id=f"OMS-{oms_b}-{oms_a}",
                node_id=oms_b,
                severity="CRITICAL",
                specific_problem="OTS_LOS_LINE_FAIL",
                probable_cause="Loss of Signal on Optical Multiplex Section",
                raw_text=f"{model_name} {oms_b} degree->{oms_a}: OTS-LOS / APR Automatic Power Reduction active",
                extra={"cable_id": cable_id, "peer_node": oms_a},
            )

    # Check which wavelengths traverse this cable
    affected_ochs: list[dict[str, Any]] = []
    for och in WAVELENGTHS:
        wpath = och["path"]
        for i in range(len(wpath) - 1):
            seg_set = {wpath[i], wpath[i + 1]}
            if seg_set == {u_node, v_node}:
                affected_ochs.append(och)
                OPTICAL_PM_STATE[och["id"]]["operational_state"] = "DOWN"
                OPTICAL_PM_STATE[och["id"]]["rx_power_dbm"] = -40.0
                OPTICAL_PM_STATE[och["id"]]["osnr_db"] = 0.0
                opt_vendor = OPTICAL.get(wpath[0], "ciena")
                oem_name = "ciena_mcp" if opt_vendor == "ciena" else "nokia_nsp"
                add_alarm(
                    source_oem=oem_name,
                    protocol="OpenConfig-gNMI",
                    layer="dwdm_optical",
                    resource_id=och["id"],
                    node_id=wpath[0],
                    severity="MAJOR",
                    specific_problem="OCH_LOF_CHANNEL_DOWN",
                    probable_cause="Optical Channel Loss of Frame / Server Signal Fail (SSF)",
                    raw_text=(
                        f"OCh {och['id']} ({och['rate']} {och['freq']:.2f}THz {'->'.join(wpath)}): "
                        f"OTU4-LOF / ODU4-AIS asserted"
                    ),
                    extra={"cable_id": cable_id, "service": och.get("service"), "leg": och.get("leg")},
                )
                break

    # 3. IP/MPLS Core Router alarms (Cisco Syslog, Juniper SNMP, Nokia/Huawei)
    affected_och_ids = {o["id"] for o in affected_ochs}
    for ip_a, ip_b, transport_id in IP_LINKS:
        if transport_id in affected_och_ids or transport_id == cable_id:
            for r_node, peer_node in [(ip_a, ip_b), (ip_b, ip_a)]:
                rvendor, rmodel = ROUTERS.get(r_node, ("cisco", "ASR 9910"))
                if rvendor == "cisco":
                    syslog_msg = (
                        f"RP/0/RSP0/CPU0:RTR-{r_node}: %PKT_INFRA-LINK-3-UPDOWN : "
                        f"Interface HundredGigE0/1/0/{peer_node}, changed state to Down (BFD session timeout)"
                    )
                    _send_udp_syslog(f"RTR-{r_node}", "iosxr-link", syslog_msg, severity=3)
                    add_alarm(
                        source_oem="cisco_syslog",
                        protocol="Syslog-RFC5424",
                        layer="ip_mpls",
                        resource_id=f"RTR-{r_node}:Hu0/1/0/{peer_node}",
                        node_id=r_node,
                        severity="MAJOR",
                        specific_problem="INTERFACE_LINK_BFD_DOWN",
                        probable_cause="Physical or Optical Transport Down",
                        raw_text=syslog_msg,
                        extra={"peer_node": peer_node, "transport_id": transport_id},
                    )
                elif rvendor == "juniper":
                    trap_data = {
                        "oid": "1.3.6.1.4.1.2636.4.5.0.1",
                        "trap_name": "jnxDomAlarmRxLossOfSignal",
                        "device": f"RTR-{r_node}",
                        "interface": f"et-0/0/{peer_node}",
                        "rx_power_dbm": -39.8,
                    }
                    _send_udp_snmp_trap(trap_data)
                    add_alarm(
                        source_oem="juniper_snmp",
                        protocol="SNMPv2c-Trap",
                        layer="ip_mpls",
                        resource_id=f"RTR-{r_node}:et-0/0/{peer_node}",
                        node_id=r_node,
                        severity="MAJOR",
                        specific_problem="JNX_DOM_RX_LOS_BGP_DROP",
                        probable_cause="Optical Transceiver Rx LOS & ISIS/BGP Adjacency Down",
                        raw_text=(
                            f"SNMP Trap jnxDomAlarmRxLossOfSignal on RTR-{r_node} ({rmodel}) "
                            f"et-0/0/{peer_node}: RxOptPower=-39.8dBm; RPD_BGP_NEIGHBOR_STATE_CHANGED->Idle"
                        ),
                        extra={"peer_node": peer_node, "transport_id": transport_id},
                    )
                else:
                    add_alarm(
                        source_oem="nokia_nsp" if rvendor == "nokia" else "huawei_nce",
                        protocol="SNMPv2c-Trap",
                        layer="ip_mpls",
                        resource_id=f"RTR-{r_node}:port-1/1/{peer_node}",
                        node_id=r_node,
                        severity="MAJOR",
                        specific_problem="MPLS_LDP_RSVP_TUNNEL_DOWN",
                        probable_cause="Underlying link down",
                        raw_text=f"RTR-{r_node} ({rmodel}) port->RTR-{peer_node}: Link Down & RSVP-TE LSP reroute triggered",
                        extra={"peer_node": peer_node, "transport_id": transport_id},
                    )

    # 4. NMSWorks CygNet OSS Enterprise CPE & Circuit Alarms
    for svc in SERVICES:
        for leg in svc["legs"]:
            leg_hit = (leg.get("cable") == cable_id) or (leg.get("och") in affected_och_ids)
            if leg_hit:
                add_alarm(
                    source_oem="nmsworks_cygnet",
                    protocol="NMSWorks-REST",
                    layer="enterprise_sla",
                    resource_id= f"{svc['id']}:{leg['name']}",
                    node_id=cinfo["path_nodes"][-1],
                    severity="CRITICAL" if svc.get("ordered_diverse") else "MAJOR",
                    specific_problem="ENTERPRISE_CIRCUIT_LEG_DOWN",
                    probable_cause="Transport / Access Fiber Outage",
                    raw_text=(
                        f"[NMSWorks CygNet SIA] Circuit {svc['id']} ({svc['type']} {svc['bw']}) "
                        f"leg '{leg['name']}' DOWN for customer {svc['customer']}"
                    ),
                    extra={"service_id": svc["id"], "customer_id": svc["customer"], "leg": leg["name"]},
                )

    # 5. Ericsson ENM / Nokia 4G/5G Mobile RAN Hub & Tail Site Alarms (if RAN backhaul shares cable/duct)
    cut_ducts = set(cinfo["duct_ids"])
    for rsite in RAN_SITES:
        bh_cable = rsite.get("backhaul_cable")
        if bh_cable == cable_id or (bh_cable in cables_by_id and set(cables_by_id[bh_cable]["duct_ids"]) & cut_ducts):
            add_alarm(
                source_oem=rsite["controller"],
                protocol="3GPP-TMF642",
                layer="mobile_ran",
                resource_id=rsite["id"],
                node_id=rsite["id"],
                severity="CRITICAL",
                specific_problem="GNODEB_S1_NG_LINK_FAILURE",
                probable_cause="Backhaul Transport Link Down",
                raw_text=(
                    f"[Ericsson ENM] {rsite['name']}: S1-U / NG-C SCTP Association Lost to 5GC UPF/AMF; "
                    f"{len(rsite['cells'])} cells ({', '.join(rsite['cells'])}) out of service"
                ),
                extra={"cells": rsite["cells"], "hub_site": rsite["id"]},
            )
            # Cascade downstream daisy-chained tail sites!
            for tail_id in rsite.get("downstream_tails", []):
                tail_site = next((s for s in RAN_SITES if s["id"] == tail_id), None)
                if tail_site:
                    add_alarm(
                        source_oem=tail_site["controller"],
                        protocol="3GPP-TMF642",
                        layer="mobile_ran",
                        resource_id=tail_site["id"],
                        node_id=tail_site["id"],
                        severity="MAJOR",
                        specific_problem="DAISY_CHAIN_TAIL_SITE_ISOLATED",
                        probable_cause=f"Upstream Hub Site {rsite['id']} Backhaul Failure",
                        raw_text=(
                            f"[Ericsson ENM] {tail_site['name']}: Cascaded backhaul isolation via hub {rsite['id']}; "
                            f"cells {', '.join(tail_site['cells'])} unreachable"
                        ),
                        extra={"cells": tail_site["cells"], "upstream_hub": rsite["id"]},
                    )

    return alarms


# ---------------------------------------------------------------- Emulator Control Endpoints
class FaultInjectRequest(BaseModel):
    scenario_id: str | None = None
    fault_type: str | None = None  # fibre_cut | duct_cut | power_outage | optical_degradation
    target_id: str | None = None   # cable_id, duct_id, or node_id
    cut_ratio: float = 0.55
    skip_webhook: bool = False


@app.get("/", response_class=HTMLResponse)
async def emulator_landing_page() -> str:
    sample_cable = CABLES[0]["id"] if CABLES else "sample"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Pandita — Multi-OEM Network Emulator (:8001)</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; max-width: 880px; margin: 40px auto; padding: 0 24px; color: #111827; line-height: 1.55; background: #f8f9fb; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 22px 24px; margin-bottom: 18px; }}
    h1 {{ font-size: 20px; margin: 0 0 4px 0; }}
    h2 {{ font-size: 14px; margin: 0 0 12px 0; color: #111827; }}
    p {{ margin: 0 0 12px 0; font-size: 13.5px; color: #4b5563; }}
    .pill {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: #ecfdf5; color: #047857; }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{ padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 13px; display: flex; justify-content: space-between; gap: 12px; }}
    li:last-child {{ border-bottom: none; }}
    a {{ color: #1d4ed8; text-decoration: none; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12.5px; }}
    a:hover {{ text-decoration: underline; }}
    .btn {{ display: inline-block; padding: 7px 14px; border-radius: 8px; background: #111827; color: #fff !important; font-family: inherit; font-weight: 500; font-size: 12.5px; margin-right: 8px; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h1>Multi-OEM Telco Lab Emulator (:8001)</h1>
      <span class="pill">● Running ({len(ACTIVE_ALARMS)} active alarms)</span>
    </div>
    <p>Simulates 12 vendor network, GIS, OTDR, and ITSM interfaces so you can inspect raw protocol payloads, download binary <code>.sor</code> files, or trigger faults directly via API.</p>
    <div style="margin-top:14px;">
      <a class="btn" href="/docs">Open Interactive Swagger API (/docs)</a>
      <a class="btn" style="background:#4b5563;" href="http://127.0.0.1:5173">Back to NOC UI (:5173)</a>
    </div>
  </div>

  <div class="card">
    <h2>Live Emulated Vendor Endpoints (Click to Inspect)</h2>
    <ul>
      <li><span><strong>Emulator Health &amp; Scenarios</strong></span> <a href="/emulator/status">/emulator/status</a></li>
      <li><span><strong>Lepton GIS</strong> · OGC WFS GeoJSON Cables</span> <a href="/lepton-gis/wfs?typeName=osp:cables">/lepton-gis/wfs?typeName=osp:cables</a></li>
      <li><span><strong>VIAVI / EXFO OTDR</strong> · Parsed SR-4731 Trace JSON</span> <a href="/viavi-onmsi/api/v1/traces/{sample_cable}/parsed">/viavi-onmsi/api/v1/traces/{sample_cable}/parsed</a></li>
      <li><span><strong>VIAVI / EXFO OTDR</strong> · Raw Binary <code>.sor</code> File</span> <a href="/viavi-onmsi/api/v1/traces/{sample_cable}.sor">/viavi-onmsi/api/v1/traces/{sample_cable}.sor</a></li>
      <li><span><strong>Ciena MCP</strong> · DWDM Wavelengths &amp; Routing</span> <a href="/ciena-mcp/nsa/api/v1/fres">/ciena-mcp/nsa/api/v1/fres</a></li>
      <li><span><strong>Nokia NSP</strong> · OpenConfig OSNR &amp; Pre-FEC BER</span> <a href="/nokia-nsp/restconf/data/openconfig-optical">/nokia-nsp/restconf/data/openconfig-optical</a></li>
      <li><span><strong>Ericsson ENM</strong> · 3GPP TS 32.435 5G PM XML</span> <a href="/ericsson-enm/api/v1/pm-counters.xml">/ericsson-enm/api/v1/pm-counters.xml</a></li>
      <li><span><strong>Subsea CLS</strong> · PFE High-Voltage &amp; Repeater Telemetry</span> <a href="/subsea-cls/api/v1/telemetry">/subsea-cls/api/v1/telemetry</a></li>
      <li><span><strong>Comviva BSS</strong> · Enterprise Customers &amp; SLAs</span> <a href="/comviva-bss/tmf-api/customerManagement/v4/customer">/comviva-bss/tmf-api/customerManagement/v4/customer</a></li>
      <li><span><strong>ServiceNow ITSM / FSM</strong> · Created Work Orders</span> <a href="/servicenow/api/now/table/wm_order">/servicenow/api/now/table/wm_order</a></li>
      <li><span><strong>Jira Service Management</strong> · Created Master Issues</span> <a href="/jira/rest/api/3/issue">/jira/rest/api/3/issue</a></li>
    </ul>
  </div>
</body>
</html>"""


@app.get("/emulator/status")
async def get_emulator_status() -> dict[str, Any]:
    return {
        "status": "running",
        "active_faults": list(ACTIVE_FAULTS.values()),
        "active_alarm_count": len(ACTIVE_ALARMS),
        "jira_issue_count": len(JIRA_ISSUES),
        "servicenow_incident_count": len(SERVICENOW_INCIDENTS),
        "servicenow_work_order_count": len(SERVICENOW_WORK_ORDERS),
        "scenarios": FAULT_SCENARIOS,
        "operator_profiles": OPERATOR_PROFILES,
    }


@app.post("/emulator/faults/inject")
async def inject_fault(req: FaultInjectRequest) -> dict[str, Any]:
    scenario: dict[str, Any] | None = None
    if req.scenario_id:
        scenario = next((s for s in FAULT_SCENARIOS if s["id"] == req.scenario_id), None)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Unknown scenario {req.scenario_id}")
        fault_type = scenario["fault_type"]
        cut_ratio = float(scenario.get("cut_ratio", 0.55))
        target_id = scenario.get("target_cable") or scenario.get("target_duct") or scenario.get("target_node")
        scen_id = scenario["id"]
    else:
        fault_type = req.fault_type or "fibre_cut"
        target_id = req.target_id or "CBL-QZ-BB-01"
        cut_ratio = req.cut_ratio
        scen_id = f"custom_{fault_type}_{target_id}"

    new_alarms: list[dict[str, Any]] = []
    cables_by_id = {c["id"]: c for c in OSP_DATA["cables"]}

    if fault_type == "fibre_cut":
        new_alarms.extend(_synthesize_cable_cut_alarms(target_id, cut_ratio, scen_id))
    elif fault_type == "duct_cut":
        # A duct cut severs ALL cables running inside that duct!
        hit_cables = [c["id"] for c in OSP_DATA["cables"] if target_id in c["duct_ids"]]
        if not hit_cables:
            raise HTTPException(status_code=400, detail=f"No cables occupy duct {target_id}")
        for cid in hit_cables:
            new_alarms.extend(_synthesize_cable_cut_alarms(cid, cut_ratio, scen_id))
    elif fault_type == "power_outage":
        now = _now_iso()
        # Generate GPON OLT dying-gasp alarms + clean OTDR continuity trace + smart-grid CPE power-off
        new_alarms.extend([
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nmsworks_cygnet",
                "protocol": "TR-069/G.984-PLOAM",
                "layer": "gpon_access",
                "resource_id": "SPL-QZ-IND-02",
                "node_id": "QZ",
                "severity": "MAJOR",
                "specific_problem": "GPON_MASS_ONT_DYING_GASP",
                "probable_cause": "Customer Premises Commercial AC Power Loss (24/24 ONTs sent Dying-Gasp bit)",
                "raw_text": (
                    "[OLT-QZ-NK-01 / GenieACS] 24 of 24 ONTs on splitter SPL-QZ-IND-02 (cable CBL-QZ-AQI-01) "
                    "transmitted G.984 PLOAM Dying-Gasp within 650ms prior to link loss. Optical feeder Rx healthy."
                ),
                "raised_at": now,
                "extra": {"cable_id": "CBL-QZ-AQI-01", "dying_gasp_count": 24, "losi_without_gasp": 0},
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "viavi_onmsi",
                "protocol": "RFTS-REST+SOR",
                "layer": "fibre_osp",
                "resource_id": "CBL-QZ-AQI-01",
                "node_id": "QZ",
                "severity": "CLEARED",
                "specific_problem": "OTDR_CONTINUITY_VERIFIED_NO_CUT",
                "probable_cause": "On-demand 1625nm OTDR trace confirms intact fiber end-to-end (no break)",
                "raw_text": (
                    f"[ONMSI-RTU-QZ] Triggered 1625nm check on CBL-QZ-AQI-01: End-to-end continuity verified "
                    f"({cables_by_id['CBL-QZ-AQI-01']['optical_length_m']} m, total loss 0.84 dB). Zero fiber fault."
                ),
                "raised_at": now,
                "extra": {"cable_id": "CBL-QZ-AQI-01", "fiber_intact": True},
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nmsworks_cygnet",
                "protocol": "NMSWorks-REST",
                "layer": "enterprise_sla",
                "resource_id": "SVC-AQI-DIA-01:primary",
                "node_id": "C_AQI",
                "severity": "MAJOR",
                "specific_problem": "CPE_POWER_DOWN_DYING_GASP",
                "probable_cause": "Premises AC Mains Outage at Al Quoz Industrial Smart-Grid Hub",
                "raw_text": (
                    "[NMSWorks CygNet] CPE-C_AQI-01 reported SNMP sysUpTime power-fail trap & 802.3ah OAM Dying Gasp "
                    "on SVC-AQI-DIA-01 (Customer CUST-1008)"
                ),
                "raised_at": now,
                "extra": {"service_id": "SVC-AQI-DIA-01", "customer_id": "CUST-1008", "dying_gasp": True},
            },
        ])
    elif fault_type == "optical_degradation":
        now = _now_iso()
        cinfo = cables_by_id["CBL-AIR-DSO-01"]
        _, optical_deg_m, _, _ = _optical_cut_distance_for_cable(cinfo, cut_ratio)
        OPTICAL_PM_STATE["OCH-SODC-AIR"].update({
            "osnr_db": 14.2,
            "pre_fec_ber": 8.4e-4,
            "rx_power_dbm": -16.9,
            "operational_state": "DEGRADED_TCA",
            "updated_at": now,
        })
        new_alarms.extend([
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nokia_nsp",
                "protocol": "OpenConfig-gNMI",
                "layer": "dwdm_optical",
                "resource_id": "OCH-SODC-AIR",
                "node_id": "DSO",
                "severity": "MAJOR",
                "specific_problem": "OPTICAL_PRE_FEC_BER_TCA_BREACH",
                "probable_cause": "High-Loss Bend / Pinched Splice Degrading OSNR Before Hard Failure",
                "raw_text": (
                    "[Nokia NSP 1830 PSS] OCh OCH-SODC-AIR (100G 193.70THz DSO<->AIR): 15-min TCA crossed — "
                    "Pre-FEC BER degraded from 1.2e-6 to 8.4e-4 (FEC uncorrectable margin < 1.1 dB), OSNR dropped "
                    "to 14.2 dB, span RxPower -16.9 dBm on CBL-AIR-DSO-01."
                ),
                "raised_at": now,
                "extra": {
                    "cable_id": "CBL-AIR-DSO-01",
                    "och_id": "OCH-SODC-AIR",
                    "service_id": "SVC-SODC-DCI-100G",
                    "pre_fec_ber": 8.4e-4,
                    "osnr_db": 14.2,
                    "optical_event_distance_m": optical_deg_m,
                },
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "exfo_nova",
                "protocol": "RFTS-REST+SOR",
                "layer": "fibre_osp",
                "resource_id": "CBL-AIR-DSO-01",
                "node_id": "AIR",
                "severity": "WARNING",
                "specific_problem": "OTDR_NON_REFLECTIVE_HIGH_SPLICE_LOSS",
                "probable_cause": f"4.8 dB macro-bend / splice attenuation anomaly at {optical_deg_m:.1f} m",
                "raw_text": (
                    f"[NOVA-RTU-AIR] EXFO Nova OTDR comparison on CBL-AIR-DSO-01 detected +4.8 dB non-reflective "
                    f"macro-bend loss step at optical distance {optical_deg_m:.1f} m from AIR POP."
                ),
                "raised_at": now,
                "extra": {
                    "cable_id": "CBL-AIR-DSO-01",
                    "launch_node": "AIR",
                    "optical_distance_m": optical_deg_m,
                },
            },
        ])
    elif fault_type == "ran_battery_lvd":
        now = _now_iso()
        RAN_PM_STATE["RAN_BB_HUB"].update({
            "operational_state": "ON_BATTERY_CRITICAL_LVD_RISK",
            "ac_mains_status": "FAILED",
            "dc_bus_voltage_v": 44.1,
            "battery_remaining_mins": 36,
            "cabinet_temp_c": 44.8,
            "updated_at": now,
        })
        _send_udp_snmp_trap({
            "enterprise_oid": "1.3.6.1.4.1.193.183.4.1",
            "agent": "RAN_BB_HUB",
            "specific_trap": "cePowerRectifierAcMainsFail",
            "dcVoltageV": 44.1,
            "lvdThresholdV": 43.2,
            "remainingMinutes": 36,
        })
        new_alarms.extend([
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "ericsson_enm",
                "protocol": "3GPP-TS28.532+SNMP",
                "layer": "mobile_ran",
                "resource_id": "RAN_BB_HUB",
                "node_id": "BB",
                "severity": "CRITICAL",
                "specific_problem": "RAN_RECTIFIER_AC_MAINS_FAIL_LVD_COUNTDOWN",
                "probable_cause": "Commercial 3-Phase AC Mains Loss; DC Bus Discharging on VRLA Battery (44.1V -> LVD at 43.2V, 36 mins left)",
                "raw_text": (
                    "[Ericsson ENM / Enclosure Power] gNB-BB-01 (RAN_BB_HUB): Rectifier AC Mains Fail. "
                    "Site running on VRLA battery bank: Vdc = 44.1V (LVD trip at 43.2V, est. 36 mins remaining). "
                    "Downstream daisy-chained tail sites gNB-BB-02 (RAN_BB_T1) & gNB-BB-03 (RAN_BB_T2) will lose CSR backhaul if LVD trips!"
                ),
                "raised_at": now,
                "extra": {
                    "site_id": "RAN_BB_HUB",
                    "dc_bus_voltage_v": 44.1,
                    "lvd_threshold_v": 43.2,
                    "battery_remaining_mins": 36,
                    "cells": ["CELL-BB01-N78-S1", "CELL-BB01-N78-S2", "CELL-BB01-N78-S3", "CELL-BB01-B3-S1"],
                    "cascaded_tail_sites": ["RAN_BB_T1", "RAN_BB_T2"],
                },
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "ericsson_enm",
                "protocol": "3GPP-TS32.435-PM",
                "layer": "mobile_ran",
                "resource_id": "RAN_BB_HUB",
                "node_id": "BB",
                "severity": "MAJOR",
                "specific_problem": "RAN_ENCLOSURE_HIGH_TEMP_HVAC_OFF",
                "probable_cause": "Outdoor cabinet HVAC shed on AC loss; internal temp 44.8°C (+1.4°C/10min)",
                "raw_text": (
                    "[Ericsson ENM] gNB-BB-01 Baseband 6648 thermal sensor 44.8°C (HVAC load-shed active on battery)."
                ),
                "raised_at": now,
                "extra": {"site_id": "RAN_BB_HUB", "cabinet_temp_c": 44.8, "cells": []},
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "viavi_onmsi",
                "protocol": "RFTS-REST+SOR",
                "layer": "fibre_osp",
                "resource_id": "CBL-BB-RANHUB-01",
                "node_id": "QZ",
                "severity": "CLEARED",
                "specific_problem": "OTDR_CONTINUITY_VERIFIED_NO_CUT",
                "probable_cause": "Backhaul fiber CBL-BB-RANHUB-01 optical continuity 100% healthy",
                "raw_text": "[ONMSI-RTU-QZ] Backhaul fiber CBL-BB-RANHUB-01 optical path healthy (no fiber break).",
                "raised_at": now,
                "extra": {"cable_id": "CBL-BB-RANHUB-01", "fiber_intact": True},
            },
        ])
    elif fault_type == "microwave_rain_fade":
        now = _now_iso()
        RAN_PM_STATE["RAN_DSO_MW1"].update({
            "operational_state": "DEGRADED_ACM_WEATHER_FADE",
            "mw_rsl_dbm": -69.4,
            "mw_snr_db": 9.2,
            "mw_acm_modulation": "QPSK (650 Mbps — Downshifted from 1024QAM)",
            "rain_rate_mm_hr": 42.0,
            "dl_prb_util_pct": 91.5,
            "erab_drop_rate_pct": 1.45,
            "updated_at": now,
        })
        new_alarms.extend([
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nokia_nsp",
                "protocol": "NETCONF/Wavence-PM",
                "layer": "mobile_ran",
                "resource_id": "RAN_DSO_MW1",
                "node_id": "DSO",
                "severity": "MAJOR",
                "specific_problem": "MW_EBAND_RSL_DEEP_FADE_ACM_QPSK",
                "probable_cause": "80GHz E-Band Atmospheric Rain Attenuation (42 mm/hr squall); RSL dropped 31.2 dB (-38.2 -> -69.4 dBm)",
                "raw_text": (
                    "[Nokia Wavence UBT-m 80GHz] Link MW-DSO-ACAD-80G (DSO <-> gNB-DSO-04): RSL -69.4 dBm, SNR 9.2 dB. "
                    "Adaptive Coding & Modulation (ACM) downshifted 1024QAM (10 Gbps) -> QPSK (650 Mbps). "
                    "Transceiver TX power normal (+18.0 dBm); adjacent 80GHz hops in DSO sector report correlated rain attenuation."
                ),
                "raised_at": now,
                "extra": {
                    "site_id": "RAN_DSO_MW1",
                    "mw_link_id": "MW-DSO-ACAD-80G",
                    "rsl_dbm": -69.4,
                    "snr_db": 9.2,
                    "acm_state": "QPSK",
                    "rain_rate_mm_hr": 42.0,
                    "hardware_healthy": True,
                    "cells": ["CELL-DSO04-N78-S1", "CELL-DSO04-B3-S1"],
                },
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nmsworks_cygnet",
                "protocol": "CygNet-SIA",
                "layer": "ip_mpls",
                "resource_id": "CSR-DSO-MW1:eth0",
                "node_id": "DSO",
                "severity": "WARNING",
                "specific_problem": "BACKHAUL_QOS_BE_QUEUE_TAIL_DROP",
                "probable_cause": "Best-Effort queue congestion due to temporary microwave ACM bandwidth compression; VoNR/Control-Plane EF queue 0% loss",
                "raw_text": (
                    "[NMSWorks CygNet] Cell-site router CSR-DSO-MW1: Best-Effort queue tail-drop during E-band ACM QPSK profile; "
                    "5G VoNR & 3GPP F1-C control plane protected via DiffServ EF."
                ),
                "raised_at": now,
                "extra": {"site_id": "RAN_DSO_MW1"},
            },
        ])
    elif fault_type == "subsea_shunt":
        now = _now_iso()
        SUBSEA_STATE["SUBSEA-FALCON-JBL-MUM"].update({
            "operational_state": "SHUNT_FAULT_SINGLE_END_FEED_REQUIRED",
            "pfe_voltage_v": 2890.0,
            "pfe_current_ma": 950.0,
            "earth_leakage_ma": 318.5,
            "shunt_fault_detected": True,
            "cotdr_shunt_distance_km": 412.6,
            "fault_span": "Repeater Span R07 -> R08 (14.2 km seaward of R07)",
            "water_depth_m": 68,
            "updated_at": now,
        })
        OPTICAL_PM_STATE["OCH-JLC-W"].update({
            "osnr_db": 16.8,
            "pre_fec_ber": 3.9e-4,
            "operational_state": "SUBSEA_SHUNT_RISK",
            "updated_at": now,
        })
        new_alarms.extend([
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "ciena_mcp",
                "protocol": "Subsea-PFE+COTDR",
                "layer": "dwdm_optical",
                "resource_id": "OCH-JLC-W",
                "node_id": "JBL",
                "severity": "CRITICAL",
                "specific_problem": "SUBSEA_PFE_SHUNT_FAULT_REPEATER_SPAN",
                "probable_cause": "Wet-plant insulation shunt fault on SUBSEA-FALCON-JBL-MUM at 412.6 km from Jebel Ali CLS (Span R07-R08)",
                "raw_text": (
                    "[Jebel Ali CLS PFE-JBL-01 & Ciena WaveLogic 5e] Subsea cable SUBSEA-FALCON-JBL-MUM: PFE output voltage "
                    "dropped from +4,120V to +2,890V at 950mA constant current (earth leakage 318.5mA). Coherent OTDR (C-OTDR) "
                    "pinpoints insulation shunt fault 412.6 km from Jebel Ali CLS (14.2 km past Repeater R07, depth 68m). "
                    "Optical pump current on R07/R08 degraded (-2.4 dB gain tilt on OCH-JLC-W)."
                ),
                "raised_at": now,
                "extra": {
                    "subsea_cable_id": "SUBSEA-FALCON-JBL-MUM",
                    "cls_node": "JBL",
                    "pfe_id": "PFE-JBL-01",
                    "pfe_voltage_v": 2890.0,
                    "cotdr_shunt_distance_km": 412.6,
                    "fault_span": "Repeater Span R07 -> R08 (14.2 km past R07)",
                    "water_depth_m": 68,
                    "service_id": "SVC-JLC-WAVE-100G",
                    "och_id": "OCH-JLC-W",
                },
            },
            {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8].upper()}",
                "scenario_id": scen_id,
                "source_oem": "nmsworks_cygnet",
                "protocol": "TMF642",
                "layer": "enterprise_sla",
                "resource_id": "SVC-JLC-WAVE-100G:working",
                "node_id": "C_JLC",
                "severity": "MAJOR",
                "specific_problem": "WHOLESALE_DCI_SUBSEA_PROTECTION_ALERT",
                "probable_cause": "Subsea wet-plant shunt fault threatening Jebel Ali Logistics Cloud 100G DCI wave",
                "raw_text": (
                    "[NMSWorks CygNet] Wholesale 100G DCI service SVC-JLC-WAVE-100G on subsea feeder SUBSEA-FALCON-JBL-MUM "
                    "requires PFE polarity rebalance & protection switch."
                ),
                "raised_at": now,
                "extra": {"service_id": "SVC-JLC-WAVE-100G", "customer_id": "CUST-1004"},
            },
        ])


    ACTIVE_FAULTS[scen_id] = {
        "scenario_id": scen_id,
        "fault_type": fault_type,
        "target_id": target_id,
        "cut_ratio": cut_ratio,
        "injected_at": _now_iso(),
        "alarm_count": len(new_alarms),
    }
    ACTIVE_ALARMS.extend(new_alarms)
    asyncio.create_task(_publish_alarms_to_kafka_and_webhook(new_alarms, skip_webhook=req.skip_webhook))
    return {"injected": ACTIVE_FAULTS[scen_id], "alarms_emitted": len(new_alarms), "alarms": new_alarms}


@app.post("/emulator/faults/clear")
async def clear_all_faults() -> dict[str, Any]:
    ACTIVE_FAULTS.clear()
    ACTIVE_ALARMS.clear()
    REROUTED_WAVELENGTHS.clear()
    _init_baseline_traces_and_pm()
    return {"status": "cleared"}


# ---------------------------------------------------------------- 1. Ciena MCP Emulator
@app.get("/ciena-mcp/nsa/api/v1/alarms")
async def ciena_mcp_alarms() -> dict[str, Any]:
    items = [a for a in ACTIVE_ALARMS if a["source_oem"] == "ciena_mcp"]
    return {"meta": {"vendor": "Ciena", "system": "MCP 7.2", "total": len(items)}, "data": items}


@app.get("/ciena-mcp/nsa/api/v1/fres")
async def ciena_mcp_fres() -> dict[str, Any]:
    """Forwarding Resource Endpoints (OMS & OCh wavelengths in Ciena domain)."""
    ciena_ochs = [w for w in WAVELENGTHS if OPTICAL.get(w["path"][0]) == "ciena"]
    return {
        "meta": {"vendor": "Ciena", "system": "MCP 7.2"},
        "oms_sections": [
            {"id": f"OMS-{a}-{b}", "a": a, "b": b, "cable_id": c}
            for a, b, c in OMS
            if OPTICAL.get(a) == "ciena"
        ],
        "wavelengths": ciena_ochs,
        "pm_telemetry": {k: v for k, v in OPTICAL_PM_STATE.items() if any(w["id"] == k for w in ciena_ochs)},
        "reroutes": REROUTED_WAVELENGTHS,
    }


class WavelengthRerouteRequest(BaseModel):
    new_path: list[str]
    reason: str
    approved_by: str


@app.post("/ciena-mcp/nsa/api/v1/fres/{och_id}/reroute")
async def ciena_mcp_reroute_wavelength(och_id: str, req: WavelengthRerouteRequest) -> dict[str, Any]:
    if och_id not in OPTICAL_PM_STATE:
        raise HTTPException(status_code=404, detail=f"Unknown OCh {och_id}")
    OPTICAL_PM_STATE[och_id]["path"] = req.new_path
    OPTICAL_PM_STATE[och_id]["operational_state"] = "UP_REROUTED"
    OPTICAL_PM_STATE[och_id]["osnr_db"] = 25.2
    OPTICAL_PM_STATE[och_id]["pre_fec_ber"] = 1.8e-6
    OPTICAL_PM_STATE[och_id]["rx_power_dbm"] = -8.4
    OPTICAL_PM_STATE[och_id]["updated_at"] = _now_iso()
    rec = {
        "och_id": och_id,
        "new_path": req.new_path,
        "reason": req.reason,
        "approved_by": req.approved_by,
        "executed_at": _now_iso(),
        "status": "PROVISIONED_HITLESS",
    }
    REROUTED_WAVELENGTHS[och_id] = rec
    return rec


# ---------------------------------------------------------------- 2. Nokia NSP Emulator
@app.get("/nokia-nsp/restconf/data/openconfig-optical")
async def nokia_nsp_optical() -> dict[str, Any]:
    nokia_ochs = [w for w in WAVELENGTHS if OPTICAL.get(w["path"][0]) == "nokia"]
    return {
        "vendor": "Nokia",
        "system": "NSP 24.8 / WaveSuite",
        "oms_sections": [
            {"id": f"OMS-{a}-{b}", "a": a, "b": b, "cable_id": c}
            for a, b, c in OMS
            if OPTICAL.get(a) == "nokia"
        ],
        "wavelengths": nokia_ochs,
        "pm_telemetry": {k: v for k, v in OPTICAL_PM_STATE.items() if any(w["id"] == k for w in nokia_ochs)},
    }


@app.get("/nokia-nsp/tmf-api/alarmManagement/v4/alarm")
async def nokia_nsp_alarms() -> list[dict[str, Any]]:
    return [a for a in ACTIVE_ALARMS if a["source_oem"] == "nokia_nsp"]


# ---------------------------------------------------------------- 3. NMSWorks CygNet OSS Emulator
@app.get("/nmsworks-cygnet/api/v2/inventory/topology")
async def nmsworks_topology() -> dict[str, Any]:
    return {
        "oss": "NMSWorks CygNet v12.4",
        "nodes": NODES,
        "routers": {
            nid: {"id": f"RTR-{nid}-01", "vendor": v, "model": m, "pop": nid}
            for nid, (v, m) in ROUTERS.items()
        },
        "optical_elements": {
            nid: {
                "id": f"ROADM-{nid}-01",
                "vendor": v,
                "model": "Ciena 6500" if v == "ciena" else "Nokia 1830 PSS-32",
                "pop": nid,
            }
            for nid, v in OPTICAL.items()
        },
        "oms_links": [{"id": f"OMS-{a}-{b}", "a": a, "b": b, "cable_id": c} for a, b, c in OMS],
        "wavelengths": WAVELENGTHS,
        "ip_links": [{"id": f"IPL-{a}-{b}", "a": a, "b": b, "transport": t} for a, b, t in IP_LINKS],
        "ran_sites": RAN_SITES,
        "gpon_splitters": GPON_SPLITTER_CLUSTERS,
    }


@app.get("/nmsworks-cygnet/api/v2/alarms")
async def nmsworks_alarms() -> dict[str, Any]:
    return {"oss": "NMSWorks CygNet v12.4", "count": len(ACTIVE_ALARMS), "alarms": ACTIVE_ALARMS}


# ---------------------------------------------------------------- 4. NetBox DCIM / Circuits Emulator
@app.get("/netbox/api/dcim/sites/")
async def netbox_sites() -> dict[str, Any]:
    results = [
        {"id": i + 1, "slug": nid.lower(), "name": n["name"], "kind": n["kind"], "latitude": n["lat"], "longitude": n["lon"]}
        for i, (nid, n) in enumerate(NODES.items())
    ]
    return {"count": len(results), "results": results}


@app.get("/netbox/api/circuits/circuits/")
async def netbox_circuits() -> dict[str, Any]:
    return {"count": len(SERVICES), "results": SERVICES}


# ---------------------------------------------------------------- 5. Lepton Software GIS (OGC WFS GeoJSON)
@app.get("/lepton-gis/wfs")
async def lepton_gis_wfs(
    typeName: str = Query("osp:all", description="osp:ducts | osp:cables | osp:manholes | osp:all"),
) -> dict[str, Any]:
    """Authentic OGC WFS GeoJSON FeatureCollection for Lepton SmartInventory / NetworkAccess."""
    features: list[dict[str, Any]] = []
    if typeName in ("osp:ducts", "osp:all"):
        for d in OSP_DATA["ducts"]:
            features.append({
                "type": "Feature",
                "id": d["id"],
                "geometry": {"type": "LineString", "coordinates": d["coordinates"]},
                "properties": {
                    "feature_type": "duct",
                    "duct_id": d["id"],
                    "node_a": d["node_a"],
                    "node_b": d["node_b"],
                    "bridge": d.get("bridge"),
                    "trench_length_m": d["trench_length_m"],
                },
            })
    if typeName in ("osp:cables", "osp:all"):
        for c in OSP_DATA["cables"]:
            features.append({
                "type": "Feature",
                "id": c["id"],
                "geometry": {"type": "LineString", "coordinates": c["coordinates"]},
                "properties": {
                    "feature_type": "cable",
                    "cable_id": c["id"],
                    "path_nodes": c["path_nodes"],
                    "duct_ids": c["duct_ids"],
                    "bridges": c["bridges"],
                    "fibres": c["fibres"],
                    "role": c["role"],
                    "helix_factor": c["helix_factor"],
                    "trench_length_m": c["trench_length_m"],
                    "optical_length_m": c["optical_length_m"],
                    "splices": c["splices"],
                },
            })
    if typeName in ("osp:manholes", "osp:all"):
        for mh in OSP_DATA["manholes"]:
            features.append({
                "type": "Feature",
                "id": mh["id"],
                "geometry": {"type": "Point", "coordinates": [mh["lon"], mh["lat"]]},
                "properties": {
                    "feature_type": "manhole",
                    "manhole_id": mh["id"],
                    "node_id": mh["node_id"],
                    "name": mh["name"],
                    "kind": mh["kind"],
                    "slack_coil_m": mh["slack_coil_m"],
                },
            })
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "vendor": "Lepton Software SmartInventory / NetworkAccess GIS",
        "features": features,
    }


# ---------------------------------------------------------------- 6. VIAVI ONMSi & EXFO Nova RFTS OTDR Emulators
@app.get("/viavi-onmsi/api/v1/rtus")
async def viavi_rtus() -> dict[str, Any]:
    return {
        "system": "VIAVI ONMSi Optical Network Monitoring System",
        "rtus": RFTS,
        "measurements": list(OTDR_MEASUREMENT_META.values()),
    }


@app.get("/viavi-onmsi/api/v1/traces/{cable_id}.sor")
@app.get("/exfo-nova/api/v1/traces/{cable_id}.sor")
async def download_sor_trace(cable_id: str) -> Response:
    raw = GENERATED_SOR_TRACES.get(cable_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"No .sor trace for {cable_id}")
    return Response(
        content=raw,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{cable_id}.sor"'},
    )


@app.get("/viavi-onmsi/api/v1/traces/{cable_id}/parsed")
async def get_parsed_sor_preview(cable_id: str) -> dict[str, Any]:
    raw = GENERATED_SOR_TRACES.get(cable_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"No .sor trace for {cable_id}")
    parsed = parse_sor_bytes(raw)
    return {
        "cable_id": parsed.cable_id,
        "wavelength_nm": parsed.wavelength_nm,
        "supplier_name": parsed.supplier_name,
        "unit_name": parsed.unit_name,
        "serial_number": parsed.serial_number,
        "location_a": parsed.location_a,
        "location_b": parsed.location_b,
        "refractive_index": parsed.refractive_index,
        "pulse_width_ns": parsed.pulse_width_ns,
        "range_m": parsed.range_m,
        "sample_spacing_m": parsed.sample_spacing_m,
        "crc_valid": parsed.crc_valid,
        "byte_size": len(raw),
        "fault_distance_optical_m": parsed.fault_distance_optical_m,
        "key_events": [vars(e) for e in parsed.key_events],
        "trace_points_db": parsed.trace_points_db[::4],  # 250 points for smooth chart rendering
    }


# ---------------------------------------------------------------- 7. Ericsson ENM, 3GPP TS 32.435 PM XML, Subsea CLS & GPON Emulator
@app.get("/ericsson-enm/api/v1/ran-sites")
async def ericsson_ran_sites() -> dict[str, Any]:
    return {
        "system": "Ericsson Network Manager (ENM) + Nokia MantaRay + 3GPP TS 32.435 PM",
        "sites": RAN_SITES,
        "pm_telemetry": list(RAN_PM_STATE.values()),
        "subsea_systems": list(SUBSEA_STATE.values()),
    }


@app.get("/ericsson-enm/api/v1/pm-counters.xml")
async def ericsson_3gpp_pm_xml() -> Response:
    """Authentic 3GPP TS 32.435 <measCollecFile> XML performance counter document."""
    now = _now_iso()
    meas_blocks: list[str] = []
    for s in RAN_PM_STATE.values():
        meas_blocks.append(
            f"""    <measInfo measInfoId="NR_Cell_And_Enclosure_PM_{s['site_id']}">
      <granPeriod duration="PT900S" endTime="{now}"/>
      <measType p="1">RRU.PrbTotDl</measType>
      <measType p="2">RRU.PrbTotUl</measType>
      <measType p="3">RRC.ConnEstabSuccRate</measType>
      <measType p="4">DRB.ErabDropRate</measType>
      <measType p="5">Enclosure.DcBusVoltageV</measType>
      <measType p="6">Enclosure.BatteryRemainingMins</measType>
      <measType p="7">Microwave.RslDbm</measType>
      <measValue measObjLdn="ManagedElement={s['site_id']},GNBDUFunction=1">
        <r p="1">{s['dl_prb_util_pct']}</r>
        <r p="2">{s['ul_prb_util_pct']}</r>
        <r p="3">{s['rrc_conn_success_pct']}</r>
        <r p="4">{s['erab_drop_rate_pct']}</r>
        <r p="5">{s['dc_bus_voltage_v']}</r>
        <r p="6">{s['battery_remaining_mins']}</r>
        <r p="7">{s['mw_rsl_dbm'] if s['mw_rsl_dbm'] is not None else 'NIL'}</r>
      </measValue>
    </measInfo>"""
        )
    xml_doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<measCollecFile xmlns="http://www.3gpp.org/ftp/specs/archive/32_series/32.435#measCollec">\n'
        f'  <fileHeader fileFormatVersion="32.435 V17.0" vendorName="Ericsson ENM / Nokia NSP">\n'
        f'    <fileSender localDn="SubNetwork=UAE_Metro_5G"/>\n'
        f'    <measCollec beginTime="{now}"/>\n'
        '  </fileHeader>\n'
        '  <measData>\n'
        + "\n".join(meas_blocks)
        + '\n  </measData>\n'
        f'  <fileFooter>\n    <measCollec endTime="{now}"/>\n  </fileFooter>\n'
        '</measCollecFile>\n'
    )
    return Response(content=xml_doc, media_type="application/xml")


@app.get("/subsea-cls/api/v1/telemetry")
async def subsea_cls_telemetry() -> dict[str, Any]:
    return {
        "system": "Subsea Cable Landing Station PFE & C-OTDR Supervisor",
        "cables": list(SUBSEA_STATE.values()),
    }



@app.get("/genieacs/devices")
async def genieacs_gpon_devices() -> dict[str, Any]:
    return {"system": "GenieACS TR-069/TR-369 + GPON OLT Manager", "splitter_clusters": GPON_SPLITTER_CLUSTERS}


# ---------------------------------------------------------------- 8. Comviva BSS (TMF629 Customer & TMF638 Service + SLA)
@app.get("/comviva-bss/tmf-api/customerManagement/v4/customer")
async def comviva_customers() -> dict[str, Any]:
    return {
        "bss": "Comviva BlueMarble / Ngage BSS",
        "customers": CUSTOMERS,
        "sla_tiers": SLA_TIERS,
        "services": SERVICES,
    }


# ---------------------------------------------------------------- 9. Jira Service Management REST v3 & ServiceNow ITSM/FSM
class JiraCreateIssue(BaseModel):
    project_key: str = "NOC"
    summary: str
    description: str
    issue_type: str = "Incident"
    priority: str = "Highest"
    labels: list[str] = []


@app.get("/jira/rest/api/3/issue")
async def list_jira_issues() -> dict[str, Any]:
    return {"total": len(JIRA_ISSUES), "issues": list(reversed(JIRA_ISSUES))}


@app.post("/jira/rest/api/3/issue")
async def create_jira_issue(req: JiraCreateIssue) -> dict[str, Any]:
    issue_num = 4100 + len(JIRA_ISSUES) + 1
    key = f"{req.project_key}-{issue_num}"
    issue = {
        "id": str(issue_num),
        "key": key,
        "self": f"http://127.0.0.1:8001/jira/rest/api/3/issue/{key}",
        "fields": {
            "summary": req.summary,
            "description": req.description,
            "issuetype": {"name": req.issue_type},
            "priority": {"name": req.priority},
            "status": {"name": "In Progress"},
            "labels": req.labels,
            "created": _now_iso(),
        },
    }
    JIRA_ISSUES.append(issue)
    return issue


class ServiceNowRecord(BaseModel):
    short_description: str
    description: str = ""
    urgency: str = "1"
    impact: str = "1"
    cmdb_ci: str = ""
    assignment_group: str = "OSP Field Fibre Engineering"
    location_lat: float | None = None
    location_lon: float | None = None


@app.get("/servicenow/api/now/table/{table_name}")
async def list_servicenow_table(table_name: str) -> dict[str, Any]:
    if table_name == "incident":
        return {"result": list(reversed(SERVICENOW_INCIDENTS))}
    if table_name == "wm_order":
        return {"result": list(reversed(SERVICENOW_WORK_ORDERS))}
    if table_name == "change_request":
        return {"result": SERVICENOW_CHANGES}
    raise HTTPException(status_code=404, detail=f"Unknown table {table_name}")


@app.post("/servicenow/api/now/table/{table_name}")
async def create_servicenow_record(table_name: str, req: ServiceNowRecord) -> dict[str, Any]:
    if table_name == "incident":
        num = f"INC009{100 + len(SERVICENOW_INCIDENTS) + 1}"
        rec = {
            "sys_id": uuid.uuid4().hex,
            "number": num,
            "state": "In Progress",
            "Opened_at": _now_iso(),
            **req.model_dump(),
        }
        SERVICENOW_INCIDENTS.append(rec)
        return {"result": rec}
    if table_name == "wm_order":
        num = f"WOT005{200 + len(SERVICENOW_WORK_ORDERS) + 1}"
        rec = {
            "sys_id": uuid.uuid4().hex,
            "number": num,
            "state": "Assigned — Field Crew Dispatched",
            "opened_at": _now_iso(),
            **req.model_dump(),
        }
        SERVICENOW_WORK_ORDERS.append(rec)
        return {"result": rec}
    raise HTTPException(status_code=404, detail=f"Unknown table {table_name}")
