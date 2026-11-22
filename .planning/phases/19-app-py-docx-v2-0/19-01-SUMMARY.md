---
phase: 19-app-py-docx-v2-0
plan: 01
subsystem: docx-export-and-schema-isolation
tags: [docx, openxml, ecma-376, clavien-dindo, red-flags, clinical-decision-nuances, workspace-isolation, v2-verification]

# Dependency graph
requires:
  - phase: 17-prisma
    provides: "validate_nosology_id(), Clavien-Dindo/reversibility/event_class enums, and extracted_complications schema"
  - phase: 18-v2-0
    provides: "validate_kb_v2(), clinical_decision_nuances contract, and read-only verify_reports.py v2.0 linter"
provides:
  - "Pure-Python OpenXML v2.0 appendices generator (render_v2_kb_appendices_markdown, build_executive_docx_bytes, build_full_dossier_docx_bytes, is_v2_kb_index) in src/docx_exporter.py"
  - "Strict ECMA-376 table formatting (<w:cantSplit/><w:tblHeader/>, single <w:shd>) with scoped Clavien-Dindo IIIb/IV/V and Red Flags pastel shading without stage false positives"
  - "Frozen v1.x PermissionError overwrite guards (FROZEN_V1_NOSOLOGIES) in src/docx_exporter.py (+ --allow-frozen-overwrite CLI flag) and src/universal_schema.py"
  - "INFO_SEARCHER_ROOT dynamic workspace isolation in src/universal_schema.py (get_active_project_root, _get_*_dir, discover_nosologies(configs_dir=None)) and src/verify_reports.py with monkeypatch.setattr compatibility"
  - "Legacy YAML query key normalization (openalex -> openalex_search, clinicaltrials -> clinical_trials_condition) in save_new_nosology_config()"
  - "6-module v2.0 KB report compatibility (>= 5 matched KB .md modules) in src/verify_reports.py"
