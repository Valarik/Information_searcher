---
phase: 18-v2-0
plan: 02
subsystem: verifier-and-tests
tags: [humanizer-v2, anti-ai-linter, verify-reports, read-only, pytest, backward-compatibility]

# Dependency graph
requires:
  - phase: 18-v2-0
    provides: "ru-medical-humanizer v2.0 & nosology-research-pipeline v2.0 skills, validate_kb_clinical_nuances_v2(), and validate_kb_v2() in src/universal_schema.py"
provides:
  - "Structural anti-AI linter v2.0 (check_humanizer_v2_structure) with expanded BANNED_AI_V2_CONCLUSION_PHRASES, bold_lead_bullet_ratio metric, pigeonhole routing detector, non-linear nuance & complications gates, and validate_kb_v2() enforcement in src/verify_reports.py"
  - "Security-hardened get_nosology_paths() (T-18-03) and strictly read-only SQLite + --read-only verification mode (T-18-04) preserving frozen v1.x corpora untouched"
  - "Comprehensive offline + live read-only Phase 18 test suite in tests/test_phase18_humanizer.py covering HUM2-01..HUM2-03"
affects: [19-v2-0, verify-reports, ci-regression, app-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural anti-AI linter v2.0: prose-to-bullet ratio (bold_lead_bullet_ratio <= 0.35), sliding-window mechanical pigeonhole detection across distinct stage/group slots, non-linear clinical nuance signals, and structured Clavien-Dindo/CTCAE complications check"
    - "Read-only verification contract: _connect_sqlite_readonly() + write_outputs=False (--read-only) skips @PMID writes, .docx export, and verification_audit.md so frozen v1.x files remain byte-identical"
    - "Schema-versioned enforcement: auto | v1 | v2 CLI modes keep v1.x advisory warnings non-blocking while enforcing strict Humanizer v2.0 + validate_kb_v2() gates on v2.0 reports"

key-files:
  created:
    - tests/test_phase18_humanizer.py
  modified:
    - src/verify_reports.py

key-decisions:
  - "Added pandas>=2.2.0 and markdown>=3.6 to PEP 723 script metadata in src/verify_reports.py so standalone `uv run src/verify_reports.py --nosology <id> --verify --read-only` succeeds without extra --with flags."
  - "Applied negative lookahead for stage ranges (e.g. 'стадий I–III') and distinct-slot windowing (3+ distinct stage/group slots within 900 chars) in _detect_pigeonhole_routing() so legitimate multi-stage spectrum prose never triggers false positives while inline, bulleted, em-dash, and method-first pigeonhole patterns are reliably caught."
  - "Scoped git immutability checks in tests/test_phase18_humanizer.py explicitly to the 6 frozen v1.x directories (data/prom, data/metroplasty_pregnancy, data/trigger_finger, reports/prom, reports/metroplasty_pregnancy, reports/trigger_finger) alongside per-file (st_mtime_ns, st_size) and WAL/SHM checks."

patterns-established:
  - "verify_all_reports(..., schema_version='auto'|'v1'|'v2', write_outputs=True|False, base_dir=None) returns a structured verification dict with linter metrics and supports isolated tmp_path end-to-end testing."
  - "CLI safety guard refuses --compile-bibliography combined with --read-only."

requirements-completed: [HUM2-03, HUM2-01, HUM2-02]

# Metrics
duration: 12 min
completed: 2026-11-20
---

# Phase 18 Plan 02: Structural Anti-AI Linter v2.0 & Humanizer Verification Suite Summary

**Implemented the structural anti-AI linter `v2.0` (`check_humanizer_v2_structure`) with `T-18-03`/`T-18-04` security hardening in `src/verify_reports.py` and built `tests/test_phase18_humanizer.py`, passing all 16 pytest tests (`11` Phase 17 + `5` Phase 18) and `uv run app.py --self-test` with zero mutations in frozen `v1.x` corpora.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-11-20T08:43:57Z
- **Completed:** 2026-11-20T08:55:32Z
- **Tasks:** 2
- **Files modified:** 2 (`src/verify_reports.py`, `tests/test_phase18_humanizer.py`)

## Accomplishments
- Upgraded `src/verify_reports.py` with `check_humanizer_v2_structure()`, `BANNED_AI_V2_CONCLUSION_PHRASES` (10 formulaic conclusion/AI clichés alongside legacy `BANNED_AI_PHRASES`), `bold_lead_bullet_ratio` computation (`<= 0.35` gate in `dissertation` mode, `max_consecutive_bold_bullets > 6` advisory warning), sliding-window mechanical pigeonhole routing detection across distinct stage/group slots, non-linear clinical nuance signal verification in the final analytical section, and treatment complications analysis verification.
- Hardened `src/verify_reports.py` against `T-18-03` and `T-18-04`: `get_nosology_paths()` validates `nosology_id` via `validate_nosology_id()` and enforces `.resolve().is_relative_to(...)` containment; `compile_dissertation_bibliography()` and `verify_all_reports()` open SQLite strictly via `_connect_sqlite_readonly()`; `--schema-version {auto,v1,v2}` and `--read-only` (`write_outputs=False`) perform zero disk writes while gating `v2.0` reports on both `check_humanizer_v2_structure()` and `validate_kb_v2()`.
- Created `tests/test_phase18_humanizer.py` with 5 comprehensive test suites covering skill `v2.0` contracts (`HUM2-01`, `HUM2-02`), `clinical_decision_nuances` validator rejections (`HUM2-02`), all `check_humanizer_v2_structure()` anti-patterns & valid prose (`HUM2-03`), synthetic end-to-end `v2.0` pipeline verification + path-traversal blocking (`T-18-03`, `T-18-04`), and live read-only backward compatibility + byte-level immutability on `prom`, `metroplasty_pregnancy`, and `trigger_finger`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement structural anti-AI linter v2.0 and security hardening in src/verify_reports.py (HUM2-03)** - `3e110d7` (`feat`)
2. **Task 2: Build and run tests/test_phase18_humanizer.py and full regression suite (HUM2-01..HUM2-03)** - `597eded` (`test`)

## Files Created/Modified
- `src/verify_reports.py` - Added PEP 723 dependencies (`pandas>=2.2.0`, `markdown>=3.6`), hardened `get_nosology_paths()`, added `BANNED_AI_V2_CONCLUSION_PHRASES` and `check_humanizer_v2_structure()`, integrated `validate_kb_v2()`, `_connect_sqlite_readonly()`, `--schema-version`, and `--read-only` mode in `verify_all_reports()` and `main()`.
- `tests/test_phase18_humanizer.py` - Added 5 pytest suites verifying `HUM2-01..HUM2-03`, structural linter positive/negative cases, synthetic `v2.0` end-to-end verification, `T-18-03`/`T-18-04` mitigations, and live read-only `v1.x` compatibility & git immutability.

## Verification Results
- **Live read-only `v1.x` CLI checks (standalone & `--with`):**
  - `prom`: `PASSED` (`Schema=1.x`, `COMPAT_V1`, `bold_lead_bullet_ratio=0.7209`, 97 refs)
  - `metroplasty_pregnancy`: `PASSED` (`Schema=1.x`, `COMPAT_V1`, `bold_lead_bullet_ratio=0.6296`, 78 refs)
  - `trigger_finger`: `PASSED` (`Schema=1.x`, `COMPAT_V1`, `bold_lead_bullet_ratio=0.8511`, 98 refs)
  - Strict `--schema-version v2 --read-only` cleanly rejected legacy `v1.x` reports (`exit 1`) without disk writes.
- **Full pytest regression suite:** `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v` -> **16 passed in 1.79s** (`11` Phase 17 + `5` Phase 18).
- **App self-test:** `uv run app.py --self-test` -> **`[3/3] [PASS]`** (0 exceptions, metrics=6, dataframes=6, tabs=8).
- **Immutability & tracking hygiene:** `git status --porcelain` across `data/prom`, `data/metroplasty_pregnancy`, `data/trigger_finger`, `reports/prom`, `reports/metroplasty_pregnancy`, `reports/trigger_finger`, `.planning/STATE.md`, and `.planning/ROADMAP.md` confirmed zero changes.

## Decisions Made
- Added `"pandas>=2.2.0"` and `"markdown>=3.6"` to `# /// script` in `src/verify_reports.py` so importing `src.universal_schema` works cleanly via standalone `uv run src/verify_reports.py --nosology <id> --verify --read-only`.
- Added stage-range negative lookahead (`(?!\s*[–-]\s*(?:IV|III|II|I|[1-4])\b)`) and named-procedure em-dash detection in `_detect_pigeonhole_routing()` to accurately catch mechanical stage-to-method slots while permitting multi-stage workhorse spectrum prose (`стадий I–III`).
- Blocked combining `--compile-bibliography` with `--read-only` at the CLI parser boundary to uphold the zero-write invariant of `--read-only`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 18 (`18-01` and `18-02`) implementation and automated verification are complete (`HUM2-01..HUM2-03`).
- Ready for orchestrator tracking update and Phase 19 (UI/DOCX integration of complications & `clinical_decision_nuances`).

## Self-Check: PASSED

- Verified `src/verify_reports.py` and `tests/test_phase18_humanizer.py` exist on disk and contain zero stub/placeholder markers (`TODO`/`FIXME`/`placeholder`/`coming soon`/`not available`).
- Verified atomic task commits `3e110d7` and `597eded` exist in git history with zero unintended deletions.
- Verified all acceptance criteria passed (`16 passed` in `pytest tests/ -v`, `uv run app.py --self-test` exit 0, 3/3 frozen `v1.x` CLI verifications exit 0) and frozen `v1.x` folders + `.planning/STATE.md` / `.planning/ROADMAP.md` remain completely untouched.

---
*Phase: 18-v2-0*
*Completed: 2026-11-20*
