---
phase: 17-prisma
plan: 01
subsystem: database
tags: [sqlite, clavien-dindo, ctcae, jats-xml, universal-schema, backward-compat, prisma]

# Dependency graph
requires:
  - phase: 04-universal-schema
    provides: Universal nosology JSON schema adapter, SQLite corpus explorer, and verification CLI
provides:
  - Relational SQLite table `extracted_complications` (20 columns, 4 indexes) via idempotent `init_db()`
  - Dual-axis severity normalizer (`Clavien-Dindo I..V` + `CTCAE Grade 1-5` + `reversibility`), recurrence/incomplete-release exclusion guard, CI-safe frequency parser, JATS safety section matching, and parameterized CRUD helpers in `src/extractor_common.py`
  - Median-based complication aggregator (`frequent_complications >= 1.0%` + `rare_critical_red_flags < 1.0%`), strict `schema_version: "2.0"` validator (`--schema-version {auto,v1,v2}`), and read-only SQLite URI + `sqlite_master` compatibility guards in `src/universal_schema.py`
affects: [17-02, 17-03, 18-anti-ai-linter, 19-ui-docx-v2]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only SQLite URI connector (`file:<posix>?mode=ro`) paired with parameterized `sqlite_master` table existence checks (`table_exists`) to keep frozen v1.x corpora untouched"
    - "Two-contour complication separation (Tier 1-3 & sample_size >= 20 cohort medians vs Tier 4 / N < 20 rare casuistry with 1/1 100% numeric nullification)"
    - "Dual-axis severity contract (`clavien_dindo_grade` + `ctcae_grade` mapping + `reversibility`) and `event_class` split (`true_complication` vs `transient_postop_sequela` with mandatory `time_window`)"

key-files:
  created: []
  modified:
    - src/schema.py
    - src/extractor_common.py
    - src/universal_schema.py

key-decisions:
  - "Strip explicit parenthesized and inline `90%/95%/99% CI` spans before standalone range/percentage matching in `extract_complication_frequency()` so strings like `12.5% (95% CI 8.1-17.2%)` and `95% CI 10-28%` never misparse CI bounds as complication rates"
  - "Use `_connect_sqlite_readonly()` across all SQLite reader functions in `src/universal_schema.py` (`get_sqlite_corpus_stats`, `build_dynamic_fallback_kb`, `aggregate_complications_from_sqlite`, and all `query_*_df` helpers) so inspecting frozen `v1.x` databases never creates `-wal`/`-shm` artifacts or mutates files on disk"
  - "Enforce ASCII regex `^[a-z0-9_]+$` and resolved-parent path check in `save_new_nosology_config()` to block Unicode/path-traversal edge cases (T-17-05)"

patterns-established:
  - "All reader helpers checking new tables MUST call `table_exists(conn, 'extracted_complications')` via parameterized `sqlite_master` lookup and never invoke `init_db()`"
  - "Direct CLI execution of `src/universal_schema.py` via `uv run` resolves `src.*` imports cleanly via `PROJECT_ROOT` `sys.path` bootstrap"

requirements-completed:
  - COMP-03
  - COMP-04

# Metrics
duration: 10 min
completed: 2026-11-19
---

# Phase 17 Plan 01: Relational Complications Schema & Universal v2.0 Adapter Summary

**SQLite `extracted_complications` schema, dual-axis Clavien-Dindo/CTCAE & CI-safe JATS extraction helpers, and median-sorted `frequent_complications` / `rare_critical_red_flags` aggregator with read-only v1.x corpus compatibility**

## Performance

- **Duration:** 10 min
- **Started:** 2026-11-19T16:22:23Z
- **Completed:** 2026-11-19T16:32:14Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added idempotent `extracted_complications` table (20 columns: `id` + 19 domain fields) and 4 query indexes (`idx_ext_comp_article`, `idx_ext_comp_modality`, `idx_ext_comp_grade`, `idx_ext_comp_class`) to `init_db()` in `src/schema.py` while keeping all 4 existing tables intact (`COMP-03`, `D-07`, `D-08`).
- Implemented dual-axis severity normalization (`normalize_clavien_dindo` with `I..V`, `IVa/IVb -> IV`, `III -> IIIa/IIIb`, and `CTCAE Grade 1-5` mapping), disease recurrence / incomplete release rejection (`is_excluded_recurrence_event`), CI-safe rate/grade/time-window extractors, JATS XML safety section matching (`adverse`, `safety`, `morbidity`, `side effect`, `sequela`, `harms`), and strictly parameterized CRUD helpers (`table_exists`, `insert_extracted_complication`, `fetch_extracted_complications`) with `D-04` Tier 4 casuistry nullification in `src/extractor_common.py`.
- Implemented read-only SQLite URI access (`_connect_sqlite_readonly`), `query_complications_df`, two-contour median aggregation (`aggregate_complications_from_sqlite` -> `frequent_complications >= 1.0%` descending per modality + `rare_critical_red_flags < 1.0%`), `validate_kb_complications_v2`, `--schema-version {auto,v1,v2}` CLI support, `PROJECT_ROOT` `sys.path` bootstrap, and `surgical_focus` / `treatment_profile` normalization in `src/universal_schema.py` (`COMP-04`, `D-01`, `D-09`, `T-17-02`, `T-17-05`).
- Verified read-only `[PASS]` compatibility on all 3 frozen `v1.x` nosologies (`prom`, `metroplasty_pregnancy`, `trigger_finger`) with zero mutations in `data/` and `reports/`, plus strict `[FAIL]` rejection on `--schema-version v2` for legacy KBs and clean `[PASS]` on v2.0 round-trip aggregation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add extracted_complications SQLite table and dual-axis extraction/CRUD helpers** - `fa0e13b` (feat)
2. **Task 2: Add frequent_complications aggregator, v2.0 validator, and read-only sqlite_master guards in universal_schema.py** - `d5779ec` (feat)

