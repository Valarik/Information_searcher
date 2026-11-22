---
phase: 19-app-py-docx-v2-0
plan: 02
subsystem: streamlit-ui-v2-complications-and-nuances
tags: [streamlit, plotly, clavien-dindo, red-flags, clinical-decision-nuances, extracted-complications, surgical-focus, read-only-audit, apptests, v2-ui]

# Dependency graph
requires:
  - phase: 19-app-py-docx-v2-0
    provides: "build_executive_docx_bytes(), build_full_dossier_docx_bytes(), get_active_project_root(), INFO_SEARCHER_ROOT isolation, and frozen v1.x PermissionError guards (Plan 19-01)"
  - phase: 17-prisma
    provides: "query_complications_df(), save_new_nosology_config(), harvester.build_complications_queries(), and Clavien-Dindo/reversibility/event_class enums"
  - phase: 18-v2-0
    provides: "clinical_decision_nuances v2.0 schema and verify_reports.py --verify --read-only"
provides:
  - "Streamlit v2.0 UI in app.py with width='stretch' migration, workspace_root-keyed cached_bundle(), and cached_complications()"
  - "Sidebar v2.0 Строк осложнений KPI, dynamic Mode C module count, and unified build_executive_docx_bytes() / build_full_dossier_docx_bytes() downloads across Sidebar & Tab 1"
  - "Tab 2 subtabs 2.5 (Clavien-Dindo 4 filters, color toggle, 2 Plotly charts, 11-column table + CSV, Red Flags cards, v1.x fallback) and 2.6 (3-block clinical_decision_nuances with validated PMID links & v1.x fallback) with zero new unsafe_allow_html=True"
  - "Tab 3 option 5 (extracted_complications) with casuistry toggle, df_comp_all-derived multiselects, empty-df guard, PubMed/DOI LinkColumns, CSV export, and read-only v1.x notice"
  - "Tab 4 --verify --read-only audit button (validate_nosology_id + shell=False), reactive surgical_focus/MeSH/core_terms live build_complications_queries() preview above st.form('new_nosology_form'), safe carpal_tunnel_syndrome default, and aligned openalex_search/clinical_trials_condition YAML keys"
  - "Extended run_self_test() validating all discovered nosologies, subtabs 2.5/2.6, dynamic Mode C, and Tab 3 option 5 with 0 exceptions and 0 deprecation warnings"
affects: [19-03, app-ui, e2e-tests]

# Tech tracking
tech-stack:
  added: ["truststore>=0.10.0 (PEP 723 header of app.py; already in repo)", "streamlit>=1.50.0 (PEP 723 floor for width='stretch')"]
  patterns:
    - "Strict native Streamlit containers (st.error, st.warning, st.container(border=True), st.markdown) for v2.0 panels with zero new unsafe_allow_html=True calls and ^[1-9]\\d{0,8}$ PMID URL validation"
    - "Reactive live-preview controls (t4_profile_radio, t4_mesh_terms, t4_core_terms) placed above st.form('new_nosology_form') so harvester.build_complications_queries() updates immediately on toggle"
    - "Multiselect options/defaults in Tab 3 option 5 derived strictly from full df_comp_all (include_casuistry=True) with explicit empty df_comp guard before LinkColumn/URL indexing"
    - "Workspace-isolated @st.cache_data keying via cached_bundle(nosology_id, workspace_root=str(get_active_project_root()))"

key-files:
  created: []
  modified:
    - app.py

