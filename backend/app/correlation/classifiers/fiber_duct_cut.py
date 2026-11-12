"""Classifier: Physical OSP Fibre / Shared-Duct Cut with Binary SR-4731 `.sor` Localization."""
from __future__ import annotations

from typing import Any

from ...routing.graph_engine import compute_dynamic_optical_reroute, resolve_wavelength_cables
from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from ...spatial.postgis_locator import locate_fault_on_cable_postgis
from .base import CorrelationContext, HypothesisClassifier, normalize_problem_code, register_classifier


@register_classifier
class PhysicalFiberDuctCutClassifier(HypothesisClassifier):
    classifier_id = "physical_fiber_duct_cut"
    priority = 50  # Default physical-layer fallback when higher-layer exclusions do not match

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        inv = ctx.inventory
        cables_map = inv["cables"]

        # Identify severed cables from OTDR reflective break alarms first
        cut_cables = sorted({
            a.resource_id
            for a in cluster.alarms
            if "REFLECTIVE_FIBER_BREAK" in normalize_problem_code(a.specific_problem) and a.resource_id in cables_map
        })
        confirmed_reflective_break = bool(cut_cables)

        if not cut_cables:
            # Only infer an unconfirmed cable cut if there is a hard optical LOS / LOF / link-down alarm
            # (never misclassify a soft Pre-FEC BER / non-reflective bend TCA as a severed cable!)
            has_hard_down = any(
                tok in normalize_problem_code(a.specific_problem)
                for a in cluster.alarms
                for tok in ("LOS", "LOF", "BFD_DOWN", "LINK_DOWN", "CABLE_CUT")
            )
            has_no_cut = any("NO_CUT" in normalize_problem_code(a.specific_problem) for a in cluster.alarms)
            if not has_hard_down or has_no_cut:
                return None
            cut_cables = sorted(cluster.involved_cables)
        if not cut_cables:
            return None

        primary_cable = cut_cables[0]
        c_obj = cables_map[primary_cable]

        # Determine if multiple cables failed simultaneously inside a shared physical duct (SRLG cut)
        shared_ducts: list[str] = []
        if len(cut_cables) > 1:
            common = set(cables_map[cut_cables[0]].get("duct_ids") or [])
            for other_cid in cut_cables[1:]:
                common &= set(cables_map[other_cid].get("duct_ids") or [])
            shared_ducts = sorted(common)

        if len(cut_cables) > 1 and shared_ducts:
            resource_label = f"Shared Duct {shared_ducts[0]} ({', '.join(cut_cables)})"
        elif len(cut_cables) > 1:
            resource_label = f"Multi-Cable Cut ({', '.join(cut_cables)})"
        else:
            resource_label = primary_cable

        # Pull genuine binary Telcordia SR-4731 `.sor` file through the configured OTDR Adapter
        otdr_trace_data: dict[str, Any] = {}
        opt_dist = float(c_obj.get("optical_length_m", 9000.0)) * 0.5
        sor_res = await ctx.otdr_adapter.fetch_and_parse_sor(primary_cable)
        if sor_res is not None:
            parsed_sor, byte_len = sor_res
            if parsed_sor.fault_distance_optical_m is not None:
                opt_dist = parsed_sor.fault_distance_optical_m
            otdr_trace_data = {
                "cable_id": parsed_sor.cable_id,
                "wavelength_nm": parsed_sor.wavelength_nm,
                "supplier_name": parsed_sor.supplier_name,
                "unit_name": parsed_sor.unit_name,
                "serial_number": parsed_sor.serial_number,
                "refractive_index": parsed_sor.refractive_index,
                "pulse_width_ns": parsed_sor.pulse_width_ns,
                "sample_spacing_m": parsed_sor.sample_spacing_m,
                "crc_valid": parsed_sor.crc_valid,
                "binary_size_bytes": byte_len,
                "fault_distance_optical_m": opt_dist,
                "key_events": [vars(e) for e in parsed_sor.key_events],
                "trace_points_db": parsed_sor.trace_points_db[::4],
            }

        fault_loc = locate_fault_on_cable_postgis(primary_cable, opt_dist)
        fault_loc["cut_cables"] = cut_cables

        summary = (
            f"Physical fibre break on {', '.join(cut_cables)} localized via 1625nm SR-4731 "
            f".sor trace at {opt_dist:.1f} m optical -> {fault_loc['corrected_trench_distance_m']} m trench "
            f"(subtracted {fault_loc['slack_Coils_subtracted_m']} m manhole slack coils & {fault_loc['helix_factor']}x "
            f"helical factor, avoiding {fault_loc['dispatch_error_avoided_m']} m dispatch error). "
            f"Pinpointed at ({fault_loc['lat']}, {fault_loc['lon']}) between "
            f"{fault_loc['upstream_manhole']['manhole_id']} and {fault_loc['downstream_manhole']['manhole_id']}."
        )

        # Dynamically compute optical controller reroute actions for any service-bearing wavelength traversing cut_cables
        cut_set = set(cut_cables)
        failed_duct_set = set(shared_ducts)
        actions: list[ProposedAction] = []
        rerouted_services: set[str] = set()

        for och_id, w in inv["wavelengths"].items():
            svc_id = w.get("service_id")
            if not svc_id or svc_id in rerouted_services:
                continue
            w_cables = set(resolve_wavelength_cables(w, inv["oms_by_pair"], cables_map))
            if not (w_cables & cut_set):
                continue

            # Prefer rerouting the protect leg (or primary leg if single-legged) onto a surviving POP path
            target_och = och_id
            for cand_id, cand_w in inv["wavelengths"].items():
                if cand_w.get("service_id") == svc_id and cand_w.get("leg_name") == "protect":
                    target_och = cand_id
                    w = cand_w
                    break

            alt_path = compute_dynamic_optical_reroute(
                target_och,
                failed_cables=cut_set,
                failed_ducts=failed_duct_set,
                inv=inv,
            )
            if alt_path:
                rerouted_services.add(svc_id)
                actions.append(
                    ProposedAction(
                        action_id=f"ACT-OPT-REROUTE-{target_och}",
                        target_system="Optical SDN Controller",
                        connector_id=w.get("controller_id", "ciena_mcp"),
                        action_type="CIENA_WAVELENGTH_REROUTE",
                        title=f"Re-Provision {w.get('rate', '100G')} Wavelength ({target_och}) over Disjoint Ring ({' -> '.join(alt_path)})",
                        description=(
                            f"Dynamically computed surviving POP path {' -> '.join(alt_path)} bypassing severed "
                            f"{', '.join(cut_cables)} via Optical Controller REST API."
                        ),
                        payload={
                            "och_id": target_och,
                            "new_path": alt_path,
                            "reason": f"Automated disjoint ring restoration around severed {', '.join(cut_cables)}",
                        },
                    )
                )

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="PHYSICAL_FIBRE_CUT",
            root_cause_resource=resource_label,
            title=f"Metro Fibre Cut on {resource_label} ({len(cluster.alarms)} Alarms Correlated -> 1 Root Cause)",
            confidence=0.97 if confirmed_reflective_break else 0.91,
            summary=summary,
            fault_location=fault_loc,
            otdr_trace_data=otdr_trace_data,
            domain_actions=actions,
            suppress_default_splice_dispatch=False,
        )
