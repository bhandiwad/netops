"""PostGIS + Slack-Loop & Helical Stranding Optical Fault Localization.

For non-telecom software engineers:
When an OTDR test shoots a laser pulse down an optical fiber and reports a break at
e.g. `4,820 meters`, you CANNOT simply measure `4,820 meters` along the street trench:
  1. **Manhole Slack Coils (`slack_coil_m`):** At underground splice chambers, crews
     leave `15m–30m` coils of spare fiber so splicing vans can lift the tray into the truck.
  2. **Helical Stranding (`helix_factor` ~ `1.015`):** Loose buffer tubes spiral inside
     the armored cable jacket, making glass `~1.5%` longer than the duct.
  3. **Splice-Landmark Anchoring (`±20m–30m` Dig Corridor):** Real GIS duct maps have
     `5m–15m` as-built drift and refractive index (`IOR`) varies `±0.05%`. Field OSP
     crews anchor at the nearest upstream chamber splice reflection in the `.sor` trace
     and excavate a `±20m` dig corridor rather than chasing sub-meter decimals.
"""
from __future__ import annotations

import json
from typing import Any

from ..db import get_conn

TIA598_COLORS: tuple[str, ...] = (
    "Blue",
    "Orange",
    "Green",
    "Brown",
    "Slate",
    "White",
    "Red",
    "Black",
    "Yellow",
    "Violet",
    "Rose",
    "Aqua",
)


