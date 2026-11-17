"""Connector Registry, Single-Roundtrip Batched Inventory Sync, OTDR Adapter & Northbound Executor."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from shared.sor_codec import OtdrTrace, parse_sor_bytes
from ..db import DEFAULT_EMULATOR_BASE, get_conn
from .base import NorthboundActionAdapter, OtdrTraceAdapter

_CONNECTORS_CACHE: list[dict[str, Any]] | None = None


def invalidate_connectors_cache() -> None:
    global _CONNECTORS_CACHE
    _CONNECTORS_CACHE = None


def _load_all_connectors() -> list[dict[str, Any]]:
    global _CONNECTORS_CACHE
    if _CONNECTORS_CACHE is not None:
        return _CONNECTORS_CACHE
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM connectors ORDER BY id")
            rows = [dict(r) for r in cur.fetchall()]
    _CONNECTORS_CACHE = rows
    return rows


def get_emulator_control_base_url() -> str:
    """Derive the emulator base host from configured connectors (falling back to env default)."""
    for row in _load_all_connectors():
        if row.get("mode") == "emulator" and row.get("endpoint_url"):
            parts = str(row["endpoint_url"]).split("/")
            if len(parts) >= 3:
                return f"{parts[0]}//{parts[2]}"
    return DEFAULT_EMULATOR_BASE


def get_connectors_map(only_enabled: bool = True) -> dict[str, dict[str, Any]]:
    rows = _load_all_connectors()
    return {
        r["id"]: dict(r)
        for r in rows
        if (not only_enabled or r.get("enabled"))
    }


def _append_snapshot_sql(
    cur: Any,
    stmts: list[bytes],
    key: str,
    payload: Any,
    connector_id: str,
    latency_ms: float,
    rec_count: int,
) -> None:
    stmts.append(
        cur.mogrify(
            """
            INSERT INTO topology_state (key, payload, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (key, json.dumps(payload)),
        )
    )
    stmts.append(
        cur.mogrify(
            "UPDATE connectors SET status='CONNECTED', latency_ms=%s, records_synced=%s, last_sync_at=NOW() WHERE id=%s",
            (latency_ms, rec_count, connector_id),
        )
    )