key-decisions:
  - "Keep Tab 1 existing 3 unsafe_allow_html=True search-highlight calls unchanged and enforce strictly 0 new unsafe_allow_html=True calls across all v2.0 UI blocks (subtabs 2.5 & 2.6, Tab 3 option 5, Tab 4 preview)."
  - "Derive Tab 3 option 5 multiselect options and defaults strictly from df_comp_all (include_casuistry=True) and guard empty df_comp before URL/column projection so toggling t3_comp_casuistry immediately surfaces casuistry-only modalities/grades and casuistry-only DBs never raise KeyError."
  - "Place t4_profile_radio, t4_mesh_terms, t4_core_terms, and the live harvester.build_complications_queries() preview container directly above st.form('new_nosology_form') to preserve instant reactivity without breaking st.form batch submission."
  - "Add read-only compatibility fallbacks in Tab 2 subtabs 2.1–2.4 for frozen v1.x trigger_finger kb_index.json field variants and empty-DataFrame guards on Tab 3 options 1–4 rather than mutating frozen v1.x archives."

patterns-established:
  - "All Streamlit width-stretched charts, tables, and download buttons in app.py use width='stretch' (zero use_container_width deprecation warnings in Streamlit 1.67)."
  - "Dynamic widget option discovery in run_self_test() matches Mode A/B/C and Tab 3 options 1 & 5 by prefix so both 5-module v1.x and 6-module v2.0 corpora pass cleanly."

requirements-completed: [UI-02, EXPORT-02]

# Metrics
duration: 11 min
completed: 2026-11-22
---

# Phase 19 Plan 02: `app.py` `v2.0` UI Upgrade (Subtabs `2.5`/`2.6`, Tab 3 `extracted_complications`, Tab 4 Live Preview & Read-Only Audit) Summary

**Upgraded `app.py` to full `v2.0` clinical analytics and safe configurator parity: added Clavien–Dindo complications (`2.5`) and clinical decision nuances (`2.6`) subtabs, Tab 3 `extracted_complications` explorer with casuistry toggle, Tab 4 reactive `surgical_focus` live query preview & `--read-only` audit, unified `v2.0` DOCX downloads, `width="stretch"` migration, and multi-nosology `--self-test` with 100% frozen `v1.x` compatibility.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-11-22T08:25:54Z
- **Completed:** 2026-11-22T08:37:05Z
- **Tasks:** 2
- **Files modified:** 1 (`app.py`)

## Accomplishments
- Upgraded `app.py` PEP 723 dependencies (`streamlit>=1.50.0`, `truststore>=0.10.0`), migrated all `use_container_width=True` calls to `width="stretch"` (0 deprecation warnings), added `workspace_root`-keyed `cached_bundle()` and `cached_complications()`, added the Sidebar `Строк осложнений` KPI for `v2.0`, made Tab 1 Mode C module counts dynamic (`len(kb_modules)`), and switched `sb_dl_exec_docx`, `sb_dl_full_docx`, and `t1_exec_docx_btn` to unified `build_executive_docx_bytes()` / `build_full_dossier_docx_bytes()`.
- Built Tab 2 subtabs `2.5 «⚠️ Осложнения (Clavien–Dindo)»` (4 multiselect filters, color encoding toggle between `Clavien–Dindo` and `Обратимость`, horizontal median frequency bar chart, stacked `I–V` distribution bar chart, 11-column table + `.csv`, native `rare_critical_red_flags` warning cards with validated PMID links, and read-only `v1.x` fallback) and `2.6 «🧭 Клинические компромиссы и серые зоны»` (3-block `clinical_decision_nuances` cards with validated PMID links and `v1.x` fallback referencing `2.4`), introducing zero new `unsafe_allow_html=True` calls.
- Added Tab 3 option 5 `5. Извлечённые осложнения лечения (extracted_complications)` backed by read-only `cached_complications()`, with casuistry toggle (`t3_comp_casuistry`), 4 multiselects strictly derived from `df_comp_all`, text search, empty-`df_comp` guard before `pubmed_url`/`doi_url` access, clickable `LinkColumn`s, `.csv` export (`dl_csv_comp`), and calm 0-row `v1.x` notice.
- Upgraded Tab 4 with strictly `--verify --read-only` audit execution (`validate_nosology_id`, `shell=False`, `timeout=60`), reactive `t4_profile_radio` / `t4_mesh_terms` / `t4_core_terms` + live `harvester.build_complications_queries()` preview above `st.form("new_nosology_form")`, safe default ID `carpal_tunnel_syndrome`, optional `complications_queries` overrides, and aligned `openalex_search` / `clinical_trials_condition` YAML keys.
- Extended `run_self_test()` to verify all discovered nosologies (`metroplasty_pregnancy`, `prom`, `trigger_finger`), subtabs `2.5`/`2.6`, dynamic Mode C, and Tab 3 option 5 with 0 exceptions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Upgrade `app.py` header, cache isolation, Sidebar, Tab 1, and Tab 2 subtabs `2.5` (Clavien–Dindo) & `2.6` (Clinical Decision Nuances) (D-01, D-02, D-03, D-06, UI-02)** - `70b61c5` (`feat`)
2. **Task 2: Add Tab 3 `extracted_complications` explorer, Tab 4 `surgical_focus` live preview + read-only audit, and extended `app.py --self-test` (D-04, D-05, D-08, UI-02, EXPORT-02)** - `b59c39b` (`feat`)

