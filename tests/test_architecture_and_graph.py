"""Architectural, Graph-Clustering, Dynamic-Reroute & Anti-Hardcoding Verification Suite.

Validates:
1. Zero topology hardcoding in `backend/app/` (`scripts/check_no_hardcoded_topology.py`).
2. Normalized relational PostgreSQL inventory + dynamic NetworkX Dijkstra optical rerouting.
3. Concurrent multi-fault alarm batch partitioning (`cluster_alarms_by_dependency_graph`) —
   proving two unrelated simultaneous city faults in one TMF642 batch produce 2 distinct incidents.
4. Remaining fault classifiers (SRLG Chamber Cut, GPON Dying-Gasp vs Cut, DWDM Pre-FEC BER)
   and human-gated Northbound action execution (`POST /api/v1/incidents/{id}/approve`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import httpx

from backend.app.routing.graph_engine import (
    audit_all_srlg_diversity,
    compute_dynamic_optical_reroute,
    load_normalized_inventory,
)

COPILOT_URL = "http://127.0.0.1:8002"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_zero_hardcoded_topology_in_backend():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_no_hardcoded_topology.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Anti-hardcoding gate failed:\n{proc.stdout}\n{proc.stderr}"
    assert "PASSED" in proc.stdout


def test_normalized_inventory_and_dynamic_dijkstra_reroute():
    inv = load_normalized_inventory()
    assert len(inv["nodes"]) >= 15
    assert len(inv["cables"]) >= 10
    assert len(inv["wavelengths"]) >= 4
    assert len(inv["services"]) >= 4

    # When CBL-QZ-BB-01 / duct D-I2-I1 is severed on Sheikh Zayed Rd Canal,
    # Dijkstra dynamically routes OCH-JLC-P (JBL -> DIFC) via the healthy inland DSO ring.
    reroute = compute_dynamic_optical_reroute(
        "OCH-JLC-P",
        failed_cables={"CBL-QZ-BB-01"},
        failed_ducts={"D-I2-I1"},
        inv=inv,
    )
    assert reroute is not None
    assert reroute[0] == "JBL"
    assert reroute[-1] == "DIFC"
    # Ensure severed QZ <-> BB hop is NOT traversed
    hop_pairs = {(reroute[i], reroute[i + 1]) for i in range(len(reroute) - 1)}
    assert ("QZ", "BB") not in hop_pairs
    assert ("BB", "QZ") not in hop_pairs
    assert "DSO" in reroute

    # Verify SRLG auditor detects false-diversity services strictly via relational graph walk
    findings = audit_all_srlg_diversity(inv)
    violations = [f for f in findings if not f["diversity_compliant"]]
    assert len(violations) >= 2


def test_concurrent_disjoint_multi_fault_clustering():
    now_iso = datetime.now(timezone.utc).isoformat()
    concurrent_batch = [
        # Fault Cluster A: GPON Commercial Power Outage in Al Quoz Industrial
        {
            "alarm_id": "ALM-CONC-GPON-1",
            "scenario_id": "concurrent_batch",
            "source_oem": "GenieACS / OLT EMS",
            "protocol": "ITU-T G.984 PLOAM",
            "layer": "GPON_ACCESS",
            "resource_id": "SPL-QZ-IND-02",
            "node_id": "AQI",
            "severity": "MAJOR",
            "specific_problem": "PON-LOSi-WITH-DYING-GASP-BURST",
            "probable_cause": "powerProblem",
            "raw_text": "24/24 ONTs on SPL-QZ-IND-02 emitted G.984 dying-gasp within 650ms prior to LOSi.",
            "raised_at": now_iso,
            "extra": {
                "splitter_id": "SPL-QZ-IND-02",
                "cable_id": "CBL-QZ-AQI-01",
                "dying_gasp_count": 24,
                "total_onts": 24,
            },
        },
        # Fault Cluster B: 80 GHz E-Band Microwave Rain Fade in Silicon Oasis / Academic City
        {
            "alarm_id": "ALM-CONC-MW-1",
            "scenario_id": "concurrent_batch",
            "source_oem": "Ericsson ENM / MINI-LINK",
            "protocol": "SNMPv2c / 3GPP FM",
            "layer": "MICROWAVE_BACKHAUL",
            "resource_id": "MW-DSO-ACAD-80G",
            "node_id": "RAN_DSO_TAIL",
            "severity": "MAJOR",
            "specific_problem": "EBAND-RSL-DEGRADATION-ACM-QPSK",
            "probable_cause": "atmosphericAttenuation",
            "raw_text": "80GHz E-Band RSL dropped -38.2 dBm -> -69.4 dBm during 42 mm/hr rain cell; ACM shifted to QPSK.",
            "raised_at": now_iso,
            "extra": {
                "mw_link_id": "MW-DSO-ACAD-80G",
                "rsl_dbm": -69.4,
                "rain_rate_mm_hr": 42.0,
                "acm_modulation": "QPSK (Downshifted from 1024QAM)",
                "local_tx_power_dbm": 18.0,
            },
        },
    ]

    with httpx.Client(timeout=15.0) as client:
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r = client.post(
            f"{COPILOT_URL}/api/v1/ingest/tmf642",
            json={"alarms": concurrent_batch},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["incident_ids"]) == 2, f"Expected 2 disjoint incidents, got: {body}"

        ov = client.get(f"{COPILOT_URL}/api/v1/overview").json()
        rc_types = {inc["root_cause_type"] for inc in ov["incidents"]}
        assert "COMMERCIAL_AC_POWER_OUTAGE" in rc_types
        assert "MICROWAVE_RAIN_FADE_ACM" in rc_types


def test_remaining_scenarios_and_gated_action_approval():
    with httpx.Client(timeout=15.0) as client:
        # Scenario 2: DIFC Shared Chamber SRLG Cut
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r2 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "difc_gate_srlg_cut"},
        )
        assert r2.status_code == 200
        inc2 = r2.json()["incident"]
        assert inc2["root_cause_type"] == "PHYSICAL_FIBRE_CUT"
        assert "Shared Duct" in inc2["root_cause_resource"]

        # Scenario 3: Al Quoz GPON Dying-Gasp vs Cut
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r3 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "al_quoz_dying_gasp_vs_cut"},
        )
        assert r3.status_code == 200
        inc3 = r3.json()["incident"]
        assert inc3["root_cause_type"] == "COMMERCIAL_AC_POWER_OUTAGE"

        # Scenario 4: DSO Pre-Failure DWDM Pre-FEC BER Degradation
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r4 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "dso_optical_degradation"},
        )
        assert r4.status_code == 200
        inc4 = r4.json()["incident"]
        assert inc4["root_cause_type"] == "OPTICAL_SPLICE_DEGRADATION_TCA"

        # Scenario 1 + Human-Gated Northbound Approval Execution
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r1 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "szr_canal_fibre_cut"},
        )
        assert r1.status_code == 200
        inc1 = r1.json()["incident"]
        assert inc1["root_cause_type"] == "PHYSICAL_FIBRE_CUT"
        assert inc1["fault_location"]["dispatch_error_avoided_m"] > 100.0

        # Execute gated Northbound approvals (Jira + ServiceNow + Ciena dynamic reroute)
        r_app = client.post(
            f"{COPILOT_URL}/api/v1/incidents/{inc1['incident_id']}/approve",
            json={"approved_by": "Automated Pytest Gate"},
        )
        assert r_app.status_code == 200
        updated = r_app.json()["incident"]
        assert updated["status"] == "APPROVED_EXECUTED"
        assert len(updated["executed_actions"]) == len(updated["proposed_actions"])
        assert all(a["status"] == "EXECUTED" for a in updated["executed_actions"])
