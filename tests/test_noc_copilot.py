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
        inc1 = r1.json()["incident"]
        fl1 = inc1["fault_location"]
        assert fl1["confidence_radius_m"] in (20, 30)
        assert fl1["google_maps_url"].startswith("https://www.google.com/maps?q=")
        assert fl1["tia598_splice_plan"]["standard"] == "ANSI/TIA-598-D"
        assert "OSP EMERGENCY SPLICE DISPATCH" in fl1["whatsapp_dispatch_text"]
        assert "protection_summary" in inc1["impact"]

        ov = client.get(f"{COPILOT_URL}/api/v1/overview").json()
        assert len(ov["dependency_graph"]["nodes"]) > 10
        assert len(ov["scenarios"]) == 7
        assert ov["background_noise"]["suppressed_total"] == 38
        trunk_cables = [c for c in ov["gis"]["cables"] if c["role"] == "trunk"]
        access_cables = [c for c in ov["gis"]["cables"] if c["role"] == "access"]
        assert any(c.get("rfts_monitored") is True for c in trunk_cables)
        assert all(c.get("rfts_monitored") is False for c in access_cables)


def test_kml_osp_import_and_csv_alarm_correlation():
    sample_kml = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Junction Pit 1</name>
      <Point><coordinates>55.2610,25.1810,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Field Spur 96F</name>
      <LineString>
        <coordinates>
          55.2520,25.1740,0
          55.2610,25.1810,0
          55.2740,25.1915,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    sample_csv = (
        "alarm_id,source_oem,layer,resource_id,node_id,severity,specific_problem,optical_distance_m,raw_text\n"
        "CSV-TEST-1,viavi_onmsi,fibre_osp,CBL-QZ-BB-01,QZ,CRITICAL,OTDR_REFLECTIVE_FIBER_BREAK,5400,\"[CSV] Break on CBL-QZ-BB-01\"\n"
        "CSV-TEST-2,ciena_mcp,dwdm_optical,OMS-QZ-BB,QZ,CRITICAL,OTS_LOS_LINE_FAIL,,\"[CSV] OTS-LOS QZ->BB\"\n"
    ).encode("utf-8")

    with httpx.Client(timeout=15.0) as client:
        r_kml = client.post(
            f"{COPILOT_URL}/api/v1/import/kml",
            files={"file": ("field_spur.kml", sample_kml, "application/vnd.google-earth.kml+xml")},
        )
        assert r_kml.status_code == 200, r_kml.text
        kdata = r_kml.json()
        assert kdata["imported_cable_count"] == 1
        cid = kdata["primary_cable_id"]
        assert cid.startswith("KML-")

        # Verify emulator synthesized a real binary SR-4731 .sor trace for the imported KML route
        r_otdr = client.get(f"{COPILOT_URL}/api/v1/otdr/cable/{cid}")
        assert r_otdr.status_code == 200
        assert r_otdr.json()["crc_valid"] is True

        # Verify vendor CSV alarm import correlates into a root-cause incident
        client.post(f"{COPILOT_URL}/api/v1/faults/reset")
        r_csv = client.post(
            f"{COPILOT_URL}/api/v1/import/alarms-csv",
            files={"file": ("ems_alarms.csv", sample_csv, "text/csv")},
        )
        assert r_csv.status_code == 200, r_csv.text
        cdata = r_csv.json()
        assert cdata["alarms_imported"] == 2
        assert cdata["incident"]["root_cause_type"] == "PHYSICAL_FIBRE_CUT"

        # Restore clean UAE baseline so subsequent runs start fresh
        client.post(f"{COPILOT_URL}/api/v1/region/switch", json={"region_id": "uae_dubai"})
