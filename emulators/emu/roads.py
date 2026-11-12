"""Builds and caches road-following duct geometry, manholes, splice closures,
and cable optical-vs-trench length profiles for the Lepton GIS and VIAVI/EXFO emulators.

Validates a SHA-256 topology fingerprint so changing `TELCO_DATASET_PATH` or adding
new ducts/cables automatically recomputes changed segments while reusing cached OSRM
polylines for unchanged ducts.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import httpx
from pyproj import Geod

from .spec import CABLES, DUCTS, NODES

GEOD = Geod(ellps="WGS84")
CACHE_PATH = Path(__file__).parent / "road_cache.json"


def _topology_fingerprint() -> str:
    canonical = json.dumps(
        {"nodes": NODES, "ducts": DUCTS, "cables": CABLES},
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _geodesic_length_m(coords_lon_lat: list[list[float]]) -> float:
    if len(coords_lon_lat) < 2:
        return 0.0
    lons = [c[0] for c in coords_lon_lat]
    lats = [c[1] for c in coords_lon_lat]
    return float(GEOD.line_length(lons, lats))


def _interpolate_along_coords(coords_lon_lat: list[list[float]], fraction: float) -> tuple[float, float]:
    """Return (lon, lat) at a fraction [0, 1] of geodesic distance along coords."""
    fraction = max(0.0, min(1.0, fraction))
    total = _geodesic_length_m(coords_lon_lat)
    if total <= 0.0:
        return coords_lon_lat[0][0], coords_lon_lat[0][1]
    target = total * fraction
    acc = 0.0
    for i in range(len(coords_lon_lat) - 1):
        lon1, lat1 = coords_lon_lat[i]
        lon2, lat2 = coords_lon_lat[i + 1]
        _, _, seg_len = GEOD.inv(lon1, lat1, lon2, lat2)
        if acc + seg_len >= target and seg_len > 0:
            t = (target - acc) / seg_len
            return round(lon1 + (lon2 - lon1) * t, 6), round(lat1 + (lat2 - lat1) * t, 6)
        acc += seg_len
    return coords_lon_lat[-1][0], coords_lon_lat[-1][1]


def _fallback_road_curve(lon_a: float, lat_a: float, lon_b: float, lat_b: float, steps: int = 16) -> list[list[float]]:
    """Deterministic multi-vertex road-like polyline if OSRM is unreachable."""
    pts: list[list[float]] = []
    dx = lon_b - lon_a
    dy = lat_b - lat_a
    perp_x = -dy * 0.06
    perp_y = dx * 0.06
    for i in range(steps + 1):
        t = i / float(steps)
        bend = math.sin(t * math.pi)
        lon = round(lon_a + dx * t + perp_x * bend, 6)
        lat = round(lat_a + dy * t + perp_y * bend, 6)
        pts.append([lon, lat])
    return pts


def build_or_load_osp_geometry() -> dict[str, Any]:
    """Return complete OSP GIS dataset: ducts, manholes, and cables with splice/slack profiles."""
    fp = _topology_fingerprint()
    existing_duct_coords: dict[str, list[list[float]]] = {}
    if CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if cached.get("fingerprint") == fp:
                return cached
            for cd in cached.get("ducts", []):
                if cd.get("id") and cd.get("coordinates"):
                    existing_duct_coords[cd["id"]] = cd["coordinates"]
        except Exception:
            pass

    duct_map: dict[tuple[str, str], dict[str, Any]] = {}
    ducts_out: list[dict[str, Any]] = []

    with httpx.Client(timeout=3.5) as client:
        for d in DUCTS:
            na = NODES[d["a"]]
            nb = NODES[d["b"]]
            lon_a, lat_a = na["lon"], na["lat"]
            lon_b, lat_b = nb["lon"], nb["lat"]
            coords: list[list[float]] | None = existing_duct_coords.get(d["id"])
            if coords and (coords[0] != [lon_a, lat_a] or coords[-1] != [lon_b, lat_b]):
                coords = None

            if not coords:
                try:
                    url = (
                        f"https://router.project-osrm.org/route/v1/driving/"
                        f"{lon_a},{lat_a};{lon_b},{lat_b}?overview=full&geometries=geojson"
                    )
                    r = client.get(url)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("routes"):
                            coords = data["routes"][0]["geometry"]["coordinates"]
                            coords[0] = [lon_a, lat_a]
                            coords[-1] = [lon_b, lat_b]
                except Exception:
                    coords = None

            if not coords or len(coords) < 2:
                coords = _fallback_road_curve(lon_a, lat_a, lon_b, lat_b)

            trench_len_m = round(_geodesic_length_m(coords), 1)
            duct_rec = {
                "id": d["id"],
                "node_a": d["a"],
                "node_b": d["b"],
                "bridge": d.get("bridge"),
                "trench_length_m": trench_len_m,
                "coordinates": coords,
            }
            ducts_out.append(duct_rec)
            duct_map[(d["a"], d["b"])] = duct_rec
            duct_map[(d["b"], d["a"])] = {
                **duct_rec,
                "node_a": d["b"],
                "node_b": d["a"],
                "coordinates": list(reversed(coords)),
            }

    manholes: list[dict[str, Any]] = []
    node_manhole_slack: dict[str, float] = {}
    for nid, ninfo in NODES.items():
        slack_m = 25.0 if ninfo["kind"] in ("pop", "junction") else 15.0
        node_manhole_slack[nid] = slack_m
        manholes.append({
            "id": f"MH-{nid}",
            "node_id": nid,
            "name": f"{ninfo['name']} Chamber",
            "kind": ninfo["kind"],
            "lat": ninfo["lat"],
            "lon": ninfo["lon"],
            "slack_coil_m": slack_m,
        })

    cables_out: list[dict[str, Any]] = []
    for c in CABLES:
        path_nodes = c["path"]
        helix = float(c.get("helix_factor", 1.015))
        merged_coords: list[list[float]] = []
        duct_ids: list[str] = []
        bridges_crossed: list[str] = []
        splices: list[dict[str, Any]] = []

        cum_trench_m = 0.0
        cum_optical_m = 0.0

        start_slack = node_manhole_slack.get(path_nodes[0], 20.0)
        cum_optical_m += start_slack
        splices.append({
            "manhole_id": f"MH-{path_nodes[0]}",
            "node_id": path_nodes[0],
            "name": NODES[path_nodes[0]]["name"],
            "lat": NODES[path_nodes[0]]["lat"],
            "lon": NODES[path_nodes[0]]["lon"],
            "trench_distance_m": 0.0,
            "optical_distance_m": round(cum_optical_m, 1),
            "slack_added_m": start_slack,
        })

        for idx in range(len(path_nodes) - 1):
            u, v = path_nodes[idx], path_nodes[idx + 1]
            d_edge = duct_map.get((u, v))
            if d_edge is None:
                coords_seg = _fallback_road_curve(
                    NODES[u]["lon"], NODES[u]["lat"], NODES[v]["lon"], NODES[v]["lat"], steps=8
                )
                seg_trench = round(_geodesic_length_m(coords_seg), 1)
                did = f"D-{u}-{v}"
                bridge = None
            else:
                coords_seg = d_edge["coordinates"]
                seg_trench = d_edge["trench_length_m"]
                did = d_edge["id"]
                bridge = d_edge.get("bridge")

            duct_ids.append(did)
            if bridge:
                bridges_crossed.append(bridge)

            if not merged_coords:
                merged_coords.extend(coords_seg)
            else:
                merged_coords.extend(coords_seg[1:])

            cum_trench_m += seg_trench
            cum_optical_m += seg_trench * helix
            mh_slack = node_manhole_slack.get(v, 20.0)
            cum_optical_m += mh_slack

            splices.append({
                "manhole_id": f"MH-{v}",
                "node_id": v,
                "name": NODES[v]["name"],
                "lat": NODES[v]["lat"],
                "lon": NODES[v]["lon"],
                "trench_distance_m": round(cum_trench_m, 1),
                "optical_distance_m": round(cum_optical_m, 1),
                "slack_added_m": mh_slack,
            })

        cables_out.append({
            "id": c["id"],
            "path_nodes": path_nodes,
            "duct_ids": duct_ids,
            "bridges": bridges_crossed,
            "fibres": c["fibres"],
            "role": c["role"],
            "helix_factor": helix,
            "trench_length_m": round(cum_trench_m, 1),
            "optical_length_m": round(cum_optical_m, 1),
            "splices": splices,
            "coordinates": merged_coords,
        })

    result = {
        "fingerprint": fp,
        "nodes": NODES,
        "ducts": ducts_out,
        "manholes": manholes,
        "cables": cables_out,
    }
    try:
        CACHE_PATH.write_text(json.dumps(result, indent=2))
    except Exception:
        pass
    return result
