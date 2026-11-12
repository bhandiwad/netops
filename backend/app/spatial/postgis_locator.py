"""PostGIS + Slack-Loop & Helical Stranding Optical Fault Localization.

For non-telecom software engineers:
When an OTDR test shoots a laser pulse down an optical fiber and reports a break at
e.g. `4,820 meters`, you CANNOT simply measure `4,820 meters` along the street trench!
Why?
  1. **Manhole Slack Coils (`slack_coil_m`):** At underground splice chambers, crews
     leave `15m–30m` coils of spare fiber so splicing vans can lift the tray into the truck.
  2. **Helical Stranding (`helix_factor` ~ `1.015`):** Loose buffer tubes spiral inside
     the armored cable jacket, making glass `~1.5%` longer than the duct.

This pure spatial service subtracts passed slack coils, divides by `helix_factor`,
and uses PostGIS `ST_LineInterpolatePoint` to return exact WGS84 `(lat, lon)` street
coordinates — plus the naive uncorrected coordinate so operators see the dispatch error avoided.
"""
from __future__ import annotations

from typing import Any

from ..db import get_conn


def locate_fault_on_cable_postgis(cable_id: str, optical_distance_m: float) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM osp_cables WHERE id = %s", (cable_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Cable '{cable_id}' not found in osp_cables")
            cable = dict(row)

    splices = cable["splices_json"]
    helix = float(cable["helix_factor"])
    trench_total = float(cable["trench_length_m"])
    optical_total = float(cable["optical_length_m"])

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

    return {
        "cable_id": cable_id,
        "launch_node": splices[0]["node_id"],
        "optical_distance_m": round(optical_distance_m, 1),
        "cable_optical_length_m": optical_total,
        "cable_trench_length_m": trench_total,
        "helix_factor": helix,
        "slack_Coils_subtracted_m": round(slack_subtracted_m, 1),
        "corrected_trench_distance_m": corrected_trench_m,
        "naive_uncorrected_trench_m": naive_trench_m,
        "dispatch_error_avoided_m": error_avoided_m,
        "lat": round(float(pt["corr_lat"]), 6),
        "lon": round(float(pt["corr_lon"]), 6),
        "naive_lat": round(float(pt["naive_lat"]), 6),
        "naive_lon": round(float(pt["naive_lon"]), 6),
        "upstream_manhole": upstream_mh,
        "downstream_manhole": downstream_mh,
        "distance_from_upstream_manhole_m": dist_from_upstream_mh_m,
        "bridges_on_cable": cable["bridges"],
        "duct_ids": cable["duct_ids"],
    }