async def _timed_get(
    client: httpx.AsyncClient,
    cid: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> tuple[str, httpx.Response | None, float, str | None]:
    t0 = time.perf_counter()
    try:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return cid, r, round((time.perf_counter() - t0) * 1000, 1), None
    except Exception as exc:
        return cid, None, round((time.perf_counter() - t0) * 1000, 1), str(exc)


async def sync_all_connectors(
    include_static_topology: bool = True,
    clear_existing: bool = False,
) -> dict[str, Any]:
    """Fetch all enabled southbound connectors concurrently and persist in ONE single PostgreSQL round-trip."""
    cmap = get_connectors_map(only_enabled=True)
    summary: dict[str, Any] = {"synced": [], "errors": []}

    fetch_specs: list[tuple[str, str, dict[str, Any] | None]] = []
    if include_static_topology:
        if "lepton_gis" in cmap:
            fetch_specs.append(("lepton_gis", cmap["lepton_gis"]["endpoint_url"], {"typeName": "osp:all"}))
        if "nmsworks_cygnet" in cmap:
            fetch_specs.append(("nmsworks_cygnet", cmap["nmsworks_cygnet"]["endpoint_url"].rstrip("/") + "/inventory/topology", None))
        if "comviva_bss" in cmap:
            fetch_specs.append(("comviva_bss", cmap["comviva_bss"]["endpoint_url"].rstrip("/") + "/customerManagement/v4/customer", None))
        if "viavi_onmsi" in cmap:
            fetch_specs.append(("viavi_onmsi", cmap["viavi_onmsi"]["endpoint_url"].rstrip("/") + "/rtus", None))

    if "ciena_mcp" in cmap:
        fetch_specs.append(("ciena_mcp", cmap["ciena_mcp"]["endpoint_url"].rstrip("/") + "/fres", None))
    if "nokia_nsp" in cmap:
        fetch_specs.append(("nokia_nsp", cmap["nokia_nsp"]["endpoint_url"].rstrip("/") + "/restconf/data/openconfig-optical", None))
    if "ericsson_enm" in cmap:
        fetch_specs.append(("ericsson_enm", cmap["ericsson_enm"]["endpoint_url"].rstrip("/") + "/ran-sites", None))
    for aux_cid, aux_suffix in [
        ("netbox_dcim", "/dcim/sites/"),
        ("jira_sm", "/rest/api/3/issue"),
        ("servicenow_itsm", "/api/now/table/change_request"),
    ]:
        if aux_cid in cmap:
            fetch_specs.append((aux_cid, cmap[aux_cid]["endpoint_url"].rstrip("/") + aux_suffix, None))

    responses: dict[str, tuple[httpx.Response, float]] = {}
    exfo_probe: tuple[int, float] | None = None

    async with httpx.AsyncClient(timeout=4.0) as client:
        gathered = await asyncio.gather(*[_timed_get(client, cid, url, params) for cid, url, params in fetch_specs])
        for cid, resp, lat_ms, err in gathered:
            if err or resp is None:
                summary["errors"].append({"id": cid, "error": err or "Request failed"})
            else:
                responses[cid] = (resp, lat_ms)

        if include_static_topology and "viavi_onmsi" in responses and "exfo_nova" in cmap:
            rtus = responses["viavi_onmsi"][0].json().get("rtus", [])
            exfo_cable = next(
                (r["monitors"][0] for r in rtus if r.get("vendor") != "viavi" and r.get("monitors")),
                None,
            )
            if exfo_cable:
                _, eresp, elat, eerr = await _timed_get(
                    client,
                    "exfo_nova",
                    cmap["exfo_nova"]["endpoint_url"].rstrip("/") + f"/traces/{exfo_cable}.sor",
                )
                if eerr or eresp is None:
                    summary["errors"].append({"id": "exfo_nova", "error": eerr or "Probe failed"})
                else:
                    exfo_probe = (len(eresp.content), elat)

    with get_conn() as conn:
        with conn.cursor() as cur:
            stmts: list[bytes] = []

            if clear_existing:
                for tbl in (
                    "alarms",
                    "incidents",
                    "customer_services",
                    "customers",
                    "sla_tiers",
                    "gpon_clusters",
                    "ran_sites",
                    "ip_links",
                    "optical_channels",
                    "oms_links",
                    "rfts_units",
                    "subsea_cables",
                    "osp_cables",
                    "osp_manholes",
                    "osp_ducts",
                    "network_nodes",
                    "topology_state",
                ):
                    stmts.append(f"DELETE FROM {tbl}".encode("utf-8"))

            # 1. Lepton GIS WFS -> osp_ducts, osp_manholes, osp_cables
            if "lepton_gis" in responses:
                resp, latency = responses["lepton_gis"]
                feats = resp.json().get("features", [])
                for f in feats:
                    props = f["properties"]
                    geom_json = json.dumps(f["geometry"])
                    ftype = props["feature_type"]
                    if ftype == "duct":
                        stmts.append(
                            cur.mogrify(
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
                        )
                    elif ftype == "manhole":
                        lon, lat = f["geometry"]["coordinates"]
                        stmts.append(
                            cur.mogrify(
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
                        )
                    elif ftype == "cable":
                        stmts.append(
                            cur.mogrify(
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
                        )
                stmts.append(
                    cur.mogrify(
                        "UPDATE connectors SET status='CONNECTED', latency_ms=%s, records_synced=%s, last_sync_at=NOW() WHERE id='lepton_gis'",
                        (latency, len(feats)),
                    )
                )
                summary["synced"].append({"id": "lepton_gis", "records": len(feats), "latency_ms": latency})

            # 2. NMSWorks CygNet Unified Topology
            if "nmsworks_cygnet" in responses:
                resp, latency = responses["nmsworks_cygnet"]
                topo = resp.json()
                nodes = topo.get("nodes", {})
                routers = topo.get("routers", {})
                opt_elems = topo.get("optical_elements", {})
                for nid, ninfo in nodes.items():
                    pt_geojson = json.dumps({"type": "Point", "coordinates": [ninfo["lon"], ninfo["lat"]]})
                    stmts.append(
                        cur.mogrify(
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
                    )
                for oms in topo.get("oms_links", []):
                    vendor = opt_elems.get(oms["a"], {}).get("vendor", "ciena")
                    stmts.append(
                        cur.mogrify(
                            """
                            INSERT INTO oms_links (id, node_a, node_b, cable_id, controller_vendor)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                cable_id = EXCLUDED.cable_id,
                                controller_vendor = EXCLUDED.controller_vendor
                            """,
                            (oms["id"], oms["a"], oms["b"], oms["cable_id"], vendor),
                        )
                    )
                for w in topo.get("wavelengths", []):
                    head_node = w["path"][0] if w.get("path") else ""
                    vendor = opt_elems.get(head_node, {}).get("vendor", "ciena")
                    ctrl_id = "ciena_mcp" if vendor == "ciena" else "nokia_nsp"
                    stmts.append(
                        cur.mogrify(
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
                    )
                for ipl in topo.get("ip_links", []):
                    stmts.append(
                        cur.mogrify(
                            """
                            INSERT INTO ip_links (id, node_a, node_b, underlay_id)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET underlay_id = EXCLUDED.underlay_id
                            """,
                            (ipl["id"], ipl["a"], ipl["b"], ipl["transport"]),
                        )
                    )
                for rsite in topo.get("ran_sites", []):
                    n_coord = nodes.get(rsite["id"], {})
                    lat = n_coord.get("lat")
                    lon = n_coord.get("lon")
                    pt_json = (
                        json.dumps({"type": "Point", "coordinates": [lon, lat]})
                        if (lat is not None and lon is not None)
                        else None
                    )
                    stmts.append(
                        cur.mogrify(
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
                    )
                for gpon in topo.get("gpon_splitters", []):
                    stmts.append(
                        cur.mogrify(
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
                    )
                _append_snapshot_sql(cur, stmts, "topology", topo, "nmsworks_cygnet", latency, len(nodes))
                summary["synced"].append({"id": "nmsworks_cygnet", "records": len(nodes), "latency_ms": latency})

            # 3. Ciena MCP & Nokia NSP Optical PM Telemetry
            for cid, state_key in [("ciena_mcp", "ciena_fres"), ("nokia_nsp", "nokia_optical")]:
                if cid not in responses:
                    continue
                resp, latency = responses[cid]
                payload = resp.json()
                pm_map = payload.get("pm_telemetry", {})
                for och_id, pm in pm_map.items():
                    stmts.append(
                        cur.mogrify(
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
                    )
                _append_snapshot_sql(cur, stmts, state_key, payload, cid, latency, len(pm_map))
                summary["synced"].append({"id": cid, "records": len(pm_map), "latency_ms": latency})

            # 4. Comviva BSS -> sla_tiers, customers, customer_services
            if "comviva_bss" in responses:
                resp, latency = responses["comviva_bss"]
                bss = resp.json()
                for tname, tinfo in bss.get("sla_tiers", {}).items():
                    stmts.append(
                        cur.mogrify(
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
                    )
                for cust in bss.get("customers", []):
                    stmts.append(
                        cur.mogrify(
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
                    )
                for svc in bss.get("services", []):
                    stmts.append(
                        cur.mogrify(
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
                    )
                _append_snapshot_sql(cur, stmts, "comviva_bss", bss, "comviva_bss", latency, len(bss.get("services", [])))
                summary["synced"].append({"id": "comviva_bss", "records": len(bss.get("services", [])), "latency_ms": latency})

            # 5. VIAVI ONMSi & EXFO Nova RFTS Inventory
            if "viavi_onmsi" in responses:
                resp, latency = responses["viavi_onmsi"]
                rtu_data = resp.json()
                rtus = rtu_data.get("rtus", [])
                for rtu in rtus:
                    stmts.append(
                        cur.mogrify(
                            """
                            INSERT INTO rfts_units (id, vendor, connector_id, pop_node, monitored_cables_json)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                monitored_cables_json = EXCLUDED.monitored_cables_json
                            """,
                            (
                                rtu["id"],
                                rtu["vendor"],
                                "viavi_onmsi" if rtu["vendor"] == "viavi" else "exfo_nova",
                                rtu["pop"],
                                json.dumps(rtu["monitors"]),
                            ),
                        )
                    )
                _append_snapshot_sql(cur, stmts, "viavi_rtus", rtu_data, "viavi_onmsi", latency, len(rtus))
                summary["synced"].append({"id": "viavi_onmsi", "records": len(rtus), "latency_ms": latency})

            if exfo_probe is not None:
                sor_len, elat = exfo_probe
                _append_snapshot_sql(cur, stmts, "exfo_probe", {"sor_bytes": sor_len}, "exfo_nova", elat, 1)
                summary["synced"].append({"id": "exfo_nova", "records": 1, "latency_ms": elat})

            # 6. Ericsson ENM 4G/5G RAN PM & Subsea Wet-Plant
            if "ericsson_enm" in responses:
                resp, latency = responses["ericsson_enm"]
                ran_data = resp.json()
                pm_list = ran_data.get("pm_telemetry", [])
                subsea_list = ran_data.get("subsea_systems", [])
                for pm in pm_list:
                    stmts.append(
                        cur.mogrify(
                            "UPDATE ran_sites SET pm_json = %s WHERE id = %s",
                            (json.dumps(pm), pm["site_id"]),
                        )
                    )
                for sub in subsea_list:
                    stmts.append(
                        cur.mogrify(
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
                    )
                _append_snapshot_sql(cur, stmts, "ericsson_ran", ran_data, "ericsson_enm", latency, len(pm_list))
                summary["synced"].append({"id": "ericsson_enm", "records": len(pm_list), "latency_ms": latency})

            # 7. Auxiliary connectors
            for cid, state_key in [
                ("netbox_dcim", "netbox_sites"),
                ("jira_sm", "jira_issues"),
                ("servicenow_itsm", "servicenow_changes"),
            ]:
                if cid not in responses:
                    continue
                resp, latency = responses[cid]
                payload = resp.json()
                rec_count = len(payload) if isinstance(payload, list) else len(payload.keys())
                _append_snapshot_sql(cur, stmts, state_key, payload, cid, latency, rec_count)
                summary["synced"].append({"id": cid, "records": rec_count, "latency_ms": latency})

            if stmts:
                cur.execute(b";\n".join(stmts))

    invalidate_connectors_cache()
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
                return {"external_id": f"REROUTE-{och_id}", "response": r.json()}

        raise ValueError(f"Unsupported action_type '{act_type}'")
