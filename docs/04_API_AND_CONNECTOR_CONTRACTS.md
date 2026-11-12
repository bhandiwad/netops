# 04 — REST API, Binary `.sor` & 12-OEM Connector Contracts

> **Audience:** Backend, frontend, and integration engineers connecting NOC Copilot (`:8002`) to the UI (`:5173`), automated tests, or live operator OSS/BSS/ITSM/EMS endpoints.

---

## 1. NOC Copilot Backend REST API (`http://127.0.0.1:8002`)

| Method & Path | Request Body / Params | Response & Purpose |
| :--- | :--- | :--- |
| **`GET /api/v1/overview`** | — | Master dashboard state: `connectors`, `gis` (`ducts`, `manholes`, `cables`), `topology`, `dependency_graph`, `srlg_findings`, `incidents`, `alarms`, `runbooks`, `audit_log`, `wire_packets`, `scenarios`, `operator_profiles`, `external_tickets`, `llm_config`. |
| **`POST /api/v1/ingest/tmf642`** | `{ "alarms": [CanonicalAlarm, ...] }` | Graph-clusters multi-vendor alarms across 6 network layers into `1..N` independent `IncidentRecord`s. Returns `{ "status": "correlated", "incident_id": "...", "incident_ids": [...] }`. |
| **`POST /api/v1/faults/trigger`** | `{ "scenario_id"?: str, "fault_type"?: str, "target_id"?: str, "cut_ratio"?: float }` | Injects a fault on the Multi-OEM Emulator (`:8001`), ingests emitted alarms, runs correlation + `pgvector` RAG, and syncs connectors. |
| **`POST /api/v1/faults/reset`** | — | Clears active faults in Emulator + PostgreSQL (`alarms`, `incidents`), re-syncs healthy baseline, and logs `NETWORK_RESET`. |
| **`POST /api/v1/incidents/{id}/approve`** | `{ "approved_by": str, "action_ids"?: list[str] }` | Executes human-approved Northbound actions against Jira (`POST /rest/api/3/issue`), ServiceNow (`incident` / `wm_order`), and Ciena MCP (`reroute`). |
| **`POST /api/v1/incidents/{id}/regenerate-ai`** | — | Re-synthesizes the citation-locked AI Copilot executive brief & MOP using current `LLM_CONFIG` (`Anthropic` / `OpenAI` / deterministic). |
| **`GET /api/v1/otdr/cable/{cable_id}`** | Path param `cable_id` | Downloads live binary SR-4731 `.sor` trace via `OtdrTraceAdapter`, verifies CRC-16, parses key events/curve, and runs PostGIS localization. |
| **`POST /api/v1/otdr/parse-sor`** | `multipart/form-data` (`file`: `.sor`) | Parses any uploaded binary Telcordia SR-4731 `.sor` file and computes PostGIS dig coordinates if `cable_id` exists in GIS inventory. |
| **`POST /api/v1/connectors/sync`** | — | Triggers immediate inventory & telemetry sync across all enabled southbound connectors into normalized PostgreSQL/PostGIS tables. |
| **`PUT /api/v1/connectors/{id}`** | `{ "endpoint_url": str, "mode": "emulator"\|"live", "enabled": bool, "config_json": dict }` | Switches any individual OEM connector between local emulator (`:8001`) and a live customer lab/production endpoint + auth headers. |
| **`POST /api/v1/settings/llm`** | `{ "provider": "anthropic"\|"openai", "model": str, "api_key": str }` | Configures live LLM credentials in memory for citation-locked executive synthesis. |
| **`POST /api/v1/benchmark/storm`** | `{ "storm_size": int }` (`1000`–`50000`) | Runs deterministic multi-layer alarm storm deduplication benchmark and returns throughput (`alarms/sec`) and noise reduction `%`. |
| **`GET /api/v1/telemetry/3gpp-xml`** | — | Fetches live 3GPP TS 32.435 XML Performance Management (`measCollecFile`) counters from Ericsson ENM connector. |

---

## 2. Canonical TMF642 Alarm Schema (`POST /api/v1/ingest/tmf642`)

Defined in [`backend/app/schemas/models.py`](../backend/app/schemas/models.py):

```json
{
  "alarms": [
    {
      "alarm_id": "ALM-7F9A21C0",
      "scenario_id": "live_fault",
      "source_oem": "viavi_onmsi",
      "protocol": "RFTS-REST+SOR",
      "layer": "fibre_osp",
      "resource_id": "CBL-QZ-BB-01",
      "node_id": "QZ",
      "severity": "CRITICAL",
      "specific_problem": "OTDR_REFLECTIVE_FIBER_BREAK",
      "probable_cause": "Physical Fiber Cable Cut (High Fresnel Reflectance > -18 dB)",
      "raw_text": "[ONMSI-RTU-QZ] 1625nm OTDR trace detected reflective break at 7780.4 m.",
      "raised_at": "2026-11-12T04:00:00Z",
      "extra": {
        "cable_id": "CBL-QZ-BB-01",
        "optical_distance_m": 7780.4
      }
    }
  ]
}
```

---

## 3. Southbound & Northbound 12-OEM Connector Matrix

Managed by [`backend/app/adapters/registry.py`](../backend/app/adapters/registry.py) and persisted in the `connectors` table:

