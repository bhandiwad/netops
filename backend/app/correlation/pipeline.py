"""Correlation Pipeline: Graph Clustering -> Classifier Registry -> SLA Impact -> RAG -> Persistence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from ..adapters.embeddings import compute_text_embedding
from ..adapters.registry import DatabaseBackedOtdrAdapter, RestNorthboundActionAdapter
from ..db import get_conn, log_audit
from ..routing.graph_engine import audit_all_srlg_diversity, load_normalized_inventory
from ..schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from .classifiers import CorrelationContext, evaluate_cluster_hypotheses
from .clusterer import cluster_alarms_by_dependency_graph

LLM_CONFIG: dict[str, str] = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_by_attr(alarms: list[Any], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in alarms:
        val = str(getattr(a, attr, None) or (a.get(attr) if isinstance(a, dict) else "unknown"))
        counts[val] = counts.get(val, 0) + 1
    return counts


def _compute_cluster_impact(
    cluster: CausalCluster,
    hypothesis: RootCauseHypothesis,
    inv: dict[str, Any],
    all_srlg: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cut_cables = set(
        hypothesis.fault_location.get("cut_cables")
        or ([hypothesis.fault_location["cable_id"]] if not hypothesis.fault_location.get("fiber_intact") and hypothesis.fault_location.get("cable_id") else [])
    )
    down_ochs = {
        a.resource_id
        for a in cluster.alarms
        if a.layer == "dwdm_optical" and a.resource_id in inv["wavelengths"]
    }
    explicit_service_ids = {
        str(a.extra["service_id"])
        for a in cluster.alarms
        if (a.extra or {}).get("service_id")
    }

    customers = inv["customers"]
    sla_tiers = inv["sla_tiers"]
    impacted_services: list[dict[str, Any]] = []
    total_penalty_per_hour_aed = 0

    for svc in inv["services"]:
        legs = svc.get("legs_json") or []
        legs_down = 0
        leg_details: list[dict[str, Any]] = []
        for leg in legs:
            is_down = (
                leg.get("cable") in cut_cables
                or leg.get("och") in down_ochs
                or svc["id"] in explicit_service_ids
            )
            if is_down:
                legs_down += 1
            leg_details.append({
                "leg": leg["name"],
                "status": "DOWN" if is_down else "UP",
                "cable": leg.get("cable"),
                "och": leg.get("och"),
            })

        if legs_down > 0:
            cust = customers.get(svc["customer_id"], {})
            tier_name = cust.get("sla_tier", "Gold")
            tier_info = sla_tiers.get(tier_name, {"mttr_hours": 4.0, "penalty_per_hour_aed": 10000})
            outage_state = "COMPLETE_OUTAGE" if legs_down == len(legs) else "DEGRADED_REDUNDANCY_LOST"
            pen = (
                int(tier_info["penalty_per_hour_aed"])
                if outage_state == "COMPLETE_OUTAGE"
                else int(tier_info["penalty_per_hour_aed"] * 0.25)
            )
            total_penalty_per_hour_aed += pen
            impacted_services.append({
                "service_id": svc["id"],
                "service_type": svc["service_type"],
                "bandwidth": svc["bandwidth"],
                "customer_id": svc["customer_id"],
                "customer_name": cust.get("name", svc["customer_id"]),
                "segment": cust.get("segment", "Enterprise"),
                "sla_tier": tier_name,
                "mttr_target_hours": float(tier_info["mttr_hours"]),
                "penalty_per_hour_aed": pen,
                "ordered_diverse": bool(svc.get("ordered_diverse")),
                "outage_state": outage_state,
                "legs": leg_details,
            })

    ran_alarms = [a for a in cluster.alarms if a.layer == "mobile_ran"]
    impacted_ran_sites = [
        {
            "site_id": a.resource_id,
            "problem": a.specific_problem,
            "cells": (a.extra or {}).get("cells", []),
            "is_cascaded_tail": "TAIL" in a.specific_problem,
        }
        for a in ran_alarms
    ]

    impacted_srlg = [
        s for s in all_srlg
        if not s["diversity_compliant"] and any(isvc["service_id"] == s["service_id"] for isvc in impacted_services)
    ]

    impact_bundle = {
        "impacted_service_count": len(impacted_services),
        "complete_outage_count": sum(1 for s in impacted_services if s["outage_state"] == "COMPLETE_OUTAGE"),
        "total_sla_penalty_per_hour_aed": total_penalty_per_hour_aed,
        "four_hour_sla_exposure_aed": total_penalty_per_hour_aed * 4,
        "impacted_services": impacted_services,
        "impacted_ran_sites": impacted_ran_sites,
        "impacted_5g_cell_count": sum(len(r["cells"]) for r in impacted_ran_sites),
        "alarm_collapse_ratio": f"{len(cluster.alarms)} alarms -> 1 root cause",
        "alarms_by_oem": _count_by_attr(cluster.alarms, "source_oem"),
        "alarms_by_layer": _count_by_attr(cluster.alarms, "layer"),
    }
    return impact_bundle, impacted_srlg


def _assemble_proposed_actions(
    hypothesis: RootCauseHypothesis,
    impact_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[ProposedAction] = [
        ProposedAction(
            action_id="ACT-JIRA-INC",
            target_system="Jira Service Management",
            connector_id="jira_sm",
            action_type="CREATE_JIRA_INCIDENT",
            title=f"Create Master NOC Incident in Jira ({hypothesis.root_cause_resource})",
            description=(
                f"Log correlated master incident in Jira project NOC linking {impact_bundle['alarm_collapse_ratio']} "
                f"and {impact_bundle['impacted_service_count']} impacted enterprise service(s)."
            ),
            payload={
                "project_key": "NOC",
                "summary": f"[P1] {hypothesis.root_cause_type}: {hypothesis.root_cause_resource} ({impact_bundle['alarm_collapse_ratio']})",
                "description": hypothesis.summary,
                "priority": "Highest",
                "labels": ["noc-copilot", hypothesis.root_cause_type.lower(), "sla-critical"],
            },
        )
    ]

    if not hypothesis.suppress_default_splice_dispatch:
        fl = hypothesis.fault_location
        up_mh = (fl.get("upstream_manhole") or {}).get("manhole_id", "UPSTREAM-MH")
        dn_mh = (fl.get("downstream_manhole") or {}).get("manhole_id", "DOWNSTREAM-MH")
        cid = fl.get("cable_id", hypothesis.root_cause_resource)
        actions.append(
            ProposedAction(
                action_id="ACT-SNOW-FSM",
                target_system="ServiceNow Field Service (FSM)",
                connector_id="servicenow_itsm",
                action_type="DISPATCH_FIELD_SPLICE_CREW",
                title=f"Dispatch OSP Fusion-Splice Crew between {up_mh} & {dn_mh}",
                description=(
                    f"Create ServiceNow Field Work Order (`wm_order`) at slack-corrected coordinates "
                    f"({fl.get('lat')}, {fl.get('lon')}), {fl.get('distance_from_upstream_manhole_m')} m "
                    f"downstream of {up_mh}."
                ),
                payload={
                    "table": "wm_order",
                    "short_description": f"Emergency Fusion Splice Repair on {cid} ({up_mh} -> {dn_mh})",
                    "description": hypothesis.summary,
                    "cmdb_ci": cid,
                    "assignment_group": "OSP Field Fibre Splicing Crew Alpha",
                    "location_lat": fl.get("lat"),
                    "location_lon": fl.get("lon"),
                },
            )
        )

    actions.extend(hypothesis.domain_actions)
    return [a.model_dump() for a in actions]


async def generate_ai_copilot_analysis(
    *,
    incident_id: str,
    root_cause_type: str,
    root_cause_resource: str,
    root_cause_summary: str,
    fault_location: dict[str, Any],
    impact_bundle: dict[str, Any],
    srlg_findings: list[dict[str, Any]],
    alarms: list[dict[str, Any]],
) -> dict[str, Any]:
    alarm_problems = " ".join(
        f"{a.get('specific_problem', '')} {a.get('probable_cause', '')}"
        for a in alarms[:12]
    )
    query_text = f"{root_cause_type} {root_cause_resource} {root_cause_summary} {alarm_problems}"
    q_emb = "[" + ",".join(str(x) for x in compute_text_embedding(query_text)) + "]"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, domain, oem_tags, symptoms, procedure_md, past_tickets_json,
                       ROUND((1.0 - (embedding <=> %s::vector))::numeric, 4) AS cosine_similarity
                FROM runbooks
                ORDER BY embedding <=> %s::vector
                LIMIT 3
                """,
                (q_emb, q_emb),
            )
            ranked_rbs = [dict(r) for r in cur.fetchall()]

    matched_rb = ranked_rbs[0]
    cosine_sim = float(matched_rb.get("cosine_similarity") or 0.85)
    sample_alarm_ids = [a["alarm_id"] for a in alarms[:6]]
    srlg_text = (
        srlg_findings[0]["risk_summary"]
        if srlg_findings
        else "All redundant paths remained physically disjoint."
    )

    deterministic_mop = (
        f"### Executive Diagnosis (Grounded in {len(alarms)} Multi-Layer Telemetry Events)\n"
        f"- **Root Cause:** `{root_cause_type}` on **{root_cause_resource}**.\n"
        f"- **Evidence Chain:** Correlated `{len(alarms)}` alarms across `{', '.join(impact_bundle['alarms_by_oem'].keys())}` "
        f"(Sample IDs: `{', '.join(sample_alarm_ids)}`).\n"
        f"- **Spatial & Optical Physics:** {root_cause_summary}\n"
        f"- **SRLG & Redundancy Audit:** {srlg_text}\n"
        f"- **Commercial SLA Exposure:** **{impact_bundle['impacted_service_count']} enterprise services** affected "
        f"(**AED {impact_bundle['total_sla_penalty_per_hour_aed']:,}/hr** penalty risk; "
        f"**AED {impact_bundle['four_hour_sla_exposure_aed']:,}** over 4-hour Platinum MTTR window).\n\n"
        f"### Recommended Method of Procedure (Ref: `{matched_rb['id']}` — *{matched_rb['title']}*)\n"
        f"{matched_rb['procedure_md']}"
    )

    llm_used = "deterministic_evidence_synth (set API key in Console to enable live Claude/GPT generation)"
    final_narrative = deterministic_mop

    api_key = LLM_CONFIG.get("api_key", "").strip()
    provider = LLM_CONFIG.get("provider", "anthropic")
    model_name = LLM_CONFIG.get("model", "claude-sonnet-4-20250514")

    if api_key:
        prompt = (
            "You are a Principal Telco NOC Reliability Copilot. Using ONLY the verified deterministic evidence below "
            "(never invent numbers, coordinates, or circuit IDs), write a concise, operator-grade Incident Brief & "
            "Method of Procedure (MOP) in Markdown with exact source citations ([Alarm ID], [Runbook ID], [Cable/Manhole ID]).\n\n"
            f"INCIDENT ID: {incident_id}\n"
            f"ROOT CAUSE: {root_cause_type} on {root_cause_resource}\n"
            f"SUMMARY: {root_cause_summary}\n"
            f"FAULT LOCATION JSON: {json.dumps(fault_location)}\n"
            f"IMPACT JSON: {json.dumps(impact_bundle)}\n"
            f"SRLG VIOLATIONS: {json.dumps(srlg_findings)}\n"
            f"MATCHED RUNBOOK ({matched_rb['id']}): {matched_rb['procedure_md']}\n"
            f"PAST RESOLVED TICKETS: {json.dumps(matched_rb['past_tickets_json'])}\n"
        )
        try:
            if provider == "anthropic":
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=api_key, timeout=12.0)
                resp = await client.messages.create(
                    model=model_name,
                    max_tokens=700,
                    messages=[{"role": "user", "content": prompt}],
                )
                final_narrative = resp.content[0].text
                llm_used = f"Anthropic {model_name}"
            elif provider == "openai":
                import openai
                client = openai.AsyncOpenAI(api_key=api_key, timeout=12.0)
                resp = await client.chat.completions.create(
                    model=model_name,
                    max_tokens=700,
                    messages=[{"role": "user", "content": prompt}],
                )
                final_narrative = resp.choices[0].message.content or deterministic_mop
                llm_used = f"OpenAI {model_name}"
        except Exception as e:
            llm_used = f"deterministic_fallback (LLM call error: {str(e)[:80]})"

    return {
        "model_used": llm_used,
        "matched_runbook_id": matched_rb["id"],
        "matched_runbook_title": matched_rb["title"],
        "pgvector_cosine_similarity": cosine_sim,
        "top_matched_runbooks": [
            {"id": r["id"], "title": r["title"], "cosine_similarity": float(r.get("cosine_similarity") or 0.0)}
            for r in ranked_rbs
        ],
        "past_tickets": matched_rb["past_tickets_json"],
        "cited_alarm_ids": sample_alarm_ids,
        "narrative_md": final_narrative,
        "generated_at": _now_iso(),
    }


