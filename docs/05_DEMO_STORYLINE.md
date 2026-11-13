# Live Demo Flow & Presenter Guide (12–15 Minute Walkthrough)

> **Print / Shareable PDF Version:** `docs/Live_Demo_Flow_And_Presenter_Guide.pdf`

This guide walks through every scenario and screen you can showcase live across the **Fibre Assurance Console** (`http://127.0.0.1:5173`), the **Multi-OEM Lab Emulator** (`http://127.0.0.1:8001`), and the **Backend OpenAPI Explorer** (`http://127.0.0.1:8002/docs`), with plain-English explanations of what is happening under the hood and verbatim talking points.

---

## Pre-Demo Setup (30 Seconds Before Sharing Screen)

1. Start the local stack (`./start.sh`) and open **`http://127.0.0.1:5173`**.
2. Click **`Reset`** in the top bar so network status reads **Healthy**. *(Optional: click the top-right slider icon to enter a Claude or OpenAI API key if you want live LLM narrative generation instead of the built-in offline synthesizer.)*
3. *(Optional for CTO / Architect calls)* Keep **`http://127.0.0.1:8001`** open in Browser Tab 2 to inspect live ServiceNow, Jira, OGC WFS GeoJSON, and binary `.sor` payloads.

---

## Tailoring the Flow by Operator Profile (Top-Right Selector)

| Audience Archetype | Profile Selector | Lead Scenarios to Emphasise |
| :--- | :--- | :--- |
| **Metro Fibre & DCI** *(e.g., Constl)* | `Pure-Play Metro Fibre, Wavelength & DCI` | Act 1 (Shared-duct audit) -> Act 2 (Canal trunk cut + 100G reroute) -> DIFC Bank shared chamber -> Act 4B (Pre-failure BER). |
| **National Converged** *(e.g., e&, du, Vi)* | `Converged 4G/5G + Fibre + Enterprise` | Act 2 (13-alarm storm across optical/IP/5G) -> Act 4A (Al Quoz power blackout) -> Act 4C (5G battery drain & 80 GHz rain fade). |
| **Subsea & Wholesale** *(e.g., PCCW Global)* | `Global Subsea, Optical DCI & Wholesale` | Act 1 (Diverse DCI route proof) -> Act 4C (Jebel Ali CLS subsea repeater shunt) -> Act 2 (100G protection switch). |

---

## Act 1 — Proactive Route Diversity & Blast-Radius Audit (2 mins)

1. **Click to Open:** On a healthy network, click **`2 shared-duct risks ->`** on the top status bar (or **`Route Diversity`** in the top nav).
2. **What Happens Under the Hood:** Even before an alarm fires, the graph engine cross-checks BSS customer circuits marked *"Ordered Diverse"* against PostGIS underground street ducts, bridges, and manhole chambers. It flags two Platinum accounts (**Emirates Gulf Bank** and **Jebel Ali Logistics Cloud**) whose primary and backup legs quietly share chamber `J_DG` or the **Dubai Water Canal Bridge**.
3. **Interactive Dependency Trace:** Hover over any node in the **Duct-to-Customer Dependency Map** to highlight the 5-layer impact chain: `OSP Conduit -> Fibre Trunk -> 100G Optical Channel -> 5G Tower -> Enterprise SLA`.
4. **What to Say:** *"Enterprise and hyperscale customers pay a premium for dual-homed protection, yet logical circuit inventories rarely verify street-level civil ducts. Before any outage happens, we expose hidden single points of failure—and let pre-sales verify truly diverse DCI/RFP paths in seconds instead of days."*

---

## Act 2 — Street-Accurate Fibre-Cut Pinpointing & Gated Recovery (3.5 mins)

1. **Trigger Incident:** Click **`Operations`**, select **`Metro Trunk Fibre Cut + Hidden SRLG Backup Failure (Sheikh Zayed Rd Canal)`**, and click **`Simulate`**.
2. **Multi-Vendor Storm Collapse:** Point to **`13 alarms -> 1 root cause`** (`97%` confidence). Optical LOS (Ciena), router BFD drops (Cisco/Juniper), VIAVI OTDR, and 3 cascading 5G sites (`BB_HUB`, `BB_T1`, `BB_T2`) collapse onto trunk cable `CBL-QZ-BB-01`, surfacing **`AED 25,000/hr`** SLA exposure immediately.
3. **Raw Glass vs. Street Trench GPS (`239 m` Saved):** Contrast the amber pin (**`Raw OTDR (+239m off)`**) against the pulsing red pin (**`Fibre Cut · 10934.4 m`**).
   - *Under-the-hood physics:* Raw OTDR measures optical flight through glass (`11,173.4 m`), which includes `75 m` of repair slack coiled inside upstream manholes plus `1.015x` helical twist inside the cable jacket. Subtracting both pinpoints the exact dig spot between `MH-J_I2` and `MH-J_I1`.
4. **Human-Approved Execution:** Review the 3 staged actions on the right (**Jira** master ticket, **ServiceNow FSM** splice crew dispatch with exact GPS, and **Optical SDN Controller** 100G wavelength reroute `JBL -> QZ -> DSO -> BB -> DIFC`). Click **`Approve all`** to execute live while emphasising human NOC control.
5. **Inspect Binary `.sor` Trace & Vector RAG (1.5 mins):**
   - Click **`Open OTDR trace ->`** below the map to show the real `1625 nm` Telcordia SR-4731 `.sor` step-drop at `11,173.4 m`, the **Glass-to-Street Distance** breakdown, and expandable splice events.
   - Expand **`Runbook & engineering notes`** at the bottom right to show the `pgvector`-matched carrier SOP (`RB-OSP-001`) and past resolved ticket MTTR benchmarks.

