## Summary
<!-- Briefly describe what problem this PR solves and link the GitHub Issue (e.g., Closes #1). -->

## Architecture & Engineering Checklist
- [ ] **Topology-Agnostic Backend:** `python scripts/check_no_hardcoded_topology.py` passes with zero hardcoded city, node, cable, duct, or circuit IDs in `backend/app/`.
- [ ] **Modular Placement:**
  - New correlation logic implemented as a `@register_classifier` plugin under `backend/app/correlation/classifiers/`.
  - Spatial queries placed in `backend/app/spatial/` and graph/routing math in `backend/app/routing/`.
  - Pydantic contracts added to `backend/app/schemas/models.py` and mirrored in `frontend/src/types/api.ts`.
- [ ] **Automated Tests:** `pytest -v` passes (including new tests covering this feature).
- [ ] **Frontend Build & Theme Parity:** `cd frontend && npm run build` (`tsc --noEmit && vite build`) passes cleanly, and UI renders legibly in both **Light** and **Dark** themes.

## Verification Evidence
<!-- Paste pytest output or screenshots of Light + Dark UI if applicable. -->