async def correlate_alarms_into_incidents(raw_alarms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Partition incoming alarms into independent graph clusters and correlate each into an Incident."""
    if not raw_alarms:
        return []

    inv = load_normalized_inventory()
    clusters = cluster_alarms_by_dependency_graph(raw_alarms, inv)
    ctx = CorrelationContext(inventory=inv, otdr_adapter=DatabaseBackedOtdrAdapter())
    all_srlg = audit_all_srlg_diversity(inv)

    created_incidents: list[dict[str, Any]] = []

    for cluster in clusters:
        incident_id = f"INC-{cluster.cluster_id[:18]}"
        hypothesis = await evaluate_cluster_hypotheses(cluster, ctx)
        impact_bundle, impacted_srlg = _compute_cluster_impact(cluster, hypothesis, inv, all_srlg)
        proposed_actions = _assemble_proposed_actions(hypothesis, impact_bundle)

        alarm_dicts = [a.model_dump() for a in cluster.alarms]
        ai_copilot = await generate_ai_copilot_analysis(
            incident_id=incident_id,
            root_cause_type=hypothesis.root_cause_type,
            root_cause_resource=hypothesis.root_cause_resource,
            root_cause_summary=hypothesis.summary,
            fault_location=hypothesis.fault_location,
            impact_bundle=impact_bundle,
            srlg_findings=impacted_srlg,
            alarms=alarm_dicts,
        )

        with get_conn() as conn:
            with conn.cursor() as cur:
                for a in cluster.alarms:
                    cur.execute(
                        """
                        INSERT INTO alarms (
                            alarm_id, incident_id, scenario_id, source_oem, protocol, layer,
                            resource_id, node_id, severity, specific_problem, probable_cause,
                            raw_text, raised_at, extra_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (alarm_id) DO NOTHING
                        """,
                        (
                            a.alarm_id,
                            incident_id,
                            a.scenario_id,
                            a.source_oem,
                            a.protocol,
                            a.layer,
                            a.resource_id,
                            a.node_id,
                            a.severity,
                            a.specific_problem,
                            a.probable_cause,
                            a.raw_text,
                            a.raised_at,
                            json.dumps(a.extra),
                        ),
                    )
                cur.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, title, status, severity, root_cause_type, root_cause_resource,
                        root_cause_summary, confidence, alarm_count, fault_location_json,
                        impact_json, srlg_findings_json, otdr_trace_json, ai_copilot_json,
                        proposed_actions_json, executed_actions_json, updated_at
                    )
                    VALUES (%s, %s, 'PENDING_APPROVAL', 'CRITICAL', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, NOW())
                    ON CONFLICT (incident_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        status = 'PENDING_APPROVAL',
                        root_cause_type = EXCLUDED.root_cause_type,
                        root_cause_resource = EXCLUDED.root_cause_resource,
                        root_cause_summary = EXCLUDED.root_cause_summary,
                        confidence = EXCLUDED.confidence,
                        alarm_count = EXCLUDED.alarm_count,
                        fault_location_json = EXCLUDED.fault_location_json,
                        impact_json = EXCLUDED.impact_json,
                        srlg_findings_json = EXCLUDED.srlg_findings_json,
                        otdr_trace_json = EXCLUDED.otdr_trace_json,
                        ai_copilot_json = EXCLUDED.ai_copilot_json,
                        proposed_actions_json = EXCLUDED.proposed_actions_json,
                        executed_actions_json = '[]'::jsonb,
                        updated_at = NOW()
                    """,
                    (
                        incident_id,
                        hypothesis.title,
                        hypothesis.root_cause_type,
                        hypothesis.root_cause_resource,
                        hypothesis.summary,
                        hypothesis.confidence,
                        len(cluster.alarms),
                        json.dumps(hypothesis.fault_location),
                        json.dumps(impact_bundle),
                        json.dumps(impacted_srlg),
                        json.dumps(hypothesis.otdr_trace_data),
                        json.dumps(ai_copilot),
                        json.dumps(proposed_actions),
                    ),
                )

        log_audit(
            actor="correlation_pipeline",
            action_type="INCIDENT_CORRELATED",
            target_id=incident_id,
            detail={
                "classifier": hypothesis.classifier_id,
                "alarm_count": len(cluster.alarms),
                "root_cause": hypothesis.root_cause_resource,
                "confidence": hypothesis.confidence,
            },
        )
        detail = get_incident_detail(incident_id)
        if detail:
            created_incidents.append(detail)

    return created_incidents


async def correlate_alarms_into_incident(raw_alarms: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Convenience wrapper returning the primary correlated incident."""
    incidents = await correlate_alarms_into_incidents(raw_alarms)
    return incidents[0] if incidents else None


async def execute_incident_actions(
    incident_id: str,
    approved_by: str,
    action_ids: list[str] | None = None,
) -> dict[str, Any]:
    inc = get_incident_detail(incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found")

    executor = RestNorthboundActionAdapter()
    proposed = inc["proposed_actions"]
    executed: list[dict[str, Any]] = list(inc.get("executed_actions") or [])

    for act in proposed:
        if action_ids and act["action_id"] not in action_ids:
            continue
        if any(e["action_id"] == act["action_id"] for e in executed):
            continue

        result_meta = await executor.execute(act, approved_by=approved_by)
        exec_rec = {
            **act,
            "status": "EXECUTED",
            "approved_by": approved_by,
            "executed_at": _now_iso(),
            "result": result_meta,
        }
        executed.append(exec_rec)
        log_audit(
            actor=approved_by,
            action_type=act["action_type"],
            target_id=incident_id,
            detail=exec_rec,
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE incidents
                SET status = 'APPROVED_EXECUTED',
                    executed_actions_json = %s,
                    updated_at = NOW()
                WHERE incident_id = %s
                """,
                (json.dumps(executed), incident_id),
            )

    return get_incident_detail(incident_id)  # type: ignore[return-value]


def get_incident_detail(incident_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM incidents WHERE incident_id = %s", (incident_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT * FROM alarms WHERE incident_id = %s ORDER BY raised_at DESC", (incident_id,))
            alms = [dict(a) for a in cur.fetchall()]

    inc = dict(row)
    return {
        "incident_id": inc["incident_id"],
        "title": inc["title"],
        "status": inc["status"],
        "severity": inc["severity"],
        "root_cause_type": inc["root_cause_type"],
        "root_cause_resource": inc["root_cause_resource"],
        "root_cause_summary": inc["root_cause_summary"],
        "confidence": inc["confidence"],
        "alarm_count": inc["alarm_count"],
        "fault_location": inc["fault_location_json"],
        "impact": inc["impact_json"],
        "srlg_findings": inc["srlg_findings_json"],
        "otdr_trace": inc["otdr_trace_json"],
        "ai_copilot": inc["ai_copilot_json"],
        "proposed_actions": inc["proposed_actions_json"],
        "executed_actions": inc["executed_actions_json"],
        "alarms": alms,
        "created_at": inc["created_at"].isoformat() if inc.get("created_at") else None,
        "updated_at": inc["updated_at"].isoformat() if inc.get("updated_at") else None,
    }
