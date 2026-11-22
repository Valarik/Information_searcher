---
phase: 19-app-py-docx-v2-0
plan: 03
subsystem: e2e-v2-testing-and-frozen-v1-regression
tags: [pytest, e2e, openxml, docx, streamlit-apptest, security, path-traversal, frozen-v1, sha256, immutability, clavien-dindo]

# Dependency graph
requires:
  - phase: 19-app-py-docx-v2-0
    provides: "v2.0 DOCX appendices, ECMA-376 OpenXML styling, INFO_SEARCHER_ROOT isolation, 6-module verify_reports, and frozen v1.x PermissionError guards (Plan 19-01)"
  - phase: 19-app-py-docx-v2-0
    provides: "Streamlit v2.0 UI (subtabs 2.5 & 2.6, Tab 3 option 5 + casuistry toggle, Tab 4 surgical_focus preview & --read-only audit, extended --self-test) (Plan 19-02)"
  - phase: 17-prisma
    provides: "harvester.build_complications_queries(), schema.init_db(), extractor_common.insert_extracted_complication(), aggregate_complications_from_sqlite(), query_complications_df()"
  - phase: 18-v2-0
    provides: "clinical_decision_nuances v2.0 contract, Humanizer v2.0 structural linter, verify_reports.py --schema-version v2 --read-only"
provides:
  - "100% offline end-to-end v2.0 test suite in tests/test_v2_engine.py (5 tests, 1326 lines) validating harvester -> SQLite -> aggregation -> kb_index.json v2.0 -> verify_reports(v2, read-only) -> OpenXML .docx DOM -> security guards -> isolated Streamlit AppTest"
  - "Recursive byte-level zero-mutation regression gate across all 3 frozen v1.x nosologies (prom, metroplasty_pregnancy, trigger_finger) covering SHA-256, st_mtime_ns, st_size, SQLite -wal/-shm sidecar invariants, and git status --porcelain"
  - "Full Phase 19 green verification gate: 22/22 pytest tests passing + uv run app.py --self-test exit 0 + zero mutations across frozen v1.x directories"
