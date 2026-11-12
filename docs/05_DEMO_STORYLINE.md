# Live Client Demo Storyline (10–12 Minute Walkthrough)

This guide walks through everything you can showcase live right now across the UI (`http://127.0.0.1:5173`) and the Multi-OEM Lab Emulator (`http://127.0.0.1:8001`).

---

## Before You Share Your Screen (10 Seconds)
1. Open **`http://127.0.0.1:5173`** (click **Reset** in the top bar if a previous scenario is active so Status reads **Healthy**).
2. *(Optional for CTO / Architect calls)* Keep **`http://127.0.0.1:8001`** open in a second browser tab to show live vendor protocol payloads and binary `.sor` files.

---

## Act 1 — Setting the Stage & Proactive Route Diversity (2 mins)

1. **Operator Profile Switcher (Top Right):**
   - Point out the profile selector (`Converged 4G/5G + Fibre + Enterprise`, `Constl`, `Vi`, `PCCW`). Pick the one closest to your audience.
2. **Proactive Shared-Duct Risk (`2 shared-duct risks →`):**
   - Before any outage even happens, point to **`2 shared-duct risks →`** on the top status bar (or click **`Route Diversity`** in the top nav).
   - **What to say:** *"Enterprise customers buy 'dual-homed' or '1+1 protected' circuits assuming two separate paths. Before any cut happens, we cross-check BSS customer circuits against actual street ducts and manholes—and flag two accounts whose primary and backup routes secretly share the same bridge or chamber."*
   - Scroll down slightly on **Route Diversity** to hover over nodes in the **Duct-to-Customer Dependency Map**, showing how physical ducts tie directly to optical channels, 5G sites, and customer SLAs.

---

## Act 2 — Street-Accurate Fibre Cut Isolation & Human-Gated Recovery (3 mins)

1. Click **`Operations`** in the top nav.
2. Under **Quick Demo Scenarios** on the right (or via the top dropdown), click **`Metro Trunk Fibre Cut + Hidden SRLG Backup Failure (Sheikh Zayed Rd Canal)`**.
3. **Walk through what happens in 2 seconds:**
   - **Alarm Storm Compression (Top Bar):** `13 alarms → 1 root cause` across Ciena optical, Cisco/Juniper routers, VIAVI OTDR, and 3 cascading 5G sites (`BB_HUB`, `BB_T1`, `BB_T2`).
   - **Glass vs. Street GPS Pinpointing (Map):**
     - Point to the amber pin (**`Raw OTDR (+239m off)`**) vs. the pulsing red pin (**`Fibre Cut · 10934.4 m`**).
     - Point to the summary strip below the map: raw OTDR measured `11,173.4 m` of glass, which includes `75 m` of coiled slack inside upstream manholes plus cable twist. Subtracting those avoids sending a splice van **239 meters away** from the real break.
   - **Inspect Binary `.sor` Trace:** Click **`Open OTDR trace →`** below the map to show the 1625 nm reflectogram spike, glass-to-street math, `.sor` file download/upload, and expandable splice events table.
   - **Commercial Impact & 1-Click Recovery (Right Panel):**
     - Point out **Affected Customers** (`AED 25,000/hr` SLA exposure + shared-bridge warning).
     - Under **Recommended Actions**, point out the three staged actions: **Jira** master ticket, **ServiceNow** field crew dispatch with exact GPS coordinates, and **Optical SDN Controller** 100G wavelength reroute over a surviving ring.
     - Click **`Approve all`** — each row updates with live ticket/execution IDs (`✓`). *(Highlight: nothing touches the network without human NOC sign-off.)*
   - *(Optional)* Expand **`Runbook & engineering notes`** at the bottom of the right panel to show the matched operational procedure and past repair history.

---

## Act 3 — Interactive Ad-Hoc Cut & Binary `.sor` Round-Trip (1.5 mins)

1. Click **`Reset`** in the top bar, then switch back to the **`Map`** tab.
2. **Click any fibre cable directly on the map** — a bottom bar appears with a cut-position slider (`15%`–`88%`).
3. Drag the slider to any point and click **`Simulate Cut`** to prove nothing is pre-scripted: the engine generates a fresh binary `.sor` trace at that exact spot, computes manhole slack dynamically, and calculates a new backup path.
4. *(Optional)* On **`OTDR Trace`**, click **`.sor`** to download the binary trace file to your laptop, then click **`Upload .sor`** to re-parse the raw bytes live.

---

## Act 4 — Stopping Wasted Truck Rolls: Power, Battery & Weather (2.5 mins)

Show how the platform prevents expensive false dispatches when the fibre isn't actually broken:

1. **Building Power Blackout vs. Fibre Cut:**
   - Select **`Premises Power Blackout ('Dying Gasp') vs. Fibre Cut Disambiguation (Al Quoz)`** → click **`Simulate`**.
   - **What to highlight:** 24 modems drop at once, which normally triggers a fibre crew dispatch. Here, the platform pairs power-loss (`Dying Gasp`) signals with a live clean OTDR continuity shot (`Fibre intact`) — Top bar shows **`Field accuracy: Trip saved`**, and the action dispatches power/facilities instead of a splice van.
2. **Proactive Optical Degradation (Before Outage):**
   - Select **`Pre-Failure DWDM Optical OSNR & Pre-FEC BER Degradation`** → click **`Simulate`**.
   - **What to highlight:** Catches a pinched high-loss splice degrading optical signal quality *before* the circuit goes down (`AED 0/hr` outage because we shift the wavelength proactively).
3. **5G Tower Battery Drain, Rain Fade & Subsea Shunts (`Sites & Subsea` tab):**
   - Click **`Sites & Subsea`** in the top nav:
     - Click **`Test Battery Drain`** — shows a 5G hub site on backup battery (`36 min` left before 9 cells go dark) so a generator is sent in time.
     - Click **`Test Rain Fade`** — isolates an `80 GHz` microwave dip during heavy rain so nobody rolls a truck to swap healthy tower radios.
     - Click **`Test Subsea Fault`** — detects a submarine cable insulation shunt (`14.2 km` offshore, `68 m` depth) at the landing station, separating wet-plant faults from land fibre cuts.

---

## Act 5 — Scale, Integrations & Under-the-Hood Proof (1.5 mins)

1. Click **`Integrations`** in the top nav:
   - Show the **12 Connected Network & IT Systems** (Ciena, Nokia, VIAVI, Lepton GIS, Ericsson, ServiceNow, Jira, NetBox, Comviva) — click **`Edit`** on any card to show how each flips from `Local Emulator` to a `Live Network Endpoint`.
   - Click **`Run 10,000-Alarm Test`** under **Alarm Storm Stress Test** to benchmark real-time flap suppression and root-cause grouping in milliseconds.
2. *(Optional for Technical Audiences)* Switch to **`http://127.0.0.1:8001`**:
   - Show the live **Multi-OEM Lab Emulator**, click **`/servicenow/api/now/table/wm_order`** or **`/jira/rest/api/3/issue`** to show the real JSON tickets created when you clicked **Approve all** in Act 2, or open **`/docs`** to show full OpenAPI specs.
