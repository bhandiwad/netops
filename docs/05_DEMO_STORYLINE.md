# Plain-Language Live Demo Guide (UAE & India NCR)

> **Print / Shareable PDF Version:** `docs/Live_Demo_Flow_And_Presenter_Guide.pdf`

This guide explains the **Pandita — Fibre Assurance** demo in plain, everyday language—without telecom jargon—so anyone can understand the business problem, what is happening on screen, and how to present it smoothly across both **India — Delhi NCR (`INR`)** and **UAE — Dubai Metro (`AED`)**.

---

## 1. What Problem Does This Solve? (The 30-Second Elevator Pitch)

Telecom operators run thousands of kilometres of underground fibre cables carrying **5G mobile towers**, **bank networks**, and **cloud data centres**. Today, when something breaks, operations teams face four expensive daily headaches:

1. **Alarm Floods:** One excavator cutting a single underground cable triggers **dozens or hundreds of separate red alarms** across optical gear, routers, and 5G towers—each on a different vendor's screen. Engineers lose 20–45 minutes just figuring out it is all one physical cut.
2. **Digging in the Wrong Spot (`150 m – 300 m` Off):** A laser test (`OTDR`) tells you how far light travelled *inside the glass fibre* (say, `11,175 m`), **not** how far to walk along the street. Why? Because underground manholes hold `15 m – 30 m` coils of spare cable slack, and fibres spiral inside the cable jacket. Sending a crew to the raw laser number makes them dig up the wrong stretch of road.
3. **Wasted Repair Van Trips ("False Cuts"):** Roughly **1 in 3 emergency fibre callouts** isn't a cut cable at all—a building lost electricity, a cell-tower battery ran flat, or heavy monsoon rain weakened a wireless link. Sending a fibre-splicing truck wastes hours and thousands of dollars.
4. **Hidden "Fake Backup" Routes:** Banks and cloud companies pay top tier for a **Primary + Backup** line. On paper they look separate, but underground both cables quietly pass through the **same bridge or manhole chamber**—meaning a single digger knocks out both lines at once.

**What Pandita Does:** Connects read-only to existing network, map (`GIS`), laser-test (`OTDR`), and customer (`SLA`) systems to **collapse alarm storms into 1 root cause**, **pinpoint the real street dig zone (`±20 m`) with a WhatsApp crew pack & Google Maps pin**, **block wasted truck rolls**, and **expose hidden shared-duct risks before an outage happens**.

---

## 2. Screen Layout & Region / Customer Switcher (Top Bar)

Open **`http://127.0.0.1:5173`**. Everything lives in one clean workspace:

- **Top-Right Region Selector (`Globe` icon):** Switch live between:
  - **`India · Delhi NCR (INR)`** — Connaught Place, Nehru Place, Gurgaon Cyber City, Aerocity, Noida, Greater Noida, and Yamuna bridges (**DND Flyway** & **ITO Barrage**), with two customer profiles:
    1. *Metro Fibre & DCI (India)* — Wholesale dark fibre, hyperscale AI data-centre interconnects, and BFSI leased lines (`INR 450,000/hr` Platinum SLA).
    2. *Converged 4G/5G & Fibre (India)* — 5G towers, metro fibre, home/enterprise broadband, and `80 GHz` wireless hops.
  - **`UAE · Dubai (AED)`** — Sheikh Zayed Rd, Business Bay, DIFC, Al Quoz, Silicon Oasis, and Jebel Ali Subsea Landing Station, with *Converged 4G/5G + Fibre* and *Subsea & DCI Wholesale* profiles.
- **Top Operational Posture Strip:**
  - Shows **`0 P1/P2 Incidents · 38 minor/CRQ suppressed`** when healthy—reflecting real NOC life where planned maintenance windows (`CHG`) and harmless dirty-connector warnings are muted automatically (click the pill to inspect all 38 muted background events).
  - **`Import KML / .sor / CSV`:** Upload a real **Google Earth `.kml` fibre route**, a **handheld `.sor` laser trace**, or an **alarm `.csv` export** live during a prospect call (includes 1-click sample `.kml` and `.csv` loaders).
  - **`Lab Replay`:** Pick any real-world fault scenario and click **`Replay`** (or **`Reset`** to return to healthy).

---

## 3. Step-by-Step Plain-Language Demo Flow (8–10 Minutes)