## Files Created/Modified
- `src/schema.py` - Added idempotent `CREATE TABLE IF NOT EXISTS extracted_complications` (20 columns) and 4 indexes inside `init_db()`.
- `src/extractor_common.py` - Expanded JATS XML `results_parts` matching for safety/morbidity headings; added enum allowlists, `table_exists`, `is_excluded_recurrence_event`, `normalize_clavien_dindo`, `extract_complication_frequency`, `extract_clavien_dindo_grade`, `extract_resolution_time_window`, `insert_extracted_complication`, and `fetch_extracted_complications`.
- `src/universal_schema.py` - Added `PROJECT_ROOT` `sys.path` bootstrap, `_connect_sqlite_readonly`, `REQUIRED_COMPLICATION_ENTRY_KEYS`, `REQUIRED_RED_FLAG_KEYS`, `surgical_focus`/`treatment_profile` handling in `discover_nosologies` and `save_new_nosology_config`, `extracted_complications_rows` in `get_sqlite_corpus_stats`, `query_complications_df`, `aggregate_complications_from_sqlite`, `validate_kb_complications_v2`, and `--schema-version` validation mode in `verify_universal_schema` / `main`.

## Decisions Made
- Stripped explicit parenthesized and inline `90/95/99% CI` spans before matching standalone ranges/percentages in `extract_complication_frequency()`, preventing `12.5% (95% CI 8.1-17.2%)` from matching `8.1-17.2%` as a range before `12.5%`.
- Applied `_connect_sqlite_readonly()` uniformly across all reader queries in `src/universal_schema.py` (including `query_articles_df`, `query_clinical_evidence_df`, `query_mechanisms_df`, `query_clinical_trials_df`, `query_complications_df`, `get_sqlite_corpus_stats`, `build_dynamic_fallback_kb`, and `aggregate_complications_from_sqlite`) to ensure frozen Milestone 1.x SQLite files never get touched or gain `-wal`/`-shm` sidecars during inspection.
- Used `re.fullmatch(r"[a-z0-9_]+", nos_id)` plus resolved-parent verification in `save_new_nosology_config()` so non-ASCII letters and path traversal sequences are strictly rejected (`T-17-05`).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Relational schema (`extracted_complications`), validation/parsing utilities (`src/extractor_common.py`), and universal schema v2.0 contract (`src/universal_schema.py`) are ready for Plan `17-02` (`src/harvester.py`, `src/triage.py`) and Plan `17-03` (`tests/test_phase17_complications.py`).
- All frozen `v1.x` corpora (`prom`, `metroplasty_pregnancy`, `trigger_finger`) remain byte-identical on disk and pass `uv run src/universal_schema.py --verify`.

## Self-Check: PASSED

- Verified modified files on disk: `src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py` — FOUND.
- Verified atomic task commits in git history: `fa0e13b` (Task 1), `d5779ec` (Task 2) — FOUND.
- Verified plan-level checks:
  - `uv run src/universal_schema.py --verify --nosology prom` -> `[PASS]` (exit 0)
  - `uv run src/universal_schema.py --verify --nosology metroplasty_pregnancy` -> `[PASS]` (exit 0)
  - `uv run src/universal_schema.py --verify --nosology trigger_finger` -> `[PASS]` (exit 0)
  - `uv run src/universal_schema.py --verify --nosology prom --schema-version v2` -> `[FAIL]` (exit 1, strict v2 enforcement confirmed)
  - Temporary SQLite round-trip (`init_db` -> `insert_extracted_complication` -> `aggregate_complications_from_sqlite` -> `validate_kb_complications_v2`) -> PASSED
  - `git status --short data/ reports/` -> empty (zero modifications to frozen `v1.x` corpora)
  - Stub scan (`TODO|FIXME|placeholder|coming soon`) across modified files -> 0 matches.

---
*Phase: 17-prisma*
*Completed: 2026-11-19*
