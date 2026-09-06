# Changelog

## v4.0.0 — 2026-09-07
### Dashboard
- Added the Dashboard 4.0 route at `/dashboard`.
- Kept compact expandable lead cards, four themes and responsive navigation.
- Removed fake overview and analytics placeholder responses.

### Wiring
- Dashboard now uses the canonical `Database` instance from FastAPI application state.
- Discovery creates persisted DISCOVERY jobs and runs the canonical workflow.
- Dataset results come from authoritative `search_results` relationships.
- Research loads the real lead before calling the Research Worker.
- Research results are scored and persisted through the canonical database layer.
- Pitch generation now reports explicit `501 Not Implemented` until a real backend exists.

### Integrity
- Version synchronized to 4.0.0.
- Dashboard exposes a router compatible with `main.py`.
- Dashboard JavaScript test target updated to the template source.

## v3.3.0 — 2026-09-06
- Previous wiring and deployment release.
