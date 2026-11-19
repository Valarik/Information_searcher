---
phase: 17-prisma
plan: 03
subsystem: testing
tags: [pytest, sqlite, prisma, clavien-dindo, ctcae, jats-xml, universal-schema, backward-compat, security]

# Dependency graph
requires:
  - phase: 17-prisma
    provides: Relational `extracted_complications` schema, extraction/validation helpers, v2.0 aggregator/validator (17-01) and hybrid complication harvester + two-contour PRISMA safety triage / XML priority queue (17-02)
provides:
  - Deterministic offline pytest suite (`tests/test_phase17_complications.py`) covering `COMP-01..COMP-04`, `D-01..D-09`, and threat mitigations `T-17-01..T-17-05`
  - Verified live read-only backward-compatibility and byte-level immutability checks on frozen Milestone 1.x corpora (`prom`, `metroplasty_pregnancy`, `trigger_finger`)
  - Verified full Phase 17 regression gate (`pytest tests/ -q`, all 5 `-k` filters, CLI `--verify` on all 3 v1.x nosologies, `uv run app.py --self-test`, and clean `git status --porcelain data/ reports/`)
affects: [18-anti-ai-linter, 19-ui-docx-v2]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Offline skill-loader & urllib monkeypatching inside pytest `tmp_path` fixtures for deterministic `< 2s` harvester/triage integration testing (`T-17-03`)"
    - "Read-only URI (`?mode=ro`) + `(st_mtime_ns, st_size)` + `-wal`/`-shm` + `git status --porcelain data/ reports/` immutability harness for frozen `v1.x` corpora (`T-17-02`)"
    - "Adversarial negative testing for SQL injection (`?` parameters, `T-17-01`), PMCID path traversal (`../evil`, `T-17-04`), nosology ID traversal (`T-17-05`), `95% CI` frequency decoys, and Tier 4 `1/1 (100%)` casuistry isolation (`D-04`)"

key-files:
  created:
    - tests/test_phase17_complications.py
  modified: []

key-decisions:
  - "Included negative security assertions for SQL injection payloads (`T-17-01`), malicious `../evil` PMCIDs (`T-17-04`), `../escape` config IDs (`T-17-05`), and strict `--schema-version v2` rejection on legacy v1.x KBs alongside read-only `auto` compatibility (`T-17-02`)."
  - "Verified `aggregate_complications_from_sqlite()` exclusion of rows linked to `excluded_offtopic` articles in addition to median sorting (`>= 1.0%` descending per modality) and two-contour `< 1.0%` / `Tier 4` `rare_critical_red_flags` routing."

patterns-established:
  - "All Phase 17 validation `-k` selectors (`harvester`, `triage`, `schema_and_extractor`, `universal_schema`, `v1_backward_compat`) map directly to dedicated tests in `tests/test_phase17_complications.py`."
  - "Ephemeral `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -q` executes the full suite offline without modifying PEP 723 script metadata or adding a global `pyproject.toml`."

requirements-completed:
  - COMP-01
  - COMP-02
  - COMP-03
  - COMP-04

# Metrics
duration: 7 min
completed: 2026-11-19
---

# Phase 17 Plan 03: Offline Complications Test Suite & Read-Only v1.x Regression Summary

**10-test offline pytest suite (`tests/test_phase17_complications.py`, 1.13s) validating `COMP-01..COMP-04`, `D-01..D-09`, `T-17-01..T-17-05`, live read-only `v1.x` immutability across `prom`/`metroplasty_pregnancy`/`trigger_finger`, and passing `uv run app.py --self-test`**

## Performance