affects: [phase-19-verification, milestone-v2-0-audit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-contained tmp_path 6-module v2.0 synthetic workspace factory (_build_synthetic_v2_workspace) with INFO_SEARCHER_ROOT isolation and st.cache_data.clear() teardown"
    - "OpenXML word/document.xml DOM auditing via zipfile + xml.etree.ElementTree validating strict ECMA-376 child order (<w:cantSplit/><w:tblHeader/>, <w:tcW>/<w:shd>/<w:vAlign>) and scoped severity shading"
    - "Subprocess spy delegation around real subprocess.run inside Streamlit AppTest verifying btn_run_verify executes --verify --read-only with shell=False and 0 file mutations"
    - "Recursive (sha256_hex, st_mtime_ns, st_size) + SQLite WAL/SHM sidecar snapshot gate preserving pre-existing gitignored .db-wal (size==0) and .db-shm sets while verifying zero writes"

key-files:
  created:
    - tests/test_v2_engine.py
  modified: []

key-decisions:
  - "Validate RFC 4180 CSV export integrity via csv.DictReader round-trip on utf-8-sig decoded bytes rather than raw substring matching so quoted special characters (<rare> & \"pain\" | pipe) verify cleanly."
  - "Track pre-existing gitignored 0-byte .db-wal files in the recursive SHA-256/mtime/size snapshot (asserting size == 0 and exact identity) while gating .db-shm sidecars strictly by path-set equality, accounting for SQLite ?mode=ro WAL read-lock mmap timestamps on Windows without ever touching frozen v1.x directories."
  - "Access Streamlit AppTest Plotly charts inside subtab 2.5 via t25.get('plotly_chart') (the canonical Streamlit 1.50+ ElementList accessor for Plotly elements)."

patterns-established:
  - "Every Phase 17-19 regression test suite runs 100% offline in ~11 seconds via uv run --with pytest --with streamlit --with plotly --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v."

requirements-completed: [UI-02, EXPORT-02]

# Metrics
duration: 10 min
completed: 2026-11-22
---

# Phase 19 Plan 03: Offline E2E `v2.0` Engine Test Suite & Frozen `v1.x` Zero-Mutation Regression Gate Summary

**Built `tests/test_v2_engine.py` (5 tests, 1326 lines) proving the complete offline 6-module `v2.0` pipeline from `harvester.build_complications_queries` and SQLite `extracted_complications` through OpenXML `.docx` DOM validation, `T-19-01..T-19-05` security guards, and isolated `Streamlit AppTest`, while certifying 100% backward compatibility and byte-level zero mutation on all 3 frozen `v1.x` nosologies (`22 passed` + `uv run app.py --self-test` exit `0`).**

## Performance

- **Duration:** 10 min
- **Started:** 2026-11-22T08:38:32Z
- **Completed:** 2026-11-22T08:48:30Z
- **Tasks:** 2
- **Files modified:** 1 created (`tests/test_v2_engine.py`)

## Accomplishments
- Created `tests/test_v2_engine.py` with a self-contained offline 6-module `v2.0` synthetic workspace generator (`_build_synthetic_v2_workspace`) populating `configs/*.yaml` (`surgical_focus: true`), all 5 SQLite tables (`36` included articles, `2` clinical trials, `2` clinical evidence rows, `2` mechanism rows, `5` `extracted_complications` rows spanning `Clavien–Dindo I/II/IIIb/IV`, `<rare> & "pain" | pipe` escaping payload, and `Tier 4` `N=1` casuistry), aggregated `kb_index.json` (`schema_version: "2.0"`, all 8 `REQUIRED_UNIVERSAL_KEYS`, 6 modules including `06_complications_and_safety.md`, and all 3 `clinical_decision_nuances` blocks), and clean humanized Markdown reports (including a `"Стадия IV"` staging table in `executive_summary.md`).
- Verified the full `v2.0` pipeline (`test_v2_end_to_end_pipeline_and_verify_reports`), OpenXML `word/document.xml` DOM invariants and CLI/in-memory byte parity (`test_docx_exporter_v2_appendices_and_openxml_styling`), `T-19-01` path-traversal `ValueError` and frozen `v1.x` repo-root `PermissionError` guards (`test_security_guards_path_traversal_and_frozen_v1_protection`), and isolated headless `Streamlit AppTest` exercising Sidebar KPI, 6-module Mode C, subtabs `2.5` & `2.6`, Tab 3 option 5 + `Tier 4` casuistry toggle, Tab 4 reactive `surgical_focus` live preview + YAML save (`openalex_search`, `clinical_trials_condition`), and `T-19-03` `btn_run_verify --verify --read-only` (`shell=False`, zero disk writes) (`test_v2_isolated_apptest_tabs_and_configurator`).
- Added the recursive frozen `v1.x` regression and immutability gate (`_snapshot_frozen_v1_tree` + `test_v1_frozen_regression_and_zero_mutation`) covering `prom`, `metroplasty_pregnancy`, and `trigger_finger` across `load_nosology_bundle`, `is_v2_kb_index() is False`, `query_complications_df().empty`, `verify_universal_schema(auto)`, `verify_all_reports(auto, write_outputs=False)`, in-memory `.docx` builds (valid OpenXML, strictly zero `v2.0` appendices), repo-root `PermissionError` blocks, and full repo-root `Streamlit AppTest` with before/after SHA-256 + `st_mtime_ns` + `st_size` + WAL/SHM sidecar + `git status --porcelain` assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create `tests/test_v2_engine.py` with synthetic 6-module `v2.0` E2E pipeline, OpenXML DOM audit, security guard checks, and isolated Streamlit `AppTest` (`D-01..D-08`, `T-19-01..T-19-05`)** - `e59d6c4` (`test`)
2. **Task 2: Add frozen `v1.x` zero-mutation regression suite to `tests/test_v2_engine.py` and execute full Phase 19 verification gate (`D-06`, `D-07`, `D-08`, `EXPORT-02`, `UI-02`)** - `d26a446` (`test`)

## Files Created/Modified
- `tests/test_v2_engine.py` - Complete 1326-line offline E2E `v2.0` test suite, OpenXML `word/document.xml` DOM validator, security guard tests (`T-19-01..T-19-05`), isolated `Streamlit AppTest` across Tabs 1–4, and byte-level frozen `v1.x` regression gate (`prom`, `metroplasty_pregnancy`, `trigger_finger`).

## Verification Results
- **Full project pytest suite (`pytest tests/ -v`):** `22 passed in 11.06s` (`0 failed`, `0 errors`):
  - `tests/test_phase17_complications.py`: `11 passed`
  - `tests/test_phase18_humanizer.py`: `6 passed`
  - `tests/test_v2_engine.py`: `5 passed` (`test_v2_end_to_end_pipeline_and_verify_reports`, `test_docx_exporter_v2_appendices_and_openxml_styling`, `test_security_guards_path_traversal_and_frozen_v1_protection`, `test_v2_isolated_apptest_tabs_and_configurator`, `test_v1_frozen_regression_and_zero_mutation`)
- **Headless application self-test (`uv run app.py --self-test`):** Exit `0` — verified all 3 discovered frozen `v1.x` nosologies (`metroplasty_pregnancy`, `prom`, `trigger_finger`), all 4 tabs, subtabs `2.5`/`2.6`, dynamic Mode C, and Tab 3 option 5 with `0` exceptions (`metrics=6, dataframes=7, tabs=10`).
- **Frozen `v1.x` immutability gate (`git status --porcelain` across all 6 frozen folders + 3 configs):** Empty output (`FROZEN_DIFF=[]`), confirming zero byte/metadata mutations across `data/{prom,metroplasty_pregnancy,trigger_finger}`, `reports/{prom,metroplasty_pregnancy,trigger_finger}`, and `configs/{prom,metroplasty_pregnancy,trigger_finger}.yaml`.

## Decisions Made
- Validated CSV export round-trip with `csv.DictReader` over `utf-8-sig` decoded bytes so RFC 4180 quote-escaped special characters (`""pain""`) verify accurately alongside the `b"\xef\xbb\xbf"` BOM.
- Structured `_snapshot_frozen_v1_tree()` to hash and check `(sha256, st_mtime_ns, st_size)` for all frozen files including `literature.db` and pre-existing 0-byte `.db-wal` files (`st_size == 0`), while gating `.db-shm` strictly by sidecar path-set invariance because SQLite's `?mode=ro` WAL reader updates the mmap timestamp of pre-existing gitignored `.db-shm` lock files on Windows without writing to `.db` or `.db-wal`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing gitignored 0-byte `literature.db-wal` and 32 KB `literature.db-shm` sidecars exist in the frozen `v1.x` WAL-mode `data/` directories from Milestone 1.x, and SQLite `?mode=ro` refreshes `.db-shm` mmap timestamps on read while leaving `literature.db` and 0-byte `literature.db-wal` byte-identical. Resolved cleanly inside `_snapshot_frozen_v1_tree()` by enforcing `wal.stat().st_size == 0`, hashing `.db` + `.db-wal` `(sha256, st_mtime_ns, st_size)`, and asserting strict sidecar path-set invariance (`after_sidecars == before_sidecars`) without touching any frozen directory.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Wave 3 Plan `19-03` is complete and all Phase 19 plans (`19-01`, `19-02`, `19-03`) are implemented and verified.
- Ready for Phase 19 verification (`gsd-verifier`) and Milestone `v2.0` completion audit.

## Self-Check: PASSED

- Verified created file `tests/test_v2_engine.py` (1326 lines, >= 300 required) and summary `.planning/phases/19-app-py-docx-v2-0/19-03-SUMMARY.md` exist on disk with zero TODO/FIXME/stub placeholders and zero unplanned threat surfaces.
- Verified atomic task commits `e59d6c4` and `d26a446` exist in git history with zero unintended file deletions.
- Verified all automated checks (`22 passed in 11.06s`, `uv run app.py --self-test` exit `0`, and empty `git status --porcelain` across all frozen `v1.x` directories/configs) passed; `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified.

---
*Phase: 19-app-py-docx-v2-0*
*Completed: 2026-11-22*
