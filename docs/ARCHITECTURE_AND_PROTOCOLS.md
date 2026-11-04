# Architecture, OEM Protocols & Telco Data Requirements Reference

This document details the Southbound & Northbound protocols, device telemetry requirements across operator archetypes, and deterministic mathematical algorithms implemented in the **Pandita AI Telco NOC Copilot**.

---

## 1. Southbound & Northbound 12-OEM Connector Matrix

| Connector ID | OEM System | Domain Category | Protocol / Standard | Emulator Endpoint (`:8001`) |
| :--- | :--- | :--- | :--- | :--- |
| **`ciena_mcp`** | **Ciena MCP 7.2** (Ciena 6500 ROADM / WaveLogic 5e) | DWDM Optical Control | REST / OpenConfig gNMI / TMF642 + Hitless Reroute | `GET /ciena-mcp/nsa/api/v1/fres`<br>`GET /ciena-mcp/nsa/api/v1/alarms`<br>`POST /ciena-mcp/nsa/api/v1/fres/{och_id}/reroute` |
| **`nokia_nsp`** | **Nokia NSP 24.8 / WaveSuite** (1830 PSS-32 & 7750 SR) | DWDM & IP/MPLS Control | RESTCONF / OpenConfig Optical / TMF642 | `GET /nokia-nsp/restconf/data/openconfig-optical`<br>`GET /nokia-nsp/tmf-api/alarmManagement/v4/alarm` |
| **`nmsworks_cygnet`** | **NMSWorks CygNet v12.4** | Unified Multi-Layer OSS & SIA | CygNet REST v2 / TMF639 Inventory / TMF642 | `GET /nmsworks-cygnet/api/v2/inventory/topology`<br>`GET /nmsworks-cygnet/api/v2/alarms` |
| **`lepton_gis`** | **Lepton SmartInventory / NetworkAccess** | Outside-Plant (OSP) GIS | OGC WFS 2.0 GeoJSON (`urn:ogc:def:crs:OGC:1.3:CRS84`) | `GET /lepton-gis/wfs?typeName=osp:all` (`osp:ducts`, `osp:cables`, `osp:manholes`) |
| **`viavi_onmsi`** | **VIAVI ONMSi RFTS** (OTU-8000 1625nm) | Remote Fibre Test / OTDR | REST + Binary Telcordia SR-4731 Rev 2 (`.sor`) | `GET /viavi-onmsi/api/v1/rtus`<br>`GET /viavi-onmsi/api/v1/traces/{cable_id}.sor` |
| **`exfo_nova`** | **EXFO Nova Fiber** (FG-750 1625nm) | Remote Fibre Test / OTDR | REST + Binary Telcordia SR-4731 Rev 2 (`.sor`) | `GET /exfo-nova/api/v1/traces/{cable_id}.sor` |
| **`ericsson_enm`** | **Ericsson Network Manager (ENM)** | 4G/5G RAN & Enclosure Power | 3GPP TS 28.532 FM + **3GPP TS 32.435 XML PM** | `GET /ericsson-enm/api/v1/ran-sites`<br>`GET /ericsson-enm/api/v1/pm-counters.xml` |
| **`comviva_bss`** | **Comviva BlueMarble / Ngage BSS** | Customer & SLA Inventory | TMF629 Customer + TMF638 Service Inventory REST | `GET /comviva-bss/tmf-api/customerManagement/v4/customer` |
| **`netbox_dcim`** | **NetBox DCIM & Circuits** | DCIM / IPAM / Circuits | NetBox REST API v4 | `GET /netbox/api/dcim/sites/`<br>`GET /netbox/api/circuits/circuits/` |
| **`cisco_juniper_stream`** | **Cisco IOS-XR / Juniper Junos / Huawei VRP** | IP/MPLS Core Streaming | UDP RFC 5424 Syslog (`:15514`) + UDP SNMPv2c Trap (`:15162`) + Redpanda Kafka (`:19092`) | Live UDP listeners + Kafka topic `noc.alarms.raw` |
| **`jira_sm`** | **Jira Service Management** | ITSM Master Incident Queue | Atlassian Jira REST API v3 | `GET /jira/rest/api/3/issue`<br>`POST /jira/rest/api/3/issue` |
| **`servicenow_itsm`** | **ServiceNow ITSM & Field Service (FSM)** | Incident, Change & Field Dispatch | ServiceNow Table API (`incident`, `wm_order`, `change_request`) | `GET /servicenow/api/now/table/{table}`<br>`POST /servicenow/api/now/table/{table}` |

---

## 2. Endpoint Device & EMS Telemetry Required per Operator Type

### A. Pure-Play Metro Fibre, Wavelength & DCI Operator (*Constl Archetype*)
- **OSP GIS Inventory (Lepton / GE Smallworld / PostGIS):**
  - Duct segment `LineString` geometry, bridge/culvert crossings, manhole chamber coordinates, **stored slack-loop length (`slack_coil_m`)** per chamber, and cable **helical stranding factor (`1.012`–`1.035`)**.
- **RFTS / OTDR Monitoring (VIAVI ONMSi / EXFO Nova):**
  - Out-of-band 1625nm / 1650nm binary **Telcordia SR-4731 `.sor`** traces on dark/monitoring fibres, group refractive index (`IOR`), pulse width (`ns`), and key splice/break event tables.
- **DWDM Optical Control (Ciena MCP / Nokia NSP / Infinera):**
  - OMS span loss, EDFA/Raman amplifier input/output power (`dBm`), OCh wavelength routing (`path`), Pre-FEC BER, Post-FEC uncorrectable codewords, and OSNR (`dB`).