def _build_tia598_splice_plan(fibres: int, role: str) -> dict[str, Any]:
    cores_per_tube = 12 if fibres >= 12 else max(1, fibres)
    tube_count = max(1, (fibres + cores_per_tube - 1) // cores_per_tube)

    tubes: list[dict[str, Any]] = []
    for idx in range(tube_count):
        base_color = TIA598_COLORS[idx % 12]
        binder = f" (Binder {idx // 12 + 1})" if idx >= 12 else ""
        start_core = idx * cores_per_tube + 1
        end_core = min(fibres, (idx + 1) * cores_per_tube)
        if idx == 0:
            allocation = (
                "DWDM Line / Core Transport + Dark OTDR Core #12"
                if role in ("trunk", "dark")
                else "Primary Lit Access / Enterprise Circuits"
            )
        elif idx == 1:
            allocation = "5G Fronthaul / MPLS Protect Rings" if role != "access" else "GPON / Secondary Circuits"
        else:
            allocation = "Enterprise Dark / Spare Distribution"
        tubes.append({
            "tube_number": idx + 1,
            "tube_color": f"{base_color}{binder}",
            "core_range": f"{start_core}–{end_core}",
            "allocation": allocation,
        })

    # Realistic dual-splicer van repair time: 1.5h civil pit + ~1.1 min/core effective fusion & heat-shrink
    est_excavation_h = 1.5
    est_splice_h = round(max(0.8, (fibres * 1.05) / 60.0), 1)
    est_total_h = round(est_excavation_h + est_splice_h, 1)

    first_color = tubes[0]["tube_color"]
    last_color = tubes[-1]["tube_color"]
    return {
        "standard": "ANSI/TIA-598-D",
        "fibre_count": fibres,
        "buffer_tubes": tube_count,
        "cores_per_tube": cores_per_tube,
        "tube_color_range": f"Tubes 1–{tube_count} ({first_color} to {last_color})",
        "tubes": tubes[:6],
        "priority_instruction": (
            f"Splice Tube 1 ({first_color}, Cores 1–{min(cores_per_tube, fibres)}) first "
            f"for priority bearer + 1625 nm verification before completing remaining tubes."
        ),
        "est_excavation_hours": est_excavation_h,
        "est_fusion_splice_hours": est_splice_h,
        "est_total_etr_hours": est_total_h,
    }


def _round_field_m(meters: float) -> int:
    if meters < 15.0:
        return int(round(meters))
    return int(round(meters / 5.0) * 5)


def locate_fault_on_cable_postgis(cable_id: str, optical_distance_m: float) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM osp_cables WHERE id = %s", (cable_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Cable '{cable_id}' not found in osp_cables")
            cable = dict(row)

            cur.execute("SELECT id, vendor, monitored_cables_json FROM rfts_units")
            rfts_rows = [dict(r) for r in cur.fetchall()]

    splices = cable["splices_json"]
    helix = float(cable["helix_factor"])
    trench_total = float(cable["trench_length_m"])
    optical_total = float(cable["optical_length_m"])
    fibres = int(cable.get("fibres") or 48)
    role = str(cable.get("role") or "trunk")

    in_rfts_table = False
    for rtu in rfts_rows:
        mon = rtu.get("monitored_cables_json") or []
        if isinstance(mon, str):
            try:
                mon = json.loads(mon)
            except Exception:
                mon = []
        if cable_id in mon:
            in_rfts_table = True
            break

    # In real carrier plants, fixed 1625nm RFTS WDM couplers sit on core/metro trunks,
    # while access/last-mile cables require a field tech handheld OTDR (.sor upload).
    rfts_monitored = bool(in_rfts_table and role in ("trunk", "dark"))
    monitoring_mode = "IN_SERVICE_RFTS_1625NM" if rfts_monitored else "HANDHELD_OTDR_SOR"
    monitoring_label = (
        "1625 nm Auto-RFTS (In-Service)"
        if rfts_monitored
        else "Access Span · Handheld OTDR (.sor)"
    )

    slack_subtracted_m = 0.0
    upstream_mh = splices[0]
    downstream_mh = splices[-1]

    for i in range(len(splices) - 1):
        sp_curr = splices[i]
        sp_next = splices[i + 1]
        if optical_distance_m >= float(sp_curr["optical_distance_m"]):
            slack_subtracted_m += float(sp_curr["slack_added_m"])
            upstream_mh = sp_curr
            downstream_mh = sp_next
        else:
            break

    net_fiber_in_trench_m = max(0.0, optical_distance_m - slack_subtracted_m)
    corrected_trench_m = min(trench_total, round(net_fiber_in_trench_m / helix, 1))

    naive_trench_m = min(trench_total, round(optical_distance_m, 1))
    error_avoided_m = round(abs(naive_trench_m - corrected_trench_m), 1)

    frac_corrected = corrected_trench_m / trench_total if trench_total > 0 else 0.5
    frac_naive = naive_trench_m / trench_total if trench_total > 0 else 0.5

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ST_Y(ST_LineInterpolatePoint(geom, %s)) AS corr_lat,
                    ST_X(ST_LineInterpolatePoint(geom, %s)) AS corr_lon,
                    ST_Y(ST_LineInterpolatePoint(geom, %s)) AS naive_lat,
                    ST_X(ST_LineInterpolatePoint(geom, %s)) AS naive_lon
                FROM osp_cables
                WHERE id = %s
                """,
                (frac_corrected, frac_corrected, frac_naive, frac_naive, cable_id),
            )
            pt = cur.fetchone()

    dist_from_upstream_mh_m = round(
        max(0.0, corrected_trench_m - float(upstream_mh["trench_distance_m"])),
        1,
    )

    lat = round(float(pt["corr_lat"]), 6)
    lon = round(float(pt["corr_lon"]), 6)
    naive_lat = round(float(pt["naive_lat"]), 6)
    naive_lon = round(float(pt["naive_lon"]), 6)

    confidence_radius_m = 20 if (rfts_monitored and dist_from_upstream_mh_m <= 2500.0) else 30
    rounded_trench_m = _round_field_m(corrected_trench_m)
    rounded_from_up_m = _round_field_m(dist_from_upstream_mh_m)
    rounded_err_m = _round_field_m(error_avoided_m)

    up_id = upstream_mh["manhole_id"]
    up_name = upstream_mh.get("name") or up_id
    dn_id = downstream_mh["manhole_id"]
    dn_name = downstream_mh.get("name") or dn_id

    google_maps_url = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
    dig_corridor_label = f"~{rounded_from_up_m:,} m ± {confidence_radius_m} m from {up_id} toward {dn_id}"
    landmark_anchor = (
        f"Anchor at splice reflection {up_id} ({up_name}) -> measure "
        f"~{rounded_from_up_m:,} m (±{confidence_radius_m} m) along duct toward {dn_id} ({dn_name})"
    )

    tia598_plan = _build_tia598_splice_plan(fibres, role)
    whatsapp_dispatch_text = (
        f"*OSP EMERGENCY SPLICE DISPATCH*\n"
        f"• *Cable:* {cable_id} ({fibres}F {role.upper()} · {tia598_plan['standard']}: {tia598_plan['tube_color_range']})\n"
        f"• *Anchor Chamber:* {up_id} ({up_name})\n"
        f"• *Dig Zone:* Measure ~{rounded_from_up_m:,} m (±{confidence_radius_m} m) along duct toward {dn_id}\n"
        f"• *Slack Correction:* −{round(slack_subtracted_m)} m chamber coils & {helix}x helix applied "
        f"(avoids ~{rounded_err_m:,} m wrong-pit excavation)\n"
        f"• *Splice Priority:* {tia598_plan['priority_instruction']} (Est. ETR ~{tia598_plan['est_total_etr_hours']}h)\n"
        f"• *GPS Pin:* {google_maps_url}"
    )

    return {
        "cable_id": cable_id,
        "cable_role": role,
        "cable_fibres": fibres,
        "rfts_monitored": rfts_monitored,
        "monitoring_mode": monitoring_mode,
        "monitoring_label": monitoring_label,
        "launch_node": splices[0]["node_id"],
        "optical_distance_m": round(optical_distance_m, 1),
        "cable_optical_length_m": optical_total,
        "cable_trench_length_m": trench_total,
        "helix_factor": helix,
        "slack_Coils_subtracted_m": round(slack_subtracted_m, 1),
        "corrected_trench_distance_m": corrected_trench_m,
        "rounded_trench_distance_m": rounded_trench_m,
        "naive_uncorrected_trench_m": naive_trench_m,
        "dispatch_error_avoided_m": error_avoided_m,
        "rounded_error_avoided_m": rounded_err_m,
        "confidence_radius_m": confidence_radius_m,
        "dig_corridor_label": dig_corridor_label,
        "landmark_anchor": landmark_anchor,
        "google_maps_url": google_maps_url,
        "tia598_splice_plan": tia598_plan,
        "whatsapp_dispatch_text": whatsapp_dispatch_text,
        "lat": lat,
        "lon": lon,
        "naive_lat": naive_lat,
        "naive_lon": naive_lon,
        "upstream_manhole": upstream_mh,
        "downstream_manhole": downstream_mh,
        "distance_from_upstream_manhole_m": dist_from_upstream_mh_m,
        "rounded_from_upstream_manhole_m": rounded_from_up_m,
        "bridges_on_cable": cable["bridges"],
        "duct_ids": cable["duct_ids"],
    }
