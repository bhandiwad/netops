"""Connector Registry, Normalized Inventory Sync, OTDR Adapter & Northbound Executor."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from shared.sor_codec import OtdrTrace, parse_sor_bytes
from ..db import DEFAULT_EMULATOR_BASE, get_conn
from .base import NorthboundActionAdapter, OtdrTraceAdapter


def get_connectors_map(only_enabled: bool = True) -> dict[str, dict[str, Any]]:
    sql = "SELECT * FROM connectors WHERE enabled = TRUE ORDER BY id" if only_enabled else "SELECT * FROM connectors ORDER BY id"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return {r["id"]: dict(r) for r in cur.fetchall()}


def _save_state_snapshot(cur: Any, key: str, payload: Any, connector_id: str, latency_ms: float, rec_count: int) -> None:
    cur.execute(
        """
        INSERT INTO topology_state (key, payload, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
        """,
        (key, json.dumps(payload)),
    )
    cur.execute(
        "UPDATE connectors SET status='CONNECTED', latency_ms=%s, records_synced=%s, last_sync_at=NOW() WHERE id=%s",
        (latency_ms, rec_count, connector_id),
    )


async def sync_all_connectors() -> dict[str, Any]:
    """Pull inventory, GIS geometry, optical/RAN PM state, and BSS SLA data into normalized PostgreSQL tables."""
    cmap = get_connectors_map(only_enabled=True)
    summary: dict[str, Any] = {"synced": [], "errors": []}

    async with httpx.AsyncClient(timeout=6.0) as client:
        # 1. Lepton GIS WFS -> osp_ducts, osp_manholes, osp_cables (PostGIS)
        if "lepton_gis" in cmap:
            c = cmap["lepton_gis"]
            t0 = time.perf_counter()
            try:
                r = await client.get(c["endpoint_url"], params={"typeName": "osp:all"})
                r.raise_for_status()
                fc = r.json()
                feats = fc.get("features", [])
                latency = round((time.perf_counter() - t0) * 1000, 1)
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for f in feats:
                            props = f["properties"]
                            geom_json = json.dumps(f["geometry"])
                            ftype = props["feature_type"]
                            if ftype == "duct":
                                cur.execute(
                                    """
                                    INSERT INTO osp_ducts (id, node_a, node_b, bridge, trench_length_m, coords_json, geom)
                                    VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                                    ON CONFLICT (id) DO UPDATE SET
                                        node_a = EXCLUDED.node_a,
                                        node_b = EXCLUDED.node_b,
                                        bridge = EXCLUDED.bridge,
                                        trench_length_m = EXCLUDED.trench_length_m,
                                        coords_json = EXCLUDED.coords_json,
                                        geom = EXCLUDED.geom
                                    """,
                                    (
                                        props["duct_id"],
                                        props["node_a"],
                                        props["node_b"],
                                        props.get("bridge"),
                                        props["trench_length_m"],
                                        json.dumps(f["geometry"]["coordinates"]),
                                        geom_json,
                                    ),
                                )
                            elif ftype == "manhole":
                                lon, lat = f["geometry"]["coordinates"]
                                cur.execute(
                                    """
                                    INSERT INTO osp_manholes (id, node_id, name, kind, lat, lon, slack_coil_m, geom)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                                    ON CONFLICT (id) DO UPDATE SET
                                        name = EXCLUDED.name,
                                        kind = EXCLUDED.kind,
                                        lat = EXCLUDED.lat,
                                        lon = EXCLUDED.lon,
                                        slack_coil_m = EXCLUDED.slack_coil_m,
                                        geom = EXCLUDED.geom
                                    """,
                                    (
                                        props["manhole_id"],
                                        props["node_id"],
                                        props["name"],
                                        props["kind"],
                                        lat,
                                        lon,
                                        props["slack_coil_m"],
                                        geom_json,
                                    ),
                                )
                            elif ftype == "cable":
                                cur.execute(
                                    """
                                    INSERT INTO osp_cables (
                                        id, path_nodes, duct_ids, bridges, fibres, role,
                                        helix_factor, trench_length_m, optical_length_m,
                                        splices_json, coords_json, geom
                                    )
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                                    ON CONFLICT (id) DO UPDATE SET
                                        path_nodes = EXCLUDED.path_nodes,
                                        duct_ids = EXCLUDED.duct_ids,
                                        bridges = EXCLUDED.bridges,
                                        fibres = EXCLUDED.fibres,
                                        role = EXCLUDED.role,
                                        helix_factor = EXCLUDED.helix_factor,
                                        trench_length_m = EXCLUDED.trench_length_m,
                                        optical_length_m = EXCLUDED.optical_length_m,
                                        splices_json = EXCLUDED.splices_json,
                                        coords_json = EXCLUDED.coords_json,
                                        geom = EXCLUDED.geom
                                    """,
                                    (
                                        props["cable_id"],
                                        json.dumps(props["path_nodes"]),
                                        json.dumps(props["duct_ids"]),
                                        json.dumps(props["bridges"]),
                                        props["fibres"],
                                        props["role"],
                                        props["helix_factor"],
                                        props["trench_length_m"],
                                        props["optical_length_m"],
                                        json.dumps(props["splices"]),
                                        json.dumps(f["geometry"]["coordinates"]),
                                        geom_json,
                                    ),
                                )
                        cur.execute(
                            "UPDATE connectors SET status='CONNECTED', latency_ms=%s, records_synced=%s, last_sync_at=NOW() WHERE id='lepton_gis'",
                            (latency, len(feats)),
                        )
                summary["synced"].append({"id": "lepton_gis", "records": len(feats), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "lepton_gis", "error": str(e)})

        # 2. NMSWorks CygNet Unified Topology -> network_nodes, oms_links, optical_channels, ip_links, ran_sites, gpon_clusters
        if "nmsworks_cygnet" in cmap:
            c = cmap["nmsworks_cygnet"]
            t0 = time.perf_counter()
            try:
                r = await client.get(c["endpoint_url"].rstrip("/") + "/inventory/topology")
                r.raise_for_status()
                topo = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                nodes = topo.get("nodes", {})
                routers = topo.get("routers", {})
                opt_elems = topo.get("optical_elements", {})
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for nid, ninfo in nodes.items():
                            pt_geojson = json.dumps({"type": "Point", "coordinates": [ninfo["lon"], ninfo["lat"]]})
                            cur.execute(
                                """
                                INSERT INTO network_nodes (id, name, kind, lat, lon, router_json, optical_json, geom)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                                ON CONFLICT (id) DO UPDATE SET
                                    name = EXCLUDED.name,
                                    kind = EXCLUDED.kind,
                                    lat = EXCLUDED.lat,
                                    lon = EXCLUDED.lon,
                                    router_json = EXCLUDED.router_json,
                                    optical_json = EXCLUDED.optical_json,
                                    geom = EXCLUDED.geom
                                """,
                                (
                                    nid,
                                    ninfo["name"],
                                    ninfo["kind"],
                                    ninfo["lat"],
                                    ninfo["lon"],
                                    json.dumps(routers.get(nid, {})),
                                    json.dumps(opt_elems.get(nid, {})),
                                    pt_geojson,
                                ),
                            )
                        for oms in topo.get("oms_links", []):
                            vendor = opt_elems.get(oms["a"], {}).get("vendor", "ciena")
                            cur.execute(
                                """
                                INSERT INTO oms_links (id, node_a, node_b, cable_id, controller_vendor)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    cable_id = EXCLUDED.cable_id,
                                    controller_vendor = EXCLUDED.controller_vendor
                                """,
                                (oms["id"], oms["a"], oms["b"], oms["cable_id"], vendor),
                            )
                        for w in topo.get("wavelengths", []):
                            head_node = w["path"][0] if w.get("path") else ""
                            vendor = opt_elems.get(head_node, {}).get("vendor", "ciena")
                            ctrl_id = "ciena_mcp" if vendor == "ciena" else "nokia_nsp"
                            cur.execute(
                                """
                                INSERT INTO optical_channels (id, rate, freq_thz, path_nodes_json, service_id, leg_name, controller_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    rate = EXCLUDED.rate,
                                    freq_thz = EXCLUDED.freq_thz,
                                    path_nodes_json = EXCLUDED.path_nodes_json,
                                    service_id = EXCLUDED.service_id,
                                    leg_name = EXCLUDED.leg_name,
                                    controller_id = EXCLUDED.controller_id
                                """,
                                (
                                    w["id"],
                                    w["rate"],
                                    float(w["freq"]),
                                    json.dumps(w["path"]),
                                    w.get("service"),
                                    w.get("leg"),
                                    ctrl_id,
                                ),
                            )
                        for ipl in topo.get("ip_links", []):
                            cur.execute(
                                """
                                INSERT INTO ip_links (id, node_a, node_b, underlay_id)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET underlay_id = EXCLUDED.underlay_id
                                """,
                                (ipl["id"], ipl["a"], ipl["b"], ipl["transport"]),
                            )
                        for rsite in topo.get("ran_sites", []):
                            n_coord = nodes.get(rsite["id"], {})
                            lat = n_coord.get("lat")
                            lon = n_coord.get("lon")
                            pt_json = json.dumps({"type": "Point", "coordinates": [lon, lat]}) if (lat is not None and lon is not None) else None
                            cur.execute(
                                """
                                INSERT INTO ran_sites (
                                    id, name, vendor, controller_id, pop_anchor, hub_site_id,
                                    backhaul_type, backhaul_cable_id, mw_link_id, cells_json,
                                    downstream_tails_json, battery_backup_hours, lat, lon, geom
                                )
                                VALUES (
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    CASE WHEN %s IS NOT NULL THEN ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) ELSE NULL END
                                )
                                ON CONFLICT (id) DO UPDATE SET
                                    name = EXCLUDED.name,
                                    hub_site_id = EXCLUDED.hub_site_id,
                                    backhaul_type = EXCLUDED.backhaul_type,
                                    backhaul_cable_id = EXCLUDED.backhaul_cable_id,
                                    mw_link_id = EXCLUDED.mw_link_id,
                                    cells_json = EXCLUDED.cells_json,
                                    downstream_tails_json = EXCLUDED.downstream_tails_json,
                                    lat = EXCLUDED.lat,
                                    lon = EXCLUDED.lon,
                                    geom = EXCLUDED.geom
                                """,
                                (
                                    rsite["id"],
                                    rsite["name"],
                                    rsite["vendor"],
                                    rsite["controller"],
                                    rsite["pop_anchor"],
                                    rsite.get("hub_site"),
                                    rsite["backhaul_type"],
                                    rsite.get("backhaul_cable"),
                                    rsite.get("mw_link_id"),
                                    json.dumps(rsite["cells"]),
                                    json.dumps(rsite.get("downstream_tails", [])),
                                    float(rsite.get("battery_backup_hours", 4.0)),
                                    lat,
                                    lon,
                                    pt_json,
                                    pt_json,
                                ),
                            )
                        for gpon in topo.get("gpon_splitters", []):
                            cur.execute(
                                """
                                INSERT INTO gpon_clusters (id, olt_id, pop_node, feeder_cable_id, ont_count, district)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    olt_id = EXCLUDED.olt_id,
                                    feeder_cable_id = EXCLUDED.feeder_cable_id,
                                    ont_count = EXCLUDED.ont_count
                                """,
                                (
                                    gpon["id"],
                                    gpon["olt_id"],
                                    gpon["pop"],
                                    gpon["feeder_cable"],
                                    int(gpon["ont_count"]),
                                    gpon["district"],
                                ),
                            )
                        _save_state_snapshot(cur, "topology", topo, "nmsworks_cygnet", latency, len(nodes))
                summary["synced"].append({"id": "nmsworks_cygnet", "records": len(nodes), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "nmsworks_cygnet", "error": str(e)})

        # 3. Ciena MCP & Nokia NSP Optical PM Telemetry -> optical_channels
        for cid, suffix, state_key in [
            ("ciena_mcp", "/fres", "ciena_fres"),
            ("nokia_nsp", "/restconf/data/openconfig-optical", "nokia_optical"),
        ]:
            if cid not in cmap:
                continue
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap[cid]["endpoint_url"].rstrip("/") + suffix)
                r.raise_for_status()
                payload = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                pm_map = payload.get("pm_telemetry", {})
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for och_id, pm in pm_map.items():
                            cur.execute(
                                """
                                UPDATE optical_channels
                                SET path_nodes_json = COALESCE(%s, path_nodes_json),
                                    operational_state = %s,
                                    pm_json = %s,
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (
                                    json.dumps(pm["path"]) if pm.get("path") else None,
                                    pm.get("operational_state", "UP"),
                                    json.dumps(pm),
                                    och_id,
                                ),
                            )
                        _save_state_snapshot(cur, state_key, payload, cid, latency, len(pm_map))
                summary["synced"].append({"id": cid, "records": len(pm_map), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": cid, "error": str(e)})

        # 4. Comviva BSS -> sla_tiers, customers, customer_services
        if "comviva_bss" in cmap:
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap["comviva_bss"]["endpoint_url"].rstrip("/") + "/customerManagement/v4/customer")
                r.raise_for_status()
                bss = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for tname, tinfo in bss.get("sla_tiers", {}).items():
                            cur.execute(
                                """
                                INSERT INTO sla_tiers (tier_name, availability_pct, mttr_hours, penalty_per_hour_aed)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (tier_name) DO UPDATE SET
                                    availability_pct = EXCLUDED.availability_pct,
                                    mttr_hours = EXCLUDED.mttr_hours,
                                    penalty_per_hour_aed = EXCLUDED.penalty_per_hour_aed
                                """,
                                (tname, float(tinfo["availability"]), float(tinfo["mttr_hours"]), int(tinfo["penalty_per_hour_aed"])),
                            )
                        for cust in bss.get("customers", []):
                            cur.execute(
                                """
                                INSERT INTO customers (id, node_id, name, segment, sla_tier, contact)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    name = EXCLUDED.name,
                                    segment = EXCLUDED.segment,
                                    sla_tier = EXCLUDED.sla_tier,
                                    contact = EXCLUDED.contact
                                """,
                                (cust["id"], cust["node"], cust["name"], cust["segment"], cust["tier"], cust["contact"]),
                            )
                        for svc in bss.get("services", []):
                            cur.execute(
                                """
                                INSERT INTO customer_services (id, customer_id, service_type, bandwidth, ordered_diverse, legs_json)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    service_type = EXCLUDED.service_type,
                                    bandwidth = EXCLUDED.bandwidth,
                                    ordered_diverse = EXCLUDED.ordered_diverse,
                                    legs_json = EXCLUDED.legs_json
                                """,
                                (
                                    svc["id"],
                                    svc["customer"],
                                    svc["type"],
                                    svc["bw"],
                                    bool(svc.get("ordered_diverse")),
                                    json.dumps(svc["legs"]),
                                ),
                            )
                        _save_state_snapshot(cur, "comviva_bss", bss, "comviva_bss", latency, len(bss.get("services", [])))
                summary["synced"].append({"id": "comviva_bss", "records": len(bss.get("services", [])), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "comviva_bss", "error": str(e)})

        # 5. VIAVI ONMSi & EXFO Nova RFTS Inventory -> rfts_units (zero hardcoded cable names!)
        exfo_sample_cable: str | None = None
        if "viavi_onmsi" in cmap:
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap["viavi_onmsi"]["endpoint_url"].rstrip("/") + "/rtus")
                r.raise_for_status()
                rtu_data = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                rtus = rtu_data.get("rtus", [])
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for rtu in rtus:
                            v_conn = "viavi_onmsi" if rtu["vendor"] == "viavi" else "exfo_nova"
                            if v_conn == "exfo_nova" and rtu.get("monitors") and not exfo_sample_cable:
                                exfo_sample_cable = rtu["monitors"][0]
                            cur.execute(
                                """
                                INSERT INTO rfts_units (id, vendor, connector_id, pop_node, monitored_cables_json)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    monitored_cables_json = EXCLUDED.monitored_cables_json
                                """,
                                (rtu["id"], rtu["vendor"], v_conn, rtu["pop"], json.dumps(rtu["monitors"])),
                            )
                        _save_state_snapshot(cur, "viavi_rtus", rtu_data, "viavi_onmsi", latency, len(rtus))
                summary["synced"].append({"id": "viavi_onmsi", "records": len(rtus), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "viavi_onmsi", "error": str(e)})

        if "exfo_nova" in cmap and exfo_sample_cable:
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap["exfo_nova"]["endpoint_url"].rstrip("/") + f"/traces/{exfo_sample_cable}.sor")
                r.raise_for_status()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        _save_state_snapshot(cur, "exfo_probe", {"sor_bytes": len(r.content)}, "exfo_nova", latency, 1)
                summary["synced"].append({"id": "exfo_nova", "records": 1, "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "exfo_nova", "error": str(e)})

        # 6. Ericsson ENM 4G/5G RAN PM & Subsea Wet-Plant -> ran_sites, subsea_cables
        if "ericsson_enm" in cmap:
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap["ericsson_enm"]["endpoint_url"].rstrip("/") + "/ran-sites")
                r.raise_for_status()
                ran_data = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                pm_list = ran_data.get("pm_telemetry", [])
                subsea_list = ran_data.get("subsea_systems", [])
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        for pm in pm_list:
                            cur.execute(
                                "UPDATE ran_sites SET pm_json = %s WHERE id = %s",
                                (json.dumps(pm), pm["site_id"]),
                            )
                        for sub in subsea_list:
                            cur.execute(
                                """
                                INSERT INTO subsea_cables (
                                    id, name, cls_node, pfe_id, total_length_km, repeater_count,
                                    repeater_spacing_km, design_capacity_tbps, carried_services_json,
                                    telemetry_json, updated_at
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                                ON CONFLICT (id) DO UPDATE SET
                                    telemetry_json = EXCLUDED.telemetry_json,
                                    updated_at = NOW()
                                """,
                                (
                                    sub["id"],
                                    sub["name"],
                                    sub["cls_node"],
                                    sub["pfe_id"],
                                    float(sub["total_length_km"]),
                                    int(sub["repeater_count"]),
                                    float(sub.get("repeater_spacing_km") or sub.get(" repeater_spacing_km") or 68.5),
                                    float(sub["design_capacity_tbps"]),
                                    json.dumps(sub.get("carried_services", [])),
                                    json.dumps(sub),
                                ),
                            )
                        _save_state_snapshot(cur, "ericsson_ran", ran_data, "ericsson_enm", latency, len(pm_list))
                summary["synced"].append({"id": "ericsson_enm", "records": len(pm_list), "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": "ericsson_enm", "error": str(e)})

        # 7. Remaining auxiliary connectors (NetBox DCIM, Jira SM, ServiceNow ITSM)
        for cid, suffix, state_key in [
            ("netbox_dcim", "/dcim/sites/", "netbox_sites"),
            ("jira_sm", "/rest/api/3/issue", "jira_issues"),
            ("servicenow_itsm", "/api/now/table/change_request", "servicenow_changes"),
        ]:
            if cid not in cmap:
                continue
            t0 = time.perf_counter()
            try:
                r = await client.get(cmap[cid]["endpoint_url"].rstrip("/") + suffix)
                r.raise_for_status()
                payload = r.json()
                latency = round((time.perf_counter() - t0) * 1000, 1)
                rec_count = len(payload) if isinstance(payload, list) else len(payload.keys())
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        _save_state_snapshot(cur, state_key, payload, cid, latency, rec_count)
                summary["synced"].append({"id": cid, "records": rec_count, "latency_ms": latency})
            except Exception as e:
                summary["errors"].append({"id": cid, "error": str(e)})

    return summary


class DatabaseBackedOtdrAdapter(OtdrTraceAdapter):
    """Resolves the monitoring RFTS connector (`viavi_onmsi` or `exfo_nova`) from PostgreSQL."""

    async def fetch_sor_bytes(self, cable_id: str) -> bytes | None:
        cmap = get_connectors_map(only_enabled=True)
        preferred_connector = "viavi_onmsi"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT connector_id, monitored_cables_json FROM rfts_units")
                for row in cur.fetchall():
                    if cable_id in (row["monitored_cables_json"] or []):
                        preferred_connector = row["connector_id"]
                        break

        candidate_ids = [preferred_connector, "viavi_onmsi", "exfo_nova"]
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=5.0) as client:
            for cid in candidate_ids:
                if cid in seen or cid not in cmap:
                    continue
                seen.add(cid)
                base_url = cmap[cid]["endpoint_url"].rstrip("/")
                r = await client.get(f"{base_url}/traces/{cable_id}.sor")
                if r.status_code == 200:
                    return r.content
        return None

    async def fetch_and_parse_sor(self, cable_id: str) -> tuple[OtdrTrace, int] | None:
        raw = await self.fetch_sor_bytes(cable_id)
        if not raw:
            return None
        return parse_sor_bytes(raw), len(raw)