### Step 1 — Expose Hidden "Fake Backup" Routes Before Any Outage (`Route Diversity`)
1. Click **`shared-duct risks ->`** in the top bar (or **`Route Diversity`** in the top navigation).
2. **In plain English:** Point out the bank and cloud circuits marked *"Ordered Diverse"*. Although sold as independent primary and backup lines, the map audit proves both cables share the **same underground chamber or river bridge** (e.g., **Connaught Place Janpath Chamber / DND Flyway** in India, or **DIFC Gate / Water Canal Bridge** in UAE).
3. **Why buyers care:** Lets operators fix single points of failure *before* a VIP bank goes dark, and lets pre-sales engineers verify truly separate routes for new customer bids in seconds.

### Step 2 — One Backhoe Cut, Multi-Vendor Storm, Exact Dig Zone (`Operations`)
1. Switch back to **`Operations`**, pick the first scenario (*Metro Trunk Fibre Cut...*), and click **`Replay`**.
2. **Watch the Arrival Cascade:** Notice the banner showing how alarms arrive in real life: `t+0ms` physical laser loss -> `t+180ms` core router drop -> `t+1.2s` cascading 5G cell sites & enterprise SLAs—all collapsed automatically into **1 root cause**.
3. **Compare the Two Pins on the Map:**
   - **Amber Pin (`Raw OTDR ~210m off`):** Where a crew would dig if they trusted the raw laser distance—missing the break by two city blocks because of coiled spare cable inside upstream manholes.
   - **Red Pulsing Pin (`Dig Zone · ±20 m`):** The true street excavation corridor after subtracting manhole slack coils and cable twist, anchored to the nearest upstream manhole landmark.
4. **Show the Field Splicer & WhatsApp Dispatch Pack (Right Panel):**
   - Point to the **Hardware Protection Banner** explaining whether `<50 ms` automatic backup held or failed due to a shared bridge/duct.
   - Click **`Copy WhatsApp Dispatch`** (formats the exact manhole landmark, `±20 m` dig instruction, priority fibre tube colour, and Google Maps GPS link ready to paste into the field contractor's WhatsApp group) and **`Google Maps Pin`**.
   - Expand **`ANSI/TIA-598-D Tube & Core Plan`** (`Tube 1 Blue -> Tube 12 Aqua`) showing which colour-coded fibre tube to splice first and the realistic repair ETR (`~4.0h`).
5. **Human-in-the-Loop Sign-Off:** Click **`Approve all`** under **Engineering & ITSM Work Orders** to log the **Jira** master incident, create the **ServiceNow** field dispatch ticket, and execute the pre-validated **Transport Ring Restoration Work Order**.

### Step 3 — Stop Wasted Truck Rolls ("Power Cut, Not Fibre Cut")
1. Select the **Premises Power Blackout ('Dying Gasp')** scenario in **`Lab Replay`** and click **`Replay`**.
2. **In plain English:** 24–28 customer modems in an industrial estate went offline at the exact same second—which normally looks just like a severed street cable.
3. Pandita checks two facts automatically: *(a)* the modems sent a tiny "last-breath" power-loss signal (`dying gasp`) right as electricity died, and *(b)* an automatic laser test down the fibre proves the glass is **100% unbroken**.
4. Result: **`Dig zone: Trip saved`**—no splicing van is dispatched at 2 AM, and an automated power-outage notice is logged instead.

### Step 4 — Catching Problems *Before* Outage + 5G Tower & Subsea Watch
1. **Pinched Fibre Warning (*Pre-Failure DWDM...*):** Shows a fibre being crushed or bent inside a manhole. Customer traffic is still up (`0/hr` penalty), and Pandita stages a preventative traffic shift before the signal drops off a cliff.
2. **5G Batteries, Monsoon Rain & Subsea Cables (`Sites & Subsea` tab):**
   - **Battery Drain:** Tracks a 5G hub site running on backup batteries after a grid cut (`36 mins` left) so a mobile generator arrives before 9 downstream 5G sectors go dark.
   - **Monsoon / Heavy Rain Wireless Fade:** Recognises heavy rain weakening an `80 GHz` wireless link so engineers don't climb towers to replace healthy radios.
   - **Subsea Cable Fault:** Separates an undersea power-insulation leak (`km` offshore from Mumbai/chennai or Jebel Ali landing station) from land-side fibre cuts.

### Step 5 — Prove Nothing Is Fake: Cut Any Cable & Import Your Own `.kml` / `.csv`
1. Click **`Reset`**, click **any fibre cable directly on the map** (notice core trunks say **`1625 nm Auto-RFTS`** while last-mile drops say **`Access Span · Handheld .sor`**), slide the fault position anywhere (`15%–88%`), and click **`Replay Cut`**. Everything recalculates live.
2. Click **`Import KML / .sor / CSV`** in the top bar and click **`Sample .kml`** (or drop any Google Earth `.kml` file) to watch a brand-new fibre route appear live on the map with automatic manhole slack modelling and `.sor` trace support.
