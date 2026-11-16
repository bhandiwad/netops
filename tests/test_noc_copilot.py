"""End-to-end verification tests for Phases 1–7 of the NOC Copilot:
- Binary SR-4731 .sor codec & CRC-16 verification
- PostGIS slack-loop spatial localization & SRLG diversity audit
- All 7 scenarios (Fibre Cut, SRLG Chamber Cut, GPON Dying-Gasp, DWDM Pre-FEC BER,
  5G Hub Battery LVD Countdown, 80GHz E-Band Rain Fade, Subsea PFE Shunt Fault)
- pgvector semantic runbook cosine similarity search
- 3GPP TS 32.435 XML PM counters & Multi-Layer Dependency Graph
- 10,000-Alarm Storm Benchmark
"""
from __future__ import annotations

import httpx
import pytest

from shared.sor_codec import generate_sor_bytes, parse_sor_bytes

COPILOT_URL = "http://127.0.0.1:8002"
EMULATOR_URL = "http://127.0.0.1:8001"


def test_binary_sor_codec_roundtrip():
    raw = generate_sor_bytes(
        cable_id="CBL-TEST-144F",
        fiber_number=4,
        wavelength_nm=1625,
        location_a="QZ",
        location_b="BB",
        total_optical_length_m=12400.0,
        splice_distances_m=[(2100.0, "MH-J_I3"), (5400.0, "MH-J_I2")],
        cut_distance_optical_m=7850.5,
    )
    assert raw.startswith(b"Map\x00")
    parsed = parse_sor_bytes(raw)
    assert parsed.crc_valid is True
    assert parsed.cable_id == "CBL-TEST-144F"
    assert parsed.wavelength_nm == 1625
    assert parsed.fault_distance_optical_m == pytest.approx(7850.5, abs=0.5)
    assert len(parsed.key_events) == 4
    assert len(parsed.trace_points_db) == 1000


def test_all_seven_scenarios_pgvector_and_storm_benchmark():
    with httpx.Client(timeout=15.0) as client:
        # 1. Reset network
        r = client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        assert r.status_code == 200

        # 2. Scenario 5: 5G Hub Site Rectifier AC Mains Loss & Battery LVD Countdown
        r5 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "ran_site_battery_lvd_countdown"},
        )
        assert r5.status_code == 200
        inc5 = r5.json()["incident"]
        assert inc5["root_cause_type"] == "RAN_SITE_POWER_BATTERY_LVD"
        assert inc5["ai_copilot"]["matched_runbook_id"] == "RB-RAN-004"
        assert inc5["ai_copilot"]["pgvector_cosine_similarity"] > 0.7

        # 3. Scenario 6: 80GHz E-Band Microwave Rain Fade
        r6 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "eband_microwave_rain_fade"},
        )
        assert r6.status_code == 200
        inc6 = r6.json()["incident"]
        assert inc6["root_cause_type"] == "MICROWAVE_RAIN_FADE_ACM"
        assert inc6["ai_copilot"]["matched_runbook_id"] == "RB-MW-005"

        # 4. Scenario 7: Subsea Wet-Plant Repeater Shunt Fault & C-OTDR
        r7 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "subsea_shunt_fault"},
        )
        assert r7.status_code == 200
        inc7 = r7.json()["incident"]
        assert inc7["root_cause_type"] == "SUBSEA_PFE_SHUNT_FAULT"
        assert inc7["ai_copilot"]["matched_runbook_id"] == "RB-SUBSEA-006"

        # 5. 3GPP TS 32.435 XML PM Counter check
        r_xml = client.get(f"{COPILOT_URL}/api/v1/telemetry/3gpp-xml")
        assert r_xml.status_code == 200
        assert "<measCollecFile" in r_xml.json()["xml"]

        # 6. 10,000-Alarm Storm Benchmark check
        r_bench = client.post(
            f"{COPILOT_URL}/api/v1/benchmark/storm",
            json={"storm_size": 10000},
        )
        assert r_bench.status_code == 200
        bdata = r_bench.json()
        assert bdata["storm_size"] == 10000
        assert bdata["root_causes_identified"] == 3
        assert bdata["noise_reduction_pct"] > 99.9

        # 7. Switch to India — Delhi NCR region, verify 2 India customer profiles, INR SLAs & scenarios
        r_sw_in = client.post(
            f"{COPILOT_URL}/api/v1/region/switch",
            json={"region_id": "india_ncr"},
        )
        assert r_sw_in.status_code == 200
        ov_in = client.get(f"{COPILOT_URL}/api/v1/overview").json()
        assert ov_in["active_region"] == "india_ncr"
        assert ov_in["currency"] == "INR"
        assert set(ov_in["operator_profiles"].keys()) == {"in_metro_dci", "in_ran_converged"}
        assert len(ov_in["scenarios"]) == 7
        assert len(ov_in["srlg_findings"]) >= 2

        for in_scen, expected_rc in [
            ("ncr_dnd_yamuna_fibre_cut", "PHYSICAL_FIBRE_CUT"),
            ("cp_bank_srlg_cut", "PHYSICAL_FIBRE_CUT"),
            ("okhla_dying_gasp_vs_cut", "COMMERCIAL_AC_POWER_OUTAGE"),
            ("noida_dci_optical_degradation", "OPTICAL_SPLICE_DEGRADATION_TCA"),
            ("ncr_ran_battery_lvd_countdown", "RAN_SITE_POWER_BATTERY_LVD"),
            ("noida_eband_monsoon_rain_fade", "MICROWAVE_RAIN_FADE_ACM"),
            ("india_subsea_cls_shunt_fault", "SUBSEA_PFE_SHUNT_FAULT"),
        ]:
            client.post(f"{COPILOT_URL}/api/v1/faults/reset")
            r_in = client.post(
                f"{COPILOT_URL}/api/v1/faults/trigger",
                json={"scenario_id": in_scen},
            )
            assert r_in.status_code == 200, f"Failed scenario {in_scen}: {r_in.text}"
            inc_in = r_in.json()["incident"]
            assert inc_in["root_cause_type"] == expected_rc
            if in_scen == "ncr_dnd_yamuna_fibre_cut":
                assert inc_in["impact"]["currency"] == "INR"
                assert inc_in["impact"]["total_sla_penalty_per_hour_aed"] == 450000
                assert "INR 450,000/hr" in inc_in["ai_copilot"]["narrative_md"]

        # 8. Switch cleanly back to UAE — Dubai Metro so subsequent tests start on UAE baseline
        r_sw_ae = client.post(
            f"{COPILOT_URL}/api/v1/region/switch",
            json={"region_id": "uae_dubai"},
        )
        assert r_sw_ae.status_code == 200

        # 9. Leave Scenario 1 active so UI opens with a rich multi-layer incident ready to inspect
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r1 = client.post(
            f"{COPILOT_URL}/api/v1/faults/trigger",
            json={"scenario_id": "szr_canal_fibre_cut"},
        )
        assert r1.status_code == 200
        ov = client.get(f"{COPILOT_URL}/api/v1/overview").json()
        assert len(ov["dependency_graph"]["nodes"]) > 10
        assert len(ov["scenarios"]) == 7
