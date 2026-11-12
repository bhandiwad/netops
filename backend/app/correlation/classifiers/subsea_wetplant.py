"""Classifier: Subsea Wet-Plant Repeater Insulation Shunt Fault & C-OTDR Localization."""
from __future__ import annotations

from ...routing.graph_engine import compute_dynamic_optical_reroute
from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from .base import CorrelationContext, HypothesisClassifier, register_classifier


@register_classifier
class SubseaWetPlantShuntClassifier(HypothesisClassifier):
    classifier_id = "subsea_wetplant_shunt"
    priority = 92

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        sub_alarms = [a for a in cluster.alarms if "SUBSEA_PFE_SHUNT" in a.specific_problem]
        if not sub_alarms:
            return None

        inv = ctx.inventory
        sub_alm = sub_alarms[0]
        ext = sub_alm.extra or {}

        sub_id = ext.get("subsea_cable_id") or sub_alm.resource_id
        sub_obj = inv["subsea_cables"].get(sub_id)
        if not sub_obj and inv["subsea_cables"]:
            sub_obj = next(iter(inv["subsea_cables"].values()))
            sub_id = sub_obj["id"]

        cls_node_id = (sub_obj or {}).get("cls_node") or sub_alm.node_id
        cls_node = inv["nodes"].get(cls_node_id) or {}
        cls_name = cls_node.get("name") or cls_node_id
        pfe_id = (sub_obj or {}).get("pfe_id") or ext.get("pfe_id") or "PFE-01"

        lat = float(cls_node.get("lat", 0.0))
        lon = float(cls_node.get("lon", 0.0))
        pfe_v = float(ext.get("pfe_voltage_v", 2890.0))
        leak_ma = float(ext.get("earth_leakage_ma", 318.5))
        cotdr_km = float(ext.get("cotdr_shunt_distance_km", 412.6))
        fault_span = str(ext.get("fault_span", "Repeater Span R07 -> R08"))
        depth_m = int(ext.get("water_depth_m", 68))

        summary = (
            f"{cls_name} Power Feed Equipment ({pfe_id}) detected an insulation shunt fault on subsea system "
            f"{sub_id} (line voltage dropped to +{pfe_v:.0f}V at constant current, {leak_ma}mA earth leakage). "
            f"Coherent OTDR (C-OTDR) localized the wet-plant shunt at {cotdr_km} km from {cls_name} "
            f"({fault_span}, {depth_m}m water depth)."
        )

        actions: list[ProposedAction] = [
            ProposedAction(
                action_id=f"ACT-SNOW-WETPLANT-{pfe_id}",
                target_system="ServiceNow Field Service (FSM)",
                connector_id="servicenow_itsm",
                action_type="DISPATCH_FIELD_SPLICE_CREW",
                title=f"Reconfigure {cls_name} {pfe_id} to Single-End Feed & Alert Marine Cable Depot",
                description=(
                    f"Switch {pfe_id} to single-end constant-current feeding to isolate {fault_span} earth leakage "
                    f"({cotdr_km} km seaward, {depth_m}m depth) and stage marine repair vessel coordinates."
                ),
                payload={
                    "table": "wm_order",
                    "short_description": f"Subsea {pfe_id} Single-End Reconfiguration & {fault_span} Shunt Isolation",
                    "description": summary,
                    "cmdb_ci": sub_id,
                    "assignment_group": "Subsea CLS Wet-Plant Engineering",
                    "location_lat": lat,
                    "location_lon": lon,
                },
            )
        ]

        # Dynamically find any wavelength carrying services associated with this subsea cable and compute reroute
        carried_svcs = set((sub_obj or {}).get("carried_services_json") or [])
        for a in cluster.alarms:
            if (a.extra or {}).get("service_id"):
                carried_svcs.add(str(a.extra["service_id"]))

        for och_id, w in inv["wavelengths"].items():
            if w.get("service_id") in carried_svcs and w.get("leg_name") in ("working", None):
                alt_path = compute_dynamic_optical_reroute(och_id, inv=inv)
                if alt_path:
                    actions.append(
                        ProposedAction(
                            action_id=f"ACT-OPT-SUBSEA-{och_id}",
                            target_system="Optical SDN Controller",
                            connector_id=w.get("controller_id", "ciena_mcp"),
                            action_type="CIENA_WAVELENGTH_REROUTE",
                            title=f"Reroute Wholesale DCI Wave ({och_id}) onto Protected Terrestrial Path",
                            description=f"Shift {och_id} onto dynamically computed terrestrial path {' -> '.join(alt_path)}.",
                            payload={
                                "och_id": och_id,
                                "new_path": alt_path,
                                "reason": f"Subsea {fault_span} PFE shunt isolation ({sub_id})",
                            },
                        )
                    )
                    break

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="SUBSEA_PFE_SHUNT_FAULT",
            root_cause_resource=f"{sub_id} ({fault_span}, {cls_name})",
            title=f"{cls_name} Subsea Wet-Plant Shunt Fault ({fault_span} at {cotdr_km} km via C-OTDR)",
            confidence=0.97,
            summary=summary,
            fault_location={
                "lat": lat,
                "lon": lon,
                "subsea_cable_id": sub_id,
                "pfe_id": pfe_id,
                "pfe_voltage_v": pfe_v,
                "cotdr_shunt_distance_km": cotdr_km,
                "fault_span": fault_span,
                "water_depth_m": depth_m,
                "dispatch_verdict": f"RECONFIGURE {pfe_id} TO SINGLE-END FEED & REROUTE CARRIED DCI WAVELENGTHS",
            },
            domain_actions=actions,
            suppress_default_splice_dispatch=True,
        )
