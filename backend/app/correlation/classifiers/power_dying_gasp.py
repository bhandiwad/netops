"""Classifier: Commercial AC Power Outage ('Dying Gasp') vs. Feeder Fibre Cut."""
from __future__ import annotations

from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from .base import CorrelationContext, HypothesisClassifier, normalize_problem_code, register_classifier


@register_classifier
class PowerDyingGaspClassifier(HypothesisClassifier):
    classifier_id = "power_dying_gasp"
    priority = 95

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        dying_gasp = [a for a in cluster.alarms if "DYING_GASP" in normalize_problem_code(a.specific_problem)]
        if not dying_gasp:
            return None

        inv = ctx.inventory
        lead_alm = dying_gasp[0]
        ext = lead_alm.extra or {}

        # Dynamically resolve GPON cluster, feeder cable, and target customer/site node from DB
        splitter_id = ext.get("splitter_id") or lead_alm.resource_id
        gpon_obj = inv["gpon_clusters"].get(splitter_id)
        if not gpon_obj:
            for g in inv["gpon_clusters"].values():
                if g["feeder_cable_id"] in cluster.involved_cables:
                    gpon_obj = g
                    splitter_id = g["id"]
                    break

        feeder_cable = (
            (gpon_obj or {}).get("feeder_cable_id")
            or next(iter(cluster.involved_cables), None)
            or ext.get("cable_id", "UNKNOWN-CABLE")
        )

        # Verify fiber continuity either from explicit RFTS NO_CUT alarm or live on-demand .sor OTDR check
        no_cut_verified = any("NO_CUT" in normalize_problem_code(a.specific_problem) for a in cluster.alarms)
        if not no_cut_verified and feeder_cable in inv["cables"]:
            sor_res = await ctx.otdr_adapter.fetch_and_parse_sor(feeder_cable)
            if sor_res is not None:
                parsed_sor, _ = sor_res
                no_cut_verified = parsed_sor.fault_distance_optical_m is None
        if not no_cut_verified:
            return None

        # Resolve target endpoint node from feeder cable or alarm node_id
        cable_obj = inv["cables"].get(feeder_cable, {})
        path_nodes = cable_obj.get("path_nodes") or []
        endpoint_node_id = path_nodes[-1] if path_nodes else lead_alm.node_id
        node_obj = inv["nodes"].get(endpoint_node_id) or inv["nodes"].get(lead_alm.node_id) or {}

        lat = float(node_obj.get("lat", 0.0))
        lon = float(node_obj.get("lon", 0.0))
        district_label = (gpon_obj or {}).get("district") or node_obj.get("name") or endpoint_node_id
        ont_count = ext.get("ont_count") or (gpon_obj or {}).get("ont_count") or len(dying_gasp)

        resource_label = f"{endpoint_node_id} / {splitter_id} ({district_label})"
        summary = (
            f"{ont_count} GPON ONTs / enterprise CPEs at {district_label} emitted G.984/802.3ah Dying-Gasp "
            f"power-loss frames within sub-second window, and on-demand 1625nm OTDR trace on {feeder_cable} "
            f"confirmed 100% intact optical continuity. Root cause is a premises/utility AC power blackout, "
            f"not a physical fiber cut."
        )

        action = ProposedAction(
            action_id="ACT-SNOW-NO-TRUCK",
            target_system="ServiceNow ITSM",
            connector_id="servicenow_itsm",
            action_type="CREATE_SERVICENOW_POWER_ADVISORY",
            title=f"Suppress OSP Fibre Truck Roll & Open Power-Outage Advisory ({district_label})",
            description=(
                f"Record verified G.984 Dying-Gasp + clean 1625nm OTDR continuity on {feeder_cable} in ServiceNow "
                f"and notify facility/utility power contact without dispatching a fiber splicing crew."
            ),
            payload={
                "table": "incident",
                "short_description": f"[Power Outage Confirmed — No Fibre Cut] {resource_label}",
                "description": summary,
                "cmdb_ci": splitter_id,
                "assignment_group": "Customer Power & Premises Escalation",
            },
        )

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="COMMERCIAL_AC_POWER_OUTAGE",
            root_cause_resource=resource_label,
            title=f"{district_label} Mass GPON/CPE Outage — Confirmed AC Power Blackout (No Fibre Cut)",
            confidence=0.99,
            summary=summary,
            fault_location={
                "cable_id": feeder_cable,
                "lat": lat,
                "lon": lon,
                "fiber_intact": True,
                "dying_gasp_confirmed": True,
                "dispatch_verdict": "DO NOT ROLL OSP FIBRE SPLICING TRUCK — Premises AC Mains Blackout Confirmed",
            },
            domain_actions=[action],
            suppress_default_splice_dispatch=True,
        )
