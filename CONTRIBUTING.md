# Contributing to Pandita AI — Telco NOC Copilot

Welcome to the team! You **do not** need prior telecommunications experience to build high-impact features here—our codebase separates telecom physics and protocols into clean, well-documented Python & TypeScript interfaces.

---

## Mandatory Onboarding Reading (25 Minutes Total)

1. **[`docs/01_TELCO_PRIMER_FOR_ENGINEERS.md`](docs/01_TELCO_PRIMER_FOR_ENGINEERS.md)** — 15-minute visual crash course translating OSP slack coils, binary `.sor` OTDR traces, DWDM `OCh`/`OMS`/`Pre-FEC BER`/`SOP`, GPON `Dying Gasp`, 5G `LVD`, E-Band `ACM`, and `SRLG` into standard CS concepts + full Acronym Glossary.
2. **[`docs/02_SYSTEM_ARCHITECTURE_AND_DATA_FLOW.md`](docs/02_SYSTEM_ARCHITECTURE_AND_DATA_FLOW.md)** — Normalized PostgreSQL/PostGIS schema, graph-based multi-fault alarm clustering, and pluggable `HypothesisClassifier` architecture.
3. **[`docs/03_DEVELOPER_CONTRIBUTION_GUIDE.md`](docs/03_DEVELOPER_CONTRIBUTION_GUIDE.md)** — Copy-paste recipes for adding a new `@register_classifier` plugin, loading a new city dataset (`TELCO_DATASET_PATH`), or adding a typed API + React view.
4. **[`docs/04_API_AND_CONNECTOR_CONTRACTS.md`](docs/04_API_AND_CONNECTOR_CONTRACTS.md)** — Complete REST API reference, TMF642 schema, 12-OEM connector matrix, and mathematical formulas.

---

## Branching & Pull Request Workflow

1. Pick an assigned Epic / Issue (`#1`–`#6` or new issue) and branch from `main`:
   ```bash
   git checkout -b feat/epic-1-sop-precut-warning
   ```
2. Keep `backend/app/` **100% topology-agnostic**:
   - **Never** hardcode city names, node IDs, cable IDs, router names, or static reroute lists inside `backend/app/`.
   - Reference topology data belongs only in declarative datasets (`emulators/datasets/*.json`) or PostgreSQL tables queried dynamically.
3. Add or extend automated tests in `tests/` covering your new classifier, spatial query, or API endpoint.
4. Maintain **Light & Dark theme parity** across any new React views/components in `frontend/src/`.
5. Run all three local CI gates before opening your PR:
   ```bash
   .venv/bin/python scripts/check_no_hardcoded_topology.py
   .venv/bin/pytest -v
   (cd frontend && npm run build)
   ```
