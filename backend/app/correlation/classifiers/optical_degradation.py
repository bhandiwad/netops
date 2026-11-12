"""Classifier: Proactive DWDM Pre-FEC BER / OSNR Optical Degradation."""
from __future__ import annotations

from ...routing.graph_engine import compute_dynamic_optical_reroute, resolve_wavelength_cables
from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from ...spatial.postgis_locator import locate_fault_on_cable_postgis
from .base import CorrelationContext, HypothesisClassifier, normalize_problem_code, register_classifier


@register_classifier
class OpticalDegradationClassifier(HypothesisClassifier):
    classifier_id = "optical_degradation_tca"
    priority = 85

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        ber_alarms = [a for a in cluster.alarms if "PRE_FEC_BER" in normalize_problem_code(a.specific_problem)]
        if not ber_alarms:
            return None

        inv = ctx.inventory
        ber_alm = ber_alarms[0]
        ext = ber_alm.extra or {}

        och_id = ber_alm.resource_id
        w_obj = inv["wavelengths"].get(och_id, {})

        # Dynamically determine underlying cable from alarm extra or wavelength topology
        cid = ext.get("cable_id")
        if not cid and w_obj:
            w_cables = resolve_wavelength_cables(w_obj, inv["oms_by_pair"], inv["cables"])
            cid = w_cables[0] if w_cables else None
        if not cid and cluster.involved_cables:
            cid = sorted(cluster.involved_cables)[0]
        if not cid:
            return None

        c_obj = inv["cables"].get(cid, {})
        default_dist = float(c_obj.get("optical_length_m", 9600.0)) * 0.4
        opt_dist = float(ext.get("optical_event_distance_m", default_dist))
        fault_loc = locate_fault_on_cable_postgis(cid, opt_dist)

        pre_ber = ext.get("pre_fec_ber", "8.4e-4")
        osnr_db = ext.get("osnr_db", 14.2)
        step_loss_db = ext.get("step_loss_db", 4.8)

        summary = (
            f"Pre-failure optical degradation on {och_id} (Pre-FEC BER {pre_ber}, OSNR {osnr_db} dB) "
            f"caused by a +{step_loss_db} dB macro-bend / pinched splice on {cid} at {opt_dist:.1f} m optical "
            f"({fault_loc['corrected_trench_distance_m']} m trench, near {fault_loc['upstream_manhole']['name']})."
        )

        actions: list[ProposedAction] = []
        alt_path = compute_dynamic_optical_reroute(och_id, failed_cables={cid}, inv=inv)
        if alt_path:
            actions.append(
                ProposedAction(
                    action_id=f"ACT-OPT-REROUTE-{och_id}",
                    target_system="Optical SDN Controller",
                    connector_id=w_obj.get("controller_id", "ciena_mcp"),
                    action_type="CIENA_WAVELENGTH_REROUTE",
                    title=f"Proactively Shift {w_obj.get('rate', '100G')} Wave ({och_id}) Before FEC Cliff",
                    description=(
                        f"Hitless wavelength switch onto disjoint path {' -> '.join(alt_path)} to bypass "
                        f"+{step_loss_db} dB pinched splice on {cid}."
                    ),
                    payload={
                        "och_id": och_id,
                        "new_path": alt_path,
                        "reason": f"Proactive Pre-FEC BER TCA remediation on {cid}",
                    },
                )
            )

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="OPTICAL_SPLICE_DEGRADATION_TCA",
            root_cause_resource=f"{cid} (carrying {och_id})",
            title=f"{och_id} Pre-FEC BER Degradation — Pinched Splice on {cid}",
            confidence=0.95,
            summary=summary,
            fault_location=fault_loc,
            domain_actions=actions,
            suppress_default_splice_dispatch=False,
        )
