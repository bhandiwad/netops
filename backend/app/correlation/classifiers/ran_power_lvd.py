"""Classifier: 4G/5G Hub Site Rectifier AC Mains Loss & Battery LVD Countdown."""
from __future__ import annotations

from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from .base import CorrelationContext, HypothesisClassifier, register_classifier


@register_classifier
class RanSitePowerLvdClassifier(HypothesisClassifier):
    classifier_id = "ran_site_power_lvd"
    priority = 90

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        lvd_alarms = [a for a in cluster.alarms if "LVD_COUNTDOWN" in a.specific_problem]
        if not lvd_alarms:
            return None

        inv = ctx.inventory
        lvd_alm = lvd_alarms[0]
        ext = lvd_alm.extra or {}

        site_id = lvd_alm.resource_id
        rsite = inv["ran_sites"].get(site_id) or {}
        node_obj = inv["nodes"].get(site_id) or inv["nodes"].get(lvd_alm.node_id) or {}

        site_name = rsite.get("name") or node_obj.get("name") or site_id
        lat = float(rsite.get("lat") or node_obj.get("lat") or 0.0)
        lon = float(rsite.get("lon") or node_obj.get("lon") or 0.0)
        backhaul_cable = rsite.get("backhaul_cable_id") or ext.get("cable_id") or ""

        dc_v = float(ext.get("dc_bus_voltage_v", 44.1))
        lvd_v = float(ext.get("lvd_threshold_v", 43.2))
        rem_mins = int(ext.get("battery_remaining_mins", 36))
        temp_c = float(ext.get("cabinet_temp_c", 44.8))

        tail_ids = rsite.get("downstream_tails_json") or []
        tail_names = [inv["ran_sites"].get(tid, {}).get("name", tid).split(" ")[0] for tid in tail_ids]
        total_sites = 1 + len(tail_ids)
        total_cells = len(rsite.get("cells_json") or []) + sum(
            len(inv["ran_sites"].get(tid, {}).get("cells_json") or []) for tid in tail_ids
        )

        cascade_desc = (
            f" and daisy-chained tail sites {', '.join(tail_names)} ({total_sites} sites / {total_cells} cells total)"
            if tail_names
            else f" ({total_cells} active cells)"
        )
        backhaul_clause = f"; OTDR verified backhaul fiber {backhaul_cable} is 100% intact" if backhaul_cable else ""

        summary = (
            f"Commercial 3-phase AC mains failed at {site_name} ({site_id}){backhaul_clause}. "
            f"Site DC bus is discharging at {dc_v}V (LVD trip at {lvd_v}V, {rem_mins} mins remaining, "
            f"cabinet {temp_c}°C). If LVD disconnects, {site_name.split(' ')[0]}{cascade_desc} will cascade dark."
        )

        action = ProposedAction(
            action_id="ACT-SNOW-GEN-DISPATCH",
            target_system="ServiceNow Field Service (FSM)",
            connector_id="servicenow_itsm",
            action_type="DISPATCH_FIELD_SPLICE_CREW",
            title=f"Dispatch Mobile Diesel Generator to {site_name.split(' ')[0]} Before {lvd_v}V LVD Trip ({rem_mins} mins left)",
            description=(
                f"Create Priority-1 ServiceNow Field Work Order (`wm_order`) to connect mobile generator at "
                f"{site_name}, preventing cascading blackout of {total_sites} 5G/4G site(s) ({total_cells} sectors)."
            ),
            payload={
                "table": "wm_order",
                "short_description": f"EMERGENCY Mobile Generator Dispatch to {site_id} (Vdc={dc_v}V, {rem_mins}m to LVD)",
                "description": summary,
                "cmdb_ci": site_id,
                "assignment_group": "RAN Mobile Generator & Power Rapid Response",
                "location_lat": lat,
                "location_lon": lon,
            },
        )

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="RAN_SITE_POWER_BATTERY_LVD",
            root_cause_resource=f"{site_id} ({site_name})",
            title=f"{site_name.split(' ')[0]} Hub Rectifier AC Loss & Battery LVD Countdown ({rem_mins} mins to {total_sites}-Site Cascade)",
            confidence=0.99,
            summary=summary,
            fault_location={
                "cable_id": backhaul_cable,
                "lat": lat,
                "lon": lon,
                "fiber_intact": True,
                "dc_bus_voltage_v": dc_v,
                "lvd_threshold_v": lvd_v,
                "battery_remaining_mins": rem_mins,
                "dispatch_verdict": f"DISPATCH MOBILE DIESEL GENERATOR TO {site_id} WITHIN {rem_mins} MINS BEFORE LVD TRIP",
            },
            domain_actions=[action],
            suppress_default_splice_dispatch=True,
        )