| Connector ID | OEM System | Category | Standard / Wire Format | Reference Emulator Endpoint (`:8001`) |
| :--- | :--- | :--- | :--- | :--- |
| **`lepton_gis`** | **Lepton SmartInventory** | OSP GIS | OGC WFS 2.0 GeoJSON (`CRS84`) | `GET /lepton-gis/wfs?typeName=osp:all` |
| **`viavi_onmsi`** | **VIAVI ONMSi RFTS** | Remote OTDR | REST + Binary SR-4731 `.sor` | `GET /viavi-onmsi/api/v1/rtus`<br>`GET /viavi-onmsi/api/v1/traces/{cable_id}.sor` |
| **`exfo_nova`** | **EXFO Nova Fiber** | Remote OTDR | REST + Binary SR-4731 `.sor` | `GET /exfo-nova/api/v1/traces/{cable_id}.sor` |
| **`ciena_mcp`** | **Ciena MCP 7.2** | DWDM SDN | REST + Hitless FRE Reroute | `GET /ciena-mcp/nsa/api/v1/fres`<br>`POST /ciena-mcp/nsa/api/v1/fres/{och_id}/reroute` |
| **`nokia_nsp`** | **Nokia NSP 24.8** | DWDM / IP | RESTCONF OpenConfig Optical + TMF642 | `GET /nokia-nsp/restconf/data/openconfig-optical` |
| **`nmsworks_cygnet`** | **NMSWorks CygNet v12.4** | Multi-Layer OSS | CygNet Inventory & SIA REST v2 | `GET /nmsworks-cygnet/api/v2/inventory/topology` |
| **`ericsson_enm`** | **Ericsson ENM** | 4G/5G RAN & Power | 3GPP TS 28.532 FM + **TS 32.435 XML PM** | `GET /ericsson-enm/api/v1/ran-sites`<br>`GET /ericsson-enm/api/v1/pm-counters.xml` |
| **`comviva_bss`** | **Comviva BlueMarble** | Enterprise BSS | TMF629 Customer + TMF638 SLA | `GET /comviva-bss/tmf-api/customerManagement/v4/customer` |
| **`netbox_dcim`** | **NetBox DCIM v4** | DCIM & Circuits | NetBox REST API v4 | `GET /netbox/api/dcim/sites/` |
| **`cisco_juniper_stream`** | **Cisco / Juniper / Huawei** | Core Wire Stream | UDP Syslog (`:15514`) + SNMPv2c (`:15162`) + Kafka (`:19092`) | Topic `noc.alarms.raw` + UDP listeners |
| **`jira_sm`** | **Jira Service Management** | Master ITSM | Jira Cloud/DC REST API v3 | `GET /jira/rest/api/3/issue`<br>`POST /jira/rest/api/3/issue` |
| **`servicenow_itsm`** | **ServiceNow ITSM & FSM** | Incident & Crew Dispatch | ServiceNow Table API (`incident`, `wm_order`, `change_request`) | `GET /servicenow/api/now/table/{table}`<br>`POST /servicenow/api/now/table/{table}` |

---

## 4. Mathematical & Binary Format Specifications

### 4.1 PostGIS Slack-Coil & Helical Stranding Formula ([`postgis_locator.py`](../backend/app/spatial/postgis_locator.py))
Given an OTDR event at optical distance $d_{\text{optical}}$ meters from launch POP along cable $C$:
1. Collect upstream splice chambers $m_1 \dots m_k$ along $C$ where $d_{\text{opt}}(m_i) \le d_{\text{optical}}$.
2. Subtract stored chamber slack coils:
   $$d_{\text{net}} = \max\left(0,\; d_{\text{optical}} - \sum_{i=1}^{k} \text{slack}(m_i)\right)$$
3. Compensate for loose-tube helical stranding factor $\eta_{\text{helix}}$ (typically $1.015$):
   $$d_{\text{trench}} = \frac{d_{\text{net}}}{\eta_{\text{helix}}},\qquad f = \min\left(1.0,\; \frac{d_{\text{trench}}}{L_{\text{trench}}}\right)$$
4. Interpolate WGS84 street trench coordinates in PostGIS:
   ```sql
   SELECT ST_Y(ST_LineInterpolatePoint(geom, :f)) AS lat,
          ST_X(ST_LineInterpolatePoint(geom, :f)) AS lon
   FROM osp_cables WHERE id = :cable_id;
   ```

### 4.2 Binary Telcordia SR-4731 Rev 2 (`.sor`) Block Structure ([`shared/sor_codec.py`](../shared/sor_codec.py))
Little-endian binary layout verified with **CRC-16-CCITT** (`poly=0x1021`, `init=0xFFFF`):
- **`Map`** — Revision `200` (`Rev 2.00`), block directory `(block_name\0, rev_u16, size_i32)`.
- **`GenParams`** — Language (`EN`), cable ID, fiber number, nominal wavelength (`1625 nm`), launch/receive POPs.
- **`SupParams`** — Supplier (`VIAVI Solutions` / `EXFO Inc.`), OTDR mainframe model, module serial number.
- **`FxdParams`** — Timestamp (`uint32`), distance unit (`mt`), group refractive index (`146800` = $1.46800$), pulse width (`ns`), sample spacing, range.
- **`KeyEvents`** — Event index, propagation time, fiber attenuation (`dB/km`), splice loss (`0.001 dB`), Fresnel reflectance (`0.001 dB`), event code (`0F9999LS` splice / `1E9999LS` break), chamber note.
- **`DataPts`** — `1,000` `uint16` samples encoding Rayleigh backscatter curve (`1000 * dB`).
- **`Cksum`** — Trailing `uint16` CRC-16 checksum over all preceding bytes.