## Files Created/Modified
- `app.py` - Full `v2.0` Streamlit UI upgrade (PEP 723 header, cache keying, Sidebar KPI + unified DOCX buttons, dynamic Tab 1 Mode C & DOCX, Tab 2 subtabs `2.5`/`2.6` + frozen `v1.x` `trigger_finger` compatibility, Tab 3 option 5 `extracted_complications` + empty-table guards, Tab 4 reactive `surgical_focus` preview & `--read-only` audit, and extended multi-nosology `run_self_test()`).

## Verification Results
- **Extended self-test (`uv run app.py --self-test`):** Exit `0`; verified all 3 discovered frozen `v1.x` nosologies (`metroplasty_pregnancy`, `prom`, `trigger_finger`) across universal schema checks + headless `AppTest` (all 4 tabs, 6 Tab 2 subtabs including `2.5`/`2.6`, Modes A/B/C, Tab 3 option 5) with `0` exceptions and `0` `use_container_width` warnings (`metrics=6, dataframes=7, tabs=10`).
- **Existing Phases 17–18 regression suite (`pytest tests/test_phase17_complications.py tests/test_phase18_humanizer.py -q`):** `17 passed in 2.32s`.
- **Isolated synthetic `v2.0` `AppTest` smoke suite (`INFO_SEARCHER_ROOT=tmp_dir`):** All 7 end-to-end checks passed (`ALL 7 SYNTHETIC V2.0 UI SMOKE TESTS PASSED!`), verifying Sidebar `Строк осложнений` KPI, 6-module Mode C label, subtab `2.5` 2 Plotly charts / color mode switch / empty filter warning / Red Flags / malicious PMID rejection, subtab `2.6` all 3 blocks, Tab 3 option 5 casuistry toggle revealing casuistry-only modality & casuistry-only DB edge case, Tab 4 reactive surgical→conservative live preview & YAML submit with `openalex_search` / `clinical_trials_condition` / `complications_queries`, and freshly created empty-DB nosology rendering across all 5 Tab 3 tables.
- **Static & security assertions (`OK static & security checks on app.py`):** 0 `use_container_width` in code lines, `unsafe_allow_html=True` count unchanged at `3`, `--read-only` + `shell=False` verified, `carpal_tunnel_syndrome` default verified, aligned query keys verified, zero `TODO`/`FIXME` stubs.
- **Frozen `v1.x` immutability gate:** `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger configs/prom.yaml configs/metroplasty_pregnancy.yaml configs/trigger_finger.yaml` returned empty output (`FROZEN_STATUS=[]`).