- **Duration:** 7 min
- **Started:** 2026-11-19T16:47:03Z
- **Completed:** 2026-11-19T16:54:24Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Created `tests/test_phase17_complications.py` (10 tests across all 5 `-k` groups from `17-VALIDATION.md`) running completely offline in ~1.13s with zero external network calls or mutations to repository data.
- Covered Harvester (`COMP-01`, `D-01..D-03`, `T-17-03`): surgical/mixed default vs conservative switch, hybrid `complications_queries` override vs date-bounded auto-generation, dedicated `pubmed_complications.json` / `europepmc_complications.json` caching (zero `europepmc_page_*.json`), deduplicated `articles.sources` merging (`PubMed`, `PubMed:Complications`, `EuropePMC:Complications`), and cache reuse without re-invoking mocked skill loaders.
- Covered PRISMA Triage & XML Queue (`COMP-02`, `D-04..D-06`, `T-17-04`): 3-trigger `complications_safety` tagging + complication-aware PRISMA inclusion, two-contour separation (`Tier 1-3` `N >= 20` cohorts & basic-science exemption vs `Tier 4` / `1 <= N < 20` `rare_catastrophic_case`), prioritized Europe PMC Full-Text XML queue (`PMC100002` ahead of higher-cited general `PMC100001`), `PMCID_RE` rejection of `../evil`, and `prisma_stats.md` `total_raw` + `complications_safety` reporting.
- Covered Schema & Extractor (`COMP-03`, `D-04`, `D-07`, `D-08`, `T-17-01`): idempotent `init_db()` 20-column / 4-index verification, dual-axis Clavien-Dindo (`I..V`, `IVa/IVb -> IV`, `III -> IIIa/IIIb`) + `CTCAE Grade 1-5` normalization, enum & recurrence/incomplete-release rejection, `transient_postop_sequela` `time_window` auto-population, `Tier 4` `1/1 (100%)` numeric nullification, parameterized SQL injection resilience, synthetic JATS XML safety section/table parsing, and `95% CI`-safe frequency/grade/time-window regex extraction.
- Covered Universal Schema `v2.0` & Live Read-Only `v1.x` Regression (`COMP-04`, `D-09`, `T-17-02`, `T-17-05`): multi-cohort median (`15% (10–20%)`) and descending sort within modalities (`>= 1.0%`), `< 1.0%` `IIIb` & `Tier 4` `rare_critical_red_flags` routing, `validate_kb_complications_v2()` negative rejection across all violation classes, `save_new_nosology_config()` / `discover_nosologies()` `surgical_focus` & `complications_queries` handling, strict read-only URI + `(st_mtime_ns, st_size)` + zero `-wal`/`-shm` + empty `git status --porcelain data/ reports/` checks across `prom`, `metroplasty_pregnancy`, and `trigger_finger`, plus green `uv run app.py --self-test`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create offline unit and integration tests for Harvester, PRISMA Triage, and Schema/Extractor in tests/test_phase17_complications.py** - `46d7a78` (test)
2. **Task 2: Add universal_schema v2.0 aggregation tests, live read-only v1.x regression tests, and run full phase gate** - `8e3ab29` (test)

## Files Created/Modified
- `tests/test_phase17_complications.py` - Comprehensive offline pytest suite (10 test functions covering all 5 `17-VALIDATION.md` `-k` groups, `COMP-01..COMP-04`, `D-01..D-09`, and `T-17-01..T-17-05`).

## Decisions Made
None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 17 (`17-01`, `17-02`, `17-03`) is fully implemented and verified end-to-end with 10/10 tests passing offline in ~1.13s, all 3 frozen `v1.x` corpora verified byte-identical and passing `--verify`, and `uv run app.py --self-test` passing with 0 exceptions.
- Ready for Phase 18 (anti-AI structural linter & nonlinear conclusion rules) and Phase 19 (UI/DOCX v2.0 complications rendering).

## Self-Check: PASSED

- Verified created file on disk: `tests/test_phase17_complications.py` — FOUND.
- Verified atomic task commits in git history: `46d7a78` (Task 1), `8e3ab29` (Task 2) — FOUND.
- Verified all 5 `17-VALIDATION.md` `-k` selectors:
  - `-k "harvester"` -> 2 passed
  - `-k "triage"` -> 3 passed
  - `-k "schema_and_extractor"` -> 2 passed
  - `-k "universal_schema"` -> 2 passed
  - `-k "v1_backward_compat"` -> 1 passed
- Verified full suite: `pytest tests/ -q` -> 10 passed in 1.13s (exit 0).
- Verified CLI schema checks: `prom`, `metroplasty_pregnancy`, `trigger_finger` -> all `[PASS]` (exit 0).
- Verified `uv run app.py --self-test` -> `[PASS]` (4 tabs, 3 report modes, 0 exceptions, exit 0).
- Verified `git status --porcelain data/ reports/` -> empty (zero mutations to frozen `v1.x` corpora).
- Verified `.planning/STATE.md` and `.planning/ROADMAP.md` untouched.
- Verified stub scan (`TODO|FIXME|placeholder|coming soon`) on `tests/test_phase17_complications.py` -> 0 matches.

---
*Phase: 17-prisma*
*Completed: 2026-11-19*
