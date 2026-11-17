"""Bring-Your-Own-Data Importers: Google Earth `.kml` OSP Routes & Vendor Alarm `.csv` Dumps.

Allows field engineers and evaluators to upload real Google Earth `.kml` fiber route files
or vendor OSS `.csv` alarm exports directly into PostGIS and the causal correlation engine.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
import re
from typing import Any
import uuid
import xml.etree.ElementTree as ET

from ..db import get_conn


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r_earth = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _slugify_id(raw_name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", raw_name.strip().upper()).strip("-")
    # Avoid reserved test prefixes so imported user routes remain distinct
    for reserved in ("CBL-", "OCH-", "SUBSEA-", "SPL-", "SVC-", "CUST-"):
        if cleaned.startswith(reserved):
            cleaned = "KML-" + cleaned[len(reserved):]
    return cleaned[:28] if cleaned else fallback


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_coord_tuples(coord_text: str) -> list[list[float]]:
    coords: list[list[float]] = []
    for token in coord_text.replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = round(float(parts[0]), 6)
                lat = round(float(parts[1]), 6)
                if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
                    coords.append([lon, lat])
            except ValueError:
                continue
    return coords


def _interpolate_coord(coords: list[list[float]], seg_lengths: list[float], target_m: float) -> tuple[float, float]:
    if not coords:
        return 0.0, 0.0
    if target_m <= 0.0 or not seg_lengths:
        return coords[0][0], coords[0][1]
    acc = 0.0
    for idx, slen in enumerate(seg_lengths):
        if acc + slen >= target_m and slen > 0:
            ratio = (target_m - acc) / slen
            lon = coords[idx][0] + ratio * (coords[idx + 1][0] - coords[idx][0])
            lat = coords[idx][1] + ratio * (coords[idx + 1][1] - coords[idx][1])
            return round(lon, 6), round(lat, 6)
        acc += slen
    return coords[-1][0], coords[-1][1]


def import_kml_osp_routes(
    kml_bytes: bytes,
    *,
    default_fibres: int = 96,
    default_slack_m: float = 25.0,
    helix_factor: float = 1.015,
) -> dict[str, Any]:
    """Parse a Google Earth `.kml` XML payload and upsert ducts, splice chambers & cables into PostGIS."""
    try:
        root = ET.fromstring(kml_bytes.decode("utf-8", errors="replace"))
    except ET.ParseError as exc:
        raise ValueError(f"Invalid KML XML document: {exc}") from exc

    point_landmarks: list[dict[str, Any]] = []
    line_routes: list[dict[str, Any]] = []

    for elem in root.iter():
        if _local_tag(elem.tag) != "Placemark":
            continue
        pm_name = ""
        pm_desc = ""
        for child in elem:
            ctag = _local_tag(child.tag)
            if ctag == "name" and child.text:
                pm_name = child.text.strip()
            elif ctag == "description" and child.text:
                pm_desc = child.text.strip()

        for sub in elem.iter():
            stag = _local_tag(sub.tag)
            if stag == "Point":
                for cnode in sub.iter():
                    if _local_tag(cnode.tag) == "coordinates" and cnode.text:
                        pts = _parse_coord_tuples(cnode.text)
                        if pts:
                            point_landmarks.append({
                                "name": pm_name or f"KML Chamber {len(point_landmarks) + 1}",
                                "lon": pts[0][0],
                                "lat": pts[0][1],
                                "description": pm_desc,
                            })
            elif stag == "LineString":
                for cnode in sub.iter():
                    if _local_tag(cnode.tag) == "coordinates" and cnode.text:
                        pts = _parse_coord_tuples(cnode.text)
                        if len(pts) >= 2:
                            line_routes.append({
                                "name": pm_name or f"KML-SPAN-{len(line_routes) + 1:02d}",
                                "coords": pts,
                                "description": pm_desc,
                            })

    if not line_routes:
        raise ValueError("No <LineString> fiber route coordinates found in KML file.")

    imported_cables: list[dict[str, Any]] = []
    imported_ducts: list[dict[str, Any]] = []
    imported_manholes: list[dict[str, Any]] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            for r_idx, route in enumerate(line_routes, start=1):
                coords = route["coords"]
                seg_lengths = [
                    _haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
                    for i in range(len(coords) - 1)
                ]
                trench_total = round(max(50.0, sum(seg_lengths)), 1)

                slug = _slugify_id(route["name"], f"KML-SPAN-{r_idx:02d}")
                cable_id = slug if slug.startswith("KML-") else f"KML-{slug}"
                duct_id = f"KML-DUCT-{slug[-18:]}"
                node_a_id = f"KML-POP-{r_idx}A"
                node_b_id = f"KML-POP-{r_idx}B"

                # Build splice chambers at endpoints + ~1.5 km intervals along the imported KML LineString
                chamber_count = max(1, min(6, int(trench_total // 1500.0)))
                splices: list[dict[str, Any]] = []
                running_slack = 0.0

                # Start POP entry chamber
                splices.append({
                    "manhole_id": f"MH-{node_a_id}",
                    "node_id": node_a_id,
                    "name": f"{route['name']} Launch Chamber",
                    "lat": coords[0][1],
                    "lon": coords[0][0],
                    "trench_distance_m": 0.0,
                    "optical_distance_m": 0.0,
                    "slack_added_m": 15.0,
                })
                running_slack += 15.0

                for c_i in range(1, chamber_count + 1):
                    dist_m = round((trench_total * c_i) / (chamber_count + 1), 1)
                    clon, clat = _interpolate_coord(coords, seg_lengths, dist_m)
                    # Snap label if user KML included a nearby <Point> placemark within 250m
                    matched_pt = next(
                        (
                            p for p in point_landmarks
                            if _haversine_m(clon, clat, p["lon"], p["lat"]) <= 250.0
                        ),
                        None,
                    )
                    mh_node = f"KML-J-{r_idx}-{c_i}"
                    mh_id = f"MH-{mh_node}"
                    mh_name = matched_pt["name"] if matched_pt else f"{route['name']} Splice Pit #{c_i}"
                    opt_at_mh = round(dist_m * helix_factor + running_slack, 1)
                    splices.append({
                        "manhole_id": mh_id,
                        "node_id": mh_node,
                        "name": mh_name,
                        "lat": clat,
                        "lon": clon,
                        "trench_distance_m": dist_m,
                        "optical_distance_m": opt_at_mh,
                        "slack_added_m": default_slack_m,
                    })
                    running_slack += default_slack_m

                    cur.execute(
                        """
                        INSERT INTO osp_manholes (id, node_id, name, kind, lat, lon, slack_coil_m, geom)
                        VALUES (%s, %s, %s, 'junction', %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            lat = EXCLUDED.lat,
                            lon = EXCLUDED.lon,
                            slack_coil_m = EXCLUDED.slack_coil_m,
                            geom = EXCLUDED.geom
                        """,
                        (mh_id, mh_node, mh_name, clat, clon, default_slack_m, clon, clat),
                    )
                    imported_manholes.append({
                        "id": mh_id,
                        "node_id": mh_node,
                        "name": mh_name,
                        "kind": "junction",
                        "lat": clat,
                        "lon": clon,
                        "slack_coil_m": default_slack_m,
                    })

                optical_total = round(trench_total * helix_factor + running_slack, 1)
                splices.append({
                    "manhole_id": f"MH-{node_b_id}",
                    "node_id": node_b_id,
                    "name": f"{route['name']} Far-End Chamber",
                    "lat": coords[-1][1],
                    "lon": coords[-1][0],
                    "trench_distance_m": trench_total,
                    "optical_distance_m": optical_total,
                    "slack_added_m": 15.0,
                })

                # Upsert endpoint nodes so map & topology graph render them cleanly
                for nid, nlabel, nlon, nlat in [
                    (node_a_id, f"{route['name']} (A-End)", coords[0][0], coords[0][1]),
                    (node_b_id, f"{route['name']} (Z-End)", coords[-1][0], coords[-1][1]),
                ]:
                    cur.execute(
                        """
                        INSERT INTO network_nodes (id, name, kind, lat, lon, geom)
                        VALUES (%s, %s, 'pop', %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            lat = EXCLUDED.lat,
                            lon = EXCLUDED.lon,
                            geom = EXCLUDED.geom
                        """,
                        (nid, nlabel, nlat, nlon, nlon, nlat),
                    )

                wkt_line = "LINESTRING(" + ", ".join(f"{pt[0]} {pt[1]}" for pt in coords) + ")"
                cur.execute(
                    """
                    INSERT INTO osp_ducts (id, node_a, node_b, bridge, trench_length_m, coords_json, geom)
                    VALUES (%s, %s, %s, NULL, %s, %s, ST_GeomFromText(%s, 4326))
                    ON CONFLICT (id) DO UPDATE SET
                        trench_length_m = EXCLUDED.trench_length_m,
                        coords_json = EXCLUDED.coords_json,
                        geom = EXCLUDED.geom
                    """,
                    (duct_id, node_a_id, node_b_id, trench_total, json.dumps(coords), wkt_line),
                )

                fibres = default_fibres
                m_fib = re.search(r"(\d{2,3})\s*F\b", route["name"].upper())
                if m_fib:
                    fibres = int(m_fib.group(1))

                path_nodes = [sp["node_id"] for sp in splices]
                cur.execute(
                    """
                    INSERT INTO osp_cables (
                        id, path_nodes, duct_ids, bridges, fibres, role,
                        helix_factor, trench_length_m, optical_length_m, splices_json, coords_json, geom
                    )
                    VALUES (%s, %s, %s, '[]'::jsonb, %s, 'access', %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                    ON CONFLICT (id) DO UPDATE SET
                        fibres = EXCLUDED.fibres,
                        trench_length_m = EXCLUDED.trench_length_m,
                        optical_length_m = EXCLUDED.optical_length_m,
                        splices_json = EXCLUDED.splices_json,
                        coords_json = EXCLUDED.coords_json,
                        geom = EXCLUDED.geom
                    """,
                    (
                        cable_id,
                        json.dumps(path_nodes),
                        json.dumps([duct_id]),
                        fibres,
                        helix_factor,
                        trench_total,
                        optical_total,
                        json.dumps(splices),
                        json.dumps(coords),
                        wkt_line,
                    ),
                )

                imported_ducts.append({
                    "id": duct_id,
                    "node_a": node_a_id,
                    "node_b": node_b_id,
                    "bridge": None,
                    "trench_length_m": trench_total,
                    "coordinates": coords,
                })
                imported_cables.append({
                    "id": cable_id,
                    "name": route["name"],
                    "path_nodes": path_nodes,
                    "duct_ids": [duct_id],
                    "bridges": [],
                    "fibres": fibres,
                    "role": "access",
                    "helix_factor": helix_factor,
                    "trench_length_m": trench_total,
                    "optical_length_m": optical_total,
                    "splices": splices,
                    "coordinates": coords,
                })

    return {
        "imported_cable_count": len(imported_cables),
        "imported_chamber_count": len(imported_manholes),
        "cables": imported_cables,
        "ducts": imported_ducts,
        "manholes": imported_manholes,
    }


def parse_alarms_csv(csv_bytes: bytes) -> list[dict[str, Any]]:
    """Normalize a multi-vendor CSV alarm export into canonical TMF642-compatible alarm dictionaries."""
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row.")

    now_iso = datetime.now(timezone.utc).isoformat()
    alarms: list[dict[str, Any]] = []

    def _pick(row_lc: dict[str, str], keys: tuple[str, ...], default: str = "") -> str:
        for k in keys:
            if row_lc.get(k):
                return row_lc[k].strip()
        return default

    for idx, raw_row in enumerate(reader, start=1):
        row_lc = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        if not any(row_lc.values()):
            continue

        alarm_id = _pick(row_lc, ("alarm_id", "id", "event_id"), f"CSV-ALM-{uuid.uuid4().hex[:8].upper()}")
        source_oem = _pick(row_lc, ("source_oem", "vendor", "oem", "ems", "source"), "csv_import")
        layer = _pick(row_lc, ("layer", "domain", "technology"), "dwdm_optical")
        resource_id = _pick(row_lc, ("resource_id", "resource", "object", "managed_object", "circuit_id"), f"RES-{idx}")
        node_id = _pick(row_lc, ("node_id", "node", "ne_name", "site_id", "pop"), "POP")
        severity = _pick(row_lc, ("severity", "perceived_severity", "level"), "CRITICAL").upper()
        specific_problem = _pick(
            row_lc,
            ("specific_problem", "alarm_name", "problem", "event_type", "alert"),
            "INTERFACE_LINK_BFD_DOWN",
        )
        probable_cause = _pick(row_lc, ("probable_cause", "cause", "category"), "External CSV Telemetry Import")
        raw_text = _pick(
            row_lc,
            ("raw_text", "summary", "description", "additional_text", "message"),
            f"[{source_oem}] {specific_problem} on {resource_id} ({node_id})",
        )
        raised_at = _pick(row_lc, ("raised_at", "timestamp", "event_time", "time"), now_iso)

        extra: dict[str, Any] = {"imported_via": "csv"}
        opt_dist_str = _pick(row_lc, ("optical_distance_m", "otdr_distance_m", "distance_m"), "")
        if opt_dist_str:
            try:
                extra["optical_distance_m"] = float(opt_dist_str)
                extra["optical_event_distance_m"] = float(opt_dist_str)
            except ValueError:
                pass
        cable_ref = _pick(row_lc, ("cable_id",), "")
        if cable_ref:
            extra["cable_id"] = cable_ref

        alarms.append({
            "alarm_id": alarm_id,
            "scenario_id": "csv_user_import",
            "source_oem": source_oem,
            "protocol": "CSV-Batch-Import",
            "layer": layer,
            "resource_id": resource_id,
            "node_id": node_id,
            "severity": severity,
            "specific_problem": specific_problem,
            "probable_cause": probable_cause,
            "raw_text": raw_text,
            "raised_at": raised_at,
            "extra": extra,
        })

    if not alarms:
        raise ValueError("No valid alarm rows found in CSV file.")
    return alarms