---

## Act 3 — Proving Zero Hardcoding: Ad-Hoc Map Cut & `.sor` Round-Trip (1.5 mins)

1. Click **`Reset`** -> open the **`Map`** sub-tab -> **click any fibre cable directly on the street map**.
2. Drag the cut-position slider (`15%–88%`) to any random spot and click **`Simulate Cut`**. The emulator synthesises a brand-new binary `.sor` trace at that exact metre mark, PostGIS walks upstream manholes dynamically, and NetworkX computes a fresh surviving optical path.
3. On **`OTDR Trace`**, click **`.sor`** to download the raw binary trace to your laptop, then click **`Upload .sor`** to re-parse the raw bytes live.

---

## Act 4 — Stopping Wasted Truck Rolls, Pre-Outage BER & Subsea Watch (4 mins)

Up to 35% of emergency fibre callouts arrive on site to find the fibre intact—caused instead by customer power loss, tower battery drain, or heavy rain. Walk through these scenarios:

1. **4A. Building Power Blackout vs. Fibre Cut (`Premises Power Blackout ('Dying Gasp') ... Al Quoz`):**
   - *Explanation:* 24 ONTs/modems drop within 1 second. Correlating `ITU-T G.984` `dying-gasp` power-fail frames (`>=80%` cohort match) with a clean `1625 nm` OTDR continuity shot (`Fibre intact`) marks **`Field accuracy: Trip saved`**, suppressing the splice crew and logging a power advisory instead.
2. **4B. Proactive Pre-Failure Optical BER (`Pre-Failure DWDM Optical OSNR & Pre-FEC BER Degradation`):**
   - *Explanation:* Catches Pre-FEC BER crossing `1e-4` alongside a non-reflective `1.8 dB` splice pinch while Post-FEC errors are still `0` (`AED 0/hr` outage), staging a hitless wavelength switch before the circuit drops.
3. **4C. 5G Battery Countdown, 80 GHz Rain Fade & Subsea Shunts (`Sites & Subsea` tab):**
   - **`Test Battery Drain`** — Tracks DC voltage slope on `gNB-BB-01` toward the `43.2 V` cutoff (`36 min` reserve) and dispatches a mobile generator before 9 daisy-chained 5G cells go dark.
   - **`Test Rain Fade`** — Recognises `-38.2 dBm` RSL fade & `1024QAM -> QPSK` downshift on an `80 GHz` E-band hop during heavy rain so nobody rolls tower climbers to swap healthy radios.
   - **`Test Subsea Fault`** — Isolates a `+4120 V` PFE drop & C-OTDR repeater shunt (`14.2 km` offshore from Jebel Ali CLS) on **FALCON-X Gulf Subsea Express**, separating submarine faults from terrestrial fibre cuts.
4. **Bonus Banking Scenario (`Dual-Homed Bank HQ Outage via Shared Manhole Chamber — DIFC Gate`):**
   - Shows civil works breaching chamber `J_DG` and severing both primary and "diverse" backup L3VPN legs for **Emirates Gulf Bank**, visually reinforcing Act 1's shared-duct audit.

---

## Act 5 — Multi-OEM Integrations, 10k-Alarm Scale Test & Wire Proof (2 mins)

1. Click **`Integrations`** in the top nav to show all **12 standards-based vendor adapters** (`Ciena MCP`, `Nokia NSP`, `VIAVI ONMSi`, `EXFO Nova`, `Lepton GIS`, `Ericsson ENM`, `Cisco/Juniper`, `NetBox`, `Comviva BSS`, `NMSWorks`, `ServiceNow FSM`, `Jira SM`). Click **`Edit`** on any card to show zero-code cutover from `emulator` to a `live` carrier endpoint.
2. Click **`Run 10,000-Alarm Test`** at the bottom to benchmark real-time deduplication, flap suppression, and causal graph clustering in milliseconds.
3. *(Optional)* Switch to Tab 2 (**`http://127.0.0.1:8001`**) and open `/servicenow/api/now/table/wm_order` or `/jira/rest/api/3/issue` to verify the real JSON tickets created when you clicked **Approve all** in Act 2.

---

## Presenter Q&A Cheat Sheet

- **"Does AI guess the fault GPS or optical backup route?"** — Never. Coordinates, manhole slack subtraction, and Zero-SRLG backup paths are computed deterministically by binary `SR-4731 (.sor)` math, `PostGIS`, and `NetworkX`. AI handles signal anomaly detection, multi-step tool orchestration, `pgvector` SOP retrieval, RFP parsing, and cited EN/AR reporting.
- **"Can we run this air-gapped inside our own NOC?"** — Yes. Deploys in `Docker` or `Kubernetes (OpenShift)` on-prem with zero subscriber PII, supporting cloud APIs (`Claude Sonnet 4` / `GPT-4o`), self-hosted open-weight models (`Llama 3.3` / `Qwen 2.5` via `vLLM`), or a CPU-only fallback.
- **"Will it push changes to live gear automatically?"** — No. Day-1 deployment is strictly read-only; northbound reroutes and dispatches are staged as drafts behind explicit NOC engineer sign-off.
- **"What if our GIS manhole slack data isn't clean everywhere?"** — We start with a **4-week single-corridor pilot** on one priority metro ring or DCI route, calibrating chamber slack records incrementally as field splices are verified.