## Decisions Made
- Preserved all existing widget keys across Sidebar and Tabs 1–4 while introducing explicit, deterministic keys (`t25_*`, `t3_comp_*`, `dl_csv_freq_comp`, `dl_csv_comp`, `t4_*`) aligned with `19-02-PLAN.md` for Plan `19-03` (`tests/test_v2_engine.py`) `AppTest` coverage.
- Removed unused `import yaml` from `app.py` after switching Tab 4's post-save YAML preview to read the normalized output directly from `saved_path.read_text(encoding="utf-8")`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added read-only legacy key fallbacks in Tab 2 subtabs 2.1–2.4 for frozen `v1.x` `trigger_finger`**
- **Found during:** Task 2 (`uv run app.py --self-test` iterating all 3 discovered nosologies)
- **Issue:** Previously `run_self_test()` only rendered `discovered[0]` (`metroplasty_pregnancy`). Switching to frozen `v1.x` `trigger_finger` raised `KeyError: 'stage_code'` because `reports/trigger_finger/knowledge_base/kb_index.json` uses legacy field names (`system_name`, `stage`, `code`, `frequency_num`, `factor`, `phase`, list-typed `pros`/`cons`, and omits `reintervention_5y_num` and `definitions`).
- **Fix:** Added defensive read-only normalization/fallbacks and `_format_text_or_list()` in `render_tab_clinical_matrix()` subtabs `2.1–2.4` without altering any frozen `v1.x` files on disk or changing output for `prom`/`metroplasty_pregnancy`/`v2.0`.
- **Files modified:** `app.py`
- **Verification:** `uv run app.py --self-test` passed cleanly across all 3 nosologies (`metroplasty_pregnancy`, `prom`, `trigger_finger`) with 0 exceptions.
- **Committed in:** `b59c39b` (Task 2 commit)

**2. [Rule 1 - Bug] Added empty-DataFrame guards to Tab 3 options 1–4 for newly configured nosologies without `literature.db`**
- **Found during:** Task 2 (isolated synthetic `v2.0` `AppTest` smoke test after submitting a new config in Tab 4)
- **Issue:** Selecting a freshly saved nosology config whose `literature.db` has not been harvested yet returned 0-column empty `DataFrame`s from `query_*_df()`, raising `KeyError` when Tab 3 options 1–4 indexed column names (`view[disp_cols]`, `df_clin["intervention_group"]`, etc.).
- **Fix:** Added concise `if df_*.empty: st.info(...); return` guards at the top of Tab 3 branches 1–4 matching option 5's empty guard.
- **Files modified:** `app.py`
- **Verification:** Verified in isolated `AppTest` smoke test #6 iterating all 5 Tab 3 radio options on a freshly created config with 0 exceptions.
- **Committed in:** `b59c39b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both auto-fixes were essential for true 100% backward compatibility with all 3 frozen `v1.x` nosologies (specifically `trigger_finger`) and safe UX when adding new nosologies via Tab 4. Zero scope creep and zero edits to frozen `v1.x` directories.

## Issues Encountered
None beyond the two pre-existing compatibility bugs resolved inline above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 2 Plan `19-02` is complete and verified.
- Ready for Wave 3 Plan `19-03` (`tests/test_v2_engine.py`: full E2E synthetic `v2.0` pipeline + `AppTest` + frozen `v1.x` sha256/mtime regression suite).

## Self-Check: PASSED

- Verified modified file `app.py` and created summary `.planning/phases/19-app-py-docx-v2-0/19-02-SUMMARY.md` exist on disk with zero stub/TODO/FIXME placeholders and zero unplanned threat surfaces.
- Verified atomic task commits `70b61c5` and `b59c39b` exist in git history with zero unintended file deletions.
- Verified all automated checks (`uv run app.py --self-test` across all 3 nosologies, `17 passed` Phases 17–18 pytest suite, 7/7 isolated synthetic `v2.0` `AppTest` smoke checks, static/security assertions, and empty frozen `v1.x` `git status`) passed; `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified.

---
*Phase: 19-app-py-docx-v2-0*
*Completed: 2026-11-22*