- **Enterprise BSS / Circuit Inventory (Comviva / NetBox / NMSWorks):**
  - Circuit-to-wavelength/cable mapping, `ordered_diverse` SLA flag, MTTR target window (`4.0h` Platinum), and hourly liquidated damages rate.

### B. Converged 4G/5G Mobile + Fixed + Enterprise Operator (*du / e& Archetype*)
Requires everything in **A**, plus:
- **4G/5G RAN EMS (Ericsson ENM / Nokia MantaRay / Huawei U2020):**
  - Cell-site backhaul anchor topology (which hub `gNodeB` aggregates which downstream daisy-chained tail `gNodeB`s over CSR IP/MPLS rings).
  - **3GPP TS 32.435 XML PM Counters:** `RRU.PrbTotDl`, `RRU.PrbTotUl`, `RRC.ConnEstabSuccRate`, `DRB.ErabDropRate`.
- **GPON / FTTH Access (OLT EMS / GenieACS TR-069):**
  - Splitter-to-feeder-cable binding and **ITU-T G.984 PLOAM `dying-gasp`** vs. optical `LOSi` bit correlation to distinguish commercial AC power blackouts from physical fibre cuts.

### C. High-Scale Mobile, Metro Fibre & Microwave Operator (*Vodafone Idea / Vi Archetype*)
Requires everything in **B**, plus:
- **Site Power & Enclosure Telemetry (SNMP / Modbus / ENM):**
  - Commercial 3-phase AC mains status, DC rectifier bus voltage (`Vdc`), VRLA/Li-ion battery discharge slope, **Low-Voltage Disconnect (`LVD`) threshold (`43.2V`)**, and enclosure thermal sensors (`°C`).
- **E-Band / 18 GHz Microwave Transport (Nokia Wavence / Ericsson MINI-LINK):**
  - Received Signal Level (`RSL dBm`), SNR (`dB`), local TX output power, **Adaptive Coding & Modulation (`ACM`) state** (`1024QAM` down to `QPSK`), and DiffServ EF/BE queue drop counters to separate atmospheric rain fade from ODU hardware failure.

### D. Global Subsea & Wholesale DCI Carrier (*PCCW Global / HKT Archetype*)
Requires everything in **A**, plus:
- **Cable Landing Station (CLS) Power Feed Equipment (`PFE`):**
  - High-voltage constant-current line voltage (`+4,120V`), line current (`950mA`), and earth-return leakage current (`mA`) to detect wet-plant insulation shunt faults.
- **Coherent OTDR (`C-OTDR`) & Repeater Supervision:**
  - Repeater-by-repeater optical pump current, gain tilt, branching unit (`BU`) status, and C-OTDR distance-to-shunt (`km` seaward of repeater `R_n`) with bathymetric water depth (`m`).

---

## 3. Mathematical & Physics Formulas

### 3.1 Optical-to-Trench Street Localization (`locate_fault_on_cable_postgis`)
Given an OTDR reflective break at optical distance $d_{\text{optical}}$ (meters from launch POP) along cable $C$:
1. Identify all splice chambers $m_1, m_2, \dots, m_k$ along cable $C$ whose cumulative optical distance $d_{\text{opt}}(m_i) \le d_{\text{optical}}$.
2. Subtract cumulative manhole slack reserves:
   $$d_{\text{net\_fiber}} = \max\left(0,\; d_{\text{optical}} - \sum_{i=1}^{k} \text{slack}(m_i)\right)$$
3. Divide by the cable helical stranding factor $\eta_{\text{helix}}$ (typically $1.015$ for loose-tube armored trunk cables):
   $$d_{\text{trench}} = \frac{d_{\text{net\_fiber}}}{\eta_{\text{helix}}}$$
4. Compute normalized trench fraction $f = \min(1.0, d_{\text{trench}} / L_{\text{trench}})$ and evaluate PostGIS geometry interpolation:
   ```sql
   SELECT
     ST_Y(ST_LineInterpolatePoint(geom, f)) AS lat,
     ST_X(ST_LineInterpolatePoint(geom, f)) AS lon
   FROM osp_cables
   WHERE id = :cable_id;
   ```

### 3.2 Binary Telcordia SR-4731 Rev 2 (`.sor`) Layout (`shared/sor_codec.py`)
Every `.sor` file generated or parsed by the platform follows the little-endian binary block layout:
- **`Map` Block:** Format revision (`200` = Rev 2.00), block count, and `(block_id, revision, byte_size)` directory headers.
- **`GenParams` Block:** Language (`EN`), cable ID, fiber number, nominal wavelength (`1625 nm`), launch/receive POP codes.
- **`SupParams` Block:** OTDR vendor (`VIAVI Solutions` / `EXFO Inc.`), mainframe model (`ONMSi OTU-8000` / `Nova Fiber FG-750`), optical module serial number.
- **`FxdParams` Block:** UTC timestamp, units (`mt`), group refractive index (`146800` = $1.46800$), pulse width (`100 ns`), sample spacing, total acquisition range.
- **`KeyEvents` Block:** Event number, propagation time, attenuation coefficient (`dB/km`), splice loss (`0.001 dB` units), Fresnel reflectance (`0.001 dB` units), event code (`0F9999LS` non-reflective splice / `1E9999LS` reflective fiber break), and chamber annotation.
- **`DataPts` Block:** 1,000 unsigned 16-bit integers (`uint16`) encoding the Rayleigh backscatter logarithmic power profile (`1000 * dB`).
- **`Cksum` Block:** Standard **CRC-16-CCITT** (`poly=0x1021`, `init=0xFFFF`) computed over all preceding bytes.
