# 03 — Developer Contribution Guide (Cookbook for Team Engineers)

> **Audience:** Software engineers picking up a Feature Epic (GitHub Issues `#1`–`#6`) or extending NOC Copilot capabilities.
> **Prerequisite:** Skim [`01_TELCO_PRIMER_FOR_ENGINEERS.md`](01_TELCO_PRIMER_FOR_ENGINEERS.md) (15 mins) if any telecom term looks unfamiliar.

---

## 1. Local Development Setup (5 Minutes)

```bash
# 1. Start PostgreSQL 16 (PostGIS + pgvector on :5433) and Redpanda Kafka (:19092)
docker compose up -d

# 2. Set up Python 3.11+ virtualenv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Install Frontend dependencies
(cd frontend && npm install)

# 4. Run Backend + Emulator + UI (either all-in-one via ./start.sh or in 3 terminals for hot reload):
# Terminal 1 — Multi-OEM Reference Emulator (:8001)
PYTHONPATH=$(pwd) .venv/bin/uvicorn emulators.emu.server:app --reload --reload-dir emulators --reload-dir shared --host 127.0.0.1 --port 8001

# Terminal 2 — NOC Copilot Modular Backend (:8002)
PYTHONPATH=$(pwd) .venv/bin/uvicorn backend.app.main:app --reload --reload-dir backend --reload-dir shared --host 127.0.0.1 --port 8002

# Terminal 3 — React + TypeScript + Vite Console (:5173)
cd frontend && npm run dev
```

### Mandatory Pre-PR Verification Commands
Before opening a Pull Request, run all three checks locally:
```bash
# 1. Enforce zero hardcoded topology/city/device IDs inside backend/app/
.venv/bin/python scripts/check_no_hardcoded_topology.py

# 2. Run end-to-end backend, PostGIS, graph-clustering & .sor binary tests
.venv/bin/pytest -v

# 3. Run strict TypeScript check (tsc --noEmit) + Vite production build
(cd frontend && npm run build)
```

---

## 2. Recipe A: Adding a New Root-Cause `HypothesisClassifier` Plugin

Suppose your Epic requires detecting a new physical or protocol condition (e.g., **Epic 1: Coherent `SOP rad/s` Pre-Cut JCB Excavation Warning**, **Epic 3: Marine AIS Anchor-Drag**, or **Epic 4: ServiceNow Change-Window Collision**).

You **do not** edit a giant `if/elif` tree! Instead, add a standalone strategy plugin in `backend/app/correlation/classifiers/`:

### Step 1 — Create `backend/app/correlation/classifiers/sop_precut_warning.py`
```python
from __future__ import annotations

from ...schemas.models import CausalCluster, ProposedAction, RootCauseHypothesis
from ...spatial.postgis_locator import locate_fault_on_cable_postgis
from .base import (
    CorrelationContext,
    HypothesisClassifier,
    normalize_problem_code,
    register_classifier,
)


@register_classifier
class SopPreCutWarningClassifier(HypothesisClassifier):
    classifier_id = "sop_precut_excavation"
    priority = 96  # Higher priority breaks ties when confidence scores match

    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        # 1. Inspect alarms in this connected CausalCluster
        sop_alarms = [
            a for a in cluster.alarms
            if "SOP_TRANSIENT" in normalize_problem_code(a.specific_problem)
        ]
        if not sop_alarms:
            return None

        lead = sop_alarms[0]
        ext = lead.extra or {}
        sop_rad_s = float(ext.get("sop_rate_rad_s", 0.0))
        if sop_rad_s < 150.0:
            return None

        # 2. Look up physical cable & compute slack-compensated street coordinates via PostGIS
        cable_id = ext.get("cable_id") or next(iter(cluster.involved_cables), None)
        if not cable_id or cable_id not in ctx.inventory["cables"]:
            return None

        acoustic_opt_m = float(ext.get("phase_otdr_distance_m", 4200.0))
        fault_loc = locate_fault_on_cable_postgis(cable_id, acoustic_opt_m)

        # 3. Stage human-gated Northbound actions (NEVER hardcode city/cable names!)
        action = ProposedAction(
            action_id=f"ACT-PREEMPT-REROUTE-{cable_id}",
            target_system="ServiceNow Field Service (FSM)",
            connector_id="servicenow_itsm",
            action_type="DISPATCH_FIELD_SPLICE_CREW",
            title=f"Dispatch OSP Patrol to Stop Unauthorized Excavation on {cable_id}",
            description=f"SOP spike ({sop_rad_s:.0f} rad/s) pinpointed at ({fault_loc['lat']}, {fault_loc['lon']}).",
            payload={
                "table": "wm_order",
                "cmdb_ci": cable_id,
                "location_lat": fault_loc["lat"],
                "location_lon": fault_loc["lon"],
            },
        )

        return RootCauseHypothesis(
            classifier_id=self.classifier_id,
            root_cause_type="PRE_CUT_EXCAVATION_SOP_WARNING",
            root_cause_resource=cable_id,
            title=f"Pre-Cut Excavation Vibration ({sop_rad_s:.0f} rad/s) on {cable_id}",
            confidence=0.98,
            summary=f"Coherent SOP transient ({sop_rad_s:.0f} rad/s) localized prior to fiber break.",
            fault_location=fault_loc,
            domain_actions=[action],
            suppress_default_splice_dispatch=True,
        )
```