class RestNorthboundActionAdapter(NorthboundActionAdapter):
    """Executes engineer-approved ITSM, FSM, and Optical SDN Controller actions via configured connectors."""

    async def execute(self, action: dict[str, Any], approved_by: str) -> dict[str, Any]:
        cmap = get_connectors_map(only_enabled=False)
        cid = action["connector_id"]
        conn_cfg = cmap.get(cid)
        if not conn_cfg:
            raise ValueError(f"Connector '{cid}' is not registered")

        base_url = conn_cfg["endpoint_url"].rstrip("/")
        payload = action["payload"]
        act_type = action["action_type"]

        async with httpx.AsyncClient(timeout=6.0) as client:
            if act_type == "CREATE_JIRA_INCIDENT":
                r = await client.post(f"{base_url}/rest/api/3/issue", json=payload)
                r.raise_for_status()
                jdata = r.json()
                return {"external_id": jdata.get("key"), "url": jdata.get("self"), "response": jdata}

            if act_type in ("DISPATCH_FIELD_SPLICE_CREW", "CREATE_SERVICENOW_POWER_ADVISORY"):
                tbl = payload.get("table", "incident")
                body = {k: v for k, v in payload.items() if k != "table"}
                r = await client.post(f"{base_url}/api/now/table/{tbl}", json=body)
                r.raise_for_status()
                sdata = r.json().get("result", {})
                return {"external_id": sdata.get("number"), "sys_id": sdata.get("sys_id"), "response": sdata}

            if act_type == "CIENA_WAVELENGTH_REROUTE":
                och_id = payload["och_id"]
                # Use Ciena MCP controller endpoint if Nokia NSP doesn't expose direct reroute endpoint
                reroute_base = cmap.get("ciena_mcp", conn_cfg)["endpoint_url"].rstrip("/")
                r = await client.post(
                    f"{reroute_base}/fres/{och_id}/reroute",
                    json={
                        "new_path": payload["new_path"],
                        "reason": payload["reason"],
                        "approved_by": approved_by,
                    },
                )
                r.raise_for_status()
                cdata = r.json()
                return {"external_id": f"MCP-REROUTE-{och_id}", "response": cdata}

        raise ValueError(f"Unsupported northbound action_type: {act_type}")


def get_emulator_control_base_url() -> str:
    """Resolve emulator harness base URL for simulation/demo triggers (`NOC_EMULATOR_BASE_URL`)."""
    return DEFAULT_EMULATOR_BASE