affects: [19-02, 19-03, app-ui, docx-exporter, verify-reports, e2e-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Strict ECMA-376 CT_TrPrBase (<w:cantSplit/> before <w:tblHeader/>) and CT_TcPrInner (<w:tcW> -> single <w:shd> -> <w:vAlign>) ordering validated by ET.fromstring()"
    - "Scoped severity shading via Clavien-Dindo column index, Red Flag heading tracker, or explicit Clavien-Dindo inline context (zero false positives on stage tables)"
    - "INFO_SEARCHER_ROOT dynamic root resolution falling back to module-level CONFIGS_DIR/DATA_DIR/REPORTS_DIR so monkeypatch.setattr remains 100% functional"
    - "Repo-root-only FROZEN_V1_NOSOLOGIES PermissionError guard allowing unrestricted in-memory builds and tmp_path test exports"

key-files:
  created: []
  modified:
    - src/docx_exporter.py
    - src/universal_schema.py
    - src/verify_reports.py

key-decisions:
  - "Compute single (cell_fill, cell_color, cell_bold) per table cell before emitting <w:tcPr> so every cell strictly satisfies ECMA-376 single-<w:shd> and child-order invariants."
  - "Scope severity shading to Red Flag headings, Clavien-Dindo column headers, or explicit Clavien-Dindo inline phrases, ensuring v1.x/v2.0 staging tables (e.g. 'Стадия IV') retain neutral zebra fills."
  - "Resolve INFO_SEARCHER_ROOT inside _get_*_dir() helpers only when non-empty, falling back to module globals CONFIGS_DIR/DATA_DIR/REPORTS_DIR so existing monkeypatch.setattr tests in Phases 17-18 keep passing unchanged."
  - "Check FROZEN_V1_NOSOLOGIES overwrite guard before mkdir/write and only against canonical repo root paths, keeping tmp_path exports and in-memory UI downloads completely unrestricted."

patterns-established:
  - "Unified DOCX export contract: dissertation_report.docx stays pure dissertation_report.md render; executive_summary.docx and full_clinical_dossier.docx share build_executive_docx_bytes() and build_full_dossier_docx_bytes() with automatic v2.0 appendices."
  - "Isolated workspace contract: set INFO_SEARCHER_ROOT=<tmp_path> to isolate universal_schema and verify_reports across in-process AppTest and subprocess CLI runs."

requirements-completed: [UI-02, EXPORT-02]

# Metrics
duration: 7 min
completed: 2026-11-22
---

# Phase 19 Plan 01: `v2.0` DOCX Appendices, OpenXML Table Styling, `INFO_SEARCHER_ROOT` Isolation & 6-Module Verification Summary

**Implemented pure-Python ECMA-376 OpenXML `v2.0` appendices and scoped `Clavien–Dindo IIIb–V`/Red Flags table shading in `src/docx_exporter.py`, added `INFO_SEARCHER_ROOT` workspace isolation, query-key normalization, and frozen `v1.x` `PermissionError` guards in `src/universal_schema.py`, and unlocked 6-module `v2.0` KB verification in `src/verify_reports.py`.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-11-22T08:18:11Z
- **Completed:** 2026-11-22T08:24:41Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Upgraded `src/docx_exporter.py` with `FROZEN_V1_NOSOLOGIES`, `is_v2_kb_index()`, `render_v2_kb_appendices_markdown()`, `build_executive_docx_bytes()`, `build_full_dossier_docx_bytes()`, `_escape_md_cell()`, escaped-pipe splitting `(?<!\\)\|`, strict PMID validation (`^[1-9]\d{0,8}$`), ECMA-376 table child ordering (`<w:cantSplit/><w:tblHeader/>`, single `<w:shd>`), contextual `Clavien–Dindo IIIb/IV/V` & Red Flags pastel shading (zero false positives on staging tables), path-traversal containment via `validate_nosology_id()`, and repo-root frozen `v1.x` `PermissionError` guard with CLI `--allow-frozen-overwrite`.
- Upgraded `src/universal_schema.py` with `FROZEN_V1_NOSOLOGIES`, `get_active_project_root()`, `_get_configs_dir()` / `_get_data_dir()` / `_get_reports_dir()`, late-bound `discover_nosologies(configs_dir: Path | None = None)`, dynamic resolution in `load_nosology_bundle()`, legacy `queries.openalex` / `queries.clinicaltrials` normalization + frozen `v1.x` `PermissionError` guard in `save_new_nosology_config()`, and `build_executive_docx_bytes()` verification in `verify_universal_schema()`.
- Upgraded `src/verify_reports.py` with `INFO_SEARCHER_ROOT` fallback in `get_nosology_paths()` and generalized KB module validation (`len(kb_index_modules) >= 5`, `len(kb_md_files) >= 5`, `len(kb_md_files) == len(kb_index_modules)`) supporting both 5-module `v1.x` archives and 6-module `v2.0` corpora (including `06_complications_and_safety.md`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Upgrade `src/docx_exporter.py` with `v2.0` appendices, ECMA-376 table styling, and frozen `v1.x` overwrite guard (D-06, D-07, EXPORT-02)** - `6dd0dd1` (`feat`)
2. **Task 2: Add `INFO_SEARCHER_ROOT` isolation & frozen config guard to `src/universal_schema.py` and 6-module `v2.0` support to `src/verify_reports.py` (D-01, D-05, D-08, T-19-01, T-19-05)** - `4a6315f` (`feat`)

## Files Created/Modified
- `src/docx_exporter.py` - Added `v2.0` structured Markdown appendices (Appendix A complications + Red Flags, Appendix B clinical decision nuances), strict ECMA-376 table styling with scoped severity shading, pipe/XML/PMID sanitization, and `FROZEN_V1_NOSOLOGIES` repo-root overwrite guard (`--allow-frozen-overwrite`).
- `src/universal_schema.py` - Added `INFO_SEARCHER_ROOT` dynamic directory resolvers preserving `monkeypatch.setattr`, late-bound `discover_nosologies(configs_dir=None)`, legacy `openalex`/`clinicaltrials` key normalization + frozen config guard in `save_new_nosology_config()`, and `build_executive_docx_bytes()` check in `verify_universal_schema()`.
- `src/verify_reports.py` - Added `INFO_SEARCHER_ROOT` support in `get_nosology_paths()` and dynamic `>= 5` (5 or 6) matched KB module verification in `verify_all_reports()`.

## Verification Results
- **Task 1 OpenXML DOM & security check (`OK 19-01-T1` + extended edge cases):** Verified `['cantSplit', 'tblHeader']` on header rows, `['cantSplit']` on every data row, `['tcW', 'shd', 'vAlign']` (single `<w:shd>`) on every cell, `FFEDD5` on `IIIb`, `FEE2E2` on `IV`/`V` and Red Flags, zero red/amber shading on `| Стадия IV | >90 |`, byte-identical `v1.x` outputs, clean `dissertation_report.docx` without appendix duplication, pipe/XML/PMID sanitization, `ValueError` on path traversal, `PermissionError` on all 3 frozen `v1.x` repo-root exports, and clean `tmp_path` export.
- **Task 2 pytest & isolation check (`17 passed` + `OK 19-01-T2` + 6-module check):** All 17 existing tests (`tests/test_phase17_complications.py` + `tests/test_phase18_humanizer.py`) passed in `2.39s`; verified `PermissionError` on repo-root `save_new_nosology_config({'nosology': {'id': 'trigger_finger'}})`, `INFO_SEARCHER_ROOT` + `monkeypatch.setattr` isolation on `discover_nosologies()`, legacy `openalex`/`clinicaltrials` normalization, and 6-module (`8` Markdown files) `v2.0` verification + mismatch rejection in `verify_reports.py`.
- **Live read-only frozen `v1.x` CLI checks:**
  - `uv run src/universal_schema.py --verify --nosology {prom,metroplasty_pregnancy,trigger_finger}` -> `[PASS] [v1.x (compat)]` (3/3 exit `0`).
  - `uv run src/verify_reports.py --nosology {prom,metroplasty_pregnancy,trigger_finger} --verify --read-only` -> `ALL REPORT VERIFICATION CHECKS PASSED` (3/3 exit `0`).
- **Frozen `v1.x` immutability gate:** `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger configs/prom.yaml configs/metroplasty_pregnancy.yaml configs/trigger_finger.yaml` returned empty output (`FROZEN_STATUS=[]`).

## Decisions Made
- Preserved exact backward compatibility of `build_docx_bytes_from_markdown`, `build_docx_bytes_from_markdown_sections`, and positional `export_nosology_docx_files(nosology_slug, base_dir=None)` while exposing new keyword-only `allow_frozen_overwrite=False` and `v2.0` builders.
- Used `INFO_SEARCHER_ROOT` with fallback to module-level `CONFIGS_DIR` / `DATA_DIR` / `REPORTS_DIR` so both subprocess/AppTest isolation and existing `monkeypatch.setattr` unit tests work seamlessly.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Wave 1 Plan `19-01` is complete and verified.
- Ready for Plan `19-02` (`app.py` Tabs 1–4 upgrades consuming `build_executive_docx_bytes`, `build_full_dossier_docx_bytes`, `get_active_project_root`, `save_new_nosology_config`, and `verify_reports.py --read-only`) and Wave 2 Plan `19-03` (`tests/test_v2_engine.py`).

## Self-Check: PASSED

- Verified modified files `src/docx_exporter.py`, `src/universal_schema.py`, and `src/verify_reports.py` exist on disk with zero stub/TODO/FIXME placeholders and zero unplanned threat surfaces.
- Verified atomic task commits `6dd0dd1` and `4a6315f` exist in git history with zero unintended file deletions.
- Verified all automated checks (`OK 19-01-T1`, `OK 19-01-T2`, `17 passed`, 3/3 `universal_schema --verify`, 3/3 `verify_reports --verify --read-only`, 6-module `v2.0` verification, and clean frozen `v1.x` `git status`) passed; `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified.

---
*Phase: 19-app-py-docx-v2-0*
*Completed: 2026-11-22*