### Step 2 — Export in [`backend/app/correlation/classifiers/__init__.py`](../backend/app/correlation/classifiers/__init__.py)
Import your new class in `__init__.py` so `@register_classifier` registers it at startup.

### Step 3 — Add a Matching MOP Runbook in [`backend/app/knowledge/runbooks.json`](../backend/app/knowledge/runbooks.json)
Add a JSON object with `id`, `title`, `domain`, `oem_tags`, `symptoms`, and `procedure_md`. On startup, `db.py` automatically embeds `title + symptoms + procedure_md` into `vector(64)` in `pgvector` so `pipeline.py` retrieves your runbook by cosine similarity!

---

## 3. Recipe B: Loading a Different City / Customer Topology Dataset

Because all topology lives outside `backend/app/`, you can create a new dataset for **Abu Dhabi (`e&`)**, **Mumbai (`Constl`)**, or **Hong Kong–Singapore (`PCCW Global`)** without changing a single line of backend code:

1. Copy [`emulators/datasets/dubai_metro.json`](../emulators/datasets/dubai_metro.json) to `emulators/datasets/mumbai_metro.json`.
2. Edit `nodes`, `ducts`, `cables`, `oms_links`, `wavelengths`, `customers`, and `services`.
3. Launch the emulator pointing at your dataset:
   ```bash
   TELCO_DATASET_PATH=emulators/datasets/mumbai_metro.json \
     PYTHONPATH=$(pwd) .venv/bin/uvicorn emulators.emu.server:app --port 8001
   ```
   `emulators/emu/roads.py` automatically detects the new SHA-256 topology fingerprint, queries OSRM road geometry for the new city's coordinates, caches it, and syncs it into PostGIS via WFS/TMF APIs!

---

## 4. Recipe C: Adding a New Backend Endpoint & Frontend View / Modal

1. **Pydantic Request/Response Contract:**
   - Add typed Pydantic models in [`backend/app/schemas/models.py`](../backend/app/schemas/models.py) and export in [`backend/app/schemas/__init__.py`](../backend/app/schemas/__init__.py).
2. **FastAPI Route:**
   - Mount your route in [`backend/app/main.py`](../backend/app/main.py) (or a dedicated `APIRouter` imported into `main.py`), delegating business/physics logic to `spatial/`, `routing/`, or `correlation/`.
3. **TypeScript Mirrors & Typed Client:**
   - Add matching TypeScript interfaces in [`frontend/src/types/api.ts`](../frontend/src/types/api.ts).
   - Add typed fetch helpers in [`frontend/src/api/client.ts`](../frontend/src/api/client.ts).
4. **UI View / Component (`Light` + `Dark` Theme Parity):**
   - Place standalone tabs in `frontend/src/views/` and reusable panels/modals in `frontend/src/components/`.
   - Always use semantic theme classes (`bg-white dark:bg-slate-900`, `text-slate-900 dark:text-slate-100`, `border-slate-200 dark:border-slate-800`) so both Light and Dark themes remain crisp and legible.

---

## 5. Golden Rule: Passing the Anti-Hardcoding Gate

[`scripts/check_no_hardcoded_topology.py`](../scripts/check_no_hardcoded_topology.py) scans every `.py` file under `backend/app/` and fails CI if it sees dataset-specific identifiers such as:
- Cable IDs (`CBL-QZ-BB-01`, `SUBSEA-IMEWE-AE1`, ...)
- Duct / Chamber IDs (`D-I2-I1`, `J_DG`, ...)
- Circuit / Wavelength IDs (`OCH-JLC-P`, `SVC-EGB-L3VPN`, ...)
- RAN / GPON / Customer IDs (`RAN_BB_HUB`, `SPL-QZ-IND-02`, `CUST-1001`, ...)

**Always query `ctx.inventory` or PostgreSQL tables dynamically** using resource relationships (`cable.duct_ids`, `wavelength.path_nodes_json`, `service.legs_json`, PostGIS `ST_DWithin` / `ST_LineInterpolatePoint`, NetworkX `nx.shortest_path`).
